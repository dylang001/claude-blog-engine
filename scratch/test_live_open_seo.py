import asyncio
from content_machine.config import load_settings
from content_machine.open_seo_client import OpenSeoClient

async def main():
    settings = load_settings()
    print(f"Loaded Settings. OPEN_SEO_URL = {settings.open_seo_url}")
    client = OpenSeoClient(settings)
    
    print("Checking health...")
    is_healthy = await client.health()
    print(f"Health check: {is_healthy}")
    
    if is_healthy:
        print("Testing keyword ideas for 'AI content marketing'...")
        ideas = await client.keyword_ideas("AI content marketing")
        print(f"Found {len(ideas)} ideas.")
        if ideas:
            print(f"First idea: {ideas[0]}")
            
        print("Testing SERP check for 'AI marketing agent'...")
        serp = await client.serp("AI marketing agent")
        print(f"SERP status: {'Success' if serp else 'Failed'}")
        if serp:
            print(f"Keys: {list(serp.keys())}")
    else:
        print("Service is not reachable!")

if __name__ == "__main__":
    asyncio.run(main())
