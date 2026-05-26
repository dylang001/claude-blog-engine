from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from .config import Settings
from .data_sources import OpportunityCollector
from .google_auth import GA4_SCOPE, GSC_SCOPE, get_google_credentials
from .research import ResearchEngine
from .schema_intelligence import schema_improvement_report
from .scoring import choose_opportunity
from .wordpress import WordPressClient


class DiscoveryReporter:
    """Runs the research/discovery pass without generating or publishing content."""

    claude_seo_sources = [
        "dylang001/claude-seo:README.md",
        "vendor/claude-seo/gsc_query.py",
        "vendor/claude-seo/ga4_report.py",
        "vendor/claude-seo/pagespeed_check.py",
        "vendor/claude-seo/schema-templates.json",
    ]

    def __init__(self, settings: Settings):
        self.settings = settings
        self.collector = OpportunityCollector(settings)
        self.researcher = ResearchEngine(self.collector.dataforseo)
        self.wordpress = WordPressClient(settings)

    async def run(self, limit: int = 5, days: int = 28, strict: bool = False) -> dict[str, Any]:
        started_at = datetime.now(timezone.utc)
        opportunities = await self.collector.collect(strict=strict)
        ranked = sorted(opportunities, key=lambda item: item.score, reverse=True)
        selected = choose_opportunity(ranked)

        briefs = []
        for opportunity in ranked[:limit]:
            brief = await self.researcher.brief(opportunity, strict=strict)
            briefs.append(
                {
                    "opportunity": asdict(opportunity),
                    "serp_summary": _summarize_serp(brief.get("serp", {})),
                    "requirements": brief.get("requirements", []),
                }
            )

        internal_links = await self._internal_links(strict=strict)
        claude_seo = await self._claude_seo_signals(days=days)
        if strict:
            _require_strict_discovery(claude_seo, internal_links)
        report = {
            "generated_at": started_at.isoformat(),
            "site": {
                "brand": self.settings.site.brand_name,
                "site_url": self.settings.site.site_url,
                "wordpress_base_url": self.settings.wp_base_url,
            },
            "fallbacks_allowed": not strict,
            "selected_opportunity": asdict(selected),
            "opportunities": [asdict(item) for item in ranked[:limit]],
            "research_briefs": briefs,
            "internal_links": internal_links,
            "claude_seo": claude_seo,
            "schema_improvements": schema_improvement_report(internal_links, claude_seo),
            "next_actions": _next_actions(ranked[:limit], claude_seo),
        }
        saved = self.save_report(report)
        report["saved_report"] = str(saved)
        return report

    def save_report(self, report: dict[str, Any]) -> Path:
        reports_dir = self.settings.data_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        path = reports_dir / f"discovery-{stamp}.json"
        path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        return path

    async def _internal_links(self, strict: bool = False) -> list[dict[str, str]]:
        try:
            return await self.wordpress.internal_link_candidates(limit=30)
        except Exception as exc:
            if strict:
                raise RuntimeError(f"WordPress internal-link collection failed: {exc}") from exc
            return [{"error": str(exc)}]

    async def _claude_seo_signals(self, days: int) -> dict[str, Any]:
        site_url = self.settings.site.site_url or self.settings.wp_base_url
        return {
            "source": "dylang001/claude-seo",
            "source_files": self.claude_seo_sources,
            "technical": await self._technical_checks(site_url),
            "pagespeed": await self._pagespeed(site_url),
            "gsc": await self._gsc(days),
            "ga4": await self._ga4(days),
            "schema_templates_available": self._schema_templates_available(),
        }

    async def _technical_checks(self, site_url: str) -> dict[str, Any]:
        if not site_url:
            return {"ok": False, "error": "site_url is not configured"}
        base = site_url.rstrip("/")
        checks: dict[str, Any] = {}
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for name, url in {
                "home": base,
                "robots": f"{base}/robots.txt",
                "sitemap": f"{base}/sitemap_index.xml",
            }.items():
                try:
                    resp = await client.get(url)
                    checks[name] = {
                        "url": url,
                        "status": resp.status_code,
                        "content_type": resp.headers.get("content-type", ""),
                        "ok": 200 <= resp.status_code < 400,
                    }
                except Exception as exc:
                    checks[name] = {"url": url, "ok": False, "error": str(exc)}
        return {"ok": all(item.get("ok") for item in checks.values()), "checks": checks}

    async def _pagespeed(self, site_url: str) -> dict[str, Any]:
        if not site_url:
            return {"ok": False, "error": "site_url is not configured"}
        params = {
            "url": site_url,
            "strategy": "mobile",
            "category": ["PERFORMANCE", "SEO", "ACCESSIBILITY", "BEST_PRACTICES"],
        }
        if self.settings.pagespeed_api_key:
            params["key"] = self.settings.pagespeed_api_key
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed", params=params)
            if resp.status_code >= 400:
                return {"ok": False, "status": resp.status_code, "error": resp.text[:500]}
            data = resp.json()
            lighthouse = data.get("lighthouseResult", {})
            categories = lighthouse.get("categories", {})
            return {
                "ok": True,
                "status": resp.status_code,
                "auth_mode": "api_key" if self.settings.pagespeed_api_key else "unauthenticated",
                "analysis_timestamp": data.get("analysisUTCTimestamp"),
                "scores": {key: round(value.get("score", 0) * 100) for key, value in categories.items()},
                "core_web_vitals": _extract_pagespeed_cwv(data),
                "source_script": "vendor/claude-seo/pagespeed_check.py",
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc), "source_script": "vendor/claude-seo/pagespeed_check.py"}

    async def _gsc(self, days: int) -> dict[str, Any]:
        try:
            rows, auth_mode = await _run_gsc_query(self.settings, days)
            return {
                "ok": True,
                "auth_mode": auth_mode,
                "row_count": len(rows),
                "top_rows": rows[:20],
                "quick_wins": _gsc_quick_wins(rows),
                "source_script": "vendor/claude-seo/gsc_query.py",
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc), "diagnosis": _google_error_diagnosis(str(exc), "gsc"), "source_script": "vendor/claude-seo/gsc_query.py"}

    async def _ga4(self, days: int) -> dict[str, Any]:
        try:
            report = await _run_ga4_report(self.settings, days)
            report["ok"] = True
            report["source_script"] = "vendor/claude-seo/ga4_report.py"
            return report
        except Exception as exc:
            return {"ok": False, "error": str(exc), "diagnosis": _google_error_diagnosis(str(exc), "ga4"), "source_script": "vendor/claude-seo/ga4_report.py"}

    def _schema_templates_available(self) -> bool:
        return (Path(self.settings.root_dir) / "vendor" / "claude-seo" / "schema-templates.json").exists()


