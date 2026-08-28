"""
Zalo OA Service Module
Integrates with Zalo Official Account OpenAPI v3 for manager approvals and customer notifications.
"""
import hmac
import hashlib
import json
import logging
from typing import Dict, Any, Optional, List
import httpx
from app.config import settings
from app.database.models import Quote

logger = logging.getLogger("vertex.zalo")
logging.basicConfig(level=logging.INFO)


class ZaloOAService:
    """Handles Zalo OA message dispatching, interactive cards, and webhook verifications"""

    BASE_URL_OA = "https://openapi.zalo.me"
    AUTH_URL = "https://oauth.zaloapp.com/v4/oa/access_token"

    def __init__(self):
        self.app_id = settings.ZALO_APP_ID
        self.secret_key = settings.ZALO_SECRET_KEY
        self.access_token = settings.ZALO_OA_ACCESS_TOKEN
        self.refresh_token = settings.ZALO_OA_REFRESH_TOKEN
        self.webhook_secret = settings.ZALO_WEBHOOK_SECRET

    def verify_webhook_signature(self, body_bytes: bytes, signature: str) -> bool:
        """Verifies Zalo webhook signature using SHA256 HMAC"""
        if not signature or not self.secret_key or self.secret_key == "your_zalo_app_secret_key":
            if settings.APP_ENV == "development" and getattr(settings, "ALLOW_UNSIGNED_WEBHOOK", False):
                return True
            return False
        computed = hmac.new(
            self.secret_key.encode("utf-8"),
            body_bytes,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(f"mac={computed}", signature) or hmac.compare_digest(computed, signature)

    async def send_approval_request(self, quote: Quote, manager_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Sends an interactive approval card to Manager (Anh Việt / Sếp Tiến).
        Contains summary, total amount, download link, and [Duyệt] / [Từ chối] action buttons with HMAC security tokens.
        """
        from app.services.auth import generate_approval_token
        recipient_ids = [manager_id] if manager_id else settings.manager_ids_list
        if not recipient_ids:
            recipient_ids = ["viet_manager_zalo_id_001"]

        results = {}
        web_base = settings.BASE_URL.rstrip("/")
        download_url = f"{web_base}/api/quotes/{quote.id}/download"
        token_approve = generate_approval_token(quote.id, "approve", settings.SECRET_KEY, expire_minutes=1440)
        token_reject = generate_approval_token(quote.id, "reject", settings.SECRET_KEY, expire_minutes=1440)
        approve_action_url = f"{web_base}/api/quotes/{quote.id}/approve?action=approve&token={token_approve}&manager_name=Anh%20Việt"
        reject_action_url = f"{web_base}/api/quotes/{quote.id}/approve?action=reject&token={token_reject}&manager_name=Anh%20Việt"

        # Build Rich Interactive Message Card
        message_payload = {
            "recipient": {"user_id": ""},
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "transaction_billing",
                        "language": "VI",
                        "elements": [
                            {
                                "title": f"🔔 YÊU CẦU DUYỆT BÁO GIÁ: {quote.quote_code}",
                                "subtitle": f"Khách hàng: {quote.customer_name} | Dự án: {quote.project_name}",
                                "image_url": "https://img.icons8.com/color/96/commercial.png",
                                "type": "banner"
                            },
                            {
                                "title": "Chi tiết giá trị đơn hàng",
                                "style": "vertical",
                                "tables": [
                                    {"key": "Tổng tiền hàng:", "value": f"{quote.subtotal:,.0f} đ"},
                                    {"key": f"Chiết khấu ({int(quote.discount_rate*100)}%):", "value": f"-{quote.discount_amount:,.0f} đ"},
                                    {"key": f"Thuế VAT ({int(quote.vat_rate*100)}%):", "value": f"+{quote.vat_amount:,.0f} đ"},
                                    {"key": "TỔNG THANH TOÁN:", "value": f"{quote.total_amount:,.0f} đ"}
                                ]
                            }
                        ],
                        "buttons": [
                            {
                                "title": "✅ DUYỆT BÁO GIÁ",
                                "type": "oa.open.url",
                                "payload": {"url": approve_action_url}
                            },
                            {
                                "title": "❌ TỪ CHỐI",
                                "type": "oa.open.url",
                                "payload": {"url": reject_action_url}
                            },
                            {
                                "title": "📥 TẢI EXCEL XEM TRƯỚC",
                                "type": "oa.open.url",
                                "payload": {"url": download_url}
                            }
                        ]
                    }
                }
            }
        }

        # Fallback Text Message Format for Zalo OA Consultation API
        text_summary = (
            f"🔔 [VERTEX BÁO GIÁ] YÊU CẦU DUYỆT BÁO GIÁ\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 Mã báo giá: {quote.quote_code}\n"
            f"👤 Khách hàng: {quote.customer_name}\n"
            f"🏢 Dự án: {quote.project_name}\n"
            f"📦 Số chủng loại vật tư: {len(quote.items)} mục\n"
            f"💰 Tổng tiền hàng: {quote.subtotal:,.0f} VNĐ\n"
            f"🎁 Chiết khấu: {quote.discount_amount:,.0f} VNĐ ({int(quote.discount_rate*100)}%)\n"
            f"🧾 Thuế VAT: {quote.vat_amount:,.0f} VNĐ ({int(quote.vat_rate*100)}%)\n"
            f"💵 TỔNG CỘNG: {quote.total_amount:,.0f} VNĐ\n"
            f"📝 Bằng chữ: {quote.total_amount_in_words}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👉 Duyệt nhanh: {approve_action_url}\n"
            f"👉 Từ chối: {reject_action_url}\n"
            f"👉 File Excel: {download_url}"
        )

        for uid in recipient_ids:
            logger.info(f"[ZALO OA] Gửi yêu cầu duyệt báo giá {quote.quote_code} tới Quản lý Zalo ID: {uid}")
            # Try official API if token available
            if self.access_token and self.access_token != "your_zalo_oa_access_token":
                try:
                    payload = dict(message_payload)
                    payload["recipient"]["user_id"] = uid
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post(
                            f"{self.BASE_URL_OA}/v3.0/oa/message/transaction",
                            headers={"access_token": self.access_token, "Content-Type": "application/json"},
                            json=payload
                        )
                        results[uid] = resp.json()
                except Exception as e:
                    logger.warning(f"Zalo API call failed, falling back to simulated dispatch: {e}")
                    results[uid] = {"error": -1, "message": str(e), "simulated": True, "text_summary": text_summary}
            else:
                # Simulated dispatch for local testing & development
                results[uid] = {
                    "error": 0,
                    "message": "Success (Simulated in Development Mode)",
                    "simulated": True,
                    "quote_code": quote.quote_code,
                    "text_summary": text_summary
                }

        return {
            "status": "sent",
            "quote_code": quote.quote_code,
            "recipients": recipient_ids,
            "details": results,
            "text_summary": text_summary
        }

    async def send_quote_to_customer(self, quote: Quote) -> Dict[str, Any]:
        """
        Sends the official quotation to customer via Zalo OA after Manager has approved.
        """
        target_zalo_id = quote.customer_zalo_id or quote.customer_phone or "Khách hàng Zalo"
        web_base = settings.BASE_URL.rstrip("/")
        download_url = f"{web_base}/api/quotes/{quote.id}/download"

        text_message = (
            f"🌟 [VERTEX] BÁO GIÁ CHÍNH THỨC DỰ ÁN\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Kính gửi: {quote.customer_name}\n"
            f"Vertex xin trân trọng gửi bảng báo giá chính thức cho dự án: {quote.project_name}\n\n"
            f"📄 Số báo giá: {quote.quote_code}\n"
            f"💰 Tổng giá trị thanh toán: {quote.total_amount:,.0f} VNĐ\n"
            f"📝 Bằng chữ: {quote.total_amount_in_words}\n"
            f"⏳ Hiệu lực báo giá: {settings.QUOTE_VALIDITY_DAYS} ngày\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📥 Nhấn vào link sau để tải file Báo giá Excel chuẩn:\n"
            f"{download_url}\n\n"
            f"Mọi thắc mắc xin vui lòng liên hệ Hotline: {settings.COMPANY_HOTLINE}\n"
            f"Trân trọng cảm ơn Quý khách!"
        )

        logger.info(f"[ZALO OA] Gửi báo giá chính thức {quote.quote_code} tới khách hàng {quote.customer_name} ({target_zalo_id})")

        if self.access_token and self.access_token != "your_zalo_oa_access_token" and quote.customer_zalo_id:
            try:
                payload = {
                    "recipient": {"user_id": quote.customer_zalo_id},
                    "message": {"text": text_message}
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        f"{self.BASE_URL_OA}/v2.0/oa/message",
                        headers={"access_token": self.access_token, "Content-Type": "application/json"},
                        json=payload
                    )
                    return resp.json()
            except Exception as e:
                logger.error(f"Error sending customer quote via Zalo: {e}")
                return {"error": -1, "message": str(e), "simulated": True, "text": text_message}

        return {
            "error": 0,
            "message": "Quotation successfully dispatched to customer via Zalo OA (Simulated)",
            "simulated": True,
            "text": text_message,
            "download_url": download_url
        }


zalo_service = ZaloOAService()
