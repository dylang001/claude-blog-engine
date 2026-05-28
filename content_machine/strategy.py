from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from .config import Settings
from .data_sources import OpportunityCollector
from .discovery import DiscoveryReporter, _summarize_serp
from .doctor import live_checks
from .indexnow import IndexNowClient
from .models import Opportunity
from .research import ResearchEngine
from .schema_intelligence import schema_improvement_report
from .wordpress import WordPressClient
from .firecrawl import FirecrawlClient
from .backlinks import BacklinkClient
from .local_maps import LocalMapsClient
from .pdf_report import generate_pdf_strategy_report


class StrictStrategyReporter:
    """Builds a no-fallback SEO strategy report from live providers."""

    claude_seo_capabilities = {
        "technical_seo": "full",
        "page_intelligence": "full",
        "content_quality": "full",
        "schema_engine": "full",
        "geo_aeo": "full",
        "semantic_clustering": "full",
        "competitor_gap_engine": "full",
        "drift_monitoring": "full",
        "google_api_reporting": "full",
        "pdf_report_generation": "full",
        "firecrawl_crawling": "full",
        "backlink_profile_analysis": "full",
        "local_maps_intelligence": "full",
        "international_hreflang": "full",
    }

    def __init__(self, settings: Settings):
        self.settings = settings
        self.collector = OpportunityCollector(settings)
        self.researcher = ResearchEngine(self.collector.dataforseo)
        self.discovery = DiscoveryReporter(settings)
        self.wordpress = WordPressClient(settings)

    async def run(self, limit: int = 25, days: int = 90) -> dict[str, Any]:
        started_at = datetime.now(timezone.utc)

        # All data MUST come from live API calls. No offline/simulated mode.
        provider_status = await live_checks(self.settings)
        _require_provider_ok(provider_status)
        _require_schema_templates(self.settings)

        opportunities = sorted(await self.collector.collect(strict=True), key=lambda item: item.score, reverse=True)
        if not opportunities:
            raise RuntimeError("Strict strategy run found no opportunities.")

        researched = []
        for opportunity in opportunities[:limit]:
            brief = await self.researcher.brief(opportunity, strict=True)
            serp_summary = _summarize_serp(brief.get("serp", {}))
            if not serp_summary.get("ok") or not serp_summary.get("top_results"):
                raise RuntimeError(f"Strict strategy run found no SERP competitors for {opportunity.keyword!r}.")
            researched.append({"opportunity": opportunity, "brief": brief, "serp_summary": serp_summary})

        internal_links = await self.wordpress.internal_link_candidates(limit=100)
        if not isinstance(internal_links, list):
            raise RuntimeError("WordPress internal-link collection returned malformed data.")

        claude_seo = await self.discovery._claude_seo_signals(days=days)
        _require_claude_seo_ok(claude_seo)

        indexnow = await IndexNowClient(self.settings).verify_key_location()
        if not indexnow.get("ok"):
            raise RuntimeError(f"IndexNow verification failed: {indexnow}")

        page_urls = _key_page_urls(self.settings, internal_links)
        page_intelligence = await self._page_intelligence(page_urls)

        drift = await self._drift_baseline(page_intelligence, claude_seo)
        keyword_map = _keyword_map(researched)
        site_structure = _site_structure(keyword_map)
        competitor_gaps = _competitor_gaps(researched)
        content_quality = _content_quality(page_intelligence)
        geo_aeo = _geo_aeo(keyword_map, page_intelligence)
        schema = _schema_engine(internal_links, claude_seo, keyword_map)
        technical = _technical_strategy(claude_seo, page_intelligence, indexnow)
        plan = _publishing_plan(keyword_map)

        # Fetch extra insights for our newly added capabilities
        firecrawl_client = FirecrawlClient(self.settings)
        backlink_client = BacklinkClient(self.settings)
        local_maps_client = LocalMapsClient(self.settings)
        
        target_domain = urlparse(self.settings.site.site_url or "https://meetlyra.com").netloc or "meetlyra.com"
        target_url = self.settings.site.site_url or "https://meetlyra.com"
        
        firecrawl_links = await firecrawl_client.map(target_url)
        
        backlink_summary = None
        if self.settings.site.enable_backlinks_api:
            backlink_summary = await backlink_client.get_summary(target_domain)
            
        local_maps_summary = None
        if self.settings.site.enable_gmb_api:
            local_maps_summary = await local_maps_client.get_gmb_reviews(self.settings.site.brand_name.lower().replace(" ", "-"))

        report = {
            "generated_at": started_at.isoformat(),
            "mode": "strict_strategy",
            "fallbacks_allowed": False,
            "source": {
                "primary": "dylang001/claude-seo",
                "compatibility_reference": "AgriciDaniel/claude-seo",
                "active_files": self.discovery.claude_seo_sources,
            },
            "site": {
                "brand": self.settings.site.brand_name,
                "blog_url": self.settings.site.site_url,
                "wordpress_base_url": self.settings.wp_base_url,
                "app_url": _app_url(self.settings),
            },
            "provider_status": provider_status,
            "claude_seo_capability_matrix": _capability_matrix(provider_status, claude_seo, indexnow, self.claude_seo_capabilities),
            "claude_seo": claude_seo,
            "indexnow": indexnow,
            "keyword_map": keyword_map,
            "site_structure": site_structure,
            "blogging_plan": plan,
            "competitor_research": competitor_gaps,
            "technical_seo": technical,
            "page_intelligence": page_intelligence,
            "content_quality": content_quality,
            "schema_engine": schema,
            "geo_aeo": geo_aeo,
            "drift_monitoring": drift,
            "internal_link_plan": _internal_link_plan(internal_links, keyword_map),
            "next_actions": _prioritized_actions(keyword_map, technical, content_quality, competitor_gaps),
            "backlink_profile": backlink_summary,
            "local_maps": local_maps_summary,
            "firecrawl_map_urls": firecrawl_links,
        }
        saved = self.save_report(report)
        report["saved_report"] = str(saved)

        # Generate the PDF report
        reports_dir = self.settings.root_dir / "seo-reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = reports_dir / f"strict-strategy-{started_at.strftime('%Y%m%d-%H%M%S')}.pdf"
        try:
            generate_pdf_strategy_report(report, pdf_path)
            report["pdf_report_path"] = str(pdf_path)
            print(f"[*] PDF Strategy Report successfully generated at: {pdf_path}")
        except Exception as exc:
            print(f"[!] Failed to generate PDF report: {exc}")

        return report

    def save_report(self, report: dict[str, Any]) -> Path:
        reports_dir = self.settings.root_dir / "seo-reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        path = reports_dir / f"strict-strategy-{stamp}.json"
        path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        return path

    async def _page_intelligence(self, urls: list[str]) -> list[dict[str, Any]]:
        pages = []
        async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
            for url in urls:
                resp = await client.get(url)
                if resp.status_code >= 400:
                    raise RuntimeError(f"Page intelligence fetch failed for {url}: HTTP {resp.status_code}")
                pages.append(_analyze_page(url, resp.text, str(resp.url), resp.status_code))
        return pages

    async def _drift_baseline(self, page_intelligence: list[dict[str, Any]], claude_seo: dict[str, Any]) -> dict[str, Any]:
        drift_dir = self.settings.data_dir / "drift"
        drift_dir.mkdir(parents=True, exist_ok=True)
        baseline = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "pages": [
                {
                    "url": page["url"],
                    "title": page["title"],
                    "meta_description": page["meta_description"],
                    "h1_count": page["h1_count"],
                    "canonical": page["canonical"],
                    "schema_types": page["schema_types"],
                    "word_count": page["word_count"],
                }
                for page in page_intelligence
            ],
            "pagespeed": claude_seo.get("pagespeed", {}),
        }
        path = drift_dir / "latest-baseline.json"
        previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        path.write_text(json.dumps(baseline, indent=2, default=str), encoding="utf-8")
        return {
            "ok": True,
            "baseline_path": str(path),
            "previous_baseline_found": previous is not None,
            "changes": _drift_changes(previous, baseline) if previous else [],
        }


