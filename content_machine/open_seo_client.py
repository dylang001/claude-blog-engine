"""OpenSEO HTTP client for the self-hosted open-seo Cloud Run service.

This module wraps the open-seo MCP API endpoints that are backed by
DataForSEO. It is designed to be imported by ResearchEngine and
ClusterPlanner as a best-effort enrichment layer — all methods return
empty/None on any error so callers can fall back gracefully to the
existing DataForSEO direct client.

Docs: https://github.com/every-app/open-seo
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import Settings

logger = logging.getLogger(__name__)

# Default connection/read timeout in seconds
_DEFAULT_TIMEOUT = 30.0


class OpenSeoClient:
    """Async HTTP client for the self-hosted open-seo service.

    Usage::

        client = OpenSeoClient(settings)
        ideas = await client.keyword_ideas("AI content marketing")
        serp = await client.serp("AI marketing agent")
    """

    def __init__(self, settings: Settings) -> None:
        self.base_url = (settings.open_seo_url or "").rstrip("/")
        self._enabled = bool(self.base_url)
        if not self._enabled:
            logger.debug("OpenSeoClient: OPEN_SEO_URL not set — client disabled")

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def keyword_ideas(
        self,
        keyword: str,
        location_code: int = 2840,
        language_code: str = "en",
        limit: int = 150,
    ) -> list[dict[str, Any]]:
        """Fetch related keyword ideas from open-seo's DataForSEO Labs endpoint.

        Returns a list of keyword dicts with at minimum:
          {"keyword": str, "search_volume": int|None, "keyword_difficulty": int|None,
           "cpc": float|None, "competition": float|None, "intent": str|None}
        """
        if not self._enabled:
            return []
        try:
            project_id = await self._get_project_id()
            if not project_id:
                logger.warning("OpenSeoClient.keyword_ideas failed: no project ID available")
                return []

            if limit <= 150:
                result_limit = 150
            elif limit <= 300:
                result_limit = 300
            else:
                result_limit = 500

            result = await self._call_tool(
                "research_keywords",
                {
                    "projectId": project_id,
                    "seeds": [
                        {
                            "seed": keyword,
                            "locationCode": location_code,
                            "languageCode": language_code,
                        }
                    ],
                    "resultLimit": result_limit,
                },
            )

            content = result.get("structuredContent", {})
            results = content.get("results") or []
            if not results:
                return []

            first_result = results[0]
            if not first_result.get("ok"):
                logger.warning(f"OpenSeoClient.keyword_ideas failed for {keyword!r}: {first_result.get('error')}")
                return []

            items = first_result.get("topRows") or []
            return [_normalize_idea(item) for item in items if isinstance(item, dict)]
        except Exception as exc:
            logger.warning(f"OpenSeoClient.keyword_ideas failed for {keyword!r}: {exc}")
            return []

    async def serp(
        self,
        keyword: str,
        location_code: int = 2840,
        language_code: str = "en",
        depth: int = 10,
    ) -> dict[str, Any]:
        """Fetch a live SERP snapshot for a keyword.

        Returns a dict that mirrors the DataForSEO SERP response shape so
        callers can treat it as a drop-in replacement.
        """
        if not self._enabled:
            return {}
        try:
            project_id = await self._get_project_id()
            if not project_id:
                logger.warning("OpenSeoClient.serp failed: no project ID available")
                return {}

            result = await self._call_tool(
                "get_serp_results",
                {
                    "projectId": project_id,
                    "queries": [
                        {
                            "keyword": keyword,
                            "locationCode": location_code,
                            "languageCode": language_code,
                        }
                    ],
                },
            )

            content = result.get("structuredContent", {})
            results = content.get("results") or []
            if not results:
                return {}

            first_result = results[0]
            if not first_result.get("ok"):
                logger.warning(f"OpenSeoClient.serp failed for {keyword!r}: {first_result.get('error')}")
                return {}

            items = first_result.get("items") or []

            organic_items = []
            for item in items:
                organic_items.append({
                    "type": item.get("type") or "organic",
                    "rank_absolute": item.get("rank"),
                    "rank_group": item.get("rank"),
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "domain": item.get("domain"),
                    "description": item.get("description"),
                })

            return {
                "keyword": keyword,
                "tasks": [
                    {
                        "result": [
                            {
                                "items": organic_items
                            }
                        ]
                    }
                ]
            }
        except Exception as exc:
            logger.warning(f"OpenSeoClient.serp failed for {keyword!r}: {exc}")
            return {}

    async def domain_overview(self, domain: str) -> dict[str, Any]:
        """Fetch a domain overview (traffic, keywords, authority metrics).

        Returns an empty dict on failure.
        """
        if not self._enabled:
            return {}
        try:
            project_id = await self._get_project_id()
            if not project_id:
                logger.warning("OpenSeoClient.domain_overview failed: no project ID available")
                return {}

            result = await self._call_tool(
                "get_domain_overview",
                {
                    "projectId": project_id,
                    "domain": domain,
                },
            )

            structured_content = result.get("structuredContent") or result
            return structured_content or {}
        except Exception as exc:
            logger.warning(f"OpenSeoClient.domain_overview failed for {domain!r}: {exc}")
            return {}

    async def site_audit_summary(self, domain: str) -> dict[str, Any]:
        """Fetch the latest site-audit summary for a domain (stubbed for compatibility).

        Returns an empty dict on failure.
        """
        return {}

    async def rank_tracking(self, domain: str, keywords: list[str]) -> list[dict[str, Any]]:
        """Fetch rank positions for a set of keywords on a domain.

        Returns a list of position dicts on success, empty list on failure.
        """
        if not self._enabled:
            return []
        try:
            project_id = await self._get_project_id()
            if not project_id:
                return []

            result = await self._call_tool("get_rank_tracker", {"projectId": project_id})
            content = result.get("structuredContent") or {}
            configs = content.get("configs") or []

            tracker_id = None
            for c in configs:
                if c.get("domain") == domain:
                    tracker_id = c.get("id")
                    break

            if not tracker_id:
                return []

            tracker_data = await self._call_tool(
                "get_rank_tracker",
                {"projectId": project_id, "trackerId": tracker_id}
            )
            tracker_content = tracker_data.get("structuredContent") or {}
            results = tracker_content.get("results") or {}
            rows = results.get("rows") or []

            keyword_set = set(keywords)
            mapped_results = []
            for row in rows:
                kw = row.get("keyword")
                if kw in keyword_set:
                    desktop = row.get("desktop") or {}
                    mobile = row.get("mobile") or {}
                    pos = desktop.get("position") or mobile.get("position")
                    mapped_results.append({
                        "keyword": kw,
                        "rank": pos
                    })
            return mapped_results
        except Exception as exc:
            logger.warning(f"OpenSeoClient.rank_tracking failed for {domain!r}: {exc}")
            return []

    async def backlinks_summary(self, target: str) -> dict[str, Any]:
        """Fetch backlink profile summary for a target domain/URL via open-seo.

        Returns a dict with keys compatible with BacklinkClient.get_summary.
        """
        if not self._enabled:
            return {}
        try:
            project_id = await self._get_project_id()
            if not project_id:
                logger.warning("OpenSeoClient.backlinks_summary failed: no project ID available")
                return {}

            result = await self._call_tool(
                "get_backlinks_overview",
                {
                    "projectId": project_id,
                    "target": target,
                },
            )

            content = result.get("structuredContent", {})
            overview = content.get("overview") or {}
            if overview:
                return {
                    "target": target,
                    "rank": overview.get("rank") or 0,
                    "backlinks": overview.get("backlinks") or 0,
                    "referring_domains": overview.get("referring_domains") or 0,
                }
            return {}
        except Exception as exc:
            logger.warning(f"OpenSeoClient.backlinks_summary failed for {target!r}: {exc}")
            return {}

    async def health(self) -> bool:
        """Return True if the service is reachable."""
        if not self._enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/")
            return resp.status_code < 500
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _get_project_id(self) -> str:
        """Fetch the first project ID from the service, caching it for subsequent calls.
        If no projects exist, the backend's list_projects tool automatically initializes a default one.
        """
        if hasattr(self, "_project_id") and self._project_id:
            return self._project_id

        try:
            result = await self._call_tool("list_projects", {})
            content = result.get("structuredContent", {})
            projects = content.get("projects") or []
            if projects:
                self._project_id = projects[0]["id"]
                return self._project_id
        except Exception as exc:
            logger.warning(f"OpenSeoClient: failed to list/retrieve project ID: {exc}")

        return ""

    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke a tool on the MCP server."""
        url = f"{self.base_url}/mcp"
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments,
            },
            "id": 1
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            res_data = resp.json()
            if "error" in res_data:
                err = res_data["error"]
                raise RuntimeError(f"MCP error: {err.get('message', err)}")
            return res_data.get("result", {})


