import sqlite3
import asyncio
import re
import json
import logging
from content_machine.config import load_settings
from content_machine.pipeline import ContentMachine

logging.basicConfig(level=logging.INFO)
db_path = ".content-machine/content_machine.db"

def setup_db():
    conn = sqlite3.connect(db_path)
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
    print("Database updated: Both pillars marked as published.")

def restore_db():
    conn = sqlite3.connect(db_path)
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
    print("Database restored: Both pillars marked as planned.")

async def run_pipeline():
    settings = load_settings()
    machine = ContentMachine(settings)
    
    # Let's manually run the steps of run_once so we can inspect everything.
    candidates = await machine.collector.collect()
    from content_machine.scoring import choose_opportunity
    opportunity = choose_opportunity(candidates, machine.store.seen_keywords())
    
    print(f"Selected Opportunity: {opportunity.keyword} (Kind: {opportunity.kind.value})")
    print(f"Metadata: {opportunity.metadata}")
    
    research = await machine.researcher.brief(opportunity)
    research = await machine._enrich_research_with_internal_links(research)
    
    parent_pillar_kw = opportunity.metadata.get("parent_pillar")
    anchor_text = opportunity.metadata.get("anchor_text")
    if parent_pillar_kw and anchor_text:
        parent_pillar_url = None
        plan_items = machine.store.get_content_plan()
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
            print(f"Injected target_internal_link: {research['target_internal_link']}")
        else:
            print("WARNING: Parent pillar URL not found in plan items.")
            
    print("\n--- Phase 3: Content generation ---")
    content = await machine.writer.generate(opportunity, research)
    print("Generation successful!")
    print(f"Title: {content.title}")
    print(f"Slug: {content.slug}")
    print(f"Focus Keyphrase: {content.focus_keyphrase}")
    
    audit = machine.auditor.audit(content, opportunity, research)
    print(f"\n--- Initial Audit Report (Score: {audit.score}, Decision: {audit.decision.value}) ---")
    print(f"Issues: {audit.issues}")
    print(f"Warnings: {audit.warnings}")
    
    # Check if target internal link is in HTML
    pattern = r'href=["\']https://blog\.meetlyra\.app/what-is-an-ai-marketing-agent/?["\'][^>]*>ai marketing agent</a>'
    match = re.search(pattern, content.html, re.IGNORECASE)
    if match:
        print("\nSUCCESS: Target link found in initial generation!")
        print(f"Context: {content.html[max(0, match.start()-50):min(len(content.html), match.end()+50)]}")
    else:
        print("\nFAILURE: Target link NOT found in initial generation.")
        print("Searching for URL snippet:")
        for m in re.finditer(r'what-is-an-ai-marketing-agent', content.html, re.IGNORECASE):
            print(content.html[max(0, m.start()-50):min(len(content.html), m.end()+50)])
            
    if audit.decision != "publish":
        print("\nRunning content repair...")
        try:
            repaired = await machine.writer.repair(content, opportunity, research, audit)
            print("Repair completed successfully!")
            repaired_audit = machine.auditor.audit(repaired, opportunity, research)
            print(f"Repaired Audit Score: {repaired_audit.score}, Decision: {repaired_audit.decision.value}")
            print(f"Repaired Issues: {repaired_audit.issues}")
            match_rep = re.search(pattern, repaired.html, re.IGNORECASE)
            if match_rep:
                print("SUCCESS: Target link found in repaired content!")
            else:
                print("FAILURE: Target link NOT found in repaired content.")
        except Exception as e:
            print(f"Repair failed: {e}")
            # If it's a JSON parse error, let's see if we can get the raw response
            import traceback
            traceback.print_exc()

def main():
    setup_db()
    try:
        asyncio.run(run_pipeline())
    finally:
        restore_db()

if __name__ == "__main__":
    main()
