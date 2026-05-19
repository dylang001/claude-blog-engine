from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from content_machine.config import Settings, SiteConfig
from content_machine.firecrawl import FirecrawlClient
from content_machine.backlinks import BacklinkClient
from content_machine.local_maps import LocalMapsClient
from content_machine.pdf_report import PDFReportGenerator, generate_pdf_strategy_report


@pytest.fixture
def mock_settings():
    return Settings(
        root_dir=Path("."),
        data_dir=Path(".content-machine"),
        state_db=Path(".content-machine/test.db"),
        site=SiteConfig(brand_name="MeetLyra", site_url="https://meetlyra.com"),
    )


# --- Firecrawl Tests ---

def test_firecrawl_requires_api_key(mock_settings):
    """Firecrawl must raise RuntimeError when no API key is configured."""
    client = FirecrawlClient(mock_settings)
    assert client.api_key == ""
    with pytest.raises(RuntimeError, match="FIRECRAWL_API_KEY is required"):
        import asyncio
        asyncio.run(client.scrape("https://example.com"))


def test_firecrawl_map_requires_api_key(mock_settings):
    client = FirecrawlClient(mock_settings)
    with pytest.raises(RuntimeError, match="FIRECRAWL_API_KEY is required"):
        import asyncio
        asyncio.run(client.map("https://example.com"))


def test_firecrawl_crawl_requires_api_key(mock_settings):
    client = FirecrawlClient(mock_settings)
    with pytest.raises(RuntimeError, match="FIRECRAWL_API_KEY is required"):
        import asyncio
        asyncio.run(client.crawl("https://example.com"))


# --- Backlinks Tests ---

def test_backlinks_requires_credentials(mock_settings):
    """BacklinkClient must raise RuntimeError when no DataForSEO credentials are configured."""
    client = BacklinkClient(mock_settings)
    with pytest.raises(RuntimeError, match="DataForSEO credentials are required"):
        import asyncio
        asyncio.run(client.get_summary("meetlyra.com"))


# --- Local Maps Tests ---

def test_local_maps_requires_credentials(mock_settings):
    """LocalMapsClient must raise RuntimeError when no DataForSEO credentials are configured."""
    client = LocalMapsClient(mock_settings)
    with pytest.raises(RuntimeError, match="DataForSEO credentials are required"):
        import asyncio
        asyncio.run(client.get_gmb_reviews("meetlyra"))


def test_local_maps_search_requires_credentials(mock_settings):
    client = LocalMapsClient(mock_settings)
    with pytest.raises(RuntimeError, match="DataForSEO credentials are required"):
        import asyncio
        asyncio.run(client.search_local_competitors("ai marketing", "San Francisco"))


# --- PDF Report Tests (these don't need external APIs) ---

def test_pdf_report_generator(mock_settings):
    pdf = PDFReportGenerator("Test Title")
    pdf.add_title("SEO Strategy Audit Report")
    pdf.add_header("1. Performance Metrics")
    pdf.add_paragraph("This is a paragraph detailing performance of the target website.")
    pdf.add_bullet("Issue 1: Slow page speed on mobile.")
    pdf.add_bullet("Issue 2: Missing schema tags.")
    
    headers = ["Metric", "Value", "Notes"]
    rows = [
        ["CLS", "0.01", "Excellent"],
        ["LCP", "1.2s", "Fast"],
        ["FID", "15ms", "Ideal"]
    ]
    pdf.add_table(headers, rows, [100, 100, 295])
    
    pdf_bytes = pdf.generate_bytes()
    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert pdf_bytes.endswith(b"%%EOF\n")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "report.pdf"
        saved_path = pdf.save(output_path)
        assert saved_path.exists()
        assert saved_path.stat().st_size > 0
        
        # Test helper function
        report_data = {
            "site": {"brand": "MeetLyra"},
            "generated_at": "2026-05-19",
            "claude_seo_capability_matrix": [
                {"capability": "technical_seo", "status": "full", "detail": "Test"}
            ],
            "next_actions": [
                {"priority": "high", "action": "Fix tags", "impact": "High"}
            ],
            "competitor_research": {"content_gaps": ["Gap 1"]},
            "schema_engine": {
                "strategy": "yoast_schema_api",
                "required_graph_pieces": ["Organization"]
            }
        }
        helper_path = Path(tmp_dir) / "helper.pdf"
        res_helper = generate_pdf_strategy_report(report_data, helper_path)
        assert res_helper.exists()
        assert res_helper.stat().st_size > 0
