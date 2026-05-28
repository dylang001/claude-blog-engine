import asyncio
from content_machine.config import load_settings
from content_machine.keyword_research_google_ads_api import _classify_batch_with_gemini

async def main():
    settings = load_settings()
    batch = [
        {
            "keyword": "ai marketing agent",
            "avg_monthly_searches": 1500,
            "competition": "MEDIUM",
            "low_top_of_page_bid": 1.5,
            "high_top_of_page_bid": 4.5
        }
    ]
    try:
        res = await _classify_batch_with_gemini(settings, batch)
        print("Success:", res)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
