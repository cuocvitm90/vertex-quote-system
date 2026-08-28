"""
Catalog API Router
Allows viewing and updating Vertex standard price list items and syncing with Google Drive.
Protected by JWT Authentication to prevent unauthorized access to confidential price lists.
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from app.database.db import db
from app.database.models import PriceCatalogItem, User
from app.services.auth import get_current_user, require_manager_or_admin
from app.tools.gdrive_sync import GoogleDriveSyncTool

router = APIRouter(prefix="/api/catalog", tags=["Price Catalog"])


@router.get("", response_model=List[PriceCatalogItem])
def get_catalog_items(current_user: User = Depends(get_current_user)):
    """Lấy danh mục bảng giá chuẩn Vertex (Yêu cầu đăng nhập)"""
    return db.get_catalog()


@router.post("", response_model=PriceCatalogItem)
def update_catalog_item(
    item: PriceCatalogItem,
    current_user: User = Depends(require_manager_or_admin)
):
    """Thêm mới hoặc cập nhật đơn giá một mục vật tư trong Catalog (Yêu cầu Quản lý / Giám đốc)"""
    return db.save_catalog_item(item)


@router.post("/sync-gdrive")
async def sync_catalog_with_google_drive(
    folder_id: Optional[str] = Query(None),
    current_user: User = Depends(require_manager_or_admin)
):
    """Đồng bộ bảng giá và mẫu biểu từ Google Drive (Yêu cầu Quản lý / Giám đốc)"""
    res = await GoogleDriveSyncTool.sync_folder(folder_id)
    return res
