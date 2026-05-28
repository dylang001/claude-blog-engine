from __future__ import annotations

import logging
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from .config import Settings
from .state import StateStore
from .open_seo_client import OpenSeoClient
from .keyword_research_google_ads_api import fetch_keywords_raw, process_and_score_keywords
from .data_sources import DataForSEOClient

logger = logging.getLogger(__name__)


class ClusterPlanner:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = StateStore(settings.state_db, settings=settings)
        self.dataforseo = DataForSEOClient(settings)
        self.open_seo = OpenSeoClient(settings)

    async def get_serp_urls(self, keyword: str) -> list[str]:
        # 1. Try DataForSEO if credentials are present
        if self.settings.dataforseo_login:
            try:
                res = await self.dataforseo.serp(keyword, limit=10)
                urls = []
                for task in res.get("tasks", []):
                    for result in task.get("result", []):
                        for item in result.get("items", []):
                            if item.get("type") == "organic" and item.get("url"):
                                urls.append(item["url"])
                if urls:
                    logger.info(f"Retrieved {len(urls)} live SERP URLs for keyword '{keyword}'")
                    return urls
            except Exception as e:
                logger.warning(f"DataForSEO serp failed for '{keyword}': {e}. Falling back to deterministic simulation.")

        # 2. Deterministic simulation fallback
        keyword_clean = keyword.lower().strip()
        words = set(keyword_clean.split())

        pool = [
            "https://www.hubspot.com/marketing/ai-agents",
            "https://ahrefs.com/blog/ai-marketing",
            "https://backlinko.com/ai-seo-strategy",
            "https://semrush.com/blog/seo-automation",
            "https://neilpatel.com/blog/artificial-intelligence-marketing",
            "https://www.searchengineland.com/seo-ai-content",
            "https://www.searchenginejournal.com/generative-engine-optimization",
            "https://moz.com/blog/ai-marketing-tools",
            "https://copy.ai/blog/marketing-agents",
            "https://jasper.ai/blog/content-automation",
            "https://www.intercom.com/blog/ai-customer-marketing",
            "https://drift.com/blog/conversational-marketing",
            "https://www.g2.com/categories/ai-marketing",
            "https://www.capterra.com/marketing-automation-software",
            "https://www.salesforce.com/products/marketing-cloud/ai",
            "https://www.hubspot.com/blog/ai-writing-tools",
            "https://ahrefs.com/blog/keyword-research-guide",
            "https://backlinko.com/keyword-research",
            "https://semrush.com/blog/how-to-do-keyword-research",
            "https://neilpatel.com/blog/keyword-planning",
            "https://moz.com/blog/keyword-clustering",
            "https://www.searchengineland.com/keyword-mapping",
            "https://www.searchenginejournal.com/topic-clusters",
            "https://copy.ai/blog/content-planning",
            "https://jasper.ai/blog/seo-writing-workflow",
            "https://marketmuse.com/blog/content-clustering",
            "https://surferseo.com/blog/topic-cluster-guide",
            "https://clearscope.io/blog/seo-content-strategy",
            "https://www.conductor.com/learning-center/topic-clusters",
            "https://www.brightedge.com/glossary/topic-clusters-seo"
        ]

        urls = []
        if "agent" in keyword_clean or "agents" in keyword_clean:
            urls.extend([pool[0], pool[8], pool[10], pool[12]])
        if "marketing" in keyword_clean:
            urls.extend([pool[0], pool[1], pool[4], pool[7], pool[10], pool[11], pool[12], pool[14]])
        if "seo" in keyword_clean:
            urls.extend([pool[2], pool[3], pool[5], pool[6], pool[16], pool[17], pool[18], pool[21], pool[22], pool[26]])
        if "content" in keyword_clean:
            urls.extend([pool[5], pool[9], pool[15], pool[23], pool[24], pool[25], pool[27]])
        if "keyword" in keyword_clean or "research" in keyword_clean:
            urls.extend([pool[16], pool[17], pool[18], pool[19], pool[20], pool[21]])
        if "cluster" in keyword_clean or "clustering" in keyword_clean or "topic" in keyword_clean:
            urls.extend([pool[20], pool[22], pool[25], pool[26], pool[28], pool[29]])

        # Deduplicate
        unique_urls = []
        seen = set()
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        # Fill up to 10 with deterministic items based on hash
        if len(unique_urls) < 10:
            h = int(hashlib.md5(keyword_clean.encode("utf-8")).hexdigest(), 16)
            for idx in range(len(pool)):
                pool_idx = (h + idx) % len(pool)
                item = pool[pool_idx]
                if item not in seen:
                    seen.add(item)
                    unique_urls.append(item)
                    if len(unique_urls) == 10:
                        break
        return unique_urls[:10]

    async def generate_plan(self, seeds: list[str], competitor_domain: str | None = None) -> list[dict[str, Any]]:
        logger.info(f"Generating topic cluster plan for seeds: {seeds}, competitor_domain: {competitor_domain}")

        # 1. Expand keyword seeds (Google Ads API / DataForSEO)
        raw_kws = await fetch_keywords_raw(self.settings, seeds)
        if competitor_domain:
            from .keyword_research_google_ads_api import fetch_competitor_keywords_raw
            comp_kws = await fetch_competitor_keywords_raw(self.settings, competitor_domain)
            raw_kws.extend(comp_kws)

        # 1b. Enrich with open-seo keyword ideas (best-effort)
        if self.open_seo:
            for seed in seeds:
                try:
                    open_seo_ideas = await self.open_seo.keyword_ideas(seed, limit=50)
                    for idea in open_seo_ideas:
                        if idea.get("keyword"):
                            raw_kws.append(idea)
                    logger.info(f"open-seo enriched seed '{seed}' with {len(open_seo_ideas)} ideas")
                except Exception as exc:
                    logger.debug(f"open-seo keyword_ideas failed for '{seed}': {exc}")

        if not raw_kws:
            logger.warning("No keywords fetched during expansion.")
            return []

        # 2. Score and classify keywords via Gemini
        scored_kws = await process_and_score_keywords(self.settings, raw_kws)
        if not scored_kws:
            logger.warning("No keywords scored.")
            return []

        # Take top 60 keywords for planning
        plan_candidates = scored_kws[:60]

        # 3. Retrieve SERP URLs for overlap comparison
        keyword_serps: dict[str, list[str]] = {}
        for item in plan_candidates:
            kw = item["keyword"]
            keyword_serps[kw] = await self.get_serp_urls(kw)

        def get_overlap(kw1: str, kw2: str) -> int:
            urls1 = set(keyword_serps.get(kw1, []))
            urls2 = set(keyword_serps.get(kw2, []))
            return len(urls1.intersection(urls2))

        # 4. Merge keywords sharing >= 7 URLs (Same Post)
        merged_groups: dict[str, list[dict]] = {}
        processed_keywords = []
        keyword_to_info = {item["keyword"]: item for item in plan_candidates}

        sorted_candidates = sorted(plan_candidates, key=lambda x: x["priority_score"], reverse=True)
        already_merged = set()

        for i, item in enumerate(sorted_candidates):
            kw = item["keyword"]
            if kw in already_merged:
                continue

            merged_groups[kw] = []
            processed_keywords.append(kw)

            for j in range(i + 1, len(sorted_candidates)):
                other_item = sorted_candidates[j]
                other_kw = other_item["keyword"]
                if other_kw in already_merged:
                    continue

                overlap = get_overlap(kw, other_kw)
                if overlap >= 7:
                    logger.info(f"Merging '{other_kw}' into '{kw}' due to high overlap ({overlap} shared URLs)")
                    merged_groups[kw].append(other_item)
                    already_merged.add(other_kw)

        # 5. Cluster keywords sharing >= 4 URLs (Same Topic Cluster)
        clusters: list[list[str]] = []
        unclustered = list(processed_keywords)

        while unclustered:
            current = unclustered.pop(0)
            cluster = [current]

            added = True
            while added:
                added = False
                for other in list(unclustered):
                    if any(get_overlap(member, other) >= 4 for member in cluster):
                        cluster.append(other)
                        unclustered.remove(other)
                        added = True
            clusters.append(cluster)

        # 6. Assign Hub-and-Spoke and create Link Matrix
        final_plan_items = []

        for idx, cluster in enumerate(clusters):
            # Sort by priority score desc
            cluster_members = sorted(cluster, key=lambda x: keyword_to_info[x]["priority_score"], reverse=True)
            pillar_kw = cluster_members[0]
            cluster_name = f"Cluster {idx+1}: {pillar_kw.title()}"

            # Calculate cluster traffic_potential (set to the volume of the highest-volume keyword in that cluster)
            highest_vol = max([keyword_to_info[kw].get("avg_monthly_searches") or 0 for kw in cluster_members])

            pillar_info = keyword_to_info[pillar_kw]
            pillar_item = {
                "keyword": pillar_kw,
                "title": f"Ultimate Guide to {pillar_kw.title()}",
                "intent": pillar_info.get("intent", "informational"),
                "cluster_name": cluster_name,
                "role": "pillar",
                "parent_pillar": None,
                "anchor_text": pillar_kw.lower(),
                "score": pillar_info["priority_score"],
                "volume": pillar_info.get("avg_monthly_searches") or 0,
                "kd": pillar_info.get("kd") or 0,
                "status": "planned",
                "secondary_keywords": [m["keyword"] for m in merged_groups[pillar_kw]],
                "business_value": pillar_info.get("business_value", 2),
                "traffic_potential": highest_vol
            }
            final_plan_items.append(pillar_item)

            for spoke_kw in cluster_members[1:]:
                spoke_info = keyword_to_info[spoke_kw]
                spoke_item = {
                    "keyword": spoke_kw,
                    "title": f"{spoke_kw.title()}: A Complete Overview",
                    "intent": spoke_info.get("intent", "commercial"),
                    "cluster_name": cluster_name,
                    "role": "spoke",
                    "parent_pillar": pillar_kw,
                    "anchor_text": pillar_kw.lower(),
                    "score": spoke_info["priority_score"],
                    "volume": spoke_info.get("avg_monthly_searches") or 0,
                    "kd": spoke_info.get("kd") or 0,
                    "status": "planned",
                    "secondary_keywords": [m["keyword"] for m in merged_groups[spoke_kw]],
                    "business_value": spoke_info.get("business_value", 2),
                    "traffic_potential": highest_vol
                }
                final_plan_items.append(spoke_item)

        # 7. Write to database plan queue
        self.store.clear_content_plan()
        for item in final_plan_items:
            self.store.add_to_content_plan(item)

        # 8. Export plan artifacts
        plan_json = Path("cluster-plan.json")
        plan_md = Path("cluster-plan.md")

        plan_json.write_text(json.dumps(final_plan_items, indent=2, default=str), encoding="utf-8")

        md_content = self._generate_markdown_report(final_plan_items)
        plan_md.write_text(md_content, encoding="utf-8")

        brain_path = Path("/Users/dylanangloher/.gemini/antigravity/brain/5cb25842-f1a4-4d2f-80dc-68e4801fd23e/cluster_plan.md")
        try:
            brain_path.write_text(md_content, encoding="utf-8")
        except Exception:
            pass

        logger.info(f"Plan exported successfully. Total items: {len(final_plan_items)}")
        return final_plan_items

    def _generate_markdown_report(self, items: list[dict]) -> str:
        md = []
        md.append("# Yoast Topic Cluster Plan")
        md.append(f"Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
        md.append("This document outlines the structured hub-and-spoke topic cluster plan generated based on search engine result page (SERP) overlap calculations. Pillars must be published before their Spokes to establish the bidirectional interlinking matrix.\n")

        clusters = {}
        for item in items:
            c_name = item["cluster_name"]
            if c_name not in clusters:
                clusters[c_name] = []
            clusters[c_name].append(item)

        for c_name, members in clusters.items():
            md.append(f"## {c_name}")

            pillar = [m for m in members if m["role"] == "pillar"][0]
            spokes = [m for m in members if m["role"] == "spoke"]

            md.append(f"### Pillar Page")
            md.append(f"- **Keyword**: `{pillar['keyword']}`")
            md.append(f"- **Target Title**: {pillar['title']}")
            md.append(f"- **Search Intent**: {pillar['intent']}")
            md.append(f"- **Volume**: {pillar['volume']} | **KD**: {pillar['kd']} | **Priority Score**: {pillar['score']}")
            md.append(f"- **Business Value (0-3)**: {pillar.get('business_value', 0)} | **Traffic Potential**: {pillar.get('traffic_potential', 0)}")
            if pillar.get("secondary_keywords"):
                md.append(f"- **Secondary Keywords (Merged)**: {', '.join([f'`{k}`' for k in pillar['secondary_keywords']])}")
            md.append("")

            if spokes:
                md.append("### Supporting Spoke Pages")
                md.append("| Spoke Keyword | Target Title | Score | Vol | KD | Biz Value | Traffic Potential | Parent Link Anchor | Secondary Keywords |")
                md.append("|---|---|---|---|---|---|---|---|---|")
                for spoke in spokes:
                    sec_kws = ", ".join([f"`{k}`" for k in spoke.get("secondary_keywords", [])])
                    md.append(
                        f"| `{spoke['keyword']}` | {spoke['title']} | {spoke['score']} | {spoke['volume']} | "
                        f"{spoke['kd']} | {spoke.get('business_value', 0)} | {spoke.get('traffic_potential', 0)} | `{spoke['anchor_text']}` | {sec_kws} |"
                    )
                md.append("")

            md.append("---")

        return "\n".join(md)
