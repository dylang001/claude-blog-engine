from __future__ import annotations

import json
import uuid
from dataclasses import asdict, replace
from datetime import datetime, timezone

from .anthropic_writer import ContentWriter
from .gemini_writer import GeminiWriter
from .content_optimizer import optimize_content, validate_and_sanitize_content_images
from .config import Settings
from .data_sources import OpportunityCollector
from .images import BananaImageGenerator
from .indexnow import IndexNowClient
from .indexing import GoogleIndexingClient
from .models import PipelineResult, PublishDecision
from .research import ResearchEngine
from .scoring import choose_opportunity
from .seo_audit import SEOAuditEngine
from .state import StateStore
from .wordpress import WordPressClient
from .supermemory import SuperMemoryClient


class ContentMachine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = StateStore(settings.state_db)
        self.collector = OpportunityCollector(settings)
        self.researcher = ResearchEngine(self.collector.dataforseo)
        self.writer = ContentWriter(settings)
        self.gemini_writer = GeminiWriter(settings)
        self.images = BananaImageGenerator(settings)
        self.auditor = SEOAuditEngine(settings)
        self.wordpress = WordPressClient(settings)
        self.indexnow = IndexNowClient(settings)
        self.google_indexing = GoogleIndexingClient(settings)
        self.supermemory = SuperMemoryClient(settings)

    async def run_once(self, dry_run: bool | None = None) -> PipelineResult:
        started_at = datetime.now(timezone.utc).isoformat()
        run_id = str(uuid.uuid4())
        is_dry_run = self.settings.dry_run_default if dry_run is None else dry_run

        try:
            candidates = await self.collector.collect()
            opportunity = choose_opportunity(candidates, self.store.seen_keywords())
            research = await self.researcher.brief(opportunity)
            research = await self._enrich_research_with_internal_links(research)
            
            try:
                import logging
                pipeline_logger = logging.getLogger("content_machine.pipeline")
                pipeline_logger.info("Searching SuperMemory for query: %s", opportunity.keyword)
                sm_results = await self.supermemory.search_memory(opportunity.keyword, limit=5)
                research["supermemory_context"] = sm_results
            except Exception as sm_exc:
                import logging
                pipeline_logger = logging.getLogger("content_machine.pipeline")
                pipeline_logger.error("Failed to query SuperMemory during research: %s", sm_exc)

            content = await self._generate_with_fallback(opportunity, research)
            content = optimize_content(content, opportunity)
            content = await validate_and_sanitize_content_images(content, self.settings)
            content = await self.images.maybe_generate(content, run_id)
            audit = self.auditor.audit(content, opportunity, research)
            best_content = content
            best_audit = audit
            repair_attempts = 0
            while audit.decision != PublishDecision.PUBLISH and audit.details.get("repairable", True) and repair_attempts < 2:
                repair_attempts += 1
                candidate_content = await self._repair_with_fallback(content, opportunity, research, audit)
                candidate_content = optimize_content(candidate_content, opportunity)
                candidate_content = await validate_and_sanitize_content_images(candidate_content, self.settings)
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
                    import logging as _log
                    _pl = _log.getLogger("content_machine.pipeline")

                    # --- IndexNow: notify Bing, Yandex, Seznam, IndexNow network ---
                    indexnow_results = await self.indexnow.submit([wordpress_url])
                    if indexnow_results:
                        for r in indexnow_results:
                            if r.success:
                                _pl.info("IndexNow: %s submitted to %s (%d)", wordpress_url, r.engine, r.status)
                            else:
                                _pl.warning("IndexNow: %s failed for %s — %s", r.engine, wordpress_url, r.message)

                    # --- Google Indexing API: notify Google directly ---
                    try:
                        google_result = await self.google_indexing.notify(wordpress_url, action="URL_UPDATED")
                        if google_result["success"]:
                            _pl.info("Google Indexing API: URL_UPDATED submitted for %s", wordpress_url)
                        else:
                            _pl.warning("Google Indexing API: %s — %s", wordpress_url, google_result.get("error"))
                    except Exception as gi_exc:
                        _pl.error("Google Indexing API exception for %s: %s", wordpress_url, gi_exc)

                    # --- SuperMemory: ingest full article for knowledge graph ---
                    try:
                        await self.supermemory.push_post(content.slug, content.title, wordpress_url, content.body)
                        _pl.info("SuperMemory: article '%s' ingested.", content.slug)
                    except Exception as sm_exc:
                        _pl.error("SuperMemory: push failed for %s — %s", content.slug, sm_exc)
                self.store.mark_published(
                    key=f"{opportunity.kind.value}:{content.slug}",
                    kind=opportunity.kind.value,
                    keyword=opportunity.keyword,
                    run_id=run_id,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    wordpress_id=wordpress_id,
                    wordpress_url=wordpress_url,
                )
                # Auto-trigger outreach campaign for the new article
                try:
                    import logging
                    from .outreach_agent import OutreachAgent
                    pipeline_logger = logging.getLogger("content_machine.pipeline")
                    pipeline_logger.info("Auto-triggering cold email outreach campaign for slug %s...", content.slug)
                    outreach = OutreachAgent(self.settings)
                    await outreach.generate_campaign_for_post(content.slug)
                except Exception as outreach_exc:
                    import logging
                    pipeline_logger = logging.getLogger("content_machine.pipeline")
                    pipeline_logger.error("Failed to auto-trigger outreach campaign for post %s: %s", content.slug, outreach_exc)
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
        except Exception as exc:
            payload = {
                "run_id": run_id,
                "dry_run": is_dry_run,
                "wordpress_status": "failed",
                "error": str(exc),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                if "opportunity" in locals():
                    payload["opportunity"] = asdict(opportunity)
                if "audit" in locals():
                    payload["audit"] = asdict(audit)
            except Exception:
                pass
            self.store.save_run(run_id, started_at, payload)
            raise exc

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

    async def _generate_with_fallback(self, opportunity, research):
        """Try Anthropic first; fall back to Gemini on credit/quota errors."""
        import logging as _log
        _pl = _log.getLogger("content_machine.pipeline")
        try:
            return await self.writer.generate(opportunity, research)
        except RuntimeError as exc:
            if _is_credit_error(str(exc)):
                if self.gemini_writer.is_configured():
                    _pl.warning(
                        "Anthropic credit/quota error — switching to Gemini (%s): %s",
                        self.settings.gemini_writing_model, exc,
                    )
                    return await self.gemini_writer.generate(opportunity, research)
                _pl.error("Anthropic credit error and GEMINI_API_KEY not set — cannot fall back.")
            raise

    async def _repair_with_fallback(self, content, opportunity, research, audit):
        """Try Anthropic repair first; fall back to Gemini on credit/quota errors."""
        import logging as _log
        _pl = _log.getLogger("content_machine.pipeline")
        try:
            return await self.writer.repair(content, opportunity, research, audit)
        except RuntimeError as exc:
            if _is_credit_error(str(exc)):
                if self.gemini_writer.is_configured():
                    _pl.warning(
                        "Anthropic credit/quota error during repair — switching to Gemini (%s): %s",
                        self.settings.gemini_writing_model, exc,
                    )
                    return await self.gemini_writer.repair(content, opportunity, research, audit)
                _pl.error("Anthropic credit error during repair and GEMINI_API_KEY not set.")
            raise


def _is_better_audit(candidate, current) -> bool:
    if candidate.decision == PublishDecision.PUBLISH and current.decision != PublishDecision.PUBLISH:
        return True
    if candidate.score != current.score:
        return candidate.score > current.score
    if len(candidate.issues) != len(current.issues):
        return len(candidate.issues) < len(current.issues)
    return len(candidate.warnings) < len(current.warnings)


def _is_credit_error(message: str) -> bool:
    """Detect Anthropic billing / quota errors that warrant a Gemini fallback."""
    credit_signals = [
        "credit_balance_too_low",
        "insufficient_credits",
        "billing",
        "payment",
        "quota",
        "rate_limit",
        "529",            # Anthropic overloaded HTTP status
        "overloaded",
        "capacity",
    ]
    msg_lower = message.lower()
    return any(signal in msg_lower for signal in credit_signals)