def _summarize_serp(serp: dict[str, Any]) -> dict[str, Any]:
    if serp.get("error"):
        return {"ok": False, "error": serp["error"]}
    items: list[dict[str, Any]] = []
    for task in serp.get("tasks", []):
        for result in task.get("result") or []:
            for item in result.get("items") or []:
                if item.get("type") == "organic":
                    items.append(
                        {
                            "rank": item.get("rank_group") or item.get("rank_absolute"),
                            "title": item.get("title"),
                            "url": item.get("url"),
                            "domain": item.get("domain"),
                        }
                    )
    return {"ok": True, "organic_count": len(items), "top_results": items[:10]}


def _next_actions(opportunities: list[Any], claude_seo: dict[str, Any]) -> list[str]:
    actions = []
    if opportunities:
        actions.append(f"Prioritize `{opportunities[0].keyword}` as the next content opportunity unless GSC quick wins outrank it.")
    quick_wins = claude_seo.get("gsc", {}).get("quick_wins") or []
    if quick_wins:
        actions.append("Refresh existing pages with high impressions in positions 4-10 before adding more net-new content.")
    if not claude_seo.get("pagespeed", {}).get("ok"):
        actions.append("Resolve PageSpeed data access before relying on Core Web Vitals scoring.")
    if not claude_seo.get("ga4", {}).get("ok"):
        diagnosis = claude_seo.get("ga4", {}).get("diagnosis")
        actions.append(diagnosis or "Resolve GA4 access so discovery can rank content by organic traffic impact.")
    if not claude_seo.get("gsc", {}).get("ok"):
        diagnosis = claude_seo.get("gsc", {}).get("diagnosis")
        actions.append(diagnosis or "Resolve GSC access so discovery can rank refresh opportunities from search performance.")
    actions.append("Use the internal link candidates in the next writer run to strengthen topical authority.")
    return actions


def _require_strict_discovery(claude_seo: dict[str, Any], internal_links: list[dict[str, str]]) -> None:
    if any("error" in item for item in internal_links):
        raise RuntimeError(f"Strict discovery failed while collecting internal links: {internal_links}")
    required = ["technical", "pagespeed", "gsc", "ga4"]
    failed = {name: claude_seo.get(name) for name in required if not claude_seo.get(name, {}).get("ok")}
    if failed:
        raise RuntimeError(f"Strict discovery failed while collecting claude-seo signals: {failed}")
    if not claude_seo.get("schema_templates_available"):
        raise RuntimeError("Strict discovery failed because claude-seo schema templates are unavailable.")


