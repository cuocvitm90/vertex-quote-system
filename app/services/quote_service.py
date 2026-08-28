"""
Quote Service Module
Manages the lifecycle, business logic, approval state machine, version control, and customer dispatching of quotations.
Includes Multi-Level Approval Matrix (Manager vs Director threshold) and Comprehensive Audit Trail Logging.
"""
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from app.config import settings
from app.database.db import db
from app.database.models import Quote, QuoteItem, QuoteStatus, ApprovalRequest, User, UserRole, AuditLog
from app.services.zalo_service import zalo_service
from app.tools.excel_generator import VertexExcelGenerator
from app.tools.calculator import QuoteCalculator


class QuoteService:
    """Manages business operations and multi-level approval for Vertex Quotations"""

    @classmethod
    def generate_quote_code(cls) -> str:
        """Generates sequential quote code: VTX-YYYY-XXXX"""
        current_year = datetime.now().year
        count = db.count_quotes() + 1
        return f"{settings.QUOTE_CODE_PREFIX}-{current_year}-{count:04d}"

    @classmethod
    def get_quote(cls, quote_id: str) -> Optional[Quote]:
        return db.get_quote(quote_id)

    @classmethod
    def list_quotes(cls, limit: int = 50, offset: int = 0) -> List[Quote]:
        return db.list_quotes(limit=limit, offset=offset)

    @classmethod
    def evaluate_approval_level(cls, quote: Quote) -> str:
        """
        Determines whether quote requires Manager approval only or Director (Executive) approval.
        Director approval is required if:
        - Total payment >= 100,000,000 VNĐ (100 million)
        - OR Discount rate > 5% (0.05)
        - OR Contains AI Market Estimate items (pricing uncertainty)
        """
        has_ai_items = any(it.price_source == "AI_MARKET_ESTIMATE" for it in quote.items)
        if quote.total_amount >= 100_000_000 or quote.discount_rate > 0.05 or has_ai_items:
            return "DIRECTOR"
        return "MANAGER"

    @classmethod
    async def approve_quote(
        cls,
        quote_id: str,
        manager_name: str = "Anh Việt",
        manager_id: Optional[str] = None,
        manager_role: str = "MANAGER",
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processes approval under Multi-Level Approval Policy:
        - If role is MANAGER and quote requires DIRECTOR approval:
          Sets status to PENDING_DIRECTOR_APPROVAL (Stage 1 approved, forwarded to Sếp Tiến).
        - If role is ADMIN (Sếp Tiến) or quote is standard (<100M and <=5% discount):
          Sets status to APPROVED, dispatches to customer via Zalo OA, and sets status to SENT_TO_CUSTOMER.
        """
        quote = db.get_quote(quote_id)
        if not quote:
            raise ValueError(f"Không tìm thấy báo giá với ID: {quote_id}")

        if quote.status in [QuoteStatus.APPROVED, QuoteStatus.SENT_TO_CUSTOMER]:
            return {
                "status": "already_approved",
                "message": f"Báo giá {quote.quote_code} đã được phê duyệt trước đó bởi {quote.approved_by}.",
                "quote": quote
            }

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Evaluate required approval level if missing
        if not quote.required_approval_level:
            quote.required_approval_level = cls.evaluate_approval_level(quote)

        # Stage 1: Manager reviews a high-value / high-discount quote
        if manager_role == "MANAGER" and quote.required_approval_level == "DIRECTOR" and quote.status == QuoteStatus.PENDING_APPROVAL:
            quote.status = QuoteStatus.PENDING_DIRECTOR_APPROVAL
            quote.manager_approved_by = manager_name
            quote.manager_approved_at = now_str
            quote.approved_by = f"{manager_name} (Đã thông qua, chờ Giám đốc duyệt)"
            quote.updated_at = now_str
            
            log_msg = f"[{now_str}] Trưởng phòng KD '{manager_name}' đã xem xét & THÔNG QUA báo giá. Chuyển tiếp tới Giám đốc (Sếp Tiến) phê duyệt hạn mức cao."
            quote.logs.append(log_msg)

            # Record in Audit Log
            db.add_audit_log(
                quote_id=quote.id,
                user_id=manager_id or "",
                user_name=manager_name,
                user_role=manager_role,
                action="MANAGER_REVIEW_PASSED",
                details=f"Trưởng phòng KD đã thông qua dự thảo (Tổng tiền: {quote.total_amount:,.0f} đ, Chiết khấu: {quote.discount_rate*100:.0f}%). Chuyển tiếp Giám đốc duyệt.",
                ip_address=ip_address
            )

            db.save_quote(quote)

            return {
                "status": "pending_director",
                "message": f"Báo giá {quote.quote_code} có tổng tiền {quote.total_amount:,.0f} đ (>100tr hoặc chiết khấu >5%). Trưởng phòng {manager_name} đã thông qua và chuyển tiếp Giám đốc (Sếp Tiến) duyệt!",
                "quote": quote
            }

        # Final Stage: Director approves or standard quote approved by Manager
        is_director = (manager_role == "ADMIN")
        if is_director:
            quote.director_approved_by = manager_name
            quote.director_approved_at = now_str
            quote.approved_by = f"{manager_name} (Giám đốc)"
            action_code = "DIRECTOR_APPROVE"
            log_msg = f"[{now_str}] Giám đốc '{manager_name}' đã PHÊ DUYỆT CHÍNH THỨC báo giá."
        else:
            quote.manager_approved_by = manager_name
            quote.manager_approved_at = now_str
            quote.approved_by = f"{manager_name} (Trưởng phòng KD)"
            action_code = "MANAGER_APPROVE"
            log_msg = f"[{now_str}] Trưởng phòng KD '{manager_name}' đã PHÊ DUYỆT báo giá chuẩn."

        quote.status = QuoteStatus.APPROVED
        quote.approved_at = now_str
        quote.updated_at = now_str
        quote.logs.append(log_msg)

        # Record Audit Log
        db.add_audit_log(
            quote_id=quote.id,
            user_id=manager_id or "",
            user_name=manager_name,
            user_role=manager_role,
            action=action_code,
            details=f"Phê duyệt hoàn tất báo giá {quote.quote_code} (Tổng: {quote.total_amount:,.0f} VNĐ).",
            ip_address=ip_address
        )

        # Trigger Dispatch to Customer via Zalo OA
        customer_dispatch_res = await zalo_service.send_quote_to_customer(quote)
        quote.status = QuoteStatus.SENT_TO_CUSTOMER
        dispatch_log = f"[{now_str}] Đã gửi báo giá chính thức kèm link tải Excel tới khách hàng qua Zalo OA."
        quote.logs.append(dispatch_log)

        db.add_audit_log(
            quote_id=quote.id,
            user_id=manager_id or "",
            user_name="Zalo OA Dispatcher",
            user_role="SYSTEM",
            action="SEND_TO_CUSTOMER",
            details=f"Đã gửi thông báo báo giá chính thức tới khách hàng '{quote.customer_name}' qua Zalo OA.",
            ip_address=ip_address
        )

        db.save_quote(quote)

        return {
            "status": "success",
            "message": f"Đã duyệt thành công báo giá {quote.quote_code} và gửi cho khách hàng!",
            "quote": quote,
            "zalo_result": customer_dispatch_res
        }

    @classmethod
    async def reject_quote(
        cls,
        quote_id: str,
        manager_name: str = "Anh Việt",
        manager_id: Optional[str] = None,
        manager_role: str = "MANAGER",
        reason: str = "Yêu cầu kiểm tra lại đơn giá hoặc quy cách",
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Manager / Director rejects quote with reason.
        """
        quote = db.get_quote(quote_id)
        if not quote:
            raise ValueError(f"Không tìm thấy báo giá với ID: {quote_id}")

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        quote.status = QuoteStatus.REJECTED
        quote.approved_by = manager_name
        quote.rejection_reason = reason
        quote.updated_at = now_str
        
        log_msg = f"[{now_str}] Quản lý '{manager_name}' ({manager_role}) đã TỪ CHỐI báo giá. Lý do: {reason}"
        quote.logs.append(log_msg)

        db.add_audit_log(
            quote_id=quote.id,
            user_id=manager_id or "",
            user_name=manager_name,
            user_role=manager_role,
            action="REJECT_QUOTE",
            details=f"Từ chối báo giá {quote.quote_code}. Lý do: {reason}",
            ip_address=ip_address
        )

        db.save_quote(quote)

        return {
            "status": "rejected",
            "message": f"Đã từ chối báo giá {quote.quote_code}. Lý do: {reason}",
            "quote": quote
        }

    @classmethod
    def create_revision(
        cls,
        quote_id: str,
        user: User,
        revision_note: str = "Điều chỉnh khối lượng / đơn giá",
        discount_rate: Optional[float] = None,
        vat_rate: Optional[float] = None,
        updated_items: Optional[List[QuoteItem]] = None,
        ip_address: Optional[str] = None
    ) -> Quote:
        """
        Creates a new version (v2, v3...) branching from an existing quote:
        - Retains parent linkage
        - Recalculates finances strictly via Python math
        - Generates corresponding Excel file
        - Logs version creation in Audit Trail
        """
        parent = db.get_quote(quote_id)
        if not parent:
            raise ValueError(f"Không tìm thấy báo giá gốc với ID: {quote_id}")

        # Find version lineage
        existing_versions = db.get_quote_versions(quote_id)
        max_version = max([q.version for q in existing_versions], default=parent.version)
        new_version = max_version + 1

        # Root code determination: remove existing version suffix
        root_code = parent.quote_code.split(" (v")[0].split("-v")[0]
        new_quote_code = f"{root_code} (v{new_version})"
        new_quote_id = f"{parent.id}_v{new_version}_{uuid.uuid4().hex[:4]}"
        root_parent_id = parent.parent_quote_id if parent.parent_quote_id else parent.id

        # Use updated items or copy parent items
        items_to_use = updated_items if updated_items is not None else [item.model_copy() for item in parent.items]
        
        # Calculate totals
        disc = discount_rate if discount_rate is not None else parent.discount_rate
        vat = vat_rate if vat_rate is not None else parent.vat_rate
        totals = QuoteCalculator.calculate_quote_totals(items_to_use, discount_rate=disc, vat_rate=vat)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        new_quote = Quote(
            id=new_quote_id,
            quote_code=new_quote_code,
            customer_name=parent.customer_name,
            customer_phone=parent.customer_phone,
            customer_email=parent.customer_email,
            customer_zalo_id=parent.customer_zalo_id,
            project_name=parent.project_name,
            project_address=parent.project_address,
            status=QuoteStatus.PENDING_APPROVAL,
            language=parent.language,
            version=new_version,
            parent_quote_id=root_parent_id,
            revision_note=revision_note.strip() or f"Phiên bản v{new_version} điều chỉnh",
            template_id=parent.template_id,
            template_name=parent.template_name,
            subtotal=totals["subtotal"],
            discount_rate=totals["discount_rate"],
            discount_amount=totals["discount_amount"],
            subtotal_after_discount=totals["subtotal_after_discount"],
            vat_rate=totals["vat_rate"],
            vat_amount=totals["vat_amount"],
            total_amount=totals["total_amount"],
            total_amount_in_words=totals["total_amount_in_words"],
            input_file_name=parent.input_file_name,
            input_file_path=parent.input_file_path,
            excel_quote_path="",
            created_at=now_str,
            updated_at=now_str,
            items=items_to_use,
            logs=[
                f"[{now_str}] Tạo phiên bản mới {new_quote_code} từ {parent.quote_code} bởi {user.full_name}.",
                f"[{now_str}] Ghi chú điều chỉnh: {revision_note}"
            ]
        )

        # Set required approval level
        new_quote.required_approval_level = cls.evaluate_approval_level(new_quote)

        # Generate new Excel file
        excel_path = VertexExcelGenerator.generate(new_quote)
        new_quote.excel_quote_path = excel_path

        # Save new Quote
        db.save_quote(new_quote)

        # Record in Audit Trail
        db.add_audit_log(
            quote_id=new_quote.id,
            user_id=user.id,
            user_name=user.full_name,
            user_role=user.role.value,
            action="CREATE_REVISION",
            details=f"Tạo phiên bản {new_quote_code} (v{new_version}) từ {parent.quote_code}. Ghi chú: {revision_note}. Tổng tiền: {new_quote.total_amount:,.0f} VNĐ.",
            ip_address=ip_address
        )

        return new_quote

    @classmethod
    def regenerate_excel(cls, quote_id: str) -> str:
        """Regenerates the Excel file for an existing quote"""
        quote = db.get_quote(quote_id)
        if not quote:
            raise ValueError(f"Không tìm thấy báo giá với ID: {quote_id}")

        excel_path = VertexExcelGenerator.generate(quote)
        quote.excel_quote_path = excel_path
        db.save_quote(quote)
        return excel_path
