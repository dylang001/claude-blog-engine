import asyncio
import httpx
from content_machine.config import load_settings

async def main():
    settings = load_settings()
    api_key = getattr(settings, "tavily_api_key", "") or "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"
    print("Tavily API key:", api_key)
    
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": "best ai content automation",
        "search_depth": "basic"
    }
    
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload)
        print("Status code:", resp.status_code)
        if resp.status_code == 200:
            res = resp.json()
            print("Results:")
            for r in res.get("results", []):
                print(f"- Title: {r.get('title')} | URL: {r.get('url')}")
        else:
            print("Error response:", resp.text)

if __name__ == "__main__":
    asyncio.run(main())
