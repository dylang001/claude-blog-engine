from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from content_machine.config import Settings, SiteConfig
from content_machine.daily_report import get_daily_metrics, compile_daily_report, build_email_body, send_daily_email_report
from content_machine.state import StateStore


class FakeDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        dt = datetime(2026, 5, 25, 18, 0, 0, tzinfo=timezone.utc)
        if tz:
            return dt.astimezone(tz)
        return dt


@pytest.fixture
def temp_db(tmp_path) -> Path:
    db_path = tmp_path / "test_state.db"
    store = StateStore(db_path)
    
    # 1. A published run today
    store.save_run(
        run_id="run-1-published",
        started_at="2026-05-25T10:00:00Z",
        payload={
            "finished_at": "2026-05-25T10:01:00Z",
            "dry_run": False,
            "opportunity": {"kind": "new", "keyword": "organic reach"},
            "audit": {"score": 88.5, "decision": "publish"},
            "wordpress_status": "publish",
            "wordpress_id": 101,
        }
    )
    
    # 2. A draft run today
    store.save_run(
        run_id="run-2-draft",
        started_at="2026-05-25T11:00:00Z",
        payload={
            "finished_at": "2026-05-25T11:01:00Z",
            "dry_run": False,
            "opportunity": {"kind": "refresh", "keyword": "content optimization"},
            "audit": {"score": 75.0, "decision": "draft"},
            "wordpress_status": "draft",
            "wordpress_id": 102,
        }
    )
    
    # 3. A blocked run today
    store.save_run(
        run_id="run-3-blocked",
        started_at="2026-05-25T12:00:00Z",
        payload={
            "finished_at": "2026-05-25T12:01:00Z",
            "dry_run": False,
            "opportunity": {"kind": "new", "keyword": "spammy keyword"},
            "audit": {"score": 45.0, "decision": "block"},
            "wordpress_status": "blocked",
        }
    )
    
    # 4. A failed run today
    store.save_run(
        run_id="run-4-failed",
        started_at="2026-05-25T13:00:00Z",
        payload={
            "finished_at": "2026-05-25T13:01:00Z",
            "dry_run": False,
            "wordpress_status": "failed",
            "error": "WordPress REST API connection timeout",
        }
    )

    # 5. An old run (yesterday)
    store.save_run(
        run_id="run-old",
        started_at="2026-05-24T10:00:00Z",
        payload={
            "finished_at": "2026-05-24T10:01:00Z",
            "dry_run": False,
            "opportunity": {"kind": "new", "keyword": "yesterday keyword"},
            "audit": {"score": 90.0, "decision": "publish"},
            "wordpress_status": "publish",
            "wordpress_id": 99,
        }
    )
    
    return db_path


@pytest.fixture
def mock_settings(temp_db) -> Settings:
    return Settings(
        root_dir=Path("."),
        data_dir=temp_db.parent,
        state_db=temp_db,
        site=SiteConfig(brand_name="MeetLyra", site_url="https://blog.meetlyra.app", timezone="UTC"),
        ga4_property_id="987654321",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="user@example.com",
        smtp_password="password123",
        smtp_to="recipient@example.com",
        smtp_from="sender@example.com",
    )


def test_get_daily_metrics(temp_db):
    with patch("content_machine.daily_report.datetime", FakeDateTime):
        metrics = get_daily_metrics(temp_db, timezone_str="UTC")
        
    assert metrics["timezone"] == "UTC"
    assert "today_local_date" in metrics
    
    assert metrics["today"]["total"] == 4
    assert metrics["today"]["published"] == 1
    assert metrics["today"]["drafts"] == 1
    assert metrics["today"]["blocked"] == 1
    assert metrics["today"]["failed"] == 1
    
    runs = metrics["today"]["runs"]
    assert len(runs) == 4
    # run-4-failed (13:00) is index 0
    assert runs[0]["wordpress_status"] == "failed"
    assert runs[0]["error"] == "WordPress REST API connection timeout"
    
    # run-3-blocked (12:00) is index 1
    assert runs[1]["keyword"] == "spammy keyword"
    assert runs[1]["wordpress_status"] == "blocked"


