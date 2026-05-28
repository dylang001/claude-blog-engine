import asyncio
import logging
from content_machine.config import load_settings
from content_machine.open_seo_client import OpenSeoClient

logging.basicConfig(level=logging.INFO)

async def test():
    settings = load_settings()
    client = OpenSeoClient(settings)
    
    print("Calling whoami...")
    res = await client._call_tool("whoami", {})
    print("whoami response:", res)

if __name__ == "__main__":
    asyncio.run(test())
