import asyncio
from content_machine.config import load_settings
from content_machine.data_sources import DataForSEOClient

async def main():
    settings = load_settings()
    client = DataForSEOClient(settings)
    try:
        res = await client.serp("best ai content automation", limit=5)
        print("Success! Response keys:", res.keys())
        # Print first item structure
        for task in res.get("tasks", []):
            for result in task.get("result") or []:
                items = result.get("items") or []
                print(f"Found {len(items)} items in SERP.")
                for i, item in enumerate(items[:3]):
                    print(f"Item {i}: Type: {item.get('type')}, URL: {item.get('url')}")
    except Exception as e:
        print("Error calling DataForSEO:", e)

if __name__ == "__main__":
    asyncio.run(main())
