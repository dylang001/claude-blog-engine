import asyncio
from content_machine.config import load_settings
from content_machine.open_seo_client import OpenSeoClient

async def main():
    settings = load_settings()
    client = OpenSeoClient(settings)
    print("OpenSEO URL:", client.base_url)
    is_healthy = await client.health()
    print("OpenSEO health check:", is_healthy)
    try:
        pid = await client._get_project_id()
        print("Project ID:", pid)
        res = await client._call_tool("create_project", {"name": "Default"})
        print("Create project response:", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
