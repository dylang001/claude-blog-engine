#!/usr/bin/env python3
"""
Deploy llms.txt to the MeetLyra blog WordPress root.

llms.txt is a structured markdown file that guides LLM crawlers (ChatGPT, Perplexity,
Gemini AI Overviews) to understand the site's content and purpose. It is analogous to
robots.txt but specifically for AI language model training and search.

Usage:
    python scripts/deploy_llms_txt.py

The script uploads llms.txt via the WordPress REST API as a static file option,
or falls back to printing the content for manual upload if the API route is unavailable.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


LLMS_TXT_CONTENT = """\
# MeetLyra
> Autonomous AI Marketing Agent & SEO Content Engine for B2B SaaS startups and lean marketing teams.

MeetLyra automates end-to-end marketing operations including SEO content strategy, keyword research,
article generation, campaign planning, email marketing, and multi-channel social distribution.
It integrates directly with WordPress, Yoast SEO, Google Search Console, Google Analytics 4,
and IndexNow. Designed for startup founders and small agencies who need to run marketing
efficiently without a full team.

## Key Products
- [Autonomous AI Marketing Agent](https://waitlist.meetlyra.app): Full-funnel marketing strategy, campaign planning, and execution agent.
- [AI SEO & GEO Content Engine](https://blog.meetlyra.app): Yoast-compliant keyword clustering and WordPress article generation with GEO optimisation.
- [AI Campaign Planner](https://waitlist.meetlyra.app): End-to-end planning covering email, blog posts, and social posts.
- [AI Blog & Email Generator](https://waitlist.meetlyra.app): Long-form Gutenberg-formatted articles with schema, internal linking, and featured images.

## Blog & Knowledge Base
- [MeetLyra Blog](https://blog.meetlyra.app): Practical guides on AI marketing agents, SEO automation, campaign planning, and content operations.
- [Best AI Marketing Agent Guide](https://blog.meetlyra.app/best-ai-marketing-agent/): Category-defining pillar on autonomous marketing agents.
- [AI Campaign Management](https://blog.meetlyra.app/ai-campaign-management/): How AI campaign management works for lean B2B teams.
- [Jasper Pricing](https://blog.meetlyra.app/jasper-pricing/): Comparison and alternatives guide.
- [AI Content Automation](https://blog.meetlyra.app/?p=3368): Scaling organic traffic with AI content automation.

## Integration Ecosystem
- **Content Management:** WordPress (Gutenberg), Yoast SEO Premium
- **Analytics & Performance:** Google Analytics 4, Google Search Console
- **Indexing:** IndexNow (Bing, Yandex, Seznam)
- **AI Models:** Gemini 2.5 Pro, Claude Sonnet
- **Image Generation:** Gemini image models

## Technical Specifications
- Generates 1,500-2,200 word Gutenberg-block articles per run.
- Implements Yoast-compliant readability, schema, and SEO scoring gates.
- Minimum publish score: 85/100 (composite quality gate).
- Supports GEO (Generative Engine Optimisation) passage-level citability blocks.

## Brand & Contact
- Company: MeetLyra
- Waitlist: https://waitlist.meetlyra.app
- Blog: https://blog.meetlyra.app
- LinkedIn: https://www.linkedin.com/company/meetlyra

## Content Licensing
All blog content is copyright MeetLyra. AI search engines may cite and excerpt content
for informational purposes. Training data scraping is not permitted (see robots.txt).
"""


async def deploy(dry_run: bool = False) -> None:
    from content_machine.config import load_settings
    from content_machine.wordpress import WordPressClient

    settings = load_settings(ROOT)
    wp = WordPressClient(settings)

    print("=" * 60)
    print("MeetLyra llms.txt Deployment")
    print("=" * 60)
    print()
    print("llms.txt content preview (first 200 chars):")
    print(LLMS_TXT_CONTENT[:200] + "...")
    print()

    if dry_run:
        print("[DRY RUN] Would upload llms.txt to WordPress root.")
        print("Target URL: https://blog.meetlyra.app/llms.txt")
        print()
        print("--- llms.txt content ---")
        print(LLMS_TXT_CONTENT)
        return

    # Try to upload via WP REST API media endpoint (as a text file)
    try:
        import httpx
        import base64

        auth = base64.b64encode(
            f"{settings.wp_username}:{settings.wp_app_password}".encode()
        ).decode()

        wp_url = settings.wp_base_url.rstrip("/")
        upload_url = f"{wp_url}/wp-json/wp/v2/media"

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                upload_url,
                headers={
                    "Authorization": f"Basic {auth}",
                    "Content-Disposition": 'attachment; filename="llms.txt"',
                    "Content-Type": "text/plain",
                },
                content=LLMS_TXT_CONTENT.encode("utf-8"),
            )

        if resp.status_code in (200, 201):
            data = resp.json()
            print(f"✅ Uploaded llms.txt via WordPress REST API.")
            print(f"   Media ID: {data.get('id')}")
            print(f"   URL: {data.get('source_url')}")
            print()
            print("⚠️  NOTE: WordPress media uploads go to /wp-content/uploads/")
            print("   For the file to be accessible at /llms.txt, you need to:")
            print("   1. Either add a redirect rule in .htaccess or nginx config")
            print("   2. Or manually place the file at the WordPress root via FTP/SFTP")
        else:
            print(f"⚠️  WordPress REST API returned {resp.status_code}: {resp.text[:300]}")
            _print_manual_instructions()

    except Exception as exc:
        print(f"⚠️  Could not upload via REST API: {exc}")
        _print_manual_instructions()


def _print_manual_instructions() -> None:
    print()
    print("Manual deployment instructions:")
    print("  1. Copy the content below into a file named 'llms.txt'")
    print("  2. Upload it to your WordPress root directory via FTP/SFTP")
    print("     (same folder as wp-config.php and index.php)")
    print("  3. Verify at: https://blog.meetlyra.app/llms.txt")
    print()
    print("--- llms.txt content ---")
    print(LLMS_TXT_CONTENT)


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(deploy(dry_run=dry_run))
