import os
import httpx
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
print(f"Gemini API Key present: {bool(api_key)}")
if api_key:
    print(f"First 10 chars: {api_key[:10]}...")

try:
    resp = httpx.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}")
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        models = resp.json().get("models", [])
        for m in models:
            print(f"- {m['name']} ({m.get('displayName')})")
    else:
        print(resp.json())
except Exception as e:
    print(f"Error listing Gemini models: {e}")
