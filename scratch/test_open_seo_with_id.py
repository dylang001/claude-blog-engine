import asyncio
import logging
from content_machine.config import load_settings
from content_machine.open_seo_client import OpenSeoClient

logging.basicConfig(level=logging.INFO)

async def test():
    settings = load_settings()
    client = OpenSeoClient(settings)
    
    # Manually set project ID
    client._project_id = "7ae57b28-d4dc-4ec7-90e1-8b8c21e6ea8f"
    
    print("Testing health...")
    print("Health:", await client.health())
    
    print("Testing keyword ideas for 'AI marketing agent'...")
    ideas = await client.keyword_ideas("AI marketing agent", limit=20)
    print(f"Fetched {len(ideas)} ideas:")
    for idea in ideas[:10]:
        print(idea)

if __name__ == "__main__":
    asyncio.run(test())
