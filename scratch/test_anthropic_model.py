import os
import httpx
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")
headers = {
    "x-api-key": api_key,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}

models_to_test = ["claude-sonnet-4-5", "claude-sonnet-4-5-20250929", "claude-sonnet-4-6"]

for model in models_to_test:
    payload = {
        "model": model,
        "max_tokens": 10,
        "messages": [{"role": "user", "content": "Hi"}],
    }
    try:
        resp = httpx.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        print(f"Model: {model} -> Status: {resp.status_code}")
        if resp.status_code != 200:
            print(resp.json())
    except Exception as e:
        print(f"Model: {model} -> Error: {e}")
