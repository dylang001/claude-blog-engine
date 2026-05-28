import sqlite3
import asyncio
import json
from content_machine.config import load_settings
from content_machine.pipeline import ContentMachine

async def main():
    settings = load_settings()
    machine = ContentMachine(settings)
    
    candidates = await machine.collector.collect()
    from content_machine.scoring import choose_opportunity
    opportunity = choose_opportunity(candidates, machine.store.seen_keywords())
    
    # We want a spoke run, so let's simulate that both parent pillars have been published
    # in SQLite by updating them.
    conn = sqlite3.connect(".content-machine/content_machine.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE content_plan
        SET status = 'published', wordpress_url = 'https://blog.meetlyra.app/what-is-an-ai-marketing-agent/'
        WHERE keyword = 'ai marketing agent'
        """
    )
    cursor.execute(
        """
        UPDATE content_plan
        SET status = 'published', wordpress_url = 'https://blog.meetlyra.app/seo-keyword-research/'
        WHERE keyword = 'seo keyword research'
        """
    )
    conn.commit()
    conn.close()
    
    # Re-collect opportunity to make sure we pick the planned spoke 'ai content automation'
    candidates = await machine.collector.collect()
    opportunity = choose_opportunity(candidates, machine.store.seen_keywords())
    
    print(f"Selected: {opportunity.keyword}")
    research = await machine.researcher.brief(opportunity)
    research = await machine._enrich_research_with_internal_links(research)
    
    # Manually retrieve parent pillar URL from DB and inject it
    plan_items = machine.store.get_content_plan()
    parent_pillar_kw = opportunity.metadata.get("parent_pillar")
    anchor_text = opportunity.metadata.get("anchor_text")
    parent_pillar_url = None
    for item in plan_items:
        if item["keyword"].lower().strip() == parent_pillar_kw.lower().strip():
            if item.get("wordpress_url"):
                parent_pillar_url = item["wordpress_url"]
            break
    if parent_pillar_url:
        research["target_internal_link"] = {
            "url": parent_pillar_url,
            "anchor_text": anchor_text,
            "keyword": parent_pillar_kw
        }
        
    print(f"Target link injected: {research.get('target_internal_link')}")
    
    # Restore DB back to planned
    conn = sqlite3.connect(".content-machine/content_machine.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE content_plan
        SET status = 'planned', wordpress_url = NULL
        WHERE keyword = 'ai marketing agent'
        """
    )
    cursor.execute(
        """
        UPDATE content_plan
        SET status = 'planned', wordpress_url = NULL
        WHERE keyword = 'seo keyword research'
        """
    )
    conn.commit()
    conn.close()

    print("Generating content...")
    content = await machine.writer.generate(opportunity, research)
    
    # Write files
    with open("scratch/generated_raw_markdown.txt", "w", encoding="utf-8") as f:
        f.write(content.markdown)
    with open("scratch/generated_raw_html.txt", "w", encoding="utf-8") as f:
        f.write(content.html)
    
    print("Files written to scratch/generated_raw_markdown.txt and scratch/generated_raw_html.txt")

if __name__ == "__main__":
    asyncio.run(main())
