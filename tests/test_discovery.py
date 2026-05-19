import pytest

from content_machine.config import Settings, SiteConfig
from content_machine.discovery import DiscoveryReporter, _extract_pagespeed_cwv
from content_machine.models import Opportunity, WorkItemType


@pytest.mark.asyncio
async def test_discovery_report_uses_claude_seo_sources(tmp_path, monkeypatch):
    settings = Settings(
        root_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_db=tmp_path / "data" / "state.db",
        site=SiteConfig(brand_name="Test Brand", site_url="https://blog.example.com"),
        wp_base_url="https://blog.example.com",
    )
    reporter = DiscoveryReporter(settings)

    async def fake_collect(strict=False):
        return [Opportunity(WorkItemType.NEW_ARTICLE, "seo automation", "SEO Automation", 91)]

    async def fake_brief(opportunity, strict=False):
        return {"serp": {"tasks": []}, "requirements": ["Use SERP evidence."]}

    async def fake_links(limit=30):
        return [{"title": "Internal page", "url": "https://blog.example.com/internal", "slug": "internal"}]

    async def fake_claude_seo(days):
        return {
            "source": "dylang001/claude-seo",
            "source_files": reporter.claude_seo_sources,
            "pagespeed": {"ok": True, "scores": {"seo": 100}},
            "gsc": {"ok": True, "quick_wins": []},
            "ga4": {"ok": True, "top_pages": []},
        }

    reporter.collector.collect = fake_collect
    reporter.researcher.brief = fake_brief
    reporter.wordpress.internal_link_candidates = fake_links
    reporter._claude_seo_signals = fake_claude_seo

    report = await reporter.run(limit=1, days=28)

    assert report["selected_opportunity"]["keyword"] == "seo automation"
    assert report["claude_seo"]["source"] == "dylang001/claude-seo"
    assert "vendor/claude-seo/gsc_query.py" in report["claude_seo"]["source_files"]
    assert report["schema_improvements"]["strategy"] == "yoast_schema_api"
    assert "wpseo_schema_graph" in report["schema_improvements"]["yoast_hooks"]
    assert report["saved_report"].endswith(".json")


def test_pagespeed_cwv_extractor_reads_lighthouse_metrics():
    data = {
        "lighthouseResult": {
            "audits": {
                "largest-contentful-paint": {"displayValue": "2.1 s", "score": 0.91, "numericValue": 2100},
                "cumulative-layout-shift": {"displayValue": "0.02", "score": 1, "numericValue": 0.02},
            }
        }
    }

    metrics = _extract_pagespeed_cwv(data)

    assert metrics["largest-contentful-paint"]["label"] == "LCP"
    assert metrics["cumulative-layout-shift"]["numeric_value"] == 0.02
