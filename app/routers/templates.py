"""
Master Template & Pricing Coefficients API Router
Allows viewing, uploading, and managing company Master Templates and coefficient frameworks
(% waste, transport, labor, profit margin).
"""
import uuid
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, status
from fastapi.responses import FileResponse

from app.config import settings
from app.database.db import db
from app.database.models import MasterTemplate, UpdateCoefficientsRequest, User
from app.services.auth import get_current_user, require_manager_or_admin
from app.services.file_validator import FileValidator
from app.tools.template_generator import create_master_template_excel

router = APIRouter(prefix="/api/templates", tags=["Master Templates"])


@router.get("", response_model=List[MasterTemplate])
def get_all_templates(current_user: User = Depends(get_current_user)):
    """Lấy danh sách tất cả các File Mẫu Chuẩn & Khung Hệ Số Định Mức (Yêu cầu đăng nhập)"""
    templates = db.list_templates()
    if not templates:
        # Generate default excel template if not exists
        default_path = Path(settings.STORAGE_DIR) / "templates" / "Master_Template_Vertex.xlsx"
        if not default_path.exists():
            create_master_template_excel(str(default_path))
        templates = db.list_templates()
    return templates


@router.get("/active", response_model=MasterTemplate)
def get_active_template(current_user: User = Depends(get_current_user)):
    """Lấy File Mẫu Chuẩn đang được áp dụng mặc định"""
    return db.get_active_template()


@router.get("/{template_id}/download")
def download_template_excel(
    template_id: str,
    current_user: User = Depends(get_current_user)
):
    """Tải file Excel mẫu chuẩn Vertex về máy tính"""
    tpl = db.get_template_by_id(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Không tìm thấy file mẫu này!")

    file_path = tpl.file_path
    if not file_path or not Path(file_path).exists():
        default_path = Path(settings.STORAGE_DIR) / "templates" / "Master_Template_Vertex.xlsx"
        create_master_template_excel(str(default_path))
        file_path = str(default_path)

    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=tpl.file_name or "Master_Template_Vertex.xlsx"
    )


@router.post("/upload", response_model=MasterTemplate)
async def upload_master_template(
    file: UploadFile = File(...),
    name: str = Form(""),
    description: str = Form("Mẫu chuẩn bóc tách vật tư và định mức chi phí"),
    waste_ratio: float = Form(0.05),
    transport_ratio: float = Form(0.03),
    labor_ratio: float = Form(0.15),
    margin_ratio: float = Form(0.12),
    set_active: bool = Form(True),
    current_user: User = Depends(get_current_user)
):
    """
    Tải lên file mẫu chuẩn mới của công ty (Excel .xlsx, .pdf, .csv) kèm các khung tỷ lệ định mức.
    (Hỗ trợ người dùng đã xác thực đăng nhập)
    """
    save_dir = Path(settings.STORAGE_DIR) / "templates"
    save_dir.mkdir(parents=True, exist_ok=True)

    # Validate file
    save_path, clean_filename = await FileValidator.validate_and_save(
        upload_file=file,
        destination_dir=str(save_dir)
    )

    template_name = name.strip() if name and name.strip() else f"Mẫu Chuẩn - {clean_filename}"
    template_id = f"tpl-{uuid.uuid4().hex[:8]}"
    template = MasterTemplate(
        id=template_id,
        name=template_name,
        file_path=save_path,
        file_name=clean_filename,
        description=description.strip() or f"File mẫu tải lên bởi {current_user.full_name}",
        waste_ratio=float(waste_ratio),
        transport_ratio=float(transport_ratio),
        labor_ratio=float(labor_ratio),
        margin_ratio=float(margin_ratio),
        is_active=set_active,
        created_by=current_user.full_name
    )
    db.save_template(template)
    return template




@router.put("/{template_id}/coefficients")
def update_coefficients(
    template_id: str,
    payload: UpdateCoefficientsRequest,
    current_user: User = Depends(require_manager_or_admin)
):
    """
    Cập nhật các khung tỷ lệ % (% Hao hụt, % Vận chuyển, % Nhân công, % Lợi nhuận) của file mẫu.
    (Chỉ dành cho Admin Sếp Tiến / Manager Anh Việt)
    """
    tpl = db.get_template_by_id(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Không tìm thấy file mẫu này!")

    success = db.update_template_coefficients(
        template_id=template_id,
        waste_ratio=payload.waste_ratio,
        transport_ratio=payload.transport_ratio,
        labor_ratio=payload.labor_ratio,
        margin_ratio=payload.margin_ratio,
        name=payload.name,
        description=payload.description
    )

    if not success:
        raise HTTPException(status_code=400, detail="Không thể cập nhật hệ số định mức!")

    updated_tpl = db.get_template_by_id(template_id)
    return {
        "status": "success",
        "message": f"Đã cập nhật khung hệ số định mức cho '{updated_tpl.name}' thành công!",
        "template": updated_tpl
    }


@router.put("/{template_id}/active")
def set_active_template_endpoint(
    template_id: str,
    current_user: User = Depends(require_manager_or_admin)
):
    """Đặt một file mẫu làm mẫu chuẩn áp dụng mặc định cho các báo giá mới"""
    success = db.set_active_template(template_id)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy file mẫu này!")

    tpl = db.get_template_by_id(template_id)
    return {
        "status": "success",
        "message": f"Đã kích hoạt '{tpl.name}' làm File Mẫu Chuẩn mặc định!",
        "active_template": tpl
    }
