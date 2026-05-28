import asyncio
import logging
from content_machine.config import load_settings
from content_machine.backlinks import BacklinkClient

logging.basicConfig(level=logging.INFO)

async def main():
    settings = load_settings()
    client = BacklinkClient(settings)
    
    print("Testing backlinks retrieval...")
    res = await client.get_summary("meetlyra.app")
    print("Backlinks summary result:", res)

if __name__ == "__main__":
    asyncio.run(main())
