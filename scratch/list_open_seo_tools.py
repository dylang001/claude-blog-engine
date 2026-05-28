import asyncio
import httpx
from content_machine.config import load_settings

async def list_tools():
    settings = load_settings()
    url = f"{settings.open_seo_url.rstrip('/')}/mcp"
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "params": {},
        "id": 1
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload, headers=headers)
        print("Status code:", resp.status_code)
        res = resp.json()
        print("Result tools:")
        for tool in res.get("result", {}).get("tools", []):
            print(f"- {tool['name']}: {tool.get('description', '')}")

if __name__ == "__main__":
    asyncio.run(list_tools())
