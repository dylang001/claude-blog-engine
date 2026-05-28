import asyncio
import json
from pathlib import Path
import httpx

from content_machine.config import load_settings
from content_machine.firecrawl import FirecrawlClient

async def generate_seo_plan():
    print("Starting the SEO Master Planner...")
    settings = load_settings()
    firecrawl = FirecrawlClient(settings)
    
    knowledge_base = ""
    
    # 1. Crawl Ahrefs
    print("\nCrawling ahrefs.com/seo (this may take 30-60 seconds)...")
    try:
        ahrefs_data = await firecrawl.crawl("https://ahrefs.com/seo", limit=20, max_depth=3)
        pages = ahrefs_data.get("data", [])
        print(f"✅ Successfully extracted {len(pages)} pages from Ahrefs!")
        for page in pages:
            markdown = page.get("markdown", "")
            knowledge_base += f"\n\n--- Source: {page.get('sourceURL', 'ahrefs')} ---\n{markdown}"
    except Exception as e:
        print(f"⚠️ Failed to crawl Ahrefs: {e}")

    # 2. Crawl SEMrush
    print("\nCrawling semrush.com/kb/ (this may take 30-60 seconds)...")
    try:
        semrush_data = await firecrawl.crawl("https://www.semrush.com/kb/", limit=20, max_depth=3)
        pages = semrush_data.get("data", [])
        print(f"✅ Successfully extracted {len(pages)} pages from SEMrush!")
        for page in pages:
            markdown = page.get("markdown", "")
            knowledge_base += f"\n\n--- Source: {page.get('sourceURL', 'semrush')} ---\n{markdown}"
    except Exception as e:
        print(f"⚠️ Failed to crawl SEMrush: {e}")
    # 3. Crawl Reddit for Growth Hacks
    print("\nCrawling Reddit (/r/SEO and /r/growthhacking) for startup growth hacks...")
    try:
        reddit_data = await firecrawl.crawl("https://www.reddit.com/r/SEO/top/?t=year", limit=10, max_depth=1)
        pages = reddit_data.get("data", [])
        print(f"✅ Successfully extracted {len(pages)} pages from Reddit!")
        for page in pages:
            markdown = page.get("markdown", "")
            knowledge_base += f"\n\n--- Source: Reddit Growth Hacks ---\n{markdown}"
    except Exception as e:
        print(f"⚠️ Failed to crawl Reddit: {e}")
        
    if len(knowledge_base.strip()) < 100:
        print("\n❌ Failed to gather enough knowledge from Firecrawl. Exiting.")
        return

    # 4. Generate Strategy via Anthropic
    print(f"\n🧠 Sending {len(knowledge_base)} characters of knowledge to Claude for strategy synthesis...")
    print("Leveraging prompt caching to process this massive document efficiently...")
    
    system_prompt = (
        "You are an elite, world-class SEO genius and Growth Hacker for startups. You have been provided with an extensive knowledge base "
        "scraped directly from Ahrefs, SEMrush, and top Reddit growth hacking threads.\n\n"
        "Your task is to synthesize this exact knowledge into a highly actionable, comprehensive 'Master SEO Plan' "
        "for the MeetLyra brand. Do not restrict yourself ONLY to this data—use your absolute best outside-the-box "
        "skills and world-class expertise to construct the ultimate growth strategy.\n\n"
        "Your Master SEO Plan MUST include:\n"
        "1. Topical Authority Maps & Pillar/Cluster Strategy.\n"
        "2. Exact Long-Tail Keyword Targeting frameworks.\n"
        "3. Intent Mapping (how to capture commercial vs informational intent).\n"
        "4. A step-by-step Backlink Strategy (including Broken Backlinks and digital PR).\n"
        "5. Programmatic SEO (pSEO) Strategies: Think outside the box and find the absolute best ways to programmatically generate massive SEO traffic.\n"
        "6. Startup Growth Hacks: Unconventional, high-ROI tactics sourced from Reddit and your own expertise.\n\n"
        "Format the output as a beautiful, highly detailed Markdown document.\n\n"
        f"<knowledge_base>\n{knowledge_base}\n</knowledge_base>"
    )

    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "anthropic-beta": "prompt-caching-2024-07-31",
                "content-type": "application/json",
            },
            json={
                "model": settings.anthropic_model,
                "max_tokens": 8000,
                "system": [
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"}
                    }
                ],
                "messages": [
                    {
                        "role": "user",
                        "content": "Generate the Master SEO Plan now using the knowledge base. Return ONLY the markdown output.",
                    }
                ],
            },
        )
        
        if resp.status_code != 200:
            print(f"❌ Anthropic API Error: {resp.text}")
            return
            
        result = resp.json()
        markdown_plan = result["content"][0]["text"]
        
        out_dir = settings.root_dir / "seo-reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "master_seo_plan.md"
        out_path.write_text(markdown_plan, encoding="utf-8")
        
        print(f"\n🎉 Master SEO Plan successfully generated and saved to: {out_path}")

if __name__ == "__main__":
    asyncio.run(generate_seo_plan())
