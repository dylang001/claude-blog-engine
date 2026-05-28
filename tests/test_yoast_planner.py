from __future__ import annotations

import pytest
from pathlib import Path
from content_machine.state import StateStore
from content_machine.config import Settings, SiteConfig
from content_machine.models import WorkItemType
from content_machine.data_sources import OpportunityCollector
from content_machine.planner import ClusterPlanner


def test_content_plan_ordering_and_dependency(tmp_path):
    store = StateStore(tmp_path / "state.db")
    
    # Add a pillar page
    pillar = {
        "keyword": "ai marketing",
        "title": "Ultimate Guide to AI Marketing",
        "intent": "informational",
        "cluster_name": "Cluster 1",
        "role": "pillar",
        "parent_pillar": None,
        "anchor_text": "ai marketing",
        "score": 9.5,
        "volume": 5000,
        "kd": 40
    }
    
    # Add a spoke page dependent on the pillar
    spoke = {
        "keyword": "ai marketing agent",
        "title": "AI Marketing Agent: A Complete Overview",
        "intent": "commercial",
        "cluster_name": "Cluster 1",
        "role": "spoke",
        "parent_pillar": "ai marketing",
        "anchor_text": "ai marketing",
        "score": 8.0,
        "volume": 1200,
        "kd": 20
    }

    # Add a standalone spoke/other spoke (no parent)
    spoke_no_parent = {
        "keyword": "independent tool",
        "title": "Independent Tool: A Complete Overview",
        "intent": "commercial",
        "cluster_name": "Cluster 2",
        "role": "spoke",
        "parent_pillar": None,
        "anchor_text": "independent",
        "score": 8.5,
        "volume": 800,
        "kd": 15
    }

    store.add_to_content_plan(pillar)
    store.add_to_content_plan(spoke)
    store.add_to_content_plan(spoke_no_parent)

    # 1. First get_next_planned_post should be the pillar because it's a planned pillar,
    # even though spoke_no_parent has parent_pillar = None (pillars prioritized first).
    next_post = store.get_next_planned_post()
    assert next_post is not None
    assert next_post["keyword"] == "ai marketing"
    assert next_post["role"] == "pillar"

    # 2. If we query again, it still returns "ai marketing" because we haven't marked it published.
    # Let's mark "ai marketing" as published.
    store.mark_planned_post_published("ai marketing", "https://blog.meetlyra.app/ai-marketing/")

    # 3. Next get_next_planned_post:
    # Now "ai marketing" is published.
    # The remaining planned posts are "independent tool" (spoke, score 8.5) and "ai marketing agent" (spoke, score 8.0).
    # Since the parent of "ai marketing agent" is now published, both are eligible.
    # "independent tool" has higher score (8.5 > 8.0), so it should be picked first.
    next_post = store.get_next_planned_post()
    assert next_post is not None
    assert next_post["keyword"] == "independent tool"

    # Mark independent tool published
    store.mark_planned_post_published("independent tool", "https://blog.meetlyra.app/independent-tool/")

    # 4. Next get_next_planned_post should be "ai marketing agent" (spoke, parent published)
    next_post = store.get_next_planned_post()
    assert next_post is not None
    assert next_post["keyword"] == "ai marketing agent"


@pytest.mark.asyncio
async def test_opportunity_collector_consumes_queues(tmp_path):
    settings = Settings(
        root_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_db=tmp_path / "state.db",
        site=SiteConfig(
            brand_name="MeetLyra",
            products=["MeetLyra"]
        ),
        dry_run_default=True,
        writer_provider="mock"
    )
    
    collector = OpportunityCollector(settings)
    
    # Inject a refresh candidate
    collector.store.inject_refresh_candidate("old marketing guide", "https://blog.meetlyra.app/old/", "low CTR", 95.0)
    
    # Inject a planned post
    collector.store.add_to_content_plan({
        "keyword": "new planned post",
        "title": "New Planned Post",
        "intent": "commercial",
        "cluster_name": "Cluster 1",
        "role": "pillar",
        "parent_pillar": None,
        "anchor_text": "planned",
        "score": 90.0,
        "volume": 200,
        "kd": 10
    })

    # Collect should return the refresh candidate first because refresh queue is checked first.
    opps = await collector.collect()
    assert len(opps) == 1
    assert opps[0].kind == WorkItemType.REFRESH
    assert opps[0].keyword == "old marketing guide"

    # Consume the refresh candidate
    collector.store.mark_refresh_candidate_consumed("old marketing guide")

    # Next collect should return the planned post
    opps = await collector.collect()
    assert len(opps) == 1
    assert opps[0].kind == WorkItemType.NEW_ARTICLE
    assert opps[0].keyword == "new planned post"


@pytest.mark.asyncio
async def test_planner_clustering_logic(tmp_path):
    settings = Settings(
        root_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_db=tmp_path / "state.db",
        site=SiteConfig(
            brand_name="MeetLyra",
            products=["MeetLyra"]
        ),
        dry_run_default=True,
        writer_provider="mock"
    )
    planner = ClusterPlanner(settings)
    
    # We will test get_serp_urls deterministic fallback
    urls_agent = await planner.get_serp_urls("AI marketing agent")
    urls_agents = await planner.get_serp_urls("best AI marketing agents")
    urls_seo = await planner.get_serp_urls("SEO keywords search")
    
    # Overlap between agent and agents (should be high because both contain agent and marketing)
    overlap_agent_agents = len(set(urls_agent).intersection(set(urls_agents)))
    assert overlap_agent_agents >= 7
    
    # Overlap between agent and seo (should be lower/different)
    overlap_agent_seo = len(set(urls_agent).intersection(set(urls_seo)))
    assert overlap_agent_seo < overlap_agent_agents
