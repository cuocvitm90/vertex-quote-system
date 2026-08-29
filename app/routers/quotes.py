"""
Quotes API Router
Handles file uploads, quote listing, details, downloads, and approval actions.
All data extraction and quotation operations are strictly protected by JWT Authentication.
"""
import os
import html
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Depends, Request, status
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse

from app.config import settings
from app.database.db import db
from app.database.models import Quote, QuoteStatus, ApprovalRequest, User, QuoteRevisionRequest, AuditLog
from app.agent.orchestrator import VertexQuoteAgent
from app.services.quote_service import QuoteService
from app.services.auth import get_current_user, require_manager_or_admin
from app.dependencies import can_access_quote

router = APIRouter(prefix="/api/quotes", tags=["Quotes"])


@router.get("/sample-files/{file_type}")
def get_sample_file(file_type: str):
    """Cung cấp file mẫu Excel BOQ hoặc CAD DXF để kiểm thử nhanh hệ thống"""
    from app.tools.sample_generator import create_sample_excel_boq, create_sample_cad_dxf
    if file_type == "excel":
        path = "storage/samples/BOQ_Mau_Ong_Gio_Vertex.xlsx"
        if not Path(path).exists():
            create_sample_excel_boq(path)
        return FileResponse(path, filename="BOQ_Mau_Ong_Gio_Vertex.xlsx")
    elif file_type == "cad":
        path = "storage/samples/Ban_Ve_CAD_Ong_Gio.dxf"
        if not Path(path).exists():
            create_sample_cad_dxf(path)
        return FileResponse(path, filename="Ban_Ve_CAD_Ong_Gio.dxf")
    raise HTTPException(status_code=404, detail="Loại file mẫu không hợp lệ")


@router.post("/upload")
async def upload_boq_and_generate_quote(
    request: Request,
    file: UploadFile = File(..., description="File BOQ Excel (.xlsx, .xls), CAD (.dxf), hoặc PDF"),
    customer_name: str = Form("Quý Khách Hàng", description="Tên khách hàng / Công ty"),
    customer_phone: str = Form("", description="Số điện thoại khách hàng"),
    customer_email: str = Form("", description="Email khách hàng"),
    customer_zalo_id: str = Form("", description="Zalo User ID khách hàng"),
    project_name: str = Form("Công trình Tiêu chuẩn", description="Tên công trình / dự án"),
    project_address: str = Form("", description="Địa chỉ công trình"),
    discount_rate: Optional[float] = Form(None, description="Tỷ lệ chiết khấu (VD: 0.05 là 5%)"),
    vat_rate: Optional[float] = Form(None, description="Thuế suất VAT (VD: 0.08 là 8%)"),
    language: str = Form("vi", description="Ngôn ngữ báo giá: vi, en, zh, ko"),
    template_id: Optional[str] = Form(None, description="ID file mẫu chuẩn và hệ số định mức áp dụng"),
    current_user: User = Depends(get_current_user)
):
    """
    Nhận file BOQ Excel/CAD/PDF, kiểm tra an ninh (Magic Bytes, Max 50MB, Path Traversal),
    kích hoạt AI Agent bóc tách, tra giá theo file mẫu chuẩn / AI thị trường, tính toán thuần Python,
    sinh file Excel báo giá chuẩn và gửi yêu cầu duyệt tới Zalo OA của Quản lý.
    Yêu cầu: Người dùng phải đăng nhập hợp lệ (JWT Authentication).
    """
    from app.services.file_validator import FileValidator
    from app.services.sanitizer import clean_string
    import traceback

    try:
        # 1. Validate file extension, signature (Magic Bytes), and stream safely
        save_path, clean_filename = await FileValidator.validate_and_save(
            upload_file=file,
            destination_dir=settings.UPLOAD_DIR
        )

        # 2. Sanitize user inputs against XSS and control chars
        clean_cust_name = clean_string(customer_name, escape_html_entities=False) or "Quý Khách Hàng"
        clean_cust_phone = clean_string(customer_phone, escape_html_entities=False)
        clean_cust_email = clean_string(customer_email, escape_html_entities=False)
        clean_cust_zalo = clean_string(customer_zalo_id, escape_html_entities=False)
        clean_proj_name = clean_string(project_name, escape_html_entities=False) or "Công trình Tiêu chuẩn"
        clean_proj_addr = clean_string(project_address, escape_html_entities=False)

        # 3. Run AI Agent Workflow (Asynchronous & Non-blocking)
        quote = await VertexQuoteAgent.process_quote_request(
            file_path=save_path,
            customer_name=clean_cust_name,
            customer_phone=clean_cust_phone,
            customer_email=clean_cust_email,
            customer_zalo_id=clean_cust_zalo,
            project_name=clean_proj_name,
            project_address=clean_proj_addr,
            discount_rate=discount_rate,
            vat_rate=vat_rate,
            language=language,
            template_id=template_id
        )

        return {
            "status": "success",
            "message": f"Báo giá {quote.quote_code} đã được tạo thành công và gửi duyệt tới Quản lý qua Zalo OA!",
            "quote": quote
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CRITICAL UPLOAD ERROR] {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi xử lý file và tính toán báo giá: {str(e)}"
        )


