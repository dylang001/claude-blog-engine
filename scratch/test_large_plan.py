import asyncio
import logging
from pathlib import Path
from content_machine.config import load_settings
from content_machine.planner import ClusterPlanner
from content_machine.state import StateStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_large_plan")

async def main():
    settings = load_settings()
    store = StateStore(settings.state_db, settings=settings)
    
    # Let's read the current published posts so we can merge them
    all_current_items = store.get_content_plan()
    published_items = [item for item in all_current_items if item.get("status") == "published"]
    print(f"Published items to preserve: {len(published_items)}")
    
    seeds = [
        "AI marketing agent",
        "autonomous marketing agent",
        "AI campaign planning",
        "AI content automation",
        "AI copywriting tool",
        "marketing automation for startups"
    ]
    competitor_domain = "copy.ai"
    
    # Temporarily monkeypatch planner plan_candidates limit if it is hardcoded to 20
    import content_machine.planner
    # Let's inspect where it takes 20. We will change it or we can modify content_machine/planner.py directly.
    # Let's first run it as is to see what it generates.
    planner = ClusterPlanner(settings)
    
    # We will temporarily modify planner.py to use 60 instead of 20
    # but let's first check what happens if we change it.
    
if __name__ == "__main__":
    asyncio.run(main())
