"""
Test Groq API connection and Llama-3.3-70B model
"""
import asyncio
import sys
from app.agent.llm_client import GroqBOQAgent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


async def main():
    sample_text = """
    1. Ống gió vuông tôn mạ kẽm 500x300 L=1200 d=0.75mm bích TDC - 25m2
    2. Cút 90 độ ống gió vuông 500x300 d0.75 - 5m2
    3. Van điều chỉnh lưu lượng tay gạt VCD 500x300 - 2 cái
    """
    print("[TEST] Calling Groq API (llama-3.3-70b-versatile)...")
    result = await GroqBOQAgent.analyze_boq_text(sample_text, context_hint="Dự án Tòa Nhà Văn Phòng")
    print(f"[TEST] Result from Groq: {result is not None}")
    if result:
        print(f"[TEST] Extracted {len(result)} items:")
        for it in result:
            print(f"  - {it.get('stt')}. {it.get('standard_name')} | Spec: {it.get('spec')} | Qty: {it.get('quantity')} {it.get('unit')}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