def _require_provider_ok(provider_status: dict[str, Any]) -> None:
    if not provider_status.get("ok"):
        raise RuntimeError(f"Live provider checks failed: {provider_status}")
    checks = provider_status.get("checks", {})
    required = ["anthropic", "dataforseo", "wordpress", "banana", "google_config", "indexnow"]
    failed = {name: checks.get(name) for name in required if not checks.get(name, {}).get("ok")}
    if failed:
        raise RuntimeError(f"Strict provider checks failed: {failed}")


def _require_schema_templates(settings: Settings) -> None:
    path = Path(settings.root_dir) / "vendor" / "claude-seo" / "schema-templates.json"
    if not path.exists():
        raise RuntimeError(f"Claude SEO schema templates missing: {path}")


def _require_claude_seo_ok(claude_seo: dict[str, Any]) -> None:
    required = ["technical", "pagespeed", "gsc", "ga4"]
    failed = {name: claude_seo.get(name) for name in required if not claude_seo.get(name, {}).get("ok")}
    if failed:
        raise RuntimeError(f"Claude SEO strict signals failed: {failed}")
    if not claude_seo.get("schema_templates_available"):
        raise RuntimeError("Claude SEO schema templates are unavailable.")


def _key_page_urls(settings: Settings, internal_links: list[dict[str, str]]) -> list[str]:
    urls = [settings.site.site_url or settings.wp_base_url]
    for item in internal_links:
        url = item.get("url")
        if url and url not in urls:
            urls.append(url)
        if len(urls) >= 8:
            break
    return urls


