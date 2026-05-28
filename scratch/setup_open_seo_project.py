import asyncio
import logging
from content_machine.config import load_settings
from content_machine.open_seo_client import OpenSeoClient

logging.basicConfig(level=logging.INFO)

async def test():
    settings = load_settings()
    client = OpenSeoClient(settings)
    
    print("Listing projects...")
    res = await client._call_tool("list_projects", {})
    print("list_projects response:", res)
    
    projects = res.get("structuredContent", {}).get("projects", [])
    if not projects:
        print("No projects found. Creating a project...")
        # create_project arguments: name (string)
        create_res = await client._call_tool("create_project", {"name": "MeetLyra SEO"})
        print("create_project response:", create_res)
        
        # list again
        res2 = await client._call_tool("list_projects", {})
        print("New list_projects response:", res2)
    else:
        print(f"Found project: {projects[0]}")

if __name__ == "__main__":
    asyncio.run(test())
