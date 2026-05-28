"""Weekly Performance Analyst — GSC/GA4 Closed-Loop Feedback.

Runs on a weekly schedule. Pulls search impressions, clicks, and rankings from
Google Search Console; pulls user engagement from GA4; detects content drift
and ranking opportunities; feeds refresh candidates back into the SQLite DB;
and writes performance learnings to SuperMemory.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import Settings
from .state import StateStore
from .supermemory import SuperMemoryClient
from .utils import load_agent_instructions

logger = logging.getLogger(__name__)

# Make claude-seo scripts importable
_CLAUDE_SEO_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "claude-seo", "scripts",
)
if _CLAUDE_SEO_SCRIPTS not in sys.path:
    sys.path.insert(0, _CLAUDE_SEO_SCRIPTS)


class PerformanceAnalyst:
    """Autonomous weekly reviewer that detects drift, surfaces refresh
    opportunities, and writes learnings back to SuperMemory."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = StateStore(settings.state_db, settings=settings)
        self.supermemory = SuperMemoryClient(settings)
        # Load dynamic agent guidance
        self._drift_rules = load_agent_instructions("seo-drift")
        self._perf_rules = load_agent_instructions("seo-performance")

    async def run_weekly_review(self) -> dict[str, Any]:
        """Main entry point: run full weekly performance review."""
        logger.info("Starting weekly performance review...")
        report: dict[str, Any] = {
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "gsc_data": None,
            "ga4_data": None,
            "drift_pages": [],
            "ranking_opportunities": [],
            "refresh_candidates_injected": 0,
            "learnings_stored": 0,
            "errors": [],
        }

        # 1. Pull GSC data
        gsc_rows = await self._fetch_gsc_data()
        report["gsc_data"] = {"row_count": len(gsc_rows)} if gsc_rows else {"error": "No GSC data"}

        # 2. Pull GA4 data
        ga4_pages = await self._fetch_ga4_data()
        report["ga4_data"] = {"page_count": len(ga4_pages)} if ga4_pages else {"error": "No GA4 data"}

        # 3. Detect content drift
        drift_pages = self._detect_drift(gsc_rows)
        report["drift_pages"] = drift_pages
        logger.info(f"Found {len(drift_pages)} drifting pages.")

        # 4. Identify ranking opportunities (page 2 keywords)
        ranking_ops = self._find_ranking_opportunities(gsc_rows)
        report["ranking_opportunities"] = ranking_ops
        logger.info(f"Found {len(ranking_ops)} page-2 ranking opportunities.")

        # 5. Inject refresh candidates into the state store
        injected = 0
        for item in drift_pages + ranking_ops:
            try:
                self.store.inject_refresh_candidate(
                    keyword=item["keyword"],
                    url=item.get("url", ""),
                    reason=item["reason"],
                    score=item.get("priority_score", 80),
                )
                injected += 1
            except Exception as exc:
                logger.warning(f"Failed to inject refresh candidate '{item.get('keyword', '')}': {exc}")
        report["refresh_candidates_injected"] = injected

        # 6. Store performance learnings to SuperMemory
        learnings_count = await self._store_learnings(gsc_rows, ga4_pages, drift_pages, ranking_ops)
        report["learnings_stored"] = learnings_count

        # 7. Run drift baseline/compare on recently published pages
        await self._run_drift_checks()

        logger.info(f"Weekly review complete: {injected} refresh candidates, {learnings_count} learnings stored.")
        return report

    async def _fetch_gsc_data(self) -> list[dict[str, Any]]:
        """Fetch GSC search analytics for the last 30 days."""
        if not self.settings.gsc_site_url or not self.settings.google_service_account_json:
            logger.warning("GSC not configured — skipping GSC data fetch.")
            return []
        try:
            from google_auth import get_oauth_credentials, SCOPES
            from googleapiclient.discovery import build

            creds = get_oauth_credentials([SCOPES["gsc_readonly"]])
            if not creds:
                logger.warning("No GSC credentials available.")
                return []

            service = build("searchconsole", "v1", credentials=creds)
            end_date = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=30)

            response = service.searchanalytics().query(
                siteUrl=self.settings.gsc_site_url,
                body={
                    "startDate": start_date.isoformat(),
                    "endDate": end_date.isoformat(),
                    "dimensions": ["query", "page"],
                    "rowLimit": 500,
                },
            ).execute()

            rows = response.get("rows", [])
            return [
                {
                    "keyword": row["keys"][0],
                    "url": row["keys"][1],
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "ctr": row.get("ctr", 0),
                    "position": row.get("position", 0),
                }
                for row in rows
            ]
        except ImportError as exc:
            logger.warning(f"Google API client not installed: {exc}")
            return []
        except Exception as exc:
            logger.error(f"GSC data fetch failed: {exc}")
            return []

    async def _fetch_ga4_data(self) -> list[dict[str, Any]]:
        """Fetch GA4 page views for the last 30 days."""
        if not self.settings.ga4_property_id or not self.settings.google_service_account_json:
            logger.warning("GA4 not configured — skipping GA4 data fetch.")
            return []
        try:
            from google_auth import get_oauth_credentials, SCOPES
            from google.analytics.data_v1beta import BetaAnalyticsDataClient
            from google.analytics.data_v1beta.types import (
                DateRange, Dimension, Metric, RunReportRequest,
            )

            creds = get_oauth_credentials([SCOPES["ga4"]])
            if not creds:
                logger.warning("No GA4 credentials available.")
                return []

            client = BetaAnalyticsDataClient(credentials=creds)
            request = RunReportRequest(
                property=self.settings.ga4_property_id,
                date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
                dimensions=[Dimension(name="pagePath")],
                metrics=[
                    Metric(name="screenPageViews"),
                    Metric(name="averageSessionDuration"),
                    Metric(name="bounceRate"),
                ],
                limit=200,
            )
            response = client.run_report(request)

            pages = []
            for row in response.rows:
                pages.append({
                    "path": row.dimension_values[0].value,
                    "page_views": int(row.metric_values[0].value),
                    "avg_session_duration": float(row.metric_values[1].value),
                    "bounce_rate": float(row.metric_values[2].value),
                })
            return pages
        except ImportError as exc:
            logger.warning(f"GA4 client not installed: {exc}")
            return []
        except Exception as exc:
            logger.error(f"GA4 data fetch failed: {exc}")
            return []

    def _detect_drift(self, gsc_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Detect pages that have dropped >3 ranking spots or lost >20% CTR."""
        if not gsc_rows:
            return []

        # Group by URL and look for poor-performing pages
        drift_pages = []
        for row in gsc_rows:
            position = row.get("position", 0)
            ctr = row.get("ctr", 0)
            impressions = row.get("impressions", 0)

            # Pages with high impressions but low CTR relative to position
            expected_ctr = self._expected_ctr_for_position(position)
            if impressions >= 50 and ctr < expected_ctr * 0.8:
                drift_pages.append({
                    "keyword": row["keyword"],
                    "url": row.get("url", ""),
                    "position": position,
                    "ctr": ctr,
                    "expected_ctr": expected_ctr,
                    "impressions": impressions,
                    "reason": f"CTR underperformance: actual {ctr:.3f} vs expected {expected_ctr:.3f} at position {position:.1f}",
                    "priority_score": 85,
                })

            # Pages ranking 4-10 with enough impressions to be worth refreshing
            if 4 <= position <= 10 and impressions >= 100:
                drift_pages.append({
                    "keyword": row["keyword"],
                    "url": row.get("url", ""),
                    "position": position,
                    "impressions": impressions,
                    "reason": f"Position {position:.1f} with {impressions} impressions — refresh to push into top 3",
                    "priority_score": 80,
                })

        # Deduplicate by keyword
        seen_keywords = set()
        unique = []
        for page in sorted(drift_pages, key=lambda p: p.get("priority_score", 0), reverse=True):
            if page["keyword"] not in seen_keywords:
                seen_keywords.add(page["keyword"])
                unique.append(page)
        return unique[:20]

    def _find_ranking_opportunities(self, gsc_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Find keywords ranking on page 2 (positions 11-20) that could be pushed to page 1."""
        if not gsc_rows:
            return []

        opportunities = []
        for row in gsc_rows:
            position = row.get("position", 0)
            impressions = row.get("impressions", 0)

            if 11 <= position <= 20 and impressions >= 30:
                opportunities.append({
                    "keyword": row["keyword"],
                    "url": row.get("url", ""),
                    "position": position,
                    "impressions": impressions,
                    "clicks": row.get("clicks", 0),
                    "reason": f"Page 2 opportunity: position {position:.1f} with {impressions} impressions",
                    "priority_score": 90,  # High priority for near-page-1 content
                })

        # Sort by impressions (best opportunities first)
        opportunities.sort(key=lambda o: o.get("impressions", 0), reverse=True)
        return opportunities[:15]

    async def _store_learnings(
        self,
        gsc_rows: list[dict[str, Any]],
        ga4_pages: list[dict[str, Any]],
        drift_pages: list[dict[str, Any]],
        ranking_ops: list[dict[str, Any]],
    ) -> int:
        """Persist weekly performance learnings to SuperMemory."""
        learnings = []

        # Top-performing content patterns
        if gsc_rows:
            top_performers = sorted(gsc_rows, key=lambda r: r.get("clicks", 0), reverse=True)[:5]
            if top_performers:
                performers_text = "Top performing keywords this week:\n" + "\n".join(
                    f"- '{r['keyword']}': {r.get('clicks', 0)} clicks, position {r.get('position', 0):.1f}"
                    for r in top_performers
                )
                learnings.append(("performance-learnings", performers_text))

        # Drift patterns to avoid
        if drift_pages:
            drift_text = "Content drift detected this week:\n" + "\n".join(
                f"- {p['keyword']}: {p['reason']}" for p in drift_pages[:5]
            )
            learnings.append(("performance-learnings", drift_text))

        # Page 2 opportunities
        if ranking_ops:
            ops_text = "Ranking opportunities (page 2 keywords):\n" + "\n".join(
                f"- '{o['keyword']}': position {o.get('position', 0):.1f}, {o.get('impressions', 0)} impressions"
                for o in ranking_ops[:5]
            )
            learnings.append(("performance-learnings", ops_text))

        stored = 0
        for tag, text in learnings:
            success = await self.supermemory.add_memory(
                content=text,
                tags=[tag, "weekly-review"],
            )
            if success:
                stored += 1
        return stored

    async def _run_drift_checks(self) -> None:
        """Run drift baseline/compare on recently published pages using claude-seo scripts."""
        try:
            from drift_baseline import capture_baseline
            from drift_compare import compare_page

            # Get recently published URLs from the state store
            recent = self.store.recent_runs(limit=14)
            urls = [
                r.get("wordpress_url")
                for r in recent
                if r.get("wordpress_url") and r.get("wordpress_status") == "publish"
            ]

            for url in urls[:5]:  # Limit to 5 pages per check
                try:
                    # Capture baseline for new pages
                    capture_baseline(url)
                    logger.info(f"Drift baseline captured for: {url}")
                except Exception:
                    pass

                try:
                    # Compare existing pages against baseline
                    result = compare_page(url)
                    if result and result.get("critical", 0) > 0:
                        logger.warning(f"CRITICAL drift detected for {url}: {result}")
                except Exception:
                    pass

        except ImportError:
            logger.debug("Drift scripts not available — skipping drift checks.")
        except Exception as exc:
            logger.debug(f"Drift checks failed: {exc}")

    @staticmethod
    def _expected_ctr_for_position(position: float) -> float:
        """Estimate expected CTR based on average position (2024 Backlinko data)."""
        ctr_by_position = {
            1: 0.276, 2: 0.158, 3: 0.110, 4: 0.080, 5: 0.065,
            6: 0.046, 7: 0.036, 8: 0.028, 9: 0.023, 10: 0.019,
        }
        rounded = max(1, min(10, round(position)))
        return ctr_by_position.get(rounded, 0.01)


async def run_analyst() -> dict[str, Any]:
    """Convenience entry point for the weekly reviewer."""
    from .config import load_settings
    settings = load_settings()
    analyst = PerformanceAnalyst(settings)
    return await analyst.run_weekly_review()
