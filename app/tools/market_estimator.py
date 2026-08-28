"""
AI Market Price Estimator Tool for Vertex Construction & PCCC
Automatically estimates realistic Vietnamese market unit prices for items not found in Company Catalog
using Groq Llama-3.3-70B with specialized MEP/Fire Protection market knowledge.
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from app.config import settings

logger = logging.getLogger("vertex.market_estimator")

FALLBACK_MARKET_PRICES = {
    "foam": 450000,
    "sprinkler": 75000,
    "tủ báo cháy": 12500000,
    "trung tâm báo cháy": 14500000,
    "nút ấn": 180000,
    "chuông": 240000,
    "bình chữa cháy": 320000,
    "vòi chữa cháy": 680000,
    "lăng phun": 280000,
    "ống gió": 260000,
    "van gió": 480000,
    "cửa gió": 350000,
    "quạt hút": 8500000,
    "đèn exit": 280000,
    "đèn sự cố": 320000,
    "khớp nối mềm": 220000,
    "ti treo": 35000,
    "co": 180000,
    "tê": 220000,
    "côn": 195000
}


class AIMarketEstimator:
    """
    AI-powered Market Price Lookup & Estimation for uncataloged MEP/PCCC materials.
    """

    @classmethod
    async def estimate_market_price(
        cls,
        item_name: str,
        spec: str = "",
        unit: str = "cái",
        thickness: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Estimates realistic market base price for a single item using Groq AI.
        Returns: {raw_market_price: float, estimated_category: str, market_notes: str, confidence: float}
        """
        if not settings.AI_API_KEY or settings.AI_API_KEY.startswith("mock_"):
            return cls._fallback_estimate(item_name, spec, unit)

        client = AsyncOpenAI(
            api_key=settings.AI_API_KEY,
            base_url=settings.AI_BASE_URL
        )

        prompt = f"""Bạn là Kỹ sư Dự toán Trưởng & Chuyên gia Tra cứu Giá Thị trường Vật tư Cơ điện (HVAC/MEP) và Phòng cháy Chữa cháy (PCCC) tại Việt Nam năm 2026.
Hãy tra cứu và ước tính đơn giá thị trường thực tế (Đơn vị: VNĐ / {unit}) cho vật tư sau:

- Tên vật tư: {item_name}
- Quy cách / Model / Hãng: {spec}
- Đơn vị tính: {unit}
- Độ dày (nếu có): {thickness or 'Theo tiêu chuẩn'}

YÊU CẦU ĐỊNH DẠNG:
Trả về DUY NHẤT một JSON hợp lệ (không kèm giải thích bên ngoài):
{{
    "raw_market_price": <số nguyên VNĐ, ví dụ 350000>,
    "category": "<Phân loại: Thiết bị PCCC / Báo cháy / Bình chữa cháy / Ống gió / Van gió / Phụ kiện>",
    "market_notes": "<Ghi chú ngắn về nguồn giá tham khảo thị trường Việt Nam (tối đa 1 câu)>",
    "confidence": <độ tin cậy từ 0.70 đến 0.95>
}}
"""

        try:
            response = await client.chat.completions.create(
                model=settings.AI_MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a professional MEP & Fire Protection cost estimation AI. Always output valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )

            content = response.choices[0].message.content.strip()
            # Extract JSON substring
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                price = float(parsed.get("raw_market_price", 0.0))
                if price > 0:
                    return {
                        "raw_market_price": round(price, 0),
                        "estimated_category": parsed.get("category", "Vật tư & Thiết bị PCCC"),
                        "market_notes": f"AI Tra cứu thị trường: {parsed.get('market_notes', 'Mặt bằng giá MEP Việt Nam 2026')}",
                        "confidence": float(parsed.get("confidence", 0.85))
                    }
        except Exception as e:
            logger.warning(f"Groq market price lookup error for '{item_name}': {e}. Using fallback rule engine.")

        return cls._fallback_estimate(item_name, spec, unit)

    @classmethod
    def _fallback_estimate(cls, item_name: str, spec: str, unit: str) -> Dict[str, Any]:
        """Rule-based heuristic price fallback when AI is offline"""
        name_lower = (item_name + " " + spec).lower()
        matched_price = 250000.0

        for keyword, price in FALLBACK_MARKET_PRICES.items():
            if keyword in name_lower:
                matched_price = float(price)
                break

        # Adjust by unit
        if unit.lower() in ["m2", "m²", "mét vuông"]:
            if matched_price > 500000:
                matched_price = 280000.0
        elif unit.lower() in ["m", "mét"]:
            if matched_price > 400000:
                matched_price = 120000.0

        return {
            "raw_market_price": matched_price,
            "estimated_category": "Vật tư Cơ điện & PCCC",
            "market_notes": "Ước tính theo định mức thị trường Việt Nam",
            "confidence": 0.80
        }
