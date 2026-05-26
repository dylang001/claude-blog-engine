from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch
import pytest
import httpx

from content_machine.config import Settings
from content_machine.outreach_agent import OutreachAgent


@pytest.fixture
def test_settings(tmp_path) -> Settings:
    from content_machine.config import SiteConfig
    return Settings(
        root_dir=tmp_path,
        data_dir=tmp_path,
        state_db=tmp_path / "test.db",
        site=SiteConfig(
            brand_name="Test Brand",
            site_url="https://example.com",
            audience="B2B",
            timezone="UTC"
        ),
        anthropic_api_key="test-key",
        outbound_email_agent_url="http://test-email-agent"
    )


@pytest.mark.asyncio
async def test_generate_campaign_for_post(test_settings):
    # Mock WordPress client response
    mock_post = {
        "id": 123,
        "title": {"rendered": "How to build an AI agent"},
        "link": "https://blog.meetlyra.app/ai-agent",
        "content": {"rendered": "<p>This is a guide to AI agents.</p>"}
    }

    # Mock Anthropic response containing JSON string in messages
    mock_anthropic_resp = {
        "content": [
            {
                "text": json.dumps({
                    "prospects": [
                        {
                            "email": "editor@ai-blog.com",
                            "firstName": "John",
                            "lastName": "Doe",
                            "companyName": "AI Blog",
                            "context": "They write about AI agents."
                        }
                    ]
                })
            }
        ]
    }

    # Mock Next.js campaign response
    mock_campaign_resp = {
        "campaign": {
            "id": 42,
            "name": "Backlinks: How to build an AI agent"
        }
    }

    # Setup mocks
    with patch("content_machine.outreach_agent.WordPressClient") as mock_wp_class:
        mock_wp_instance = mock_wp_class.return_value
        mock_wp_instance.find_post_by_slug = AsyncMock(return_value=mock_post)

        # Mock httpx POST requests
        async def mock_post_request(url, **kwargs):
            req = httpx.Request("POST", url)
            if "anthropic" in url:
                return httpx.Response(200, json=mock_anthropic_resp, request=req)
            elif "/api/campaigns" in url:
                return httpx.Response(201, json=mock_campaign_resp, request=req)
            elif "/api/contacts" in url:
                return httpx.Response(201, json={"status": "queued"}, request=req)
            return httpx.Response(404, request=req)

        with patch("httpx.AsyncClient.post", side_effect=mock_post_request):
            agent = OutreachAgent(test_settings)
            result = await agent.generate_campaign_for_post("ai-agent")

            assert result["campaign_id"] == 42
            assert len(result["prospects"]) == 1
            assert result["prospects"][0]["email"] == "editor@ai-blog.com"
            assert result["prospects"][0]["company"] == "AI Blog"


@pytest.mark.asyncio
async def test_trigger_cron_job(test_settings):
    mock_cron_resp = {
        "success": True,
        "sentCount": 3,
        "repliesCount": 1
    }

    async def mock_post_request(url, **kwargs):
        req = httpx.Request("POST", url)
        if "/api/cron/process-outreach" in url:
            return httpx.Response(200, json=mock_cron_resp, request=req)
        return httpx.Response(404, request=req)

    with patch("httpx.AsyncClient.post", side_effect=mock_post_request):
        agent = OutreachAgent(test_settings)
        result = await agent.trigger_cron_job()

        assert result["success"] is True
        assert result["sentCount"] == 3
        assert result["repliesCount"] == 1
