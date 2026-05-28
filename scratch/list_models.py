import os
import httpx
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")
print(f"API Key present: {bool(api_key)}")
if api_key:
    print(f"First 10 chars: {api_key[:10]}...")

headers = {
    "x-api-key": api_key,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}

try:
    resp = httpx.get("https://api.anthropic.com/v1/models", headers=headers)
    print(f"Status: {resp.status_code}")
    print(resp.json())
except Exception as e:
    print(f"Error listing models: {e}")
