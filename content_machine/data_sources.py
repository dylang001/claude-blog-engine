from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .config import Settings
from .dataforseo_auth import dataforseo_headers
from .models import Opportunity, WorkItemType
from .scoring import opportunity_score
from .state import StateStore

logger = logging.getLogger(__name__)


class DataForSEOClient:
    def __init__(self, settings: Settings):
        self.headers = dataforseo_headers(settings)
        self.base_url = "https://api.dataforseo.com"
        self.location_code = 2840

    async def keyword_ideas(self, seeds: list[str], limit: int = 25) -> list[dict[str, Any]]:
        if not seeds:
            return []
        payload = [{"keywords": seeds[:20], "location_code": self.location_code, "language_code": "en", "limit": limit}]
        async with httpx.AsyncClient(timeout=60, headers=self.headers) as client:
            resp = await client.post(f"{self.base_url}/v3/dataforseo_labs/google/keyword_ideas/live", json=payload)
            resp.raise_for_status()
            data = resp.json()
        items = []
        for task in data.get("tasks", []):
            for result in task.get("result") or []:
                items.extend(result.get("items") or [])
        return items

    async def competitor_keywords(self, domain: str, limit: int = 50) -> list[dict[str, Any]]:
        if not domain:
            return []
        payload = [{"target": domain, "location_code": self.location_code, "language_code": "en", "limit": limit}]
        async with httpx.AsyncClient(timeout=60, headers=self.headers) as client:
            resp = await client.post(f"{self.base_url}/v3/dataforseo_labs/google/competitor_keywords/live", json=payload)
            resp.raise_for_status()
            data = resp.json()
        items = []
        for task in data.get("tasks", []):
            for result in task.get("result") or []:
                items.extend(result.get("items") or [])
        return items

    async def serp(self, keyword: str, limit: int = 10) -> dict[str, Any]:
        payload = [{"keyword": keyword, "location_code": self.location_code, "language_code": "en", "device": "desktop", "os": "windows", "depth": limit}]
        async with httpx.AsyncClient(timeout=60, headers=self.headers) as client:
            resp = await client.post(f"{self.base_url}/v3/serp/google/organic/live/advanced", json=payload)
            resp.raise_for_status()
            return resp.json()


