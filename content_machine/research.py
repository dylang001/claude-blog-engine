from __future__ import annotations

import logging
import os
import sys
from typing import Any

from .data_sources import DataForSEOClient
from .models import Opportunity
from .open_seo_client import OpenSeoClient
from .yoast_guidelines import yoast_research_requirements

logger = logging.getLogger(__name__)

# Make claude-seo scripts importable
_CLAUDE_SEO_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "claude-seo", "scripts",
)
if _CLAUDE_SEO_SCRIPTS not in sys.path:
    sys.path.insert(0, _CLAUDE_SEO_SCRIPTS)


class ResearchEngine:
    def __init__(self, dataforseo: DataForSEOClient, open_seo: OpenSeoClient | None = None, settings: Any = None):
        self.dataforseo = dataforseo
        self.open_seo = open_seo
        self.settings = settings

    async def brief(self, opportunity: Opportunity, strict: bool = False) -> dict[str, Any]:
        serp = {}

        # Primary: try open-seo (self-hosted, DataForSEO-backed)
        if self.open_seo:
            try:
                serp = await self.open_seo.serp(opportunity.keyword)
                if serp:
                    logger.info(f"SERP data fetched via open-seo for {opportunity.keyword!r}")
            except Exception as exc:
                logger.debug(
                    f"open-seo SERP failed for {opportunity.keyword!r}: {exc} "
                    "— falling back to direct DataForSEO"
                )
                serp = {}

        # Fallback: direct DataForSEO
        if not serp or "error" in serp or not _has_organic_results(serp):
            try:
                serp_res = await self.dataforseo.serp(opportunity.keyword, limit=10)
                if _has_organic_results(serp_res):
                    serp = serp_res
            except Exception as exc:
                logger.debug(f"Direct DataForSEO SERP failed for {opportunity.keyword!r}: {exc}")

        # Final Fallback: Tavily Search (free fallback if both OpenSEO/DataForSEO fail or return credit errors)
        if (not serp or "error" in serp or not _has_organic_results(serp)) and self.settings and self.settings.tavily_api_key:
            try:
                logger.info(f"OpenSEO and DataForSEO failed to return organic results for {opportunity.keyword!r}. Trying Tavily Search...")
                import httpx
                from urllib.parse import urlparse
                
                url = "https://api.tavily.com/search"
                payload = {
                    "api_key": self.settings.tavily_api_key,
                    "query": opportunity.keyword,
                    "search_depth": "basic"
                }
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        tav_data = resp.json()
                        tav_results = tav_data.get("results", [])
                        if tav_results:
                            items = []
                            for r in tav_results:
                                url_str = r.get("url", "")
                                if url_str:
                                    items.append({
                                        "type": "organic",
                                        "url": url_str,
                                        "title": r.get("title", ""),
                                        "domain": urlparse(url_str).netloc,
                                        "description": r.get("content", ""),
                                        "rank": len(items) + 1,
                                    })
                            if items:
                                serp = {
                                    "keyword": opportunity.keyword,
                                    "tasks": [
                                        {
                                            "result": [
                                                {
                                                    "items": items
                                                }
                                            ]
                                        }
                                    ]
                                }
                                logger.info(f"Successfully generated fallback SERP using Tavily Search for {opportunity.keyword!r} ({len(items)} items)")
            except Exception as exc:
                logger.warning(f"Tavily Search fallback failed for {opportunity.keyword!r}: {exc}")

        if strict and not _has_organic_results(serp):
            raise RuntimeError(
                f"No organic search results available for {opportunity.keyword!r} via OpenSEO, DataForSEO, or Tavily fallback."
            )

        # Open-seo domain overview (best-effort, for competitor insights)
        open_seo_domain = {}
        if self.open_seo and opportunity.url:
            try:
                from urllib.parse import urlparse
                domain = urlparse(opportunity.url).netloc or opportunity.url
                open_seo_domain = await self.open_seo.domain_overview(domain)
            except Exception:
                pass

        # NLP entity extraction (best-effort)
        nlp_entities = await self._extract_nlp_entities(opportunity.keyword)

        # YouTube video sourcing (best-effort)
        youtube_videos = await self._search_youtube_videos(opportunity.keyword)

        return {
            "opportunity": {
                "kind": opportunity.kind.value,
                "keyword": opportunity.keyword,
                "score": opportunity.score,
                "url": opportunity.url,
                "reason": opportunity.reason,
            },
            "serp": serp,
            "open_seo_domain": open_seo_domain,
            "nlp_entities": nlp_entities,
            "youtube_videos": youtube_videos,
            "requirements": [
                "Use exact SERP evidence when available.",
                "Fill competitor content gaps.",
                "Add Yoast title, description, focus keyphrase.",
                "Optimize for Google and AI answer engines.",
                "Include NLP entities/LSI terms from nlp_entities in the content for semantic density.",
                "Embed top YouTube videos from youtube_videos as WordPress video blocks if relevant.",
                *yoast_research_requirements(),
            ],
        }

    async def _extract_nlp_entities(self, keyword: str) -> list[dict[str, Any]]:
        """Use Google Cloud NLP API to extract salient entities for semantic enrichment."""
        try:
            from nlp_analyze import analyze_text
            result = analyze_text(
                text=f"Comprehensive guide about {keyword} for B2B SaaS operators",
                features=["entities"],
            )
            if result.get("error"):
                logger.debug(f"NLP analysis skipped: {result['error']}")
                return []
            entities = result.get("entities", [])
            return sorted(entities, key=lambda e: e.get("salience", 0), reverse=True)[:15]
        except ImportError:
            logger.debug("nlp_analyze not available — skipping NLP entity extraction.")
            return []
        except Exception as exc:
            logger.debug(f"NLP entity extraction failed: {exc}")
            return []

    async def _search_youtube_videos(self, keyword: str) -> list[dict[str, Any]]:
        """Search YouTube for authoritative videos to embed in content."""
        try:
            from youtube_search import search_videos
            result = search_videos(query=keyword, max_results=3, order="relevance")
            if result.get("error"):
                logger.debug(f"YouTube search skipped: {result['error']}")
                return []
            videos = result.get("videos", [])
            return [
                {
                    "video_id": v["video_id"],
                    "title": v["title"],
                    "channel": v["channel"],
                    "url": v["url"],
                    "views": v.get("views", 0),
                }
                for v in videos[:2]
                if v.get("views", 0) >= 500
            ]
        except ImportError:
            logger.debug("youtube_search not available — skipping YouTube video sourcing.")
            return []
        except Exception as exc:
            logger.debug(f"YouTube video search failed: {exc}")
            return []


def _has_organic_results(serp: dict[str, Any]) -> bool:
    for task in serp.get("tasks", []):
        for result in task.get("result") or []:
            for item in result.get("items") or []:
                if item.get("type") == "organic":
                    return True
    return False
