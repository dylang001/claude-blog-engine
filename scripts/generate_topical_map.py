import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

from content_machine.config import load_settings
from content_machine.state import StateStore
from content_machine.planner import ClusterPlanner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("generate_topical_map")

async def main():
    logger.info("Loading settings...")
    settings = load_settings()
    
    logger.info("Initializing State Store...")
    store = StateStore(settings.state_db, settings=settings)
    
    # 1. Back up existing published posts
    logger.info("Backing up published posts from database...")
    all_current_items = store.get_content_plan()
    published_items = [item for item in all_current_items if item.get("status") == "published"]
    logger.info(f"Found {len(published_items)} published items to preserve.")
    for item in published_items:
        logger.info(f" - Preserving: '{item['keyword']}' ({item['wordpress_url']})")

    # 2. Define seeds and competitor domain
    seeds = [
        "AI marketing agent",
        "autonomous marketing agent",
        "AI campaign planning",
        "AI content automation",
        "AI copywriting tool",
        "marketing automation for startups"
    ]
    competitor_domain = "copy.ai" # Focus competitor
    
    logger.info(f"Running ClusterPlanner with seeds={seeds} and competitor={competitor_domain}...")
    planner = ClusterPlanner(settings)
    
    # Generate new plan
    new_plan_items = await planner.generate_plan(seeds, competitor_domain=competitor_domain)
    logger.info(f"Planner generated {len(new_plan_items)} items.")

    # 3. Restore and merge published items in database
    logger.info("Restoring and merging published items in the database...")
    for pub_item in published_items:
        # If a keyword already exists in new plan, we update its status to 'published' and set WP details
        # Otherwise, we insert it back as is
        store.add_to_content_plan(pub_item)
        logger.info(f"Restored to DB: {pub_item['keyword']} (status={pub_item['status']})")

    # 4. Generate unified report from all content plan items in DB
    logger.info("Generating unified topical map report...")
    unified_items = store.get_content_plan()
    
    # Sort unified items to group by cluster
    clusters = {}
    for item in unified_items:
        c_name = item.get("cluster_name") or "Unclustered"
        if c_name not in clusters:
            clusters[c_name] = []
        clusters[c_name].append(item)

    md = []
    md.append("# Unified Yoast Topic Cluster & Topical Map Plan")
    md.append(f"Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
    md.append("This document outlines the structured hub-and-spoke topic cluster plan following Yoast's site structure guidelines and Ahrefs' keyword prioritization rules. Pillars must be published before their Spokes to establish the bidirectional interlinking matrix.\n")
    
    md.append("## Yoast Site Structure Principles Applied:")
    md.append("- **Pyramid Hierarchy**: Main keywords serve as Pillar articles, supporting subtopics serve as Spokes.")
    md.append("- **Bidirectional Contextual Linking**: Spoke posts must link back to their parent Pillar post with descriptive anchor text (indicated below). Pillars link out to their spokes.")
    md.append("- **Flat URL Path**: Enforces flat URL slug patterns under `/blog/` (e.g., `/blog/slug/`) with metadata categorizations instead of directory nesting.\n")

    md.append("## Ahrefs Keyword Prioritization Rules Applied:")
    md.append("- **Business Potential (BP)**: Ranked 0-3 based on product alignment (prioritizing BP 2-3).")
    md.append("- **Traffic Potential (TP)**: Scaled based on the total organic traffic potential of the cluster.")
    md.append("- **Keyword Difficulty (KD)**: Treated as resource cost rather than a filter.")
    md.append("- **Trend Indicator Penalty**: Subtracted 3.0 points from priority score if search volume trend is declining.\n")

    for c_name, members in clusters.items():
        md.append(f"## {c_name}")
        
        # Find pillars and spokes
        pillars = [m for m in members if m.get("role") == "pillar"]
        spokes = [m for m in members if m.get("role") == "spoke"]
        
        if pillars:
            pillar = pillars[0]
            md.append("### Pillar Page")
            md.append(f"- **Keyword**: `{pillar['keyword']}`")
            md.append(f"- **Target Title**: {pillar['title']}")
            md.append(f"- **Status**: `{pillar['status'].upper()}`")
            if pillar.get("wordpress_url"):
                md.append(f"- **Live URL**: {pillar['wordpress_url']}")
            md.append(f"- **Search Intent**: {pillar['intent']}")
            md.append(f"- **Volume**: {pillar['volume']} | **KD**: {pillar['kd']} | **Priority Score**: {pillar['score']}")
            md.append(f"- **Business Value (0-3)**: {pillar.get('business_value', 0)} | **Traffic Potential**: {pillar.get('traffic_potential', 0)}")
            md.append("")
        
        if spokes:
            md.append("### Supporting Spoke Pages")
            md.append("| Spoke Keyword | Target Title | Status | Score | Vol | KD | Biz Value | Traffic Potential | Parent Link Anchor | WordPress URL |")
            md.append("|---|---|---|---|---|---|---|---|---|---|")
            for spoke in spokes:
                wp_url = spoke.get("wordpress_url") or "None"
                status_str = spoke.get("status", "planned").upper()
                md.append(
                    f"| `{spoke['keyword']}` | {spoke['title']} | `{status_str}` | {spoke['score']} | {spoke['volume']} | "
                    f"{spoke['kd']} | {spoke.get('business_value', 0)} | {spoke.get('traffic_potential', 0)} | `{spoke['anchor_text']}` | {wp_url} |"
                )
            md.append("")
        md.append("---")

    report_content = "\n".join(md)
    
    # Save report locally
    local_md = Path("cluster-plan.md")
    local_md.write_text(report_content, encoding="utf-8")
    logger.info("Saved local cluster-plan.md report.")

    # Save to JSON
    local_json = Path("cluster-plan.json")
    local_json.write_text(json.dumps(unified_items, indent=2, default=str), encoding="utf-8")
    logger.info("Saved local cluster-plan.json backup.")

    # Save report to brain artifacts
    brain_path = Path("/Users/dylanangloher/.gemini/antigravity/brain/5cb25842-f1a4-4d2f-80dc-68e4801fd23e/cluster_plan.md")
    try:
        brain_path.write_text(report_content, encoding="utf-8")
        logger.info(f"Saved cluster_plan.md to brain artifact directory: {brain_path}")
    except Exception as e:
        logger.error(f"Failed to write to brain artifact: {e}")

if __name__ == "__main__":
    asyncio.run(main())
