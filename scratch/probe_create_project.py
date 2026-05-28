import asyncio
import httpx
from content_machine.config import load_settings

async def try_create():
    settings = load_settings()
    base_url = settings.open_seo_url.rstrip("/")
    
    endpoints = [
        ("/projects", {"name": "MeetLyra SEO"}),
        ("/api/projects", {"name": "MeetLyra SEO"}),
        ("/api/project", {"name": "MeetLyra"}),
        ("/project", {"name": "MeetLyra"}),
    ]
    
    async with httpx.AsyncClient(timeout=10) as client:
        for path, payload in endpoints:
            url = f"{base_url}{path}"
            try:
                # Try JSON POST
                resp = await client.post(url, json=payload)
                print(f"POST {path} JSON: {resp.status_code}")
                if resp.status_code < 400:
                    print(resp.json())
                    break
            except Exception as e:
                print(f"POST {path} failed: {e}")
                
            try:
                # Try Form POST
                resp = await client.post(url, data=payload)
                print(f"POST {path} Form: {resp.status_code}")
                if resp.status_code < 400:
                    print(resp.json())
                    break
            except Exception as e:
                print(f"POST {path} Form failed: {e}")

if __name__ == "__main__":
    asyncio.run(try_create())
