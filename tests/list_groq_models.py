import asyncio
import sys
from openai import AsyncOpenAI
from app.config import settings

async def list_models():
    client = AsyncOpenAI(base_url=settings.AI_BASE_URL, api_key=settings.AI_API_KEY)
    try:
        models = await client.models.list()
        print("Available Groq Models:")
        for m in models.data:
            print(" -", m.id)
    except Exception as e:
        print("Error listing models:", e)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(list_models())
