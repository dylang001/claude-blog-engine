from __future__ import annotations

import json
import uuid
from dataclasses import asdict, replace
from datetime import datetime, timezone

from .anthropic_writer import ContentWriter
from .content_optimizer import optimize_content
from .config import Settings
from .data_sources import OpportunityCollector
from .images import BananaImageGenerator
from .indexnow import IndexNowClient
from .models import PipelineResult, PublishDecision
from .research import ResearchEngine
from .scoring import choose_opportunity
from .seo_audit import SEOAuditEngine
from .state import StateStore
from .wordpress import WordPressClient


class ContentMachine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = StateStore(settings.state_db)
        self.collector = OpportunityCollector(settings)
        self.researcher = ResearchEngine(self.collector.dataforseo)
        self.writer = ContentWriter(settings)
        self.images = BananaImageGenerator(settings)
        self.auditor = SEOAuditEngine(settings)
        self.wordpress = WordPressClient(settings)
        self.indexnow = IndexNowClient(settings)

    async def run_once(self, dry_run: bool | None = None) -> PipelineResult:
        started_at = datetime.now(timezone.utc).isoformat()
        run_id = str(uuid.uuid4())
        is_dry_run = self.settings.dry_run_default if dry_run is None else dry_run

        candidates = await self.collector.collect()
        opportunity = choose_opportunity(candidates, self.store.seen_keywords())
        research = await self.researcher.brief(opportunity)
        research = await self._enrich_research_with_internal_links(research)
        content = await self.writer.generate(opportunity, research)
        content = optimize_content(content, opportunity)
        content = await self.images.maybe_generate(content, run_id)
        audit = self.auditor.audit(content, opportunity, research)
        best_content = content
        best_audit = audit
        repair_attempts = 0
        while audit.decision != PublishDecision.PUBLISH and audit.details.get("repairable", True) and repair_attempts < 2:
            repair_attempts += 1
            candidate_content = await self.writer.repair(content, opportunity, research, audit)
            candidate_content = optimize_content(candidate_content, opportunity)
            candidate_content = await self.images.maybe_generate(candidate_content, run_id)
            candidate_audit = self.auditor.audit(candidate_content, opportunity, research)
            content = candidate_content
            audit = candidate_audit
            if _is_better_audit(candidate_audit, best_audit):
                best_content = candidate_content
                best_audit = candidate_audit

        content = best_content
        audit = best_audit

        wordpress_status = "dry_run"
        wordpress_id = None
        wordpress_url = None
        if not is_dry_run and audit.decision != PublishDecision.BLOCK:
            existing_post_id = opportunity.post_id if opportunity.kind.value == "refresh" else None
            existing_post = None
            if existing_post_id is None:
                existing_post = await self.wordpress.find_post_by_slug(content.slug)
                existing_post_id = existing_post.get("id") if existing_post else None
            if audit.decision == PublishDecision.DRAFT and existing_post and existing_post.get("status") == "publish":
                existing_post_id = None
                content = replace(content, slug=f"{content.slug}-draft-{run_id[:8]}")
            wp_response = await self.wordpress.upsert_post(content, audit.decision, existing_post_id)
            wordpress_status = wp_response.get("status", audit.decision.value)
            wordpress_id = wp_response.get("id")
            wordpress_url = wp_response.get("link")
            if not wordpress_url and isinstance(wp_response.get("guid"), dict):
                wordpress_url = wp_response["guid"].get("rendered")
            if wordpress_status == "publish" and wordpress_url:
                await self.indexnow.submit([wordpress_url])
            self.store.mark_published(
                key=f"{opportunity.kind.value}:{content.slug}",
                kind=opportunity.kind.value,
                keyword=opportunity.keyword,
                run_id=run_id,
                updated_at=datetime.now(timezone.utc).isoformat(),
                wordpress_id=wordpress_id,
                wordpress_url=wordpress_url,
            )
        elif audit.decision == PublishDecision.BLOCK:
            wordpress_status = "blocked"

        result = PipelineResult(
            run_id=run_id,
            dry_run=is_dry_run,
            opportunity=opportunity,
            audit=audit,
            content=content,
            wordpress_status=wordpress_status,
            wordpress_id=wordpress_id,
            wordpress_url=wordpress_url,
        )
        payload = json.loads(json.dumps(asdict(result), default=str))
        payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        self.store.save_run(run_id, started_at, payload)
        return result

    async def _enrich_research_with_internal_links(self, research: dict) -> dict:
        enriched = dict(research or {})
        if enriched.get("internal_links"):
            return enriched
        try:
            links = await self.wordpress.internal_link_candidates(limit=20)
        except Exception:
            links = []
        if links:
            enriched["internal_links"] = links
        return enriched


def _is_better_audit(candidate, current) -> bool:
    if candidate.decision == PublishDecision.PUBLISH and current.decision != PublishDecision.PUBLISH:
        return True
    if candidate.score != current.score:
        return candidate.score > current.score
    if len(candidate.issues) != len(current.issues):
        return len(candidate.issues) < len(current.issues)
    return len(candidate.warnings) < len(current.warnings)
