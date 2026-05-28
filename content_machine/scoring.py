from __future__ import annotations

import math

from .models import AuditReport, Opportunity, PublishDecision


def volume_score(volume: int | float | None) -> float:
    value = max(float(volume or 0), 1.0)
    return min(1.0, math.log10(value) / math.log10(100_000))


def difficulty_score(kd: int | float | None) -> float:
    if kd is None:
        return 0.5
    return max(0.0, (100.0 - float(kd)) / 100.0)


def funnel_score(funnel: str | None) -> float:
    return {"BOFU": 1.0, "MOFU": 0.85, "TOFU": 0.70}.get((funnel or "").upper(), 0.75)


def opportunity_score(volume: int | None, kd: int | None, funnel: str | None, refresh_boost: float = 0.0) -> float:
    score = (0.40 * volume_score(volume) + 0.40 * difficulty_score(kd) + 0.20 * funnel_score(funnel)) * 100
    return round(min(100.0, score + refresh_boost), 1)


def choose_opportunity(candidates: list[Opportunity], seen_keywords: set[str] | None = None) -> Opportunity:
    if not candidates:
        raise ValueError("No opportunities available")
    seen = seen_keywords or set()
    fresh = [c for c in candidates if c.keyword.lower().strip() not in seen]
    pool = fresh or candidates
    return sorted(pool, key=lambda item: item.score, reverse=True)[0]


def decide_publish(score: float, publish_threshold: float = 85.0, draft_threshold: float = 70.0) -> PublishDecision:
    if score >= publish_threshold:
        return PublishDecision.PUBLISH
    if score >= draft_threshold:
        return PublishDecision.DRAFT
    return PublishDecision.BLOCK


def composite_quality_score(scores: dict[str, float]) -> float:
    weights = {
        "content": 0.20,
        "seo": 0.28,
        "technical": 0.12,
        "schema": 0.08,
        "geo": 0.10,
        "readability": 0.12,
        "human_quality": 0.07,
        "yoast_copywriting": 0.03,
    }
    total = 0.0
    weight_total = 0.0
    for key, weight in weights.items():
        if key in scores:
            total += scores[key] * weight
            weight_total += weight
    if weight_total == 0:
        return 0.0
    return round(total / weight_total, 1)


def build_audit(score: float, issues: list[str], warnings: list[str], sources: list[str], publish_threshold: float, draft_threshold: float, details: dict | None = None) -> AuditReport:
    return AuditReport(
        score=score,
        decision=decide_publish(score, publish_threshold, draft_threshold),
        issues=issues,
        warnings=warnings,
        sources=sources,
        details=details or {},
    )
