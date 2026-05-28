import sqlite3
import asyncio
import re
from content_machine.config import load_settings
from content_machine.pipeline import ContentMachine

db_path = ".content-machine/content_machine.db"

def setup_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Mark parent pillars as published with a specific URL
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
    # Restore parent pillars to planned
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
    print("Running ContentMachine pipeline...")
    result = await machine.run_once(dry_run=True)
    return result

def main():
    setup_db()
    try:
        result = asyncio.run(run_pipeline())
        print("=" * 60)
        print(f"RUN ID: {result.run_id}")
        print(f"OPPORTUNITY KEYWORD: {result.opportunity.keyword}")
        print(f"DECISION: {result.audit.decision.value}")
        print(f"SCORE: {result.audit.score}")
        print("=" * 60)
        
        markdown = result.content.markdown
        html = result.content.html
        
        # Look for the parent link in the markdown or HTML
        # Target link: <a href="https://blog.meetlyra.app/what-is-an-ai-marketing-agent/">ai marketing agent</a>
        pattern = r'href=["\']https://blog\.meetlyra\.app/what-is-an-ai-marketing-agent/?["\'][^>]*>ai marketing agent</a>'
        match = re.search(pattern, html, re.IGNORECASE)
        
        print("VERIFICATION RESULTS:")
        if match:
            print("SUCCESS: Found parent pillar link injection in the generated HTML!")
            print(f"Match context: {html[max(0, match.start()-100):min(len(html), match.end()+100)]}")
        else:
            print("FAILURE: Parent pillar link was NOT found in the generated HTML.")
            # Print search terms in html
            print("Searching for URLs containing 'what-is-an-ai-marketing-agent' in HTML:")
            for m in re.finditer(r'what-is-an-ai-marketing-agent', html, re.IGNORECASE):
                print(html[max(0, m.start()-50):min(len(html), m.end()+50)])
                
        # Also print first few lines of markdown/html
        print("=" * 60)
        print("HTML Snippet:")
        print(html[:500])
        print("=" * 60)
        
    finally:
        restore_db()

if __name__ == "__main__":
    main()
