import pytest

from content_machine.config import Settings, SiteConfig
from content_machine.data_sources import OpportunityCollector, normalize_keyword_item


def _settings(tmp_path):
    return Settings(
        root_dir=tmp_path,
        data_dir=tmp_path,
        state_db=tmp_path / "db.sqlite",
        site=SiteConfig(
            brand_name="MeetLyra",
            products=["AI SEO and GEO Content Engine"],
            forbidden_topics=["crypto"],
        ),
    )


def test_normalize_keyword_item_handles_top_level_dataforseo_shape():
    item = {
        "keyword": "ai seo agent",
        "keyword_info": {"search_volume": 140, "competition": 0.2, "competition_level": "LOW", "cpc": 4.5},
        "keyword_properties": {"keyword_difficulty": 22, "detected_language": "en"},
        "search_intent_info": {"main_intent": "commercial"},
        "avg_backlinks_info": {"backlinks": 12, "referring_domains": 4},
    }

    normalized = normalize_keyword_item(item)

    assert normalized["keyword"] == "ai seo agent"
    assert normalized["volume"] == 140
    assert normalized["kd"] == 22
    assert normalized["intent"] == "commercial"
    assert normalized["avg_referring_domains"] == 4


def test_normalize_keyword_item_handles_nested_keyword_data_shape():
    item = {
        "keyword_data": {
            "keyword": "seo content automation",
            "keyword_info": {"search_volume": 320},
            "keyword_properties": {"keyword_difficulty": 31},
            "search_intent_info": {"main_intent": "informational"},
        }
    }

    normalized = normalize_keyword_item(item)

    assert normalized["keyword"] == "seo content automation"
    assert normalized["volume"] == 320
    assert normalized["kd"] == 31
    assert normalized["intent"] == "informational"


@pytest.mark.asyncio
async def test_strict_collect_blocks_bootstrap_fallback(tmp_path):
    collector = OpportunityCollector(_settings(tmp_path))

    async def empty_keyword_ideas(seeds):
        return []

    collector.dataforseo.keyword_ideas = empty_keyword_ideas

    with pytest.raises(RuntimeError, match="returned no items"):
        await collector.collect(strict=True)


@pytest.mark.asyncio
async def test_collect_uses_real_dataforseo_metrics(tmp_path):
    collector = OpportunityCollector(_settings(tmp_path))

    async def keyword_ideas(seeds):
        return [
            {
                "keyword": "ai seo agent",
                "keyword_info": {"search_volume": 1000, "competition": 0.2, "competition_level": "LOW", "cpc": 8.1},
                "keyword_properties": {"keyword_difficulty": 18, "detected_language": "en"},
                "search_intent_info": {"main_intent": "commercial"},
            }
        ]

    collector.dataforseo.keyword_ideas = keyword_ideas

    opportunities = await collector.collect(strict=True)

    assert opportunities[0].keyword == "ai seo agent"
    assert opportunities[0].metadata["volume"] == 1000
    assert opportunities[0].metadata["kd"] == 18
    assert opportunities[0].reason == "DataForSEO keyword opportunity"
