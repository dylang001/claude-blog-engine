from __future__ import annotations

import pytest
import httpx
from pathlib import Path

from content_machine.config import Settings, SiteConfig
from content_machine.open_seo_client import OpenSeoClient


def _settings(tmp_path, open_seo_url=""):
    return Settings(
        root_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_db=tmp_path / "data" / "db.sqlite",
        site=SiteConfig(brand_name="MeetLyra", site_url="https://meetlyra.app"),
        wp_base_url="https://blog.meetlyra.app",
        open_seo_url=open_seo_url,
    )


@pytest.mark.asyncio
async def test_open_seo_disabled(tmp_path):
    settings = _settings(tmp_path, open_seo_url="")
    client = OpenSeoClient(settings)
    assert client._enabled is False

    # Should return safe defaults immediately without network calls
    assert await client.keyword_ideas("test") == []
    assert await client.serp("test") == {}
    assert await client.domain_overview("example.com") == {}
    assert await client.site_audit_summary("example.com") == {}
    assert await client.rank_tracking("example.com", ["test"]) == []
    assert await client.health() is False


@pytest.mark.asyncio
async def test_open_seo_enabled_success(tmp_path, monkeypatch):
    settings = _settings(tmp_path, open_seo_url="https://open-seo-test.run.app")
    client = OpenSeoClient(settings)
    assert client._enabled is True

    class FakeResponse:
        def __init__(self, status_code, json_data):
            self.status_code = status_code
            self._json_data = json_data

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError("Error", request=None, response=self)

        def json(self):
            return self._json_data

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def get(self, url, params=None, **kwargs):
            if url == "https://open-seo-test.run.app/":
                return FakeResponse(200, {"status": "ok"})
            raise ValueError(f"Unexpected url: {url}")

        async def post(self, url, json=None, **kwargs):
            if url == "https://open-seo-test.run.app/mcp":
                method = json.get("method")
                params = json.get("params") or {}
                tool_name = params.get("name")
                args = params.get("arguments") or {}

                if method == "tools/call" and tool_name == "list_projects":
                    return FakeResponse(200, {
                        "jsonrpc": "2.0",
                        "result": {
                            "structuredContent": {
                                "projects": [{"id": "proj_123", "name": "Default"}]
                            }
                        },
                        "id": 1
                    })
                elif method == "tools/call" and tool_name == "research_keywords":
                    return FakeResponse(200, {
                        "jsonrpc": "2.0",
                        "result": {
                            "structuredContent": {
                                "results": [
                                    {
                                        "seed": args["seeds"][0]["seed"],
                                        "ok": True,
                                        "topRows": [
                                            {
                                                "keyword": "test keyword",
                                                "searchVolume": 100,
                                                "cpc": 1.5,
                                                "competition": 0.5,
                                                "keywordDifficulty": 12,
                                                "intent": "informational"
                                            }
                                        ]
                                    }
                                ]
                            }
                        },
                        "id": 1
                    })
                elif method == "tools/call" and tool_name == "get_serp_results":
                    return FakeResponse(200, {
                        "jsonrpc": "2.0",
                        "result": {
                            "structuredContent": {
                                "results": [
                                    {
                                        "keyword": args["queries"][0]["keyword"],
                                        "ok": True,
                                        "items": [
                                            {
                                                "type": "organic",
                                                "rank": 1,
                                                "title": "Test Title",
                                                "url": "https://example.com/test",
                                                "domain": "example.com",
                                                "description": "Test Description"
                                            }
                                        ]
                                    }
                                ]
                            }
                        },
                        "id": 1
                    })
                elif method == "tools/call" and tool_name == "get_domain_overview":
                    return FakeResponse(200, {
                        "jsonrpc": "2.0",
                        "result": {
                            "structuredContent": {
                                "domain": args["domain"],
                                "organicTraffic": 5000,
                                "organicKeywords": 200,
                                "backlinks": 120,
                                "referringDomains": 10
                            }
                        },
                        "id": 1
                    })
                elif method == "tools/call" and tool_name == "get_rank_tracker":
                    if "trackerId" not in args:
                        # List configs
                        return FakeResponse(200, {
                            "jsonrpc": "2.0",
                            "result": {
                                "structuredContent": {
                                    "configs": [{"id": "tracker_123", "domain": "example.com"}]
                                }
                            },
                            "id": 1
                        })
                    else:
                        # Get details
                        return FakeResponse(200, {
                            "jsonrpc": "2.0",
                            "result": {
                                "structuredContent": {
                                    "results": {
                                        "rows": [
                                            {
                                                "keyword": "test",
                                                "desktop": {"position": 3},
                                                "mobile": {"position": 5}
                                              }
                                        ]
                                    }
                                }
                            },
                            "id": 1
                        })
            raise ValueError(f"Unexpected url: {url} with json: {json}")

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    # 1. Health check
    assert await client.health() is True

    # 2. Keyword ideas
    ideas = await client.keyword_ideas("test keyword")
    assert len(ideas) == 1
    assert ideas[0]["keyword"] == "test keyword"
    assert ideas[0]["volume"] == 100
    assert ideas[0]["kd"] == 12
    assert ideas[0]["intent"] == "informational"

    # 3. SERP
    serp = await client.serp("test")
    assert serp["keyword"] == "test"
    assert len(serp["tasks"][0]["result"][0]["items"]) == 1
    assert serp["tasks"][0]["result"][0]["items"][0]["rank_absolute"] == 1

    # 4. Domain Overview
    domain_data = await client.domain_overview("example.com")
    assert domain_data["domain"] == "example.com"

    # 5. Site Audit Summary
    audit = await client.site_audit_summary("example.com")
    assert audit == {}

    # 6. Rank Tracking
    ranks = await client.rank_tracking("example.com", ["test"])
    assert len(ranks) == 1
    assert ranks[0]["rank"] == 3


@pytest.mark.asyncio
async def test_open_seo_graceful_failures(tmp_path, monkeypatch):
    settings = _settings(tmp_path, open_seo_url="https://open-seo-test.run.app")
    client = OpenSeoClient(settings)

    class FakeErrorClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def get(self, url, params=None, **kwargs):
            return httpx.Response(500, request=httpx.Request("GET", url))

        async def post(self, url, json=None, **kwargs):
            return httpx.Response(500, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "AsyncClient", FakeErrorClient)

    # All methods must gracefully handle errors and return empty / None / False
    assert await client.health() is False
    assert await client.keyword_ideas("test") == []
    assert await client.serp("test") == {}
    assert await client.domain_overview("example.com") == {}
    assert await client.site_audit_summary("example.com") == {}
    assert await client.rank_tracking("example.com", ["test"]) == []

