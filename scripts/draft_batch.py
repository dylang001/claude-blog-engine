import asyncio
import logging
import sqlite3
import time
from datetime import datetime, timezone
from content_machine.config import load_settings
from content_machine.pipeline import ContentMachine
from content_machine.models import PublishDecision

# Set up logging to both console and a file
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(".content-machine/batch_drafting.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("batch_draft")

def mark_post_blocked(db_path: str, keyword: str):
    logger.info(f"Marking keyword '{keyword}' as blocked in database.")
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE content_plan SET status = 'blocked' WHERE LOWER(TRIM(keyword)) = LOWER(TRIM(?))",
                (keyword,)
            )
            conn.commit()
    except Exception as exc:
        logger.error(f"Failed to update database status for '{keyword}': {exc}")

async def main():
    logger.info("Starting batch drafting script...")
    settings = load_settings()
    machine = ContentMachine(settings)
    
    db_path = str(settings.state_db)
    
    success_count = 0
    blocked_count = 0
    error_count = 0
    max_articles = 24  # Process up to all remaining articles
    
    for i in range(max_articles):
        # 1. Fetch next planned post to see what keyword we are about to target
        planned = machine.store.get_next_planned_post()
        if not planned:
            logger.info("No more planned posts in the database content plan. Batch drafting complete!")
            break
            
        keyword = planned["keyword"]
        role = planned["role"]
        logger.info(f"\n==================================================")
        logger.info(f"Processing Article {i+1}/{max_articles}: '{keyword}' ({role})")
        logger.info(f"==================================================")
        
        start_time = time.time()
        try:
            # 2. Run the pipeline for the next post
            result = await machine.run_once(dry_run=False)
            duration = time.time() - start_time
            
            logger.info(f"Completed '{result.opportunity.keyword}' in {duration:.1f}s")
            logger.info(f"WP Status: {result.wordpress_status}")
            logger.info(f"WP URL: {result.wordpress_url}")
            logger.info(f"Audit Score: {result.audit.score:.1f}")
            logger.info(f"Audit Decision: {result.audit.decision.value}")
            
            if result.wordpress_status == "blocked" or result.audit.decision == PublishDecision.BLOCK:
                logger.warning(f"Article for '{keyword}' was BLOCKED by the audit engine.")
                mark_post_blocked(db_path, keyword)
                blocked_count += 1
            else:
                success_count += 1
                
        except Exception as exc:
            logger.exception(f"Unhandled exception generating article for '{keyword}': {exc}")
            mark_post_blocked(db_path, keyword)
            error_count += 1
            
        # Cooldown sleep to respect Gemini and WordPress rate limits
        cooldown = 15
        logger.info(f"Sleeping for {cooldown} seconds before starting next article...")
        await asyncio.sleep(cooldown)

    logger.info(f"\n=== Batch Run Summary ===")
    logger.info(f"Successfully processed: {success_count}")
    logger.info(f"Blocked by audit: {blocked_count}")
    logger.info(f"Errors/Exceptions: {error_count}")
    logger.info("=========================")

if __name__ == "__main__":
    asyncio.run(main())
