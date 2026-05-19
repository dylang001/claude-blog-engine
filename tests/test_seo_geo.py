from __future__ import annotations

import json
from pathlib import Path
import pytest

from content_machine.config import Settings, SiteConfig
from content_machine.seo_geo import SEOGEOAuditor

def _settings(tmp_path, anthropic_api_key=""):
    return Settings(
        root_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_db=tmp_path / "data" / "db.sqlite",
        site=SiteConfig(
            brand_name="MeetLyra",
            site_url="https://blog.meetlyra.app",
            products=["AI SEO Engine"],
            competitors=["jasper.ai"]
        ),
        wp_base_url="https://blog.meetlyra.app",
        anthropic_api_key=anthropic_api_key
    )

@pytest.mark.asyncio
async def test_seo_geo_fails_without_api_key(tmp_path, monkeypatch):
    """Must raise RuntimeError when no ANTHROPIC_API_KEY is set."""
    settings = _settings(tmp_path)
    auditor = SEOGEOAuditor(settings)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is required for GEO analysis"):
        await auditor.run_analysis()

@pytest.mark.asyncio
async def test_seo_geo_strict_fails_without_key(tmp_path, monkeypatch):
    """Must raise RuntimeError when no ANTHROPIC_API_KEY is set, even with strict=True."""
    settings = _settings(tmp_path)
    auditor = SEOGEOAuditor(settings)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is required for GEO analysis"):
        await auditor.run_analysis(strict=True)

@pytest.mark.asyncio
async def test_seo_geo_fails_on_connection_error(tmp_path, monkeypatch):
    """Must raise RuntimeError when API call fails (not return mock data)."""
    settings = _settings(tmp_path, anthropic_api_key="sk-ant-testkey")
    auditor = SEOGEOAuditor(settings)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-testkey")

    with pytest.raises(RuntimeError, match="Claude API call for GEO analysis failed"):
        await auditor.run_analysis(strict=True)
