from content_machine.state import StateStore


def test_state_store_persists_run_and_seen_keywords(tmp_path):
    store = StateStore(tmp_path / "state.db")
    store.save_run(
        "run-1",
        "2026-05-18T00:00:00+00:00",
        {
            "dry_run": True,
            "opportunity": {"kind": "new_article", "keyword": "seo automation"},
            "audit": {"score": 88, "decision": "publish"},
            "wordpress_status": "dry_run",
        },
    )
    store.mark_published("new_article:seo-automation", "new_article", "seo automation", "run-1", "2026-05-18T00:01:00+00:00", 123, "https://example.com/seo")

    assert "seo automation" in store.seen_keywords()
    assert store.recent_runs(1)[0]["audit"]["score"] == 88


def test_state_store_persists_syndication_and_backlinks(tmp_path):
    store = StateStore(tmp_path / "state.db")
    
    # Test Articles
    article = {
        "article_id": "art-1",
        "title": "Test Title",
        "url": "https://example.com/test",
        "target_keyword": "test keyword",
        "topic_cluster": "testing",
        "seo_score": 90.5,
        "publish_date": "2026-05-27T00:00:00Z",
        "status": "publish"
    }
    store.save_article(article)
    retrieved_article = store.get_article("art-1")
    assert retrieved_article is not None
    assert retrieved_article["title"] == "Test Title"
    assert retrieved_article["seo_score"] == 90.5

    # Test Distribution Assets
    asset = {
        "id": "art-1:blogger",
        "article_id": "art-1",
        "platform": "blogger",
        "content_variant": "<p>Adapted content</p>",
        "status": "published",
        "published_url": "https://blogger.com/post-1",
        "canonical_used": "https://example.com/test",
        "date_published": "2026-05-27T01:00:00Z"
    }
    store.save_distribution_asset(asset)
    assets = store.get_distribution_assets("art-1")
    assert len(assets) == 1
    assert assets[0]["platform"] == "blogger"
    assert assets[0]["published_url"] == "https://blogger.com/post-1"

    # Test Backlink Targets
    backlink = {
        "id": "art-1:competitor.com",
        "article_id": "art-1",
        "target_site": "competitor.com",
        "contact_name": "John Doe",
        "contact_email": "john@competitor.com",
        "outreach_angle": "Hey, saw your article...",
        "status": "pending",
        "response": None
    }
    store.save_backlink_target(backlink)
    backlinks = store.get_backlink_targets("art-1")
    assert len(backlinks) == 1
    assert backlinks[0]["target_site"] == "competitor.com"
    assert backlinks[0]["contact_name"] == "John Doe"

    # Test Daily Reports
    report = {
        "date": "2026-05-27",
        "posts_published": 1,
        "posts_syndicated": 1,
        "backlinks_created": 3,
        "indexing_status": "pending",
        "clicks": 10,
        "impressions": 100,
        "ranking_changes": "None",
        "repair_update_tasks": "None"
    }
    store.save_daily_report(report)
    retrieved_report = store.get_daily_report("2026-05-27")
    assert retrieved_report is not None
    assert retrieved_report["posts_published"] == 1
    assert retrieved_report["posts_syndicated"] == 1
    assert retrieved_report["backlinks_created"] == 3

