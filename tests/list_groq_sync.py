import requests
from app.config import settings

headers = {"Authorization": f"Bearer {settings.AI_API_KEY}"}
r = requests.get("https://api.groq.com/openai/v1/models", headers=headers)
print("Status:", r.status_code)
if r.status_code == 200:
    data = r.json()
    for m in data.get("data", []):
        print("Model:", m.get("id"))
else:
    print(r.text)
