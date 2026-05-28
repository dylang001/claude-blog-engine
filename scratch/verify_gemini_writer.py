import asyncio
from content_machine.config import load_settings
from content_machine.models import Opportunity, WorkItemType
from content_machine.anthropic_writer import ContentWriter

async def main():
    # Load settings from .env
    settings = load_settings()
    print(f"Loaded Settings. Writer Provider: {settings.writer_provider}")
    print(f"Gemini Model: {settings.gemini_model}")
    print(f"Gemini API Key: {bool(settings.gemini_api_key)}")

    writer = ContentWriter(settings)
    opp = Opportunity(
        kind=WorkItemType.NEW_ARTICLE,
        keyword="SEO tips for SaaS startup",
        title="10 SEO Tips for SaaS Startups to Grow Traffic",
        score=9.5,
    )
    research = {
        "competitor_headlines": ["SaaS SEO Guide", "How to grow SaaS traffic"],
        "questions": ["How do I start SEO for SaaS?", "What are key SaaS SEO strategies?"],
        "keyphrases": ["saas seo", "saas startups seo", "seo tips for saas"],
        "internal_links": [
            {"anchor": "SaaS SEO guides", "url": "https://blog.meetlyra.app/saas-seo-guide"}
        ],
        "authority_links": [
            {"anchor": "Moz Guide to SEO", "url": "https://moz.com/beginners-guide-to-seo"}
        ]
    }

    print("\n--- Generating Content (this might take a minute) ---")
    try:
        content = await writer.generate(opp, research)
        print("\n--- Generation Successful! ---")
        print(f"Title: {content.title}")
        print(f"Slug: {content.slug}")
        print(f"Meta Description: {content.meta_description}")
        print(f"Focus Keyphrase: {content.focus_keyphrase}")
        print(f"Excerpt: {content.excerpt}")
        print(f"Tags: {content.tags}")
        print(f"Categories: {content.categories}")
        print(f"HTML word count: {len(content.html.split())}")
        print(f"First 300 chars of HTML:\n{content.html[:300]}")
    except Exception as e:
        print(f"\n--- Generation Failed: {e} ---")

if __name__ == "__main__":
    asyncio.run(main())