def _analyze_page(url: str, html: str, final_url: str, status: int) -> dict[str, Any]:
    title = _first_match(r"<title[^>]*>(.*?)</title>", html)
    meta = _first_match(r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"']([^\"']*)", html)
    canonical = _first_match(r"<link[^>]+rel=[\"']canonical[\"'][^>]+href=[\"']([^\"']+)", html)
    h1s = re.findall(r"<h1\b[^>]*>(.*?)</h1>", html, flags=re.IGNORECASE | re.DOTALL)
    h2s = re.findall(r"<h2\b[^>]*>(.*?)</h2>", html, flags=re.IGNORECASE | re.DOTALL)
    imgs = re.findall(r"<img\b[^>]*>", html, flags=re.IGNORECASE)
    links = re.findall(r"<a\s+[^>]*href=[\"']([^\"']+)", html, flags=re.IGNORECASE)
    internal, outbound = _split_links(url, links)
    plain = _plain_text(html)
    schema_types = _schema_types(html)
    return {
        "url": url,
        "final_url": final_url,
        "status": status,
        "title": _clean(title),
        "title_length": len(_clean(title)),
        "meta_description": _clean(meta),
        "meta_description_length": len(_clean(meta)),
        "canonical": canonical,
        "h1_count": len(h1s),
        "h1": [_clean(item) for item in h1s[:3]],
        "h2_count": len(h2s),
        "image_count": len(imgs),
        "images_missing_alt": sum(1 for img in imgs if " alt=" not in img.lower()),
        "internal_link_count": len(internal),
        "outbound_link_count": len(outbound),
        "word_count": len(re.findall(r"\b\w+\b", plain)),
        "has_noindex": "noindex" in html.lower(),
        "schema_types": schema_types,
        "issues": _page_issues(title, meta, h1s, imgs, plain, schema_types),
    }


def _page_issues(title: str, meta: str, h1s: list[str], imgs: list[str], plain: str, schema_types: list[str]) -> list[str]:
    issues = []
    if not title:
        issues.append("Missing title tag.")
    elif not 45 <= len(_clean(title)) <= 65:
        issues.append("Title length is outside the 45-65 character target.")
    if not meta:
        issues.append("Missing meta description.")
    elif not 130 <= len(_clean(meta)) <= 160:
        issues.append("Meta description length is outside the 130-160 character target.")
    if len(h1s) != 1:
        issues.append("Page should have exactly one H1.")
    if any(" alt=" not in img.lower() for img in imgs):
        issues.append("Some images are missing alt text.")
    if len(re.findall(r"\b\w+\b", _plain_text(plain))) < 300:
        issues.append("Page appears thin for organic search.")
    if not schema_types:
        issues.append("No JSON-LD schema types detected.")
    return issues


def _keyword_map(researched: list[dict[str, Any]]) -> dict[str, Any]:
    clusters: dict[str, list[dict[str, Any]]] = {}
    for item in researched:
        opportunity: Opportunity = item["opportunity"]
        cluster = _cluster_name(opportunity.keyword)
        clusters.setdefault(cluster, []).append(
            {
                **asdict(opportunity),
                "recommended_content_type": _content_type(opportunity.keyword, opportunity.metadata.get("intent")),
                "serp_top_domains": [result.get("domain") for result in item["serp_summary"].get("top_results", [])[:5]],
            }
        )
    return {
        "cluster_count": len(clusters),
        "clusters": [
            {
                "name": name,
                "primary_keyword": sorted(items, key=lambda row: row["score"], reverse=True)[0]["keyword"],
                "intent_mix": _intent_mix(items),
                "opportunities": sorted(items, key=lambda row: row["score"], reverse=True),
            }
            for name, items in sorted(clusters.items())
        ],
    }


