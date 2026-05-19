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
