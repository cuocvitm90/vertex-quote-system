"""
Groq LLM Client (OpenAI-Compatible)
Qualitative BOQ & Drawing Extractor using Groq AI.
CRITICAL: AI only performs qualitative semantic parsing. Zero monetary calculations done here.
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from app.config import settings

logger = logging.getLogger("vertex.groq_ai")
logging.basicConfig(level=logging.INFO)


SYSTEM_PROMPT = """Bạn là Chuyên gia AI bóc tách khối lượng và quy cách vật tư cơ điện (HVAC / MEP) cho thương hiệu Vertex (Ống gió, Phụ kiện, Van gió, Cửa gió).

NHIỆM VỤ DUY NHẤT: Bóc tách ĐỊNH TÍNH và chuẩn hóa danh mục vật tư từ văn bản thô / bảng thống kê.
- Nhận diện chính xác:
  1. Tên vật tư (raw_name và standard_name chuẩn tiếng Việt)
  2. Phân loại (category: "Ống gió vuông", "Ống gió tròn xoắn", "Ống gió Inox", "Phụ kiện ống gió vuông", "Phụ kiện ống gió tròn", "Van gió", "Cửa gió / Miệng gió", "Hộp gió", "Vật tư phụ")
  3. Kích thước W (chiều rộng mm), H (chiều cao mm), D (đường kính mm), L (chiều dài m), thickness (độ dày tôn mm: 0.48, 0.58, 0.75, 0.95, 1.15...)
  4. Vật liệu (material: "Tôn mạ kẽm", "Inox SUS 304", "Nhôm định hình", "Thép mạ kẽm"...)
  5. Đơn vị tính (unit: "m2", "m", "cái", "bộ", "cây", "cuộn", "chai")
  6. Số lượng thô (quantity: float)

QUY TẮC BẮT BUỘC (CRITICAL RULES):
- TUYỆT ĐỐI KHÔNG làm toán, không nhân chia đơn giá, không tính chiết khấu hay VAT. Toàn bộ tiền bạc sẽ do máy tính Python tính toán độc lập để chống sai lệch số học.
- Trả về DUY NHẤT một mảng JSON hợp lệ (JSON Array) theo cấu trúc mẫu dưới đây, không viết thêm lời dẫn:

[
  {
    "stt": 1,
    "raw_name": "Tên gốc trong file",
    "standard_name": "Tên chuẩn hóa sản phẩm Vertex",
    "category": "Ống gió vuông",
    "spec": "500x300mm, L=1.2m, d=0.75mm, bích TDC",
    "width": 500.0,
    "height": 300.0,
    "diameter": null,
    "length": 1.2,
    "thickness": 0.75,
    "material": "Tôn mạ kẽm",
    "unit": "m2",
    "quantity": 10.0,
    "notes": "Ghi chú"
  }
]
"""


class GroqBOQAgent:
    """AI Qualitative Semantic Extractor using Groq API"""

    @classmethod
    def _get_client(cls) -> AsyncOpenAI:
        return AsyncOpenAI(
            base_url=settings.AI_BASE_URL,
            api_key=settings.AI_API_KEY
        )

    @classmethod
    async def analyze_boq_text(cls, raw_text: str, context_hint: str = "") -> Optional[List[Dict[str, Any]]]:
        """
        Calls Groq API to qualitatively parse raw text / tabular extract into structured items.
        Attempts configured model, then falls back to available Groq models if needed.
        """
        if not settings.AI_API_KEY or settings.AI_API_KEY == "your_groq_api_key":
            logger.warning("Groq API key not configured, skipping LLM qualitative parse.")
            return None

        prompt = f"""Dưới đây là dữ liệu vật tư cần bóc tách (Gợi ý ngữ cảnh: {context_hint}):

--- BẮT ĐẦU DỮ LIỆU ---
{raw_text[:12000]}
--- KẾT THÚC DỮ LIỆU ---

Hãy bóc tách thành mảng JSON theo đúng định dạng được yêu cầu."""

        client = cls._get_client()
        candidate_models = [settings.AI_MODEL_NAME, "openai/gpt-oss-120b", "qwen/qwen3.8-27b", "groq/compound"]

        for model in candidate_models:
            try:
                logger.info(f"Calling Groq API model '{model}' for qualitative parsing...")
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=4096
                )

                content = response.choices[0].message.content.strip()
                # Extract JSON from markdown code block if present
                json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
                if json_match:
                    json_str = json_match.group(1).strip()
                else:
                    json_str = content

                parsed = json.loads(json_str)
                if isinstance(parsed, list):
                    logger.info(f"Groq API ({model}) successfully extracted {len(parsed)} items qualitatively.")
                    return parsed

            except Exception as e:
                logger.warning(f"Groq API call with model '{model}' failed: {e}")
                continue

        logger.info("Falling back to internal rule-based parser.")
        return None
