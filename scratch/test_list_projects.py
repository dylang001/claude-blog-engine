import asyncio
from content_machine.config import load_settings
from content_machine.open_seo_client import OpenSeoClient

async def main():
    settings = load_settings()
    client = OpenSeoClient(settings)
    
    print("Calling whoami...")
    whoami = await client._call_tool("whoami", {})
    print("whoami response:", whoami)
    
    print("\nCalling list_projects...")
    res = await client._call_tool("list_projects", {})
    print("list_projects response:", res)

if __name__ == "__main__":
    asyncio.run(main())