def _normalize_idea(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize an open-seo keyword idea into the content-machine shape."""
    kw_data = item.get("keywordData") or item.get("keyword_data") or item
    info = kw_data.get("keywordInfo") or kw_data.get("keyword_info") or kw_data
    props = kw_data.get("keywordProperties") or kw_data.get("keyword_properties") or {}
    intent_info = kw_data.get("searchIntentInfo") or kw_data.get("search_intent_info") or {}

    keyword = str(kw_data.get("keyword") or item.get("keyword") or "").strip()
    volume = info.get("searchVolume") or info.get("search_volume") or item.get("searchVolume") or item.get("search_volume")
    kd = props.get("keywordDifficulty") or props.get("keyword_difficulty") or item.get("keywordDifficulty") or item.get("keyword_difficulty")
    cpc = info.get("cpc") or item.get("cpc")
    competition = info.get("competition") or item.get("competition")
    comp_level = info.get("competitionLevel") or info.get("competition_level") or item.get("competitionLevel") or item.get("competition_level")
    intent = intent_info.get("mainIntent") or intent_info.get("main_intent") or item.get("intent") or ""

    monthly = info.get("monthlySearches") or info.get("monthly_searches") or item.get("trend") or []
    normalized_monthly = []
    for m in monthly:
        if isinstance(m, dict):
            normalized_monthly.append({
                "year": m.get("year"),
                "month": m.get("month"),
                "search_volume": m.get("searchVolume") or m.get("search_volume")
            })

    return {
        "keyword": keyword,
        "volume": volume,
        "kd": kd,
        "cpc": cpc,
        "competition": competition,
        "competition_level": comp_level,
        "intent": intent,
        "monthly_searches": normalized_monthly,
    }

