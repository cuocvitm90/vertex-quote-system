"""
AI Agent Orchestrator for Vertex Quote Automation
Coordinates Groq LLM (Qualitative Semantic Extraction & Market Price Lookup)
and Python Tools (Deterministic Calculation, Master Template Coefficients, Excel, Zalo).
"""
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

from app.config import settings
from app.database.db import db
from app.database.models import Quote, QuoteItem, QuoteStatus, MasterTemplate
from app.agent.llm_client import GroqBOQAgent
from app.tools.extractor import BOQExtractor, ExtractedRawItem
from app.tools.price_lookup import PriceLookupTool
from app.tools.market_estimator import AIMarketEstimator
from app.tools.calculator import QuoteCalculator
from app.tools.excel_generator import VertexExcelGenerator
from app.services.zalo_service import zalo_service

logger = logging.getLogger("vertex.agent")
logging.basicConfig(level=logging.INFO)


class VertexQuoteAgent:
    """
    4-Stage Intelligent BOQ Processing Pipeline:
    1. Step 1: So khớp đầu vào với Catalog / Master Template để phát hiện các mục chưa có đơn giá.
    2. Step 2: Kích hoạt AI Price Lookup (Groq LLM) tra cứu giá thị trường thực tế cho các mục còn thiếu.
    3. Step 3: Tự động áp dụng khung tỷ lệ % (% hao hụt, % vận chuyển, % nhân công, % lợi nhuận) từ Master Template bằng Python thuần.
    4. Step 4: Tổng hợp bản báo giá dự thảo (Pending Review) gửi Quản lý / Admin duyệt trước khi xuất Excel.
    """

    @classmethod
    async def process_quote_request(
        cls,
        file_path: str,
        customer_name: str = "Quý Khách Hàng",
        customer_phone: str = "",
        customer_zalo_id: str = "",
        customer_email: str = "",
        project_name: str = "Công trình Tiêu chuẩn Vertex",
        project_address: str = "Hà Nội",
        discount_rate: Optional[float] = None,
        vat_rate: Optional[float] = None,
        language: str = "vi",
        template_id: Optional[str] = None
    ) -> Quote:
        quote_id = str(uuid.uuid4())
        quote_code = cls._generate_quote_code()
        input_filename = Path(file_path).name
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get active Master Template
        if template_id:
            active_template = db.get_template_by_id(template_id) or db.get_active_template()
        else:
            active_template = db.get_active_template()

        logs: List[str] = [
            f"[{now_str}] 🚀 Khởi động AI Agent xử lý báo giá cho {customer_name} - Dự án: {project_name} (Ngôn ngữ: {language.upper()}).",
            f"[{now_str}] 📋 Áp dụng File Mẫu Chuẩn: '{active_template.name}' (Hao hụt: {int(active_template.waste_ratio*100)}%, Vận chuyển: {int(active_template.transport_ratio*100)}%, Nhân công: {int(active_template.labor_ratio*100)}%, Lợi nhuận: {int(active_template.margin_ratio*100)}%).",
            f"[{now_str}] 📥 Đã tiếp nhận file đầu vào: '{input_filename}'."
        ]
        logger.info(f"Starting Quote Agent for {quote_code} with file {input_filename} (lang={language})")

        # -------------------------------------------------------------
        # STEP 1: Tool 1 - Extract Raw BOQ & So Khớp Catalog / Mẫu Chuẩn
        # -------------------------------------------------------------
        from app.tools.scenario_router import InputScenarioRouter

        logs.append(f"[{now_str}] 🔍 [Bước 1: So khớp File Mẫu] Đang đọc cấu trúc bảng tính và phân tích danh mục vật tư...")
        raw_items: List[ExtractedRawItem] = []
        try:
            raw_items = BOQExtractor.extract(file_path)
            logs.append(f"[{now_str}] ✅ Bóc tách thành công {len(raw_items)} dòng vật tư từ file.")
        except Exception as e:
            err_msg = f"Lỗi bóc tách file: {str(e)}"
            logger.error(err_msg)
            logs.append(f"[{now_str}] ⚠️ [Tool Extractor] {err_msg}")
            raw_items = [
                ExtractedRawItem(stt=1, raw_name="Bình chữa cháy bột ABC 4kg (MFZL4)", raw_spec="Có tem PCCC", unit="bình", quantity=20.0),
                ExtractedRawItem(stt=2, raw_name="Ống gió vuông tôn mạ kẽm d=0.75mm", raw_spec="500x300", unit="m2", quantity=25.0),
                ExtractedRawItem(stt=3, raw_name="Đầu phun foam chữa cháy D50 chuyên dụng", raw_spec="Hãng Viking", unit="cái", quantity=4.0)
            ]

        # Classify Input Scenario (Luồng 1, 2, hoặc 3)
        raw_texts = [f"{it.raw_name} {it.raw_spec}" for it in raw_items]
        scenario_type, scenario_desc = InputScenarioRouter.detect_scenario(file_path, raw_texts)
        logs.append(f"[{now_str}] 📌 [Phân Loại Luồng Đầu Vào] {scenario_desc}.")

        # -------------------------------------------------------------
        # STEP 2 & 3: Match Catalog or Trigger AI Market Price Lookup + Apply Labor & Markup Formula
        # -------------------------------------------------------------
        logs.append(f"[{now_str}] 🔎 [Bước 2 & 3: Định Giá & Nhân Công] Tra cứu đơn giá vật tư, áp Ma trận nhân công và Hệ số thương mại...")
        quote_items: List[QuoteItem] = []

        catalog_matched_count = 0
        ai_estimated_count = 0

        for item in raw_items:
            # Resolve Brand and Technical Parameters
            brand, brand_source = InputScenarioRouter.resolve_item_brand(
                item_name=item.raw_name,
                spec=item.raw_spec,
                category="",
                scenario_type=scenario_type
            )
            tech_params = InputScenarioRouter.extract_technical_parameters(item.raw_name, item.raw_spec)
            spec_with_params = item.raw_spec
            if tech_params:
                param_str = ", ".join(f"{k.upper()}: {v}" for k, v in tech_params.items())
                if param_str not in spec_with_params:
                    spec_with_params = f"{spec_with_params} ({param_str})".strip(" ()")

            # 1. Try standard catalog lookup
            price_match = PriceLookupTool.lookup_price(
                raw_name=item.raw_name,
                raw_spec=spec_with_params,
                raw_unit=item.unit,
                raw_thickness=item.raw_thickness
            )

            unit_price = float(price_match.get("unit_price", 0.0))
            confidence = float(price_match.get("confidence_score", 0.0))

            if unit_price > 0 and confidence >= 0.60:
                # Direct catalog match
                catalog_matched_count += 1
                quote_item = QuoteCalculator.process_item_pricing(
                    stt=item.stt,
                    raw_name=item.raw_name,
                    raw_spec=spec_with_params,
                    unit=item.unit,
                    quantity=item.quantity,
                    price_info=price_match,
                    price_source="CATALOG",
                    raw_market_price=unit_price,
                    brand=brand,
                    brand_source=brand_source,
                    template=active_template
                )
                quote_items.append(quote_item)
            else:
                # Missing price -> Trigger Step 2 (AI Market Lookup) & Step 3 (Apply Output Pricing Formula)
                ai_estimated_count += 1
                market_est = await AIMarketEstimator.estimate_market_price(
                    item_name=item.raw_name,
                    spec=spec_with_params,
                    unit=item.unit,
                    thickness=item.raw_thickness
                )

                raw_market_price = float(market_est["raw_market_price"])

                enriched_price_info = {
                    "item_code": f"VTX-AI-{item.stt:03d}",
                    "standard_name": item.raw_name,
                    "category": market_est.get("estimated_category", "Vật tư Cơ điện & PCCC"),
                    "unit": item.unit,
                    "material_unit_cost": raw_market_price,
                    "unit_price": raw_market_price,
                    "confidence_score": market_est.get("confidence", 0.85),
                    "notes": f"{market_est.get('market_notes', '')} | Giá vật tư gốc: {raw_market_price:,.0f} đ",
                    "parsed_spec": price_match.get("parsed_spec")
                }

                quote_item = QuoteCalculator.process_item_pricing(
                    stt=item.stt,
                    raw_name=item.raw_name,
                    raw_spec=spec_with_params,
                    unit=item.unit,
                    quantity=item.quantity,
                    price_info=enriched_price_info,
                    price_source="AI_MARKET_ESTIMATE",
                    raw_market_price=raw_market_price,
                    brand=brand,
                    brand_source=brand_source,
                    template=active_template
                )
                quote_items.append(quote_item)

        logs.append(
            f"[{now_str}] 📊 [Định Giá Hoàn Tất] "
            f"{catalog_matched_count} mục khớp bảng giá chuẩn Vertex, "
            f"{ai_estimated_count} mục AI tra cứu thị trường. "
            f"Tự động tính chi phí nhân công theo Ma trận cố định và nhân Hệ số thương mại Master Template."
        )

        # -------------------------------------------------------------
        # STEP 4: Financial Summary & Draft Quotation (Pending Review)
        # -------------------------------------------------------------
        totals = QuoteCalculator.calculate_quote_totals(
            items=quote_items,
            discount_rate=discount_rate,
            vat_rate=vat_rate
        )
        logs.append(
            f"[{now_str}] 🎯 [Bước 4: Tổng hợp Báo Giá Dự Thảo] "
            f"Chi phí Vật tư: {totals['total_material_cost']:,.0f} đ | "
            f"Chi phí Nhân công: {totals['total_labor_cost']:,.0f} đ | "
            f"Tổng tiền hàng: {totals['subtotal']:,.0f} đ | "
            f"Chiết khấu ({int(totals['discount_rate']*100)}%): {totals['discount_amount']:,.0f} đ | "
            f"VAT ({int(totals['vat_rate']*100)}%): {totals['vat_amount']:,.0f} đ | "
            f"TỔNG THANH TOÁN: {totals['total_amount']:,.0f} đ."
        )

        # Create Quote Object
        from app.services.quote_service import QuoteService

        req_level = "DIRECTOR" if (totals["total_amount"] >= 100_000_000 or totals["discount_rate"] > 0.05 or any(it.price_source == "AI_MARKET_ESTIMATE" for it in quote_items)) else "MANAGER"

        quote = Quote(
            id=quote_id,
            quote_code=quote_code,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            customer_zalo_id=customer_zalo_id,
            project_name=project_name,
            project_address=project_address,
            status=QuoteStatus.PENDING_APPROVAL,
            language=language,
            scenario_type=scenario_type,
            total_material_cost=totals["total_material_cost"],
            total_labor_cost=totals["total_labor_cost"],
            version=1,
            parent_quote_id="",
            revision_note="Bản báo giá gốc ban đầu",
            required_approval_level=req_level,
            template_id=active_template.id,
            template_name=active_template.name,
            subtotal=totals["subtotal"],
            discount_rate=totals["discount_rate"],
            discount_amount=totals["discount_amount"],
            subtotal_after_discount=totals["subtotal_after_discount"],
            vat_rate=totals["vat_rate"],
            vat_amount=totals["vat_amount"],
            total_amount=totals["total_amount"],
            total_amount_in_words=totals["total_amount_in_words"],
            input_file_name=input_filename,
            input_file_path=file_path,
            items=quote_items,
            logs=logs
        )

        # Generate standard Excel
        try:
            excel_path = VertexExcelGenerator.generate(quote)
            quote.excel_quote_path = excel_path
            logs.append(f"[{now_str}] 📄 [Tool Excel Generator] Đã xuất file Excel dự thảo: '{Path(excel_path).name}'.")
        except Exception as e:
            logger.error(f"Error generating Excel: {e}")
            logs.append(f"[{now_str}] ❌ [Tool Excel Generator] Lỗi xuất Excel: {str(e)}")

        # Save initial quote
        db.save_quote(quote)

        # Record Audit Trail for initial creation
        db.add_audit_log(
            quote_id=quote.id,
            user_name="Kỹ Sư Dự Toán",
            user_role="STAFF",
            action="CREATE_QUOTE",
            details=f"Khởi tạo báo giá {quote.quote_code} (v1) qua AI Pipeline 4 bước. Tổng tiền: {quote.total_amount:,.0f} VNĐ. Thẩm quyền duyệt yêu cầu: {quote.required_approval_level}."
        )

        # Send approval request to Manager / Admin via Zalo OA
        logs.append(f"[{now_str}] 📲 [Zalo Service] Đã gửi thẻ duyệt báo giá dự thảo ({quote.required_approval_level}) tới Quản lý để kiểm tra trước khi phát hành...")
        try:
            await zalo_service.send_approval_request(quote)
            logs.append(f"[{now_str}] 🔔 [Zalo Service] Thẻ duyệt tương tác đã sẵn sàng.")
        except Exception as e:
            logger.error(f"Error sending Zalo notification: {e}")

        quote.logs = logs
        db.save_quote(quote)
        return quote

    @classmethod
    def _generate_quote_code(cls) -> str:
        current_year = datetime.now().year
        count = db.count_quotes() + 1
        return f"{settings.QUOTE_CODE_PREFIX}-{current_year}-{count:04d}"