def normalize_keyword_item(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize DataForSEO keyword payloads across Labs response shapes."""
    keyword_data = item.get("keyword_data") if isinstance(item.get("keyword_data"), dict) else {}
    source = keyword_data or item
    info = source.get("keyword_info") or item.get("keyword_info") or {}
    props = source.get("keyword_properties") or item.get("keyword_properties") or {}
    intent = source.get("search_intent_info") or item.get("search_intent_info") or {}
    backlinks = source.get("avg_backlinks_info") or item.get("avg_backlinks_info") or {}
    keyword = source.get("keyword") or item.get("keyword") or ""
    return {
        "keyword": str(keyword).strip(),
        "volume": info.get("search_volume"),
        "kd": props.get("keyword_difficulty"),
        "intent": intent.get("main_intent") or "",
        "competition": info.get("competition"),
        "competition_level": info.get("competition_level"),
        "cpc": info.get("cpc"),
        "monthly_searches": info.get("monthly_searches") or [],
        "trend": info.get("search_volume_trend") or {},
        "detected_language": props.get("detected_language"),
        "is_another_language": props.get("is_another_language"),
        "words_count": props.get("words_count"),
        "avg_backlinks": backlinks.get("backlinks"),
        "avg_referring_domains": backlinks.get("referring_domains"),
    }


class GoogleSignals:
    """Thin integration boundary for GA4/GSC.

    The vendored Claude SEO scripts under vendor/claude-seo contain the fuller
    Google API implementations. This worker keeps the boundary small so tests
    can mock it and production can later swap in those scripts directly.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    async def refresh_candidates(self) -> list[Opportunity]:
        # Real refresh candidates should come from GSC rows: position 8-20,
        # declining clicks, low CTR/high impression pages, mapped back to WP posts.
        # Until that adapter is fully wired, return no refresh candidates rather
        # than letting a placeholder item reach autonomous publishing.
        return []


class OpportunityCollector:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.dataforseo = DataForSEOClient(settings)
        self.google = GoogleSignals(settings)
        self.store = StateStore(settings.state_db, settings=settings)

    async def collect(self, strict: bool = False) -> list[Opportunity]:
        # 1. Check refresh queue
        refresh_item = self.store.get_next_refresh_candidate()
        if refresh_item:
            logger.info(f"Consuming candidate from refresh queue: {refresh_item['keyword']}")
            return [
                Opportunity(
                    kind=WorkItemType.REFRESH,
                    keyword=refresh_item["keyword"],
                    title=f"Refresh: {refresh_item['keyword']}",
                    score=refresh_item["score"],
                    url=refresh_item["url"],
                    reason=refresh_item["reason"],
                )
            ]

        # 2. Check content plan queue
        planned_item = self.store.get_next_planned_post()
        if planned_item:
            logger.info(f"Consuming planned post from topic cluster plan: {planned_item['keyword']} (Role: {planned_item['role']})")
            metadata = {
                "volume": planned_item.get("volume") or 0,
                "kd": planned_item.get("kd") or 0,
                "intent": planned_item.get("intent", ""),
                "cluster_name": planned_item.get("cluster_name", ""),
                "role": planned_item.get("role", ""),
                "parent_pillar": planned_item.get("parent_pillar"),
                "anchor_text": planned_item.get("anchor_text"),
            }
            return [
                Opportunity(
                    kind=WorkItemType.NEW_ARTICLE,
                    keyword=planned_item["keyword"],
                    title=planned_item["title"],
                    score=planned_item["score"],
                    reason=f"Topic Cluster Plan ({planned_item['role']})",
                    metadata=metadata
                )
            ]

        # 3. Fall back to dynamic keyword discovery
        candidates: list[Opportunity] = []
        candidates.extend(await self.google.refresh_candidates())

        seeds = self._keyword_seeds()
        try:
            ideas = await self.dataforseo.keyword_ideas(seeds)
        except Exception as exc:
            if strict:
                raise RuntimeError(f"DataForSEO keyword ideas failed: {exc}") from exc
            ideas = []

        if strict and not ideas:
            raise RuntimeError("DataForSEO keyword ideas returned no items in strict mode.")

        for item in ideas:
            normalized = normalize_keyword_item(item)
            keyword = normalized["keyword"]
            if not keyword:
                continue
            if not self._is_relevant_keyword(keyword):
                continue
            intent = normalized["intent"]
            funnel = "BOFU" if intent in {"commercial", "transactional"} else "MOFU"
            score = opportunity_score(normalized["volume"], normalized["kd"], funnel)
            if score < 50:
                continue
            candidates.append(
                Opportunity(
                    kind=WorkItemType.NEW_ARTICLE,
                    keyword=keyword,
                    title=f"{keyword.title()}",
                    score=score,
                    reason="DataForSEO keyword opportunity",
                    metadata={
                        "volume": normalized["volume"],
                        "kd": normalized["kd"],
                        "intent": intent,
                        "funnel": funnel,
                        "competition": normalized["competition"],
                        "competition_level": normalized["competition_level"],
                        "cpc": normalized["cpc"],
                        "trend": normalized["trend"],
                        "monthly_searches": normalized["monthly_searches"],
                        "detected_language": normalized["detected_language"],
                        "is_another_language": normalized["is_another_language"],
                        "avg_backlinks": normalized["avg_backlinks"],
                        "avg_referring_domains": normalized["avg_referring_domains"],
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            )

        if strict and not candidates:
            raise RuntimeError("Strict keyword discovery found no relevant scored DataForSEO opportunities.")

        if not candidates:
            candidates.append(
                Opportunity(
                    kind=WorkItemType.NEW_ARTICLE,
                    keyword="AI marketing agent for SEO content",
                    title="AI Marketing Agent for SEO Content: How Autonomous Marketing Systems Work",
                    score=76.0,
                    reason="MeetLyra-specific bootstrap topic because live keyword suggestions were weak or too broad.",
                )
            )
        return candidates

    def _keyword_seeds(self) -> list[str]:
        seeds = [
            *self.settings.site.products,
            self.settings.site.brand_name,
            "ai marketing agent",
            "seo content automation",
            "ai seo agent",
            "ai content marketing",
            "content marketing automation",
            "generative engine optimization",
            "ai marketing automation",
            "autonomous marketing",
        ]
        seen = set()
        unique = []
        for seed in seeds:
            clean = seed.strip()
            key = clean.lower()
            if clean and key not in seen:
                seen.add(key)
                unique.append(clean)
        return unique

    def _is_relevant_keyword(self, keyword: str) -> bool:
        text = keyword.lower()
        if any(topic.lower() in text for topic in self.settings.site.forbidden_topics):
            return False
        if self.settings.site.brand_name.lower() in text:
            return True
        high_intent_phrases = {
            "ai marketing", "seo content", "content marketing", "marketing automation",
            "seo automation", "ai seo", "geo content", "generative engine optimization",
            "content engine", "marketing agent", "seo agent", "blog automation",
            "wordpress seo", "campaign automation", "social content", "email marketing",
        }
        if any(phrase in text for phrase in high_intent_phrases):
            return True
        has_ai_or_agent = any(term in text for term in {" ai ", "ai ", " agent", "agents", "automation", "automated"})
        has_marketing_context = any(term in text for term in {"marketing", "seo", "content", "campaign", "blog", "email", "social", "wordpress", "geo"})
        return has_ai_or_agent and has_marketing_context
