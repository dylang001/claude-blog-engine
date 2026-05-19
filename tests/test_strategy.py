import pytest

from content_machine.config import Settings, SiteConfig
from content_machine.models import Opportunity, WorkItemType
from content_machine.strategy import (
    StrictStrategyReporter,
    _app_url,
    _internal_link_plan,
)


def _settings(tmp_path):
    return Settings(
        root_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_db=tmp_path / "data" / "db.sqlite",
        site=SiteConfig(brand_name="MeetLyra", site_url="https://blog.meetlyra.app"),
        wp_base_url="https://blog.meetlyra.app",
    )


def _serp():
    return {
        "tasks": [
            {
                "result": [
                    {
                        "items": [
                            {"type": "organic", "rank_group": 1, "title": "AI SEO Agent Guide", "url": "https://example.com/guide", "domain": "example.com"},
                            {"type": "organic", "rank_group": 2, "title": "Best AI SEO Tools", "url": "https://competitor.com/tools", "domain": "competitor.com"},
                        ]
                    }
                ]
            }
        ]
    }


@pytest.mark.asyncio
async def test_strategy_report_includes_claude_seo_sections(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    schema_path = tmp_path / "vendor" / "claude-seo"
    schema_path.mkdir(parents=True)
    (schema_path / "schema-templates.json").write_text("{}", encoding="utf-8")
    reporter = StrictStrategyReporter(settings)
    opportunity = Opportunity(
        WorkItemType.NEW_ARTICLE,
        "ai seo agent",
        "AI SEO Agent",
        91,
        metadata={"volume": 1000, "kd": 18, "intent": "commercial", "funnel": "BOFU"},
        reason="DataForSEO keyword opportunity",
    )

    async def fake_live_checks(settings):
        return {"ok": True, "checks": {name: {"ok": True} for name in ["anthropic", "dataforseo", "wordpress", "banana", "google_config", "indexnow"]}}

    async def fake_collect(strict=False):
        assert strict is True
        return [opportunity]

    async def fake_brief(item, strict=False):
        assert strict is True
        return {"serp": _serp(), "requirements": ["Use SERP evidence."]}

    async def fake_links(limit=100):
        return [{"title": "Blog guide", "url": "https://blog.meetlyra.app/guide/", "slug": "guide"}]

    async def fake_claude_seo(days):
        return {
            "technical": {"ok": True, "checks": {"home": {"ok": True}}},
            "pagespeed": {"ok": True, "scores": {"performance": 92, "seo": 100}},
            "gsc": {"ok": True, "top_rows": [], "quick_wins": []},
            "ga4": {"ok": True, "top_pages": [], "totals": {"sessions": 0}},
            "schema_templates_available": True,
        }

    async def fake_indexnow():
        return {"ok": True, "key_location": "https://blog.meetlyra.app/indexnow-key.txt"}

    async def fake_pages(urls):
        return [
            {
                "url": "https://blog.meetlyra.app",
                "title": "MeetLyra Blog",
                "meta_description": "MeetLyra blog for AI marketing and SEO automation.",
                "h1_count": 1,
                "h1": ["MeetLyra Blog"],
                "h2_count": 2,
                "canonical": "https://blog.meetlyra.app",
                "schema_types": ["WebSite"],
                "word_count": 600,
                "issues": [],
                "internal_link_count": 3,
                "outbound_link_count": 1,
            }
        ]

    monkeypatch.setattr("content_machine.strategy.live_checks", fake_live_checks)
    reporter.collector.collect = fake_collect
    reporter.researcher.brief = fake_brief
    reporter.wordpress.internal_link_candidates = fake_links
    reporter.discovery._claude_seo_signals = fake_claude_seo
    monkeypatch.setattr("content_machine.strategy.IndexNowClient.verify_key_location", lambda self: fake_indexnow())
    reporter._page_intelligence = fake_pages

    # Mock the external API clients that now require live credentials
    async def fake_firecrawl_map(self, url):
        return ["https://blog.meetlyra.app", "https://blog.meetlyra.app/guide/"]

    async def fake_backlink_summary(self, target):
        return {"target": target, "rank": 0, "backlinks": 0, "referring_domains": 0}

    async def fake_gmb_reviews(self, business_id):
        return {"business_id": business_id, "title": "MeetLyra", "rating": {"value": 0, "votes_count": 0}}

    monkeypatch.setattr("content_machine.strategy.FirecrawlClient.map", fake_firecrawl_map)
    monkeypatch.setattr("content_machine.strategy.BacklinkClient.get_summary", fake_backlink_summary)
    monkeypatch.setattr("content_machine.strategy.LocalMapsClient.get_gmb_reviews", fake_gmb_reviews)

    report = await reporter.run(limit=1, days=90)

    assert report["mode"] == "strict_strategy"
    assert report["fallbacks_allowed"] is False
    assert report["keyword_map"]["clusters"]
    assert report["site_structure"]["blog_meetlyra_app"]
    assert report["competitor_research"]["top_competing_domains"]
    assert report["technical_seo"]["pagespeed"]["ok"] is True
    assert report["schema_engine"]["strategy"] == "yoast_schema_api"
    assert report["geo_aeo"]["required_blocks"]
    assert report["drift_monitoring"]["ok"] is True
    assert report["claude_seo_capability_matrix"]
    assert report["saved_report"].endswith(".json")


def test_internal_link_plan_separates_blog_and_product_domains(tmp_path):
    keyword_map = {"clusters": [{"name": "SEO Content Engine", "opportunities": []}]}
    links = [{"title": "Guide", "url": "https://blog.meetlyra.app/guide/", "slug": "guide"}]

    plan = _internal_link_plan(links, keyword_map)

    assert plan["available_blog_links"][0]["url"].startswith("https://blog.meetlyra.app")
    assert plan["recommended_product_links"][0]["url"].startswith("https://meetlyra.app")


def test_app_url_derives_root_domain_from_blog_domain(tmp_path):
    assert _app_url(_settings(tmp_path)) == "https://meetlyra.app"
