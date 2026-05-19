from __future__ import annotations

from typing import Any

from .data_sources import DataForSEOClient
from .models import Opportunity
from .yoast_guidelines import yoast_research_requirements


class ResearchEngine:
    def __init__(self, dataforseo: DataForSEOClient):
        self.dataforseo = dataforseo

    async def brief(self, opportunity: Opportunity, strict: bool = False) -> dict[str, Any]:
        serp = {}
        try:
            serp = await self.dataforseo.serp(opportunity.keyword, limit=10)
        except Exception as exc:
            if strict:
                raise RuntimeError(f"DataForSEO SERP failed for {opportunity.keyword!r}: {exc}") from exc
            serp = {"error": str(exc)}
        if strict and not _has_organic_results(serp):
            raise RuntimeError(f"DataForSEO SERP returned no organic results for {opportunity.keyword!r}.")
        return {
            "opportunity": {
                "kind": opportunity.kind.value,
                "keyword": opportunity.keyword,
                "score": opportunity.score,
                "url": opportunity.url,
                "reason": opportunity.reason,
            },
            "serp": serp,
            "requirements": [
                "Use exact SERP evidence when available.",
                "Fill competitor content gaps.",
                "Add Yoast title, description, focus keyphrase.",
                "Optimize for Google and AI answer engines.",
                *yoast_research_requirements(),
            ],
        }


def _has_organic_results(serp: dict[str, Any]) -> bool:
    for task in serp.get("tasks", []):
        for result in task.get("result") or []:
            for item in result.get("items") or []:
                if item.get("type") == "organic":
                    return True
    return False
