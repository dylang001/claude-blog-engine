import asyncio
import httpx
from content_machine.config import load_settings

async def fetch_home():
    settings = load_settings()
    url = settings.open_seo_url.rstrip("/")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{url}/")
        print("Status:", resp.status_code)
        print("Body (first 500 chars):")
        print(resp.text[:500])

if __name__ == "__main__":
    asyncio.run(fetch_home())