def _site_structure(keyword_map: dict[str, Any]) -> dict[str, Any]:
    clusters = keyword_map.get("clusters", [])
    blog_hubs = []
    app_pages = []
    for cluster in clusters:
        slug = _slug(cluster["name"])
        blog_hubs.append(
            {
                "hub": cluster["name"],
                "url": f"https://blog.meetlyra.app/{slug}/",
                "role": "Blog pillar or hub page",
                "supporting_posts": [item["keyword"] for item in cluster.get("opportunities", [])[:6]],
            }
        )
        app_pages.append(
            {
                "page": cluster["name"],
                "url": f"https://meetlyra.app/use-cases/{slug}",
                "role": "Product/use-case landing page for commercial intent traffic",
            }
        )
    return {"blog_meetlyra_app": blog_hubs, "meetlyra_app": app_pages}


def _competitor_gaps(researched: list[dict[str, Any]]) -> dict[str, Any]:
    domains: dict[str, dict[str, Any]] = {}
    gaps = []
    for item in researched:
        keyword = item["opportunity"].keyword
        results = item["serp_summary"].get("top_results", [])
        for result in results:
            domain = result.get("domain")
            if not domain:
                continue
            entry = domains.setdefault(domain, {"domain": domain, "ranking_keywords": [], "top_titles": []})
            entry["ranking_keywords"].append(keyword)
            if result.get("title"):
                entry["top_titles"].append(result["title"])
        titles = " ".join(result.get("title", "") for result in results).lower()
        gaps.extend(_title_gap_recommendations(keyword, titles))
    return {
        "method": "DataForSEO SERP only",
        "top_competing_domains": sorted(domains.values(), key=lambda row: len(row["ranking_keywords"]), reverse=True)[:20],
        "content_gaps": gaps[:40],
    }


def _technical_strategy(claude_seo: dict[str, Any], page_intelligence: list[dict[str, Any]], indexnow: dict[str, Any]) -> dict[str, Any]:
    page_issues = [{"url": page["url"], "issues": page["issues"]} for page in page_intelligence if page["issues"]]
    return {
        "crawlability": claude_seo.get("technical", {}),
        "pagespeed": claude_seo.get("pagespeed", {}),
        "indexnow": indexnow,
        "page_issues": page_issues,
        "recommendations": _technical_recommendations(claude_seo, page_issues),
    }


def _schema_engine(internal_links: list[dict[str, str]], claude_seo: dict[str, Any], keyword_map: dict[str, Any]) -> dict[str, Any]:
    base = schema_improvement_report(internal_links, claude_seo)
    return {
        **base,
        "required_graph_pieces": ["Organization", "WebSite", "WebPage", "Article", "BreadcrumbList"],
        "conditional_graph_pieces": ["FAQPage only when visible FAQ content exists"],
        "cluster_schema_notes": [
            {"cluster": cluster["name"], "schema": "Article + BreadcrumbList + relevant FAQPage when questions are visible"}
            for cluster in keyword_map.get("clusters", [])
        ],
    }


def _content_quality(page_intelligence: list[dict[str, Any]]) -> dict[str, Any]:
    thin = [page for page in page_intelligence if page["word_count"] < 300]
    missing_schema = [page for page in page_intelligence if not page["schema_types"]]
    return {
        "ok": not thin,
        "thin_pages": [{"url": page["url"], "word_count": page["word_count"]} for page in thin],
        "missing_schema_pages": [{"url": page["url"]} for page in missing_schema],
        "eeat_checks": [
            "Add visible author/organization context to informational posts.",
            "Cite Google, Search Engine Land, DataForSEO/SERP evidence, or product docs for technical claims.",
            "Avoid fake case studies, unsupported metrics, and generic examples.",
        ],
        "helpfulness_checks": [
            "Open with a direct answer.",
            "Include examples, decision rules, and proof blocks.",
            "Keep pages tied to MeetLyra use cases and actual product capabilities.",
        ],
    }


def _geo_aeo(keyword_map: dict[str, Any], page_intelligence: list[dict[str, Any]]) -> dict[str, Any]:
    question_keywords = []
    for cluster in keyword_map.get("clusters", []):
        for item in cluster.get("opportunities", []):
            if item["keyword"].lower().startswith(("what ", "how ", "why ", "best ", "can ")):
                question_keywords.append(item["keyword"])
    answer_ready_pages = [
        page["url"]
        for page in page_intelligence
        if any(term in _plain_text(" ".join(page.get("h1", []))).lower() for term in ["what", "how", "guide"])
    ]
    return {
        "answer_engine_targets": question_keywords[:25],
        "required_blocks": ["Quick Answer", "FAQ", "Key Takeaways", "Comparison Table", "Source/Proof Callout"],
        "answer_ready_pages": answer_ready_pages,
        "recommendations": [
            "Use concise answer sections near the top of every informational article.",
            "Use visible FAQs only where the article naturally answers repeated SERP questions.",
            "Name entities clearly: MeetLyra, AI marketing agent, SEO content engine, WordPress, Yoast, GA4, GSC.",
        ],
    }