@router.get("", response_model=List[Quote])
def get_all_quotes(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user)
):
    """Lấy danh sách tất cả các báo giá (Yêu cầu đăng nhập)"""
    return db.list_quotes(limit=limit, offset=offset)


@router.get("/{quote_id}")
def get_quote_details(
    quote: Quote = Depends(can_access_quote),
    current_user: User = Depends(get_current_user)
):
    """Lấy thông tin chi tiết của một báo giá theo ID hoặc Mã báo giá (Bảo vệ chống IDOR)"""
    return quote


@router.get("/{quote_id}/versions", response_model=List[Quote])
def get_quote_versions(
    quote: Quote = Depends(can_access_quote),
    current_user: User = Depends(get_current_user)
):
    """Lấy toàn bộ lịch sử các phiên bản (v1, v2...) của báo giá này (Bảo vệ chống IDOR)"""
    return db.get_quote_versions(quote.id)


@router.get("/{quote_id}/audit-logs", response_model=List[AuditLog])
def get_quote_audit_logs(
    quote: Quote = Depends(can_access_quote),
    current_user: User = Depends(get_current_user)
):
    """Lấy nhật ký kiểm toán & lịch sử thao tác chi tiết (Audit Trail) của báo giá (Bảo vệ chống IDOR)"""
    return db.get_quote_audit_logs(quote.id)


@router.post("/{quote_id}/revision", response_model=Quote)
def create_quote_revision(
    req: QuoteRevisionRequest,
    request: Request,
    quote: Quote = Depends(can_access_quote),
    current_user: User = Depends(get_current_user)
):
    """
    Tạo phiên bản mới (Revision: v2, v3...) từ báo giá hiện tại (Bảo vệ chống IDOR).
    Cho phép điều chỉnh số lượng, quy cách vật tư, tỷ lệ chiết khấu/VAT và ghi lại lịch sử.
    """
    client_ip = request.client.host if request.client else ""
    new_quote = QuoteService.create_revision(
        quote_id=quote.id,
        user=current_user,
        revision_note=req.revision_note,
        discount_rate=req.discount_rate,
        vat_rate=req.vat_rate,
        updated_items=req.items,
        ip_address=client_ip
    )
    return new_quote


@router.get("/{quote_id}/download")
def download_quote_excel(
    request: Request,
    quote: Quote = Depends(can_access_quote),
    current_user: User = Depends(get_current_user)
):
    """Tải file Excel báo giá chuẩn Vertex (Bảo vệ chống IDOR)"""
    if not quote.excel_quote_path or not Path(quote.excel_quote_path).exists():
        excel_path = QuoteService.regenerate_excel(quote.id)
    else:
        excel_path = quote.excel_quote_path

    file_name = Path(excel_path).name

    # Record download event in Audit Log
    client_ip = request.client.host if request.client else ""
    db.add_audit_log(
        quote_id=quote.id,
        user_id=current_user.id,
        user_name=current_user.full_name,
        user_role=current_user.role.value,
        action="EXPORT_EXCEL",
        details=f"Tải xuống file Excel báo giá chuẩn '{file_name}'.",
        ip_address=client_ip
    )

    return FileResponse(
        path=excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=file_name
    )


@router.post("/{quote_id}/approve")
async def approve_or_reject_quote_post(
    quote_id: str,
    req: ApprovalRequest,
    request: Request,
    current_user: User = Depends(require_manager_or_admin)
):
    """Xử lý phê duyệt hoặc từ chối báo giá (POST API - Hỗ trợ phân quyền đa cấp Manager / Director)"""
    client_ip = request.client.host if request.client else ""
    if req.action.lower() == "approve":
        result = await QuoteService.approve_quote(
            quote_id=quote_id,
            manager_name=req.manager_name or current_user.full_name,
            manager_id=req.manager_id or current_user.id,
            manager_role=current_user.role.value,
            ip_address=client_ip
        )
        return result
    else:
        result = await QuoteService.reject_quote(
            quote_id=quote_id,
            manager_name=req.manager_name or current_user.full_name,
            manager_id=req.manager_id or current_user.id,
            manager_role=current_user.role.value,
            reason=req.reason or "Quản lý từ chối yêu cầu báo giá",
            ip_address=client_ip
        )
        return result



