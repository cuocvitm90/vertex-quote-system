"""
Inventory & Manufacturing BOM Router
Vertex Construction & PCCC Quoting System
Handles Warehouse Isolation (Manufacturing vs. Commercial/Project), BOM Configurations,
and Multi-Tier Pricing (Cost, Retail, Dealer, Project Discount).
"""
import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database.db import db
from app.database.models import (
    User, UserRole, WarehouseType, InventoryItem,
    InventoryItemCreateRequest
)
from app.services.auth import get_current_user_optional, get_current_user, require_manager_or_admin
from app.services.sanitizer import clean_string
from app.tools.bom_engine import (
    calculate_bom_cost,
    calculate_manufacturing_dimensions,
    resolve_tier_price,
    calculate_gross_margin
)

router = APIRouter(tags=["Inventory & Manufacturing BOM"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/inventory", response_class=HTMLResponse)
async def inventory_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Dedicated Inventory & BOM Management Page.
    Enforces authentication: Redirects unauthenticated users to /login.
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    mfg_items = db.get_inventory_items(warehouse_type="MANUFACTURING")
    com_items = db.get_inventory_items(warehouse_type="COMMERCIAL")

    # Get distinct categories for filtering
    mfg_categories = sorted(list(set(item.category for item in mfg_items)))
    com_categories = sorted(list(set(item.category for item in com_items)))

    return templates.TemplateResponse(
        request=request,
        name="inventory.html",
        context={
            "request": request,
            "settings": settings,
            "user": current_user,
            "mfg_items": mfg_items,
            "com_items": com_items,
            "mfg_categories": mfg_categories,
            "com_categories": com_categories,
            "total_mfg_count": len(mfg_items),
            "total_com_count": len(com_items)
        }
    )


@router.get("/api/inventory/items")
async def api_list_inventory_items(
    warehouse_type: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Lists inventory items with optional filtering by warehouse, category, or search term"""
    items = db.get_inventory_items(warehouse_type=warehouse_type, category=category, search=search)
    return {"status": "success", "count": len(items), "items": items}


@router.get("/api/inventory/items/{item_id}")
async def api_get_inventory_item(
    item_id: str,
    current_user: User = Depends(get_current_user)
):
    """Returns detailed item info including BOM breakdown"""
    item = db.get_inventory_item_by_id(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sản phẩm trong kho!"
        )
    return {"status": "success", "item": item}


@router.post("/api/inventory/items")
async def api_create_inventory_item(
    payload: InventoryItemCreateRequest,
    current_user: User = Depends(require_manager_or_admin)
):
    """Creates a new inventory item with 4-tier pricing & optional BOM"""
    clean_sku = clean_string(payload.sku.strip().upper(), escape_html_entities=False)
    existing = db.get_inventory_item_by_sku(clean_sku)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã SKU '{clean_sku}' đã tồn tại trong hệ thống kho!"
        )

    clean_name = clean_string(payload.name, escape_html_entities=False)
    clean_cat = clean_string(payload.category, escape_html_entities=False)
    clean_unit = clean_string(payload.unit, escape_html_entities=False)
    clean_spec = clean_string(payload.spec, escape_html_entities=False)
    clean_notes = clean_string(payload.notes, escape_html_entities=False)

    item_id = f"inv-{str(uuid.uuid4())[:8]}"
    item = InventoryItem(
        id=item_id,
        sku=clean_sku,
        name=clean_name,
        warehouse_type=payload.warehouse_type,
        category=clean_cat,
        unit=clean_unit or "cái",
        stock_quantity=max(0.0, float(payload.stock_quantity)),
        cost_price=max(0.0, float(payload.cost_price)),
        retail_price=max(0.0, float(payload.retail_price)),
        dealer_price=max(0.0, float(payload.dealer_price)),
        project_discount_rate=max(0.0, min(100.0, float(payload.project_discount_rate))),
        is_custom_dimensions=payload.is_custom_dimensions,
        default_length=payload.default_length,
        default_width=payload.default_width,
        default_thickness=payload.default_thickness,
        material_type=payload.material_type,
        bom_data=payload.bom_data,
        spec=clean_spec,
        notes=clean_notes
    )

    created = db.create_inventory_item(item)
    return {"status": "success", "message": f"Đã thêm sản phẩm '{clean_sku}' vào kho thành công!", "item": created}


@router.put("/api/inventory/items/{item_id}")
async def api_update_inventory_item(
    item_id: str,
    payload: Dict[str, Any],
    current_user: User = Depends(require_manager_or_admin)
):
    """Updates an existing inventory item"""
    item = db.get_inventory_item_by_id(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sản phẩm cần cập nhật!"
        )

    # Sanitize string fields
    updates: Dict[str, Any] = {}
    for key, val in payload.items():
        if key in ["name", "spec", "notes", "category", "unit", "material_type"] and isinstance(val, str):
            updates[key] = clean_string(val, escape_html_entities=False)
        elif key in ["stock_quantity", "cost_price", "retail_price", "dealer_price", "project_discount_rate", "default_length", "default_width", "default_thickness"]:
            try:
                updates[key] = float(val) if val is not None else None
            except (ValueError, TypeError):
                pass
        elif key == "is_custom_dimensions":
            updates[key] = bool(val)
        elif key in ["warehouse_type", "bom_data"]:
            updates[key] = val

    updated = db.update_inventory_item(item_id, updates)
    return {"status": "success", "message": "Cập nhật sản phẩm thành công!", "item": updated}


@router.delete("/api/inventory/items/{item_id}")
async def api_delete_inventory_item(
    item_id: str,
    current_user: User = Depends(require_manager_or_admin)
):
    """Deletes an item from inventory"""
    item = db.get_inventory_item_by_id(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sản phẩm để xóa!"
        )
    db.delete_inventory_item(item_id)
    return {"status": "success", "message": f"Đã xóa sản phẩm '{item.sku}' khỏi kho."}


@router.post("/api/inventory/calculate-bom")
async def api_calculate_bom(
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """
    Computes factory cost and suggested price tiers from raw material list,
    waste scrap ratio, labor cost, and overhead.
    """
    raw_materials = payload.get("raw_materials", [])
    scrap_waste_ratio = float(payload.get("scrap_waste_ratio", 0.05))
    labor_cost = float(payload.get("labor_cost", 0.0))
    overhead_cost = float(payload.get("overhead_cost", 0.0))
    margin_retail = float(payload.get("margin_retail", 0.30))
    margin_dealer = float(payload.get("margin_dealer", 0.15))

    result = calculate_bom_cost(
        raw_materials=raw_materials,
        scrap_waste_ratio=scrap_waste_ratio,
        labor_cost=labor_cost,
        overhead_cost=overhead_cost,
        margin_retail=margin_retail,
        margin_dealer=margin_dealer
    )
    return {"status": "success", "data": result}


@router.post("/api/inventory/calculate-dimension-cost")
async def api_calculate_dimension_cost(
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """
    Computes area, weight, and pricing for custom-dimension items
    (ducts, VinFast EV protection plates, enclosures).
    """
    category = payload.get("category", "")
    material_type = payload.get("material_type", "THÉP_MẠ_KẼM")
    length_mm = float(payload.get("length_mm", 1000.0))
    width_mm = float(payload.get("width_mm", 1000.0))
    height_mm = float(payload.get("height_mm", 0.0)) if payload.get("height_mm") else None
    thickness_mm = float(payload.get("thickness_mm", 1.0)) if payload.get("thickness_mm") else None
    base_cost_price = float(payload.get("base_cost_price", 0.0))
    base_retail_price = float(payload.get("base_retail_price", 0.0))
    base_dealer_price = float(payload.get("base_dealer_price", 0.0))
    project_discount_rate = float(payload.get("project_discount_rate", 0.0))
    quantity = float(payload.get("quantity", 1.0))

    result = calculate_manufacturing_dimensions(
        category=category,
        material_type=material_type,
        length_mm=length_mm,
        width_mm=width_mm,
        height_mm=height_mm,
        thickness_mm=thickness_mm,
        base_cost_price=base_cost_price,
        base_retail_price=base_retail_price,
        base_dealer_price=base_dealer_price,
        project_discount_rate=project_discount_rate,
        quantity=quantity
    )
    return {"status": "success", "data": result}