@pytest.mark.asyncio
async def test_compile_daily_report(mock_settings):
    mock_ga4_result = {
        "totals": {
            "sessions": 500,
            "users": 400,
            "pageviews": 1500,
            "avg_daily_sessions": 500.0,
        },
        "top_pages": [
            {"landing_page": "/seo-guide", "sessions": 300},
            {"landing_page": "/about", "sessions": 200},
        ]
    }
    
    with patch("content_machine.daily_report._run_ga4_report", new_callable=AsyncMock) as mock_ga4, \
         patch("content_machine.daily_report.datetime", FakeDateTime):
        mock_ga4.return_value = mock_ga4_result
        
        report = await compile_daily_report(mock_settings)
        
        assert report["brand_name"] == "MeetLyra"
        assert report["site_url"] == "https://blog.meetlyra.app"
        assert report["ga4"]["yesterday"]["ok"] is True
        assert report["ga4"]["yesterday"]["totals"]["sessions"] == 500
        assert report["database"]["today"]["total"] == 4


def test_build_email_body():
    fake_report = {
        "brand_name": "MeetLyra",
        "site_url": "https://blog.meetlyra.app",
        "compiled_at": "2026-05-25T18:00:00Z",
        "database": {
            "today_local_date": "2026-05-25",
            "timezone": "UTC",
            "today": {
                "total": 2,
                "published": 1,
                "drafts": 0,
                "blocked": 0,
                "failed": 1,
                "dry_run": 0,
                "runs": [
                    {
                        "started_at": "2026-05-25T10:00:00Z",
                        "keyword": "organic reach",
                        "wordpress_status": "publish",
                        "wordpress_id": 101,
                        "decision": "publish",
                        "score": 88.5,
                        "error": "",
                    },
                    {
                        "started_at": "2026-05-25T13:00:00Z",
                        "keyword": "failed post",
                        "wordpress_status": "failed",
                        "wordpress_id": None,
                        "decision": "error",
                        "score": 0.0,
                        "error": "Timeout Error",
                    }
                ]
            },
            "last_24h": {
                "total": 2,
                "published": 1,
                "drafts": 0,
                "blocked": 0,
                "failed": 1,
            }
        },
        "ga4": {
            "yesterday": {
                "ok": True,
                "totals": {"sessions": 100, "users": 80, "pageviews": 300}
            },
            "last_7_days": {
                "ok": True,
                "totals": {"sessions": 700, "users": 560, "pageviews": 2100}
            }
        }
    }
    
    html_body, text_body = build_email_body(fake_report)
    
    # Verify plain text content
    assert "=== MeetLyra Daily Content Engine Summary ===" in text_body
    assert "Sessions: 100" in text_body
    assert "Sessions: 700" in text_body
    assert "organic reach" in text_body
    assert "failed post" in text_body
    
    # Verify HTML content
    assert "MeetLyra Content Machine" in html_body
    assert "organic reach" in html_body
    assert "publish" in html_body
    assert "failed" in html_body
    assert "Timeout Error" in html_body
    assert "Sessions" in html_body


def test_send_daily_email_report_missing_config():
    settings = Settings(
        root_dir=Path("."),
        data_dir=Path("."),
        state_db=Path("test.db"),
        site=SiteConfig(),
        smtp_host="",
    )
    report = {"database": {"today_local_date": "2026-05-25"}}
    res = send_daily_email_report(settings, report)
    assert res is False


@patch("smtplib.SMTP")
def test_send_daily_email_report_success(mock_smtp, mock_settings):
    mock_server = MagicMock()
    mock_smtp.return_value = mock_server
    
    fake_report = {
        "brand_name": "MeetLyra",
        "site_url": "https://blog.meetlyra.app",
        "database": {
            "today_local_date": "2026-05-25",
            "timezone": "UTC",
            "today": {
                "total": 1,
                "published": 1,
                "drafts": 0,
                "blocked": 0,
                "failed": 0,
                "dry_run": 0,
                "runs": []
            },
            "last_24h": {
                "total": 1,
                "published": 1,
                "drafts": 0,
                "blocked": 0,
                "failed": 0,
            }
        },
        "ga4": {
            "yesterday": {"ok": False, "error": "No property ID"},
            "last_7_days": {"ok": False, "error": "No property ID"}
        }
    }
    
    res = send_daily_email_report(mock_settings, fake_report)
    assert res is True
    
    mock_smtp.assert_called_once_with("smtp.example.com", 587, timeout=30)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("user@example.com", "password123")
    mock_server.sendmail.assert_called_once()
    mock_server.quit.assert_called_once()