@router.get("/{quote_id}/approve")
async def approve_or_reject_quote_get(
    quote_id: str,
    token: str = Query(..., description="Chữ ký xác thực bảo mật HMAC-SHA256"),
    action: str = Query("approve", enum=["approve", "reject"]),
    manager_name: str = Query("Anh Việt (Trưởng phòng KD)"),
    reason: str = Query("")
):
    """
    Xử lý phê duyệt/từ chối từ nút bấm link Zalo (GET Action link).
    Bắt buộc phải có HMAC token hợp lệ và còn hạn sử dụng.
    Trả về trang HTML thông báo kết quả duyệt trực quan cho Quản lý.
    """
    from app.services.auth import verify_approval_token
    if not verify_approval_token(quote_id=quote_id, action=action, token=token, secret_key=settings.SECRET_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token phê duyệt không hợp lệ hoặc đã hết hạn! Vui lòng yêu cầu cấp lại link phê duyệt mới."
        )

    quote = db.get_quote(quote_id)
    if not quote:
        return HTMLResponse("<h3>❌ Không tìm thấy thông tin báo giá!</h3>", status_code=404)

    safe_code = html.escape(str(quote.quote_code or ""))
    safe_customer = html.escape(str(quote.customer_name or ""))
    safe_project = html.escape(str(quote.project_name or ""))
    safe_manager = html.escape(str(manager_name or ""))
    safe_reason = html.escape(str(reason)) if reason else "Yêu cầu điều chỉnh lại"

    if action == "approve":
        res = await QuoteService.approve_quote(quote_id=quote_id, manager_name=manager_name)
        status_text = "ĐÃ DUYỆT THÀNH CÔNG"
        status_color = "#10B981"
        desc_text = f"Báo giá <b>{safe_code}</b> đã được phê duyệt và gửi thông báo chính thức cho khách hàng <b>{safe_customer}</b> qua Zalo OA."
    else:
        res = await QuoteService.reject_quote(quote_id=quote_id, manager_name=manager_name, reason=reason or "Quản lý yêu cầu điều chỉnh")
        status_text = "ĐÃ TỪ CHỐI BÁO GIÁ"
        status_color = "#EF4444"
        desc_text = f"Báo giá <b>{safe_code}</b> đã được chuyển sang trạng thái Từ chối. Lý do: {safe_reason}"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Kết Quả Phê Duyệt - Vertex Quote</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: #F0F4F8;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                margin: 0;
                padding: 20px;
                box-sizing: border-box;
            }}
            .card {{
                background: #FFFFFF;
                border-radius: 16px;
                box-shadow: 0 10px 25px rgba(0,0,0,0.08);
                max-width: 480px;
                width: 100%;
                padding: 32px 24px;
                text-align: center;
            }}
            .badge {{
                display: inline-block;
                padding: 8px 16px;
                border-radius: 999px;
                font-size: 14px;
                font-weight: 700;
                color: #FFFFFF;
                background: {status_color};
                margin-bottom: 16px;
            }}
            h2 {{ color: #1E293B; margin: 0 0 12px 0; font-size: 20px; }}
            p {{ color: #64748B; font-size: 14px; line-height: 1.6; margin: 0 0 24px 0; }}
            .details {{
                background: #F8FAFC;
                border-radius: 12px;
                padding: 16px;
                text-align: left;
                margin-bottom: 24px;
                font-size: 13px;
                color: #334155;
            }}
            .details div {{ margin-bottom: 8px; }}
            .details div:last-child {{ margin-bottom: 0; }}
            .btn {{
                display: inline-block;
                background: #0B4870;
                color: #FFFFFF;
                text-decoration: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="badge">{status_text}</div>
            <h2>Xác Nhận Phê Duyệt Báo Giá</h2>
            <p>{desc_text}</p>
            <div class="details">
                <div><b>Mã báo giá:</b> {safe_code}</div>
                <div><b>Khách hàng:</b> {safe_customer}</div>
                <div><b>Dự án:</b> {safe_project}</div>
                <div><b>Tổng thanh toán:</b> {quote.total_amount:,.0f} VNĐ</div>
                <div><b>Người duyệt:</b> {safe_manager}</div>
            </div>
            <a href="/api/quotes/{quote.id}/download" class="btn">📥 Tải File Excel Báo Giá</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
