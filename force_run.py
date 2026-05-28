import asyncio
from content_machine.config import load_settings
from content_machine.pipeline import ContentMachine

async def main():
    print("Starting manual pipeline run...")
    settings = load_settings()
    machine = ContentMachine(settings)
    result = await machine.run_once(dry_run=False)
    print(f"Finished! Opportunity: {result.opportunity.keyword}")
    print(f"Status: {result.wordpress_status}")
    print(f"URL: {result.wordpress_url}")
    print(f"Audit Decision: {result.audit.decision.value}")

if __name__ == "__main__":
    asyncio.run(main())
