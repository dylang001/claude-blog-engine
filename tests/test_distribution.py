from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from content_machine.config import Settings, SiteConfig
from content_machine.state import StateStore
from content_machine.models import PipelineResult, Opportunity, GeneratedContent, AuditReport, PublishDecision, WorkItemType
from content_machine.distribution import DistributionEngine

@pytest.fixture
def mock_settings(tmp_path):
    site = SiteConfig(brand_name="MeetLyra", site_url="https://blog.meetlyra.app")
    return Settings(
        root_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_db=tmp_path / "state.db",
        site=site,
        blogger_blog_id="blogger-123",
        writer_provider="gemini",
        gemini_api_key="fake-key"
    )

@pytest.fixture
def mock_pipeline_result():
    opp = Opportunity(
        kind=WorkItemType.NEW_ARTICLE,
        keyword="ai marketing agent",
        title="AI Marketing Agent Guide",
        score=95.0,
        metadata={"cluster_name": "Automation"}
    )
    content = GeneratedContent(
        title="AI Marketing Agent Guide",
        slug="ai-marketing-agent-guide",
        markdown="<!-- wp:paragraph --><p>Content</p><!-- /wp:paragraph -->",
        html="<p>Content</p>",
        meta_title="AI Marketing Agent Guide",
        meta_description="A cool guide",
        focus_keyphrase="ai marketing agent",
        excerpt="Summary",
        tags=["SEO"],
        categories=["AI"],
        schema_json={}
    )
    audit = AuditReport(score=92.0, decision=PublishDecision.PUBLISH, issues=[], warnings=[], sources=[])
    return PipelineResult(
        run_id="run-123",
        dry_run=False,
        opportunity=opp,
        audit=audit,
        content=content,
        wordpress_status="publish",
        wordpress_id=456,
        wordpress_url="https://blog.meetlyra.app/ai-marketing-agent-guide"
    )

@pytest.mark.asyncio
@patch("content_machine.distribution.BloggerClient")
@patch("content_machine.distribution.ContentWriter")
async def test_distribution_engine_distribute(mock_writer_cls, mock_blogger_cls, mock_settings, mock_pipeline_result):
    # Setup state store
    store = StateStore(mock_settings.state_db, settings=mock_settings)
    
    # Mock Blogger client
    mock_blogger = MagicMock()
    mock_blogger.publish_post = AsyncMock(return_value={"id": "blogger-post-1", "url": "https://blogger.com/post-1"})
    mock_blogger_cls.return_value = mock_blogger

    # Mock Writer
    mock_writer = MagicMock()
    mock_writer.adapt_for_blogger = AsyncMock(return_value={"title": "Summary Title", "content": "<p>Adapted summary</p>"})
    mock_writer.generate_backlink_outreach = AsyncMock(return_value={
        "contact_name": "Jane Doe",
        "contact_email": "jane@competitor.com",
        "outreach_angle": "Personal pitch email"
    })
    mock_writer_cls.return_value = mock_writer

    # Setup research brief with SERP competitor results
    research = {
        "serp": {
            "tasks": [
                {
                    "result": [
                        {
                            "items": [
                                {"type": "organic", "url": "https://competitor.com/ranking-page"},
                                {"type": "ad", "url": "https://adsite.com"}
                            ]
                        }
                    ]
                }
            ]
        }
    }

    engine = DistributionEngine(mock_settings, store=store)
    result_assets = await engine.distribute(mock_pipeline_result, research)

    # 1. Assert Blogger was called correctly
    mock_writer.adapt_for_blogger.assert_called_once_with(
        "AI Marketing Agent Guide",
        "<p>Content</p>",
        "https://blog.meetlyra.app/ai-marketing-agent-guide"
    )
    mock_blogger.publish_post.assert_called_once_with(
        "Summary Title",
        "<p>Adapted summary</p>",
        is_draft=False
    )
    
    # 2. Assert assets were recorded
    assert len(result_assets) == 1
    assert result_assets[0]["platform"] == "blogger"
    assert result_assets[0]["published_url"] == "https://blogger.com/post-1"
    
    # Verify state database has the records
    art = store.get_article("456")
    assert art is not None
    assert art["title"] == "AI Marketing Agent Guide"
    assert art["status"] == "publish"

    assets = store.get_distribution_assets("456")
    assert len(assets) == 1
    assert assets[0]["platform"] == "blogger"
    assert assets[0]["status"] == "published"

    # 3. Assert backlink outreach target was generated
    mock_writer.generate_backlink_outreach.assert_called_once_with(
        "AI Marketing Agent Guide",
        "competitor.com",
        "ai marketing agent"
    )
    
    backlinks = store.get_backlink_targets("456")
    assert len(backlinks) == 1
    assert backlinks[0]["target_site"] == "competitor.com"
    assert backlinks[0]["contact_name"] == "Jane Doe"
    assert backlinks[0]["contact_email"] == "jane@competitor.com"
    assert backlinks[0]["outreach_angle"] == "Personal pitch email"

    # 4. Assert daily report updated
    from datetime import datetime, timezone
    date_str = datetime.now(timezone.utc).date().isoformat()
    report = store.get_daily_report(date_str)
    assert report is not None
    assert report["posts_published"] == 1
    assert report["posts_syndicated"] == 1
    assert report["backlinks_created"] == 1
