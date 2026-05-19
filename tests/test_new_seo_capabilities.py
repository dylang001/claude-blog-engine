from __future__ import annotations

import json
from pathlib import Path
import pytest

from content_machine.config import Settings, SiteConfig
from content_machine.competitor_pages import CompetitorPagesGenerator
from content_machine.hreflang import HreflangAuditor
from content_machine.programmatic_seo import ProgrammaticSEOPlanner
from content_machine.indexing import GoogleIndexingClient


def _settings(tmp_path):
    return Settings(
        root_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_db=tmp_path / "data" / "db.sqlite",
        site=SiteConfig(brand_name="MeetLyra", site_url="https://meetlyra.app"),
        wp_base_url="https://blog.meetlyra.app",
    )


def test_competitor_pages_generator(tmp_path):
    settings = _settings(tmp_path)
    gen = CompetitorPagesGenerator(settings)
    report = gen.generate_vs_page("CompetitorSEO", output_dir=tmp_path)
    
    assert report["competitor"] == "CompetitorSEO"
    assert report["brand"] == "MeetLyra"
    assert "MeetLyra vs CompetitorSEO" in report["page_title"]
    assert "saved_to" in report
    assert Path(report["saved_to"]).exists()
    
    markdown_content = Path(report["saved_to"]).read_text(encoding="utf-8")
    assert "MeetLyra vs CompetitorSEO" in markdown_content
    assert "✅ Yes" in markdown_content
    assert "application/ld+json" in markdown_content


def test_hreflang_validator():
    auditor = HreflangAuditor()
    # Test valid locale codes
    ok, desc = auditor.validate_code("en-US")
    assert ok is True
    ok, desc = auditor.validate_code("ja-JP")
    assert ok is True
    ok, desc = auditor.validate_code("x-default")
    assert ok is True
    
    # Test invalid codes
    ok, desc = auditor.validate_code("jp-JP")  # jp is not ISO 639-1 language code (should be ja)
    assert ok is False
    ok, desc = auditor.validate_code("en-UK")  # UK is not ISO 3166-1 region code (should be GB)
    assert ok is False


@pytest.mark.asyncio
async def test_hreflang_audit_url(monkeypatch):
    auditor = HreflangAuditor()
    
    class FakeResponse:
        def __init__(self, text, status_code=200):
            self.text = text
            self.status_code = status_code
            
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def get(self, url, **kwargs):
            html = """
            <html>
            <head>
              <link rel="alternate" hreflang="en-US" href="https://example.com/page" />
              <link rel="alternate" hreflang="fr-FR" href="https://example.com/fr/page" />
              <link rel="alternate" hreflang="x-default" href="https://example.com/" />
            </head>
            <body></body>
            </html>
            """
            return FakeResponse(html)
        
    import httpx
    # Patch httpx.AsyncClient to be FakeClient
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    
    report = await auditor.audit_url("https://example.com/page")
    assert report["status_code"] == 200
    assert len(report["tags_found"]) == 3
    assert not report["issues"]


def test_hreflang_generator():
    auditor = HreflangAuditor()
    mapping = {
        "en-US": "https://example.com/page",
        "fr": "https://example.com/fr/page"
    }
    res = auditor.generate_tags(mapping, default_url="https://example.com/")
    assert "<link" in res["html"]
    assert "hreflang=\"en-US\"" in res["html"]
    assert "hreflang=\"x-default\"" in res["html"]
    assert "Link:" in res["http_header"]
    assert "<url>" in res["sitemap_xml"]


def test_programmatic_seo_planner():
    planner = ProgrammaticSEOPlanner()
    
    # 1. Under limit, high uniqueness -> Pass
    templates = [{
        "name": "Service Page",
        "expected_word_count": 500,
        "uniqueness_percentage": 50.0
    }]
    records = [{"slug": f"page-{i}"} for i in range(50)]
    report = planner.analyze_planning(50, templates, records)
    assert report["status"] == "pass"
    assert report["score"] == 100.0
    
    # 2. Warning limit (150 pages)
    report2 = planner.analyze_planning(150, templates, records)
    assert report2["status"] == "warning"
    assert report2["score"] < 100.0
    
    # 3. Hard stop limit (550 pages)
    report3 = planner.analyze_planning(550, templates, records)
    assert report3["status"] == "hard_stop"
    
    # 4. Thin content warning (<300 words)
    thin_templates = [{
        "name": "Service Page",
        "expected_word_count": 250,
        "uniqueness_percentage": 50.0
    }]
    report4 = planner.analyze_planning(50, thin_templates, records)
    assert any("below 300 words" in w for w in report4["warnings"])
    
    # 5. Doorway page warning (35 location pages)
    loc_templates = [{
        "name": "Location Service Page",
        "pattern": "/[city]/service",
        "expected_word_count": 500,
        "uniqueness_percentage": 50.0
    }]
    report5 = planner.analyze_planning(35, loc_templates, records)
    assert report5["status"] == "warning"
    assert any("location pages planned" in w for w in report5["warnings"])


@pytest.mark.asyncio
async def test_google_indexing_client(tmp_path):
    settings = _settings(tmp_path)
    client = GoogleIndexingClient(settings)
    
    res = await client.notify("https://example.com/new-page", action="URL_UPDATED", dry_run=True)
    assert res["success"] is True
    assert res["dry_run"] is True
    assert res["response"]["urlNotificationMetadata"]["latestUpdate"]["url"] == "https://example.com/new-page"
