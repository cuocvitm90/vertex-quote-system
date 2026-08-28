"""
Zalo OA Webhook Router
Listens for Zalo OA events, interactive button clicks, and manager approval callbacks.
"""
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, Header, HTTPException, Body, Depends
from pydantic import BaseModel

from app.config import settings
from app.database.db import db
from app.database.models import User
from app.services.auth import require_manager_or_admin
from app.services.quote_service import QuoteService
from app.services.zalo_service import zalo_service

logger = logging.getLogger("vertex.zalo.webhook")
router = APIRouter(prefix="/api/zalo", tags=["Zalo Webhook"])


class SimulateApprovalPayload(BaseModel):
    quote_id: str
    action: str = "approve"  # "approve" or "reject"
    manager_name: str = "Anh Việt (Trưởng phòng KD)"
    manager_role: str = "MANAGER"  # "MANAGER" or "ADMIN"
    reason: Optional[str] = ""


@router.get("/webhook")
async def zalo_webhook_verify(request: Request):
    """Zalo Webhook Verification Endpoint (Challenge / URL verification)"""
    params = dict(request.query_params)
    logger.info(f"Zalo Webhook GET challenge: {params}")
    challenge = params.get("challenge", "ok")
    return {"challenge": challenge, "status": "active"}


@router.post("/webhook")
async def zalo_webhook_listener(
    request: Request,
    x_zalo_signature: Optional[str] = Header(None, alias="X-Zalo-Signature")
):
    """
    Main Webhook Handler for Zalo OA events:
    - user_submit_action: Manager clicked [Duyệt] or [Từ chối] button
    - user_send_text: Manager sent text command (e.g. 'Duyệt VTX-2026-0001')
    """
    body_bytes = await request.body()
    
    # 1. Verify Signature
    is_valid = zalo_service.verify_webhook_signature(body_bytes, x_zalo_signature or "")
    if not is_valid:
        logger.warning("Invalid or missing Zalo webhook signature")
        raise HTTPException(status_code=403, detail="Chữ ký Webhook Zalo không hợp lệ hoặc bị thiếu!")

    try:
        data = await request.json()
    except Exception:
        data = {}

    event_name = data.get("event_name", "")
    logger.info(f"[ZALO WEBHOOK] Received event: {event_name} - Data: {data}")

    # 2. Handle Interactive Action (Button Click)
    if event_name in ["user_submit_action", "oa_action"]:
        info = data.get("info", {})
        action_data = info.get("data", {})
        
        # Parse action and quote_id
        action = action_data.get("action", "").lower()
        quote_id = action_data.get("quote_id", "")
        sender_id = data.get("sender", {}).get("id", "Manager")

        if quote_id and action:
            if action == "approve":
                res = await QuoteService.approve_quote(quote_id=quote_id, manager_name=f"Manager ({sender_id})")
                return {"error": 0, "message": "Quote approved successfully", "result": res}
            elif action == "reject":
                reason = action_data.get("reason", "Quản lý từ chối qua Zalo")
                res = await QuoteService.reject_quote(quote_id=quote_id, manager_name=f"Manager ({sender_id})", reason=reason)
                return {"error": 0, "message": "Quote rejected", "result": res}

    # 3. Handle Text Reply Commands (e.g. 'Duyệt VTX-2026-0001')
    elif event_name in ["user_send_text"]:
        message_text = data.get("message", {}).get("text", "").strip()
        sender_id = data.get("sender", {}).get("id", "Manager")
        
        # Text command regex
        if message_text.lower().startswith("duyệt") or message_text.lower().startswith("duyet"):
            # Extract quote code: e.g. "Duyệt VTX-2026-0001"
            parts = message_text.split()
            if len(parts) >= 2:
                quote_code = parts[1].upper()
                quote = db.get_quote(quote_code)
                if quote:
                    res = await QuoteService.approve_quote(quote_id=quote.id, manager_name=f"Zalo Manager ({sender_id})")
                    return {"error": 0, "message": f"Duyệt thành công {quote_code}", "result": res}

        elif message_text.lower().startswith("từ chối") or message_text.lower().startswith("tu choi"):
            parts = message_text.split()
            if len(parts) >= 2:
                quote_code = parts[1].upper()
                quote = db.get_quote(quote_code)
                if quote:
                    reason = " ".join(parts[2:]) if len(parts) > 2 else "Từ chối qua tin nhắn Zalo"
                    res = await QuoteService.reject_quote(quote_id=quote.id, manager_name=f"Zalo Manager ({sender_id})", reason=reason)
                    return {"error": 0, "message": f"Từ chối {quote_code}", "result": res}

    return {"error": 0, "message": "Event received and processed", "event": event_name}


@router.post("/simulate-approval")
async def simulate_zalo_approval(
    payload: SimulateApprovalPayload,
    request: Request,
    current_user: User = Depends(require_manager_or_admin)
):
    """
    Simulator Endpoint: Cho phép kiểm thử duyệt/từ chối trực tiếp từ Web Dashboard trong môi trường development.
    Bị vô hiệu hóa hoàn toàn trên môi trường Production vì lý do bảo mật.
    """
    if settings.APP_ENV == "production":
        raise HTTPException(
            status_code=403,
            detail="Endpoint giả lập phê duyệt bị vô hiệu hóa trên môi trường Production vì lý do an toàn bảo mật."
        )
    client_ip = request.client.host if request.client else ""
    if payload.action.lower() == "approve":
        result = await QuoteService.approve_quote(
            quote_id=payload.quote_id,
            manager_name=payload.manager_name or current_user.full_name,
            manager_role=payload.manager_role or current_user.role.value,
            ip_address=client_ip
        )
    else:
        result = await QuoteService.reject_quote(
            quote_id=payload.quote_id,
            manager_name=payload.manager_name or current_user.full_name,
            manager_role=payload.manager_role or current_user.role.value,
            reason=payload.reason or "Quản lý từ chối trong bộ giả lập",
            ip_address=client_ip
        )
    return result


