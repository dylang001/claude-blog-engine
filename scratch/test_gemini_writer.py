import os
import httpx
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
headers = {
    "content-type": "application/json",
}

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={api_key}"

payload = {
    "contents": [
        {
            "role": "user",
            "parts": [
                {
                    "text": "Write a short blog post about SEO. Return ONLY valid JSON with keys: title, excerpt, content."
                }
            ]
        }
    ],
    "systemInstruction": {
        "parts": [
            {
                "text": "You are a helpful content writing assistant. Always return valid JSON."
            }
        ]
    },
    "generationConfig": {
        "responseMimeType": "application/json",
        "temperature": 0.2
    }
}

try:
    resp = httpx.post(url, headers=headers, json=payload, timeout=30)
    print(f"Status: {resp.status_code}")
    print(resp.json())
except Exception as e:
    print(f"Error testing Gemini: {e}")
