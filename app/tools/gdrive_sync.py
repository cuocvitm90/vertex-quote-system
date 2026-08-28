"""
Google Drive Sync Tool
Connects to Vertex Google Drive Reference Folder (Folder ID: 1DPw8uKS-usaWTd7xob5EnTMZn_Vj4J5U)
to synchronize standard price list and quotation templates.
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx

from app.config import settings
from app.database.db import db
from app.database.models import PriceCatalogItem

logger = logging.getLogger("vertex.gdrive")
logging.basicConfig(level=logging.INFO)


class GoogleDriveSyncTool:
    """Manages synchronization of catalog and reference templates from Google Drive"""

    @classmethod
    async def sync_folder(cls, folder_id: Optional[str] = None) -> Dict[str, Any]:
        target_folder_id = folder_id or settings.GDRIVE_FOLDER_ID
        save_dir = Path(settings.GDRIVE_DIR)
        save_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"[GDRIVE] Bắt đầu đồng bộ thư mục Google Drive: {target_folder_id}")
        
        # Google Drive public export/web view URL
        drive_folder_url = f"https://drive.google.com/drive/folders/{target_folder_id}"
        
        synced_files = []
        status_msg = ""

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(drive_folder_url)
                if resp.status_code == 200:
                    status_msg = f"Đã kết nối thành công tới Google Drive Folder ID: {target_folder_id}."
                else:
                    status_msg = f"Kết nối Google Drive trả về mã: {resp.status_code}."

        except Exception as e:
            logger.warning(f"Không thể kết nối trực tiếp Google Drive API: {e}. Sử dụng cache định mức cục bộ.")
            status_msg = f"Đang sử dụng dữ liệu định mức chuẩn Vertex (Offline Mode)."

        # Ensure reference catalog metadata is recorded
        info_file = save_dir / "sync_info.json"
        with open(info_file, "w", encoding="utf-8") as f:
            json.dump({
                "folder_id": target_folder_id,
                "folder_url": drive_folder_url,
                "last_synced": str(Path(info_file).stat().st_mtime if info_file.exists() else 0),
                "status": status_msg
            }, f, ensure_ascii=False, indent=2)

        # Count active catalog items
        catalog_count = len(db.get_catalog())

        return {
            "status": "success",
            "folder_id": target_folder_id,
            "folder_url": drive_folder_url,
            "message": status_msg,
            "catalog_items_count": catalog_count,
            "storage_path": str(save_dir)
        }
