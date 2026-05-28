import asyncio
import logging
from content_machine.config import load_settings
from content_machine.open_seo_client import OpenSeoClient

logging.basicConfig(level=logging.INFO)

async def test():
    settings = load_settings()
    client = OpenSeoClient(settings)
    
    print("Base URL:", client.base_url)
    print("Enabled:", client._enabled)
    
    is_healthy = await client.health()
    print("Healthy:", is_healthy)
    
    if is_healthy:
        print("Fetching keyword ideas for 'AI marketing agent'...")
        ideas = await client.keyword_ideas("AI marketing agent", limit=10)
        print(f"Fetched {len(ideas)} ideas:")
        for idea in ideas[:5]:
            print(idea)
            
        print("Fetching SERP for 'AI marketing agent'...")
        serp_res = await client.serp("AI marketing agent")
        print("SERP keys:", serp_res.keys() if serp_res else "None")
        if serp_res:
            tasks = serp_res.get("tasks", [])
            if tasks:
                results = tasks[0].get("result", [])
                if results:
                    items = results[0].get("items", [])
                    print(f"Fetched {len(items)} SERP items. First 3:")
                    for item in items[:3]:
                        print(item)

if __name__ == "__main__":
    asyncio.run(test())
