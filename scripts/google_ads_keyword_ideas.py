#!/usr/bin/env python
import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from content_machine.config import load_settings
from content_machine.keyword_research_google_ads_api import (
    fetch_keywords_raw,
    save_raw_keywords_to_csv
)

DEFAULT_SEEDS = [
    "AI marketing agent",
    "autonomous marketing agent",
    "AI agent for marketing",
    "AI marketing automation",
    "AI campaign generator",
    "AI content automation",
    "AI marketing strategy generator",
    "AI marketing assistant",
    "AI tools for startups",
    "marketing automation for startups",
    "Jasper alternative",
    "Copy.ai alternative",
    "ChatGPT for marketing",
    "AI content planner",
    "AI go to market strategy"
]

async def main():
    print("--- Google Ads Keyword Planning CLI Test ---")
    settings = load_settings()
    
    # Check if seeds are passed in arguments, otherwise use default list
    seeds = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_SEEDS
    print(f"Loading {len(seeds)} seed keywords: {seeds}")
    
    # Save target path
    output_path = Path("data/seo/keyword_research/google_ads_raw.csv")
    
    print("\nQuerying Keyword Ideas...")
    raw_keywords = await fetch_keywords_raw(
        settings=settings,
        seeds=seeds,
        location="United States",
        language="English"
    )
    
    print(f"Retrieved {len(raw_keywords)} raw keyword combinations.")
    
    print(f"Saving raw data to {output_path}...")
    save_raw_keywords_to_csv(output_path, raw_keywords)
    
    print("\n--- Top 10 Keywords ---")
    for i, kw in enumerate(raw_keywords[:10]):
        print(
            f"{i+1}. {kw['keyword']} | Search Volume: {kw['avg_monthly_searches']} | "
            f"Competition: {kw['competition']} | Bid: ${kw['low_top_of_page_bid']:.2f} - ${kw['high_top_of_page_bid']:.2f}"
        )
    
    print("\nPhase 1 execution complete! CSV successfully exported.")

if __name__ == "__main__":
    asyncio.run(main())
