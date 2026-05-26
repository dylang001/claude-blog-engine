import logging
import json
import httpx
from typing import Any, Dict, List, Optional
from .config import Settings

logger = logging.getLogger("content_machine.supermemory")

SUPERMEMORY_BASE_URL = "https://api.supermemory.ai/v3"
CONTAINER_TAG = "meetlyra"


class SuperMemoryClient:
    """Client for syncing content, keyword research, SEO signals, and outreach data
    into the SuperMemory knowledge graph for cross-pipeline context sharing."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.api_key = settings.supermemory_api_key
        self.base_url = SUPERMEMORY_BASE_URL

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def _push(self, content: str) -> bool:
        """Low-level push to SuperMemory."""
        if not self.is_configured():
            logger.debug("SuperMemory not configured. Skipping push.")
            return False
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"content": content, "containerTag": CONTAINER_TAG}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(self.base_url + "/", json=payload, headers=headers)
                if resp.status_code in (200, 201):
                    return True
                logger.error("SuperMemory push failed: %d %s", resp.status_code, resp.text[:300])
                return False
        except Exception as exc:
            logger.error("SuperMemory push exception: %s", exc)
            return False

    async def _search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Low-level search against SuperMemory graph."""
        if not self.is_configured():
            return []
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"q": query, "limit": limit, "rewriteQuery": True}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(self.base_url + "/search", json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return data if isinstance(data, list) else data.get("results", [])
                logger.error("SuperMemory search failed: %d %s", resp.status_code, resp.text[:300])
                return []
        except Exception as exc:
            logger.error("SuperMemory search exception: %s", exc)
            return []

    # =========================================================================
    # Published Articles
    # =========================================================================

    async def push_post(self, slug: str, title: str, url: str, content: str) -> bool:
        """Ingest a published blog post into SuperMemory."""
        text = f"# PUBLISHED ARTICLE: {title}\nSlug: {slug}\nURL: {url}\n\n{content[:8000]}"
        logger.info("Pushing published post '%s' to SuperMemory.", slug)
        return await self._push(text)

    # =========================================================================
    # Article Performance (GA4)
    # =========================================================================

    async def push_article_performance(self, date_range: str, top_pages: List[Dict[str, Any]]) -> bool:
        """Push GA4 top-performing article data to SuperMemory."""
        rows = "\n".join([
            f"- URL: {p.get('url', '')} | Sessions: {p.get('sessions', 0)} | Users: {p.get('users', 0)} | Pageviews: {p.get('pageviews', 0)}"
            for p in top_pages[:30]
        ])
        text = f"# GA4 ARTICLE PERFORMANCE — {date_range}\n\nTop performing pages by organic sessions:\n{rows}"
        logger.info("Pushing GA4 article performance to SuperMemory.")
        return await self._push(text)

    # =========================================================================
    # GSC Keyword Data
    # =========================================================================

    async def push_gsc_keywords(self, date_range: str, rows: List[Dict[str, Any]]) -> bool:
        """Push Google Search Console ranking keywords to SuperMemory."""
        top_kws = "\n".join([
            f"- Query: '{r.get('query', '')}' | Position: {r.get('position', '')} | Clicks: {r.get('clicks', '')} | Impressions: {r.get('impressions', '')} | CTR: {r.get('ctr', '')}"
            for r in rows[:50]
        ])
        text = f"# GOOGLE SEARCH CONSOLE KEYWORD DATA — {date_range}\n\n{top_kws}"
        logger.info("Pushing GSC keyword data to SuperMemory.")
        return await self._push(text)

    async def push_gsc_quick_wins(self, quick_wins: List[Dict[str, Any]]) -> bool:
        """Push GSC quick-win opportunities (position 4-20) to SuperMemory."""
        if not quick_wins:
            return True
        lines = "\n".join([
            f"- Query: '{w.get('query', '')}' | Position: {w.get('position', '')} | Clicks: {w.get('clicks', '')} | Impressions: {w.get('impressions', '')}"
            for w in quick_wins[:20]
        ])
        text = f"# GSC QUICK WINS (Position 4-20) — refresh opportunities\n\n{lines}"
        logger.info("Pushing GSC quick wins to SuperMemory.")
        return await self._push(text)

    # =========================================================================
    # DataForSEO Keyword Research
    # =========================================================================

    async def push_keyword_plan(self, plan_date: str, keywords: List[Dict[str, Any]]) -> bool:
        """Push weekly keyword targets and opportunity scores to SuperMemory."""
        lines = "\n".join([
            f"- Keyword: {kw.get('keyword')} | Score: {kw.get('opportunity_score')} | Funnel: {kw.get('funnel')} | Vol: {kw.get('volume')} | KD: {kw.get('kd')}"
            for kw in keywords[:20]
        ])
        text = f"# WEEKLY KEYWORD PLAN — {plan_date}\n\n{lines}"
        logger.info("Pushing weekly keyword plan to SuperMemory.")
        return await self._push(text)

    async def push_dataforseo_serp(self, keyword: str, results: List[Dict[str, Any]]) -> bool:
        """Push DataForSEO SERP results for a keyword into SuperMemory."""
        lines = "\n".join([
            f"- Rank {r.get('rank', '')}: {r.get('title', '')} — {r.get('url', '')} ({r.get('domain', '')})"
            for r in results[:10]
        ])
        text = f"# DATAFORSEO SERP RESEARCH — Keyword: '{keyword}'\n\n{lines}"
        logger.info("Pushing DataForSEO SERP for '%s' to SuperMemory.", keyword)
        return await self._push(text)

    async def push_competitor_keywords(self, competitor_domain: str, keywords: List[Dict[str, Any]]) -> bool:
        """Push competitor keyword rankings into SuperMemory."""
        lines = "\n".join([
            f"- Keyword: '{kw.get('keyword', '')}' | Position: {kw.get('position', '')} | Volume: {kw.get('volume', '')} | KD: {kw.get('kd', '')}"
            for kw in keywords[:30]
        ])
        text = f"# COMPETITOR KEYWORD RESEARCH — Domain: {competitor_domain}\n\n{lines}"
        logger.info("Pushing competitor keyword data for %s to SuperMemory.", competitor_domain)
        return await self._push(text)

    # =========================================================================
    # SEO Audit & Gap Analysis
    # =========================================================================

    async def push_seo_audit_result(self, post_url: str, post_title: str, audit_summary: str, gaps: List[str]) -> bool:
        """Push the result of a content SEO audit into SuperMemory."""
        gap_lines = "\n".join([f"- {g}" for g in gaps]) if gaps else "- No critical gaps found."
        text = f"# SEO AUDIT RESULT\nPost: {post_title}\nURL: {post_url}\n\nSummary: {audit_summary}\n\nContent Gaps:\n{gap_lines}"
        logger.info("Pushing SEO audit result for '%s' to SuperMemory.", post_title)
        return await self._push(text)

    # =========================================================================
    # Searches / Context Retrieval
    # =========================================================================

    async def search_memory(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search SuperMemory graph for topical clusters and historical context."""
        logger.info("Searching SuperMemory for: %s", query)
        return await self._search(query, limit)

    async def get_high_performing_articles(self) -> List[Dict[str, Any]]:
        """Retrieve context on articles that performed well organically."""
        return await self._search("high traffic article sessions users organic search", 5)

    async def get_keyword_gaps(self) -> List[Dict[str, Any]]:
        """Retrieve known keyword gaps and quick win opportunities."""
        return await self._search("GSC quick wins position 4 to 20 keyword gap", 5)

    async def get_competitor_context(self, topic: str) -> List[Dict[str, Any]]:
        """Retrieve competitor keyword and content context for a topic."""
        return await self._search(f"competitor keyword {topic}", 5)