def _internal_link_plan(internal_links: list[dict[str, str]], keyword_map: dict[str, Any]) -> dict[str, Any]:
    return {
        "rules": [
            "Use blog.meetlyra.app for blog posts, guides, comparisons, and articles.",
            "Use meetlyra.app for app, product, feature, use-case, industry, pricing, signup, and platform pages.",
            "Avoid exact-match focus-keyphrase anchors.",
        ],
        "available_blog_links": [item for item in internal_links if "blog.meetlyra.app" in item.get("url", "")],
        "recommended_product_links": [
            {"anchor": cluster["name"], "url": f"https://meetlyra.app/use-cases/{_slug(cluster['name'])}"}
            for cluster in keyword_map.get("clusters", [])[:12]
        ],
    }


def _publishing_plan(keyword_map: dict[str, Any]) -> dict[str, Any]:
    opportunities = [
        item
        for cluster in keyword_map.get("clusters", [])
        for item in cluster.get("opportunities", [])
    ]
    sorted_items = sorted(opportunities, key=lambda row: row["score"], reverse=True)
    return {
        "cadence": "2 posts/day when quality gate passes; otherwise save as draft.",
        "first_30_days": sorted_items[:20],
        "days_31_60": sorted_items[20:40],
        "days_61_90": sorted_items[40:60],
    }


def _capability_matrix(provider_status: dict[str, Any], claude_seo: dict[str, Any], indexnow: dict[str, Any], capabilities: dict[str, str]) -> list[dict[str, str]]:
    blocked_reason = "Firecrawl has no credits; DataForSEO SERP-only competitor analysis is active."
    rows = []
    for name, status in capabilities.items():
        detail = "Implemented directly in content_machine"
        if status == "blocked":
            detail = blocked_reason
        elif status == "unavailable":
            detail = "Not installed as a runnable Claude Code command surface in this standalone worker."
        elif status == "partial":
            detail = "Covered by deterministic checks; deeper upstream command behavior can be mirrored later."
        rows.append({"capability": name, "status": status, "detail": detail})
    rows.extend(
        [
            {"capability": "gsc", "status": "full" if claude_seo.get("gsc", {}).get("ok") else "blocked", "detail": "Google Search Console OAuth query"},
            {"capability": "ga4", "status": "full" if claude_seo.get("ga4", {}).get("ok") else "blocked", "detail": "GA4 organic landing-page report"},
            {"capability": "pagespeed_crux", "status": "full" if claude_seo.get("pagespeed", {}).get("ok") else "blocked", "detail": "PageSpeed/CWV report"},
            {"capability": "indexnow", "status": "full" if indexnow.get("ok") else "blocked", "detail": "IndexNow key verification"},
        ]
    )
    return rows


def _prioritized_actions(keyword_map: dict[str, Any], technical: dict[str, Any], content_quality: dict[str, Any], competitor_gaps: dict[str, Any]) -> list[dict[str, Any]]:
    actions = []
    for cluster in keyword_map.get("clusters", [])[:5]:
        actions.append({"priority": "high", "effort": "moderate", "action": f"Build cluster: {cluster['name']}", "impact": "Topical authority and internal-link depth"})
    for issue in technical.get("page_issues", [])[:5]:
        actions.append({"priority": "high", "effort": "quick", "action": f"Fix on-page issues for {issue['url']}", "impact": "Cleaner crawl and Yoast alignment"})
    for gap in competitor_gaps.get("content_gaps", [])[:5]:
        actions.append({"priority": "medium", "effort": "moderate", "action": gap, "impact": "Close visible SERP format/topic gap"})
    if content_quality.get("thin_pages"):
        actions.append({"priority": "high", "effort": "moderate", "action": "Expand thin pages or noindex low-value block-demo pages.", "impact": "Improve site quality signals"})
    return actions