async def _run_gsc_query(settings: Settings, days: int) -> tuple[list[dict[str, Any]], str]:
    from googleapiclient.discovery import build

    if not settings.gsc_site_url:
        raise RuntimeError("GSC_SITE_URL is not configured")
    credentials, auth_mode = get_google_credentials(settings, [GSC_SCOPE])
    service = build("searchconsole", "v1", credentials=credentials, cache_discovery=False)
    end = (datetime.now(timezone.utc) - timedelta(days=3)).date().isoformat()
    start = (datetime.now(timezone.utc) - timedelta(days=days + 3)).date().isoformat()
    body = {
        "startDate": start,
        "endDate": end,
        "dimensions": ["query", "page"],
        "rowLimit": 100,
        "dataState": "final",
    }
    response = service.searchanalytics().query(siteUrl=settings.gsc_site_url, body=body).execute()
    rows = []
    for row in response.get("rows", []):
        keys = row.get("keys", [])
        rows.append(
            {
                "query": keys[0] if len(keys) > 0 else "",
                "page": keys[1] if len(keys) > 1 else "",
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": round(row.get("ctr", 0) * 100, 2),
                "position": round(row.get("position", 0), 1),
            }
        )
    return sorted(rows, key=lambda item: item["impressions"], reverse=True), auth_mode


async def _run_ga4_report(settings: Settings, days: int) -> dict[str, Any]:
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import DateRange, Dimension, Filter, FilterExpression, Metric, OrderBy, RunReportRequest
    if not settings.ga4_property_id:
        raise RuntimeError("GA4_PROPERTY_ID is not configured")
    credentials, auth_mode = get_google_credentials(settings, [GA4_SCOPE])
    client = BetaAnalyticsDataClient(credentials=credentials)
    prop = settings.ga4_property_id if settings.ga4_property_id.startswith("properties/") else f"properties/{settings.ga4_property_id}"
    start = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    end = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
    request = RunReportRequest(
        property=prop,
        dimensions=[Dimension(name="landingPage")],
        metrics=[Metric(name="sessions"), Metric(name="totalUsers"), Metric(name="screenPageViews"), Metric(name="engagementRate")],
        date_ranges=[DateRange(start_date=start, end_date=end)],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
        limit=50,
    )
    response = client.run_report(request)
    pages = []
    totals = {"sessions": 0, "users": 0, "pageviews": 0}
    for row in response.rows:
        sessions = int(row.metric_values[0].value)
        users = int(row.metric_values[1].value)
        pageviews = int(row.metric_values[2].value)
        pages.append(
            {
                "landing_page": row.dimension_values[0].value,
                "sessions": sessions,
                "users": users,
                "pageviews": pageviews,
                "engagement_rate": round(float(row.metric_values[3].value) * 100, 1),
            }
        )
        totals["sessions"] += sessions
        totals["users"] += users
        totals["pageviews"] += pageviews
    return {"property": prop, "auth_mode": auth_mode, "date_range": {"start": start, "end": end}, "totals": totals, "top_pages": pages}


def _gsc_quick_wins(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wins = [
        {
            **row,
            "opportunity": "Position 4-10 with impressions; refresh content, improve title/meta, and add internal links.",
        }
        for row in rows
        if 4 <= float(row.get("position", 0)) <= 10 and int(row.get("impressions", 0)) >= 25
    ]
    return wins[:20]


def _google_error_diagnosis(error: str, service: str) -> str:
    lowered = error.lower()
    if "insufficient authentication scopes" in lowered or "insufficient permission" in lowered:
        if service == "gsc":
            return "Re-run `python -m content_machine google-auth` and confirm Google grants the Search Console scope; the cached OAuth token currently lacks webmasters.readonly."
        return "Re-run `python -m content_machine google-auth` and confirm Google grants the Analytics readonly scope."
    if "accessnotconfigured" in lowered or "service_disabled" in lowered or "has not been used" in lowered:
        if service == "gsc":
            return "Enable the Google Search Console API in the selected Google Cloud project, then retry after propagation."
        return "Enable the Google Analytics Data API in the selected Google Cloud project, then retry after propagation."
    if "sufficient permission" in lowered or "forbidden" in lowered:
        if service == "gsc":
            return "Use a GSC property your OAuth user owns, e.g. sc-domain:meetlyra.app, or add dylanangloher@gmail.com to the exact Search Console property."
        return "Add dylanangloher@gmail.com to the GA4 property access management with Viewer or Analyst access, and confirm GA4_PROPERTY_ID is the numeric property ID."
    return "Review Google API credentials, property ID, and account permissions."


def _extract_pagespeed_cwv(data: dict[str, Any]) -> dict[str, Any]:
    lighthouse = data.get("lighthouseResult", {})
    audits = lighthouse.get("audits", {})
    metric_ids = {
        "largest-contentful-paint": "LCP",
        "interactive": "TTI",
        "total-blocking-time": "TBT",
        "cumulative-layout-shift": "CLS",
        "first-contentful-paint": "FCP",
        "speed-index": "Speed Index",
    }
    metrics = {}
    for audit_id, label in metric_ids.items():
        audit = audits.get(audit_id, {})
        if audit:
            metrics[audit_id] = {
                "label": label,
                "display": audit.get("displayValue", ""),
                "score": audit.get("score"),
                "numeric_value": audit.get("numericValue"),
            }
    return metrics
