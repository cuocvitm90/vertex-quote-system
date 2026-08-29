"""
Enhanced Quoting & Multi-Tier Pricing Router
Vertex Construction & PCCC Quoting System
Provides a standalone interactive quoting workspace integrating real-time inventory lookups,
manufacturing dimension calculations, customer tier pricing, gross margin tracking,
and 1-click Excel export / Zalo approval submission.
"""
import uuid
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database.db import db
from app.database.models import (
    User, UserRole, Quote, QuoteItem, QuoteStatus, CustomerTier,
    QuickQuoteLineItem, QuickQuoteCreateRequest, AuditLog
)
from app.services.auth import get_current_user_optional, get_current_user
from app.services.sanitizer import clean_string
from app.tools.bom_engine import (
    calculate_manufacturing_dimensions,
    resolve_tier_price,
    calculate_gross_margin
)
from app.tools.calculator import number_to_vietnamese_words
from app.tools.excel_generator import create_standard_excel_quote

router = APIRouter(tags=["Enhanced Quote Builder"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/quote-builder", response_class=HTMLResponse)
async def quote_builder_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Dedicated Interactive Quoting Workspace.
    Enforces authentication: Redirects unauthenticated users to /login.
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    mfg_items = db.get_inventory_items(warehouse_type="MANUFACTURING")
    com_items = db.get_inventory_items(warehouse_type="COMMERCIAL")
    active_template = db.get_active_template()

    return templates.TemplateResponse(
        request=request,
        name="quote_builder.html",
        context={
            "request": request,
            "settings": settings,
            "user": current_user,
            "mfg_items": mfg_items,
            "com_items": com_items,
            "active_template": active_template,
            "current_date": datetime.now().strftime("%d/%m/%Y")
        }
    )


@router.post("/api/quote-builder/calculate-line-item")
async def api_calculate_line_item(
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """
    Calculates line item dimensions, tier pricing, total amounts, and gross margins
    """
    inventory_id = payload.get("inventory_id")
    customer_tier_str = payload.get("customer_tier", "RETAIL").upper()
    try:
        customer_tier = CustomerTier(customer_tier_str)
    except ValueError:
        customer_tier = CustomerTier.RETAIL

    quantity = max(0.01, float(payload.get("quantity", 1.0)))

    # Fetch product from inventory if provided
    item = None
    if inventory_id:
        item = db.get_inventory_item_by_id(inventory_id)

    if not item:
        # Custom manual item
        cost_price = float(payload.get("cost_price", 0.0))
        retail_price = float(payload.get("retail_price", cost_price * 1.3))
        dealer_price = float(payload.get("dealer_price", cost_price * 1.15))
        proj_disc = float(payload.get("project_discount_rate", 0.0))
        category = payload.get("category", "Vật tư PCCC")
        is_custom_dim = bool(payload.get("is_custom_dimensions", False))
        mat_type = payload.get("material_type", "THÉP_MẠ_KẼM")
    else:
        cost_price = item.cost_price
        retail_price = item.retail_price
        dealer_price = item.dealer_price
        proj_disc = item.project_discount_rate
        category = item.category
        is_custom_dim = item.is_custom_dimensions
        mat_type = item.material_type

    # Handle dimensions
    length_mm = float(payload.get("length_mm", 0.0)) or (item.default_length if item else None)
    width_mm = float(payload.get("width_mm", 0.0)) or (item.default_width if item else None)
    thickness_mm = float(payload.get("thickness_mm", 0.0)) or (item.default_thickness if item else None)
    height_mm = float(payload.get("height_mm", 0.0))

    area_m2 = 0.0
    weight_kg = 0.0

    if is_custom_dim and length_mm and width_mm:
        dim_res = calculate_manufacturing_dimensions(
            category=category,
            material_type=mat_type,
            length_mm=length_mm,
            width_mm=width_mm,
            height_mm=height_mm,
            thickness_mm=thickness_mm,
            base_cost_price=cost_price,
            base_retail_price=retail_price,
            base_dealer_price=dealer_price,
            project_discount_rate=proj_disc,
            quantity=quantity
        )
        area_m2 = dim_res["area_per_unit_m2"]
        weight_kg = dim_res["weight_per_unit_kg"]
        cost_price = dim_res["unit_cost_price"]
        retail_price = dim_res["unit_retail_price"]
        dealer_price = dim_res["unit_dealer_price"]

    # Resolve unit price based on customer tier
    unit_price, base_cost, discount_pct = resolve_tier_price(
        cost_price=cost_price,
        retail_price=retail_price,
        dealer_price=dealer_price,
        project_discount_rate=proj_disc,
        customer_tier=customer_tier
    )

    total_price = round(unit_price * quantity, 0)
    total_cost = round(cost_price * quantity, 0)
    margin_info = calculate_gross_margin(selling_price=total_price, cost_price=total_cost)

    return {
        "status": "success",
        "data": {
            "unit_price": unit_price,
            "cost_price": cost_price,
            "total_price": total_price,
            "total_cost": total_cost,
            "discount_pct": discount_pct,
            "area_m2": area_m2,
            "weight_kg": weight_kg,
            "margin_amount": margin_info["margin_amount"],
            "margin_percent": margin_info["margin_percent"],
            "margin_status": margin_info["status"],
            "margin_label": margin_info["label"],
            "margin_color": margin_info["color"]
        }
    }


@router.post("/api/quote-builder/save-quote")
async def api_save_quote_builder(
    payload: QuickQuoteCreateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Saves an interactive quote to the database, computes subtotal, VAT, margins,
    generates standard Excel file, and creates an audit log.
    """
    if not payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Báo giá phải có ít nhất 1 dòng sản phẩm!"
        )

    clean_cust_name = clean_string(payload.customer_name, escape_html_entities=False) or "Quý Khách Hàng"
    clean_cust_phone = clean_string(payload.customer_phone, escape_html_entities=False) or ""
    clean_cust_email = clean_string(payload.customer_email, escape_html_entities=False) or ""
    clean_proj_name = clean_string(payload.project_name, escape_html_entities=False) or "Dự án PCCC & Cơ Điện Vertex"
    clean_proj_addr = clean_string(payload.project_address, escape_html_entities=False) or ""

    quote_id = f"vtx-quote-{str(uuid.uuid4())[:8]}"
    count = db.count_quotes() + 1
    today_str = datetime.now().strftime("%Y%m%d")
    quote_code = f"VTX-{today_str}-{count:04d}"

    quote_items: List[QuoteItem] = []
    subtotal = 0.0
    total_cost = 0.0
    total_material_cost = 0.0
    total_labor_cost = 0.0

    for idx, item in enumerate(payload.items, start=1):
        clean_name = clean_string(item.item_name, escape_html_entities=False)
        clean_cat = clean_string(item.category, escape_html_entities=False)
        clean_unit = clean_string(item.unit, escape_html_entities=False)

        qty = max(0.01, float(item.quantity))
        u_price = max(0.0, float(item.unit_price))
        c_price = max(0.0, float(item.cost_price))
        tot_price = round(u_price * qty, 0)
        tot_c = round(c_price * qty, 0)

        subtotal += tot_price
        total_cost += tot_c

        # Allocate material and labor rough estimate
        total_material_cost += tot_c * 0.8
        total_labor_cost += tot_c * 0.2

        q_item = QuoteItem(
            stt=idx,
            category=clean_cat,
            item_code=item.sku or f"SKU-{idx:03d}",
            item_name=clean_name,
            brand="Vertex PCCC & Manufacturing",
            spec=f"Kích thước: {item.length_mm}x{item.width_mm}mm" if item.length_mm else "Tiêu chuẩn kỹ thuật Vertex",
            unit=clean_unit or "cái",
            quantity=qty,
            area_m2=item.calculated_area_m2 or 0.0,
            material_unit_cost=c_price * 0.8,
            labor_unit_cost=c_price * 0.2,
            base_unit_cost=c_price,
            unit_price=u_price,
            total_price=tot_price,
            price_source="INVENTORY_BOM_ENGINE",
            confidence_score=1.0,
            notes=clean_string(item.notes or "", escape_html_entities=False)
        )
        quote_items.append(q_item)

    # Calculate discount & VAT
    special_disc_rate = max(0.0, min(0.5, float(payload.special_discount_percent or 0.0) / 100.0))
    discount_amount = round(subtotal * special_disc_rate, 0)
    subtotal_after_discount = subtotal - discount_amount

    vat_rate = float(payload.vat_rate or 0.08)
    vat_amount = round(subtotal_after_discount * vat_rate, 0)
    total_amount = subtotal_after_discount + vat_amount
    total_in_words = number_to_vietnamese_words(int(total_amount))

    # Overall Gross Margin Calculation
    overall_margin = calculate_gross_margin(selling_price=subtotal_after_discount, cost_price=total_cost)

    # Determine approval level
    req_level = "DIRECTOR" if total_amount >= 500_000_000 or overall_margin["margin_percent"] < 10.0 else "MANAGER"

    quote = Quote(
        id=quote_id,
        quote_code=quote_code,
        customer_name=clean_cust_name,
        customer_phone=clean_cust_phone,
        customer_email=clean_cust_email,
        project_name=clean_proj_name,
        project_address=clean_proj_addr,
        status=QuoteStatus.PENDING_APPROVAL,
        language="vi",
        scenario_type="SCENARIO_3_STANDARD_CATALOG",
        total_material_cost=round(total_material_cost, 0),
        total_labor_cost=round(total_labor_cost, 0),
        version=1,
        required_approval_level=req_level,
        subtotal=round(subtotal, 0),
        discount_rate=special_disc_rate,
        discount_amount=discount_amount,
        subtotal_after_discount=round(subtotal_after_discount, 0),
        vat_rate=vat_rate,
        vat_amount=round(vat_amount, 0),
        total_amount=round(total_amount, 0),
        total_amount_in_words=total_in_words,
        items=quote_items,
        created_by_user_id=current_user.id,
        created_by_user_name=current_user.full_name,
        created_by_user_role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    )

    # Save to Database
    saved_quote = db.save_quote(quote)

    # Generate standard Excel file
    try:
        excel_path = create_standard_excel_quote(quote, output_dir=os.path.join(settings.STORAGE_DIR, "quotes"))
        db.update_quote(quote_id, {"excel_quote_path": excel_path})
        saved_quote.excel_quote_path = excel_path
    except Exception as e:
        print(f"[EXCEL GENERATION ERROR] {e}")

    # Register Audit Log
    db.add_audit_log(
        quote_id=quote_id,
        user_id=current_user.id,
        user_name=current_user.full_name,
        user_role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        action="CREATE_QUOTE",
        details=f"Tạo báo giá thông minh '{quote_code}' cho khách hàng {clean_cust_name} ({payload.customer_tier.value}), Tổng giá trị: {total_amount:,.0f} đ, Lợi nhuận gộp: {overall_margin['margin_percent']:.1f}%"
    )

    return {
        "status": "success",
        "message": f"Báo giá '{quote_code}' đã được tạo và lưu vào hệ thống thành công!",
        "quote_id": quote_id,
        "quote_code": quote_code,
        "total_amount": total_amount,
        "total_amount_in_words": total_in_words,
        "margin_percent": overall_margin["margin_percent"],
        "margin_status": overall_margin["status"],
        "required_approval_level": req_level,
        "download_url": f"/api/quotes/{quote_id}/download"
    }