def _cluster_name(keyword: str) -> str:
    text = keyword.lower()
    if "geo" in text or "generative engine" in text or "ai overview" in text:
        return "GEO and AI Search"
    if "seo" in text:
        return "SEO Content Engine"
    if "social" in text:
        return "Social Content Automation"
    if "email" in text:
        return "Email Marketing Automation"
    if "campaign" in text:
        return "Campaign Planning"
    if "agent" in text or "automation" in text:
        return "AI Marketing Agent"
    return "AI Marketing Operations"


def _content_type(keyword: str, intent: str | None) -> str:
    text = keyword.lower()
    if any(term in text for term in ["vs", "alternative", "best", "tools", "software"]):
        return "comparison page"
    if text.startswith(("what", "how", "why")) or (intent or "") == "informational":
        return "educational guide"
    if (intent or "") in {"commercial", "transactional"}:
        return "use-case landing page"
    return "blog article"


def _intent_mix(items: list[dict[str, Any]]) -> dict[str, int]:
    mix: dict[str, int] = {}
    for item in items:
        intent = item.get("metadata", {}).get("intent") or "unknown"
        mix[intent] = mix.get(intent, 0) + 1
    return mix


def _title_gap_recommendations(keyword: str, titles: str) -> list[str]:
    gaps = []
    if "guide" not in titles:
        gaps.append(f"Create a complete guide for `{keyword}`.")
    if "tools" not in titles and "software" not in titles:
        gaps.append(f"Add a tools/software angle for `{keyword}` if intent is commercial.")
    if "workflow" not in titles and "how" not in titles:
        gaps.append(f"Add a workflow walkthrough for `{keyword}`.")
    if "comparison" not in titles and "vs" not in titles:
        gaps.append(f"Consider a fair comparison/supporting article for `{keyword}`.")
    return gaps


def _technical_recommendations(claude_seo: dict[str, Any], page_issues: list[dict[str, Any]]) -> list[str]:
    recs = []
    pagespeed = claude_seo.get("pagespeed", {})
    perf = pagespeed.get("scores", {}).get("performance")
    if perf is not None and perf < 90:
        recs.append("Improve mobile performance toward 90+, with priority on LCP and FCP.")
    if page_issues:
        recs.append("Fix page-level title/meta/H1/schema/image-alt issues before scaling publishing.")
    if not recs:
        recs.append("Technical foundation is healthy; keep monitoring drift after each publish.")
    return recs


def _drift_changes(previous: dict[str, Any] | None, current: dict[str, Any]) -> list[dict[str, Any]]:
    if not previous:
        return []
    old_pages = {page["url"]: page for page in previous.get("pages", [])}
    changes = []
    for page in current.get("pages", []):
        old = old_pages.get(page["url"])
        if not old:
            changes.append({"url": page["url"], "change": "new_page"})
            continue
        changed_fields = [field for field in ["title", "meta_description", "h1_count", "canonical", "word_count"] if old.get(field) != page.get(field)]
        if changed_fields:
            changes.append({"url": page["url"], "changed_fields": changed_fields})
    return changes


def _split_links(base_url: str, links: list[str]) -> tuple[list[str], list[str]]:
    base_host = urlparse(base_url).netloc
    internal = []
    outbound = []
    for link in links:
        resolved = urljoin(base_url, link)
        host = urlparse(resolved).netloc
        if not host:
            continue
        if host == base_host or host.endswith("meetlyra.app"):
            internal.append(resolved)
        else:
            outbound.append(resolved)
    return internal, outbound


def _schema_types(html: str) -> list[str]:
    types = []
    for block in re.findall(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", html, flags=re.IGNORECASE | re.DOTALL):
        try:
            data = json.loads(block.strip())
        except Exception:
            continue
        for value in _walk_schema(data):
            if value not in types:
                types.append(value)
    return types


def _walk_schema(value: Any) -> list[str]:
    found = []
    if isinstance(value, dict):
        item_type = value.get("@type")
        if isinstance(item_type, str):
            found.append(item_type)
        elif isinstance(item_type, list):
            found.extend(str(item) for item in item_type)
        for child in value.values():
            found.extend(_walk_schema(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_walk_schema(child))
    return found


def _first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text or "", flags=re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else ""


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", value or "")).strip()


def _plain_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value or "")).strip()


def _slug(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


def _app_url(settings: Settings) -> str:
    site = settings.site.site_url or settings.wp_base_url
    parsed = urlparse(site)
    if parsed.netloc.startswith("blog."):
        return f"{parsed.scheme}://{parsed.netloc.removeprefix('blog.')}"
    return "https://meetlyra.app"
