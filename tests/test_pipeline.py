import pytest

from content_machine.config import Settings, SiteConfig
from content_machine.models import AuditReport, GeneratedContent, Opportunity, PublishDecision, WorkItemType
from content_machine.pipeline import ContentMachine


@pytest.mark.asyncio
async def test_pipeline_dry_run_persists_without_wordpress(monkeypatch, tmp_path):
    settings = Settings(
        root_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_db=tmp_path / "data" / "state.db",
        site=SiteConfig(brand_name="Test Brand"),
    )
    machine = ContentMachine(settings)

    async def fake_collect():
        return [Opportunity(WorkItemType.NEW_ARTICLE, "seo automation", "SEO Automation", 90)]

    async def fake_brief(opportunity):
        return {"serp": {"items": []}}

    async def fake_generate(opportunity, research):
        markdown = "# SEO Automation\n\n" + "\n\n".join([f"## Section {i}\n\nseo automation words " * 90 for i in range(1, 7)])
        return GeneratedContent(
            title="SEO Automation",
            slug="seo-automation",
            markdown=markdown,
            html="<h1>SEO Automation</h1>",
            meta_title="SEO Automation: Practical Guide",
            meta_description="A practical guide to SEO automation for content teams.",
            focus_keyphrase="seo automation",
            excerpt="A practical guide.",
            tags=["seo"],
            categories=["SEO"],
            schema_json={"@context": "https://schema.org", "@type": "Article"},
        )

    async def fail_wp(*args, **kwargs):
        raise AssertionError("WordPress should not be called on dry run")

    async def fake_repair(content, opportunity, research, audit):
        return content  # Return content as-is in test

    machine.collector.collect = fake_collect
    machine.researcher.brief = fake_brief
    machine.writer.generate = fake_generate
    machine.writer.repair = fake_repair
    machine.wordpress.find_post_by_slug = fail_wp
    machine.wordpress.upsert_post = fail_wp

    result = await machine.run_once(dry_run=True)

    assert result.wordpress_status == "dry_run"
    assert result.audit.score >= 70
    assert machine.store.recent_runs(1)[0]["dry_run"] is True


@pytest.mark.asyncio
async def test_pipeline_publish_updates_existing_slug(monkeypatch, tmp_path):
    settings = Settings(
        root_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_db=tmp_path / "data" / "state.db",
        site=SiteConfig(brand_name="Test Brand"),
    )
    machine = ContentMachine(settings)

    async def fake_collect():
        return [Opportunity(WorkItemType.NEW_ARTICLE, "seo automation", "SEO Automation", 90)]

    async def fake_brief(opportunity):
        return {"serp": {"items": []}}

    async def fake_generate(opportunity, research):
        markdown = "# SEO Automation\n\n" + "\n\n".join([f"## Section {i}\n\nseo automation words " * 90 for i in range(1, 7)])
        return GeneratedContent(
            title="SEO Automation",
            slug="seo-automation",
            markdown=markdown,
            html="<h1>SEO Automation</h1>",
            meta_title="SEO Automation: Practical Guide",
            meta_description="A practical guide to SEO automation for content teams.",
            focus_keyphrase="seo automation",
            excerpt="A practical guide.",
            tags=["seo"],
            categories=["SEO"],
            schema_json={"@context": "https://schema.org", "@type": "Article"},
        )

    captured = {}

    async def fake_find_post_by_slug(slug):
        captured["slug"] = slug
        return {"id": 11}

    async def fake_upsert(content, decision, existing_post_id=None):
        captured["existing_post_id"] = existing_post_id
        return {"id": existing_post_id, "status": "publish", "link": "https://example.com/seo-automation"}

    async def fake_repair(content, opportunity, research, audit):
        return content  # Return content as-is in test

    machine.collector.collect = fake_collect
    machine.researcher.brief = fake_brief
    machine.writer.generate = fake_generate
    machine.writer.repair = fake_repair
    machine.wordpress.find_post_by_slug = fake_find_post_by_slug
    machine.wordpress.upsert_post = fake_upsert

    async def fake_indexnow(urls):
        captured["indexnow_urls"] = urls

    machine.indexnow.submit = fake_indexnow

    result = await machine.run_once(dry_run=False)

    assert captured["slug"] == "seo-automation"
    assert captured["existing_post_id"] == 11
    assert captured["indexnow_urls"] == ["https://example.com/seo-automation"]
    assert result.wordpress_id == 11


@pytest.mark.asyncio
async def test_pipeline_repairs_before_publish(monkeypatch, tmp_path):
    settings = Settings(
        root_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_db=tmp_path / "data" / "state.db",
        site=SiteConfig(brand_name="Test Brand"),
    )
    machine = ContentMachine(settings)

    async def fake_collect():
        return [Opportunity(WorkItemType.NEW_ARTICLE, "seo automation", "SEO Automation", 90)]

    async def fake_brief(opportunity):
        return {}

    async def fake_generate(opportunity, research):
        return GeneratedContent(
            title="SEO Automation",
            slug="seo-automation",
            markdown="# SEO Automation\n\nWeak draft.",
            html="<h1>SEO Automation</h1>",
            meta_title="Too long title that does not fit SEO plugin preview limits at all",
            meta_description="Too short.",
            focus_keyphrase="seo automation platform for content teams",
            excerpt="Excerpt",
            tags=["seo"],
            categories=["SEO"],
            schema_json={"@type": "Article"},
        )

    async def fake_repair(content, opportunity, research, audit):
        return GeneratedContent(
            title="SEO Automation",
            slug="seo-automation",
            markdown="SEO automation helps teams publish content. ## SEO automation: Answer\n\nSEO automation works.",
            html="<p>SEO automation helps teams publish content.</p>",
            meta_title="SEO automation: Content Systems That Scale",
            meta_description="SEO automation helps lean teams research, create, optimize, and publish stronger search content with repeatable quality controls.",
            focus_keyphrase="seo automation",
            excerpt="Excerpt",
            tags=["seo"],
            categories=["SEO"],
            schema_json={"@type": "Article"},
            image_alt_text="SEO automation workflow image",
        )

    calls = {"audit": 0, "repair": 0}

    def fake_audit(content, opportunity, research):
        calls["audit"] += 1
        if calls["audit"] == 1:
            return AuditReport(84, PublishDecision.DRAFT, ["bad metadata"], [], [], {"repairable": True})
        return AuditReport(90, PublishDecision.PUBLISH, [], [], [], {"repairable": True})

    async def fake_upsert(content, decision, existing_post_id=None):
        return {"id": 7, "status": "publish", "link": "https://example.com/seo"}

    async def fake_find(slug):
        return None

    captured = {}

    machine.collector.collect = fake_collect
    machine.researcher.brief = fake_brief
    machine.writer.generate = fake_generate
    machine.writer.repair = fake_repair
    machine.auditor.audit = fake_audit
    machine.wordpress.find_post_by_slug = fake_find
    machine.wordpress.upsert_post = fake_upsert
    async def fake_indexnow(urls):
        captured["indexnow_urls"] = urls

    machine.indexnow.submit = fake_indexnow

    result = await machine.run_once(dry_run=False)

    assert calls["audit"] == 2
    assert result.audit.decision == PublishDecision.PUBLISH
    assert result.wordpress_status == "publish"
    assert captured["indexnow_urls"] == ["https://example.com/seo"]


@pytest.mark.asyncio
async def test_pipeline_saves_draft_when_repair_leaves_issues(monkeypatch, tmp_path):
    settings = Settings(
        root_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_db=tmp_path / "data" / "state.db",
        site=SiteConfig(brand_name="Test Brand"),
    )
    machine = ContentMachine(settings)

    async def fake_collect():
        return [Opportunity(WorkItemType.NEW_ARTICLE, "seo automation", "SEO Automation", 90)]

    async def fake_brief(opportunity):
        return {}

    async def fake_generate(opportunity, research):
        return GeneratedContent(
            title="SEO Automation",
            slug="seo-automation",
            markdown="Weak draft.",
            html="<p>Weak draft.</p>",
            meta_title="SEO automation: Content Systems That Scale",
            meta_description="SEO automation helps lean teams research, create, optimize, and publish stronger search content with repeatable quality controls.",
            focus_keyphrase="seo automation",
            excerpt="Excerpt",
            tags=["seo"],
            categories=["SEO"],
            schema_json={"@type": "Article"},
        )

    async def fake_repair(content, opportunity, research, audit):
        return content

    def fake_audit(content, opportunity, research):
        return AuditReport(84, PublishDecision.DRAFT, ["unresolved yoast issue"], [], [], {"repairable": True})

    captured = {}

    async def fake_upsert(content, decision, existing_post_id=None):
        captured["decision"] = decision
        return {"id": 7, "status": "draft", "link": "https://example.com/seo"}

    async def fake_find(slug):
        return None

    machine.collector.collect = fake_collect
    machine.researcher.brief = fake_brief
    machine.writer.generate = fake_generate
    machine.writer.repair = fake_repair
    machine.auditor.audit = fake_audit
    machine.wordpress.find_post_by_slug = fake_find
    machine.wordpress.upsert_post = fake_upsert

    result = await machine.run_once(dry_run=False)

    assert captured["decision"] == PublishDecision.DRAFT
    assert result.wordpress_status == "draft"


@pytest.mark.asyncio
async def test_pipeline_keeps_best_repaired_draft(monkeypatch, tmp_path):
    settings = Settings(
        root_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_db=tmp_path / "data" / "state.db",
        site=SiteConfig(brand_name="Test Brand"),
    )
    machine = ContentMachine(settings)

    async def fake_collect():
        return [Opportunity(WorkItemType.NEW_ARTICLE, "seo automation", "SEO Automation", 90)]

    async def fake_brief(opportunity):
        return {}

    async def fake_generate(opportunity, research):
        return GeneratedContent(
            title="SEO Automation",
            slug="seo-automation",
            markdown="Initial draft.",
            html="<p>Initial draft.</p>",
            meta_title="SEO automation: Content Systems That Scale",
            meta_description="SEO automation helps lean teams research, create, optimize, and publish stronger search content with repeatable quality controls.",
            focus_keyphrase="seo automation",
            excerpt="Excerpt",
            tags=["seo"],
            categories=["SEO"],
            schema_json={"@type": "Article"},
        )

    repair_calls = {"count": 0}

    async def fake_repair(content, opportunity, research, audit):
        repair_calls["count"] += 1
        markdown = "Better draft." if repair_calls["count"] == 1 else "Worse draft."
        return GeneratedContent(
            title="SEO Automation",
            slug="seo-automation",
            markdown=markdown,
            html=f"<p>{markdown}</p>",
            meta_title="SEO automation: Content Systems That Scale",
            meta_description="SEO automation helps lean teams research, create, optimize, and publish stronger search content with repeatable quality controls.",
            focus_keyphrase="seo automation",
            excerpt="Excerpt",
            tags=["seo"],
            categories=["SEO"],
            schema_json={"@type": "Article"},
        )

    def fake_audit(content, opportunity, research):
        if "Better draft" in content.markdown:
            return AuditReport(84, PublishDecision.DRAFT, ["readability"], [], [], {"repairable": True})
        if "Worse draft" in content.markdown:
            return AuditReport(72, PublishDecision.DRAFT, ["readability", "factuality"], [], [], {"repairable": True})
        return AuditReport(78, PublishDecision.DRAFT, ["metadata"], [], [], {"repairable": True})

    captured = {}

    async def fake_upsert(content, decision, existing_post_id=None):
        captured["markdown"] = content.markdown
        return {"id": 7, "status": "draft", "link": "https://example.com/seo"}

    async def fake_find(slug):
        return None

    machine.collector.collect = fake_collect
    machine.researcher.brief = fake_brief
    machine.writer.generate = fake_generate
    machine.writer.repair = fake_repair
    machine.auditor.audit = fake_audit
    machine.wordpress.find_post_by_slug = fake_find
    machine.wordpress.upsert_post = fake_upsert

    result = await machine.run_once(dry_run=False)

    assert repair_calls["count"] == 2
    assert result.audit.score == 84
    assert "Better draft." in result.content.markdown
    assert "Worse draft." not in result.content.markdown
    assert "Better draft." in captured["markdown"]
    assert "Worse draft." not in captured["markdown"]


@pytest.mark.asyncio
async def test_pipeline_draft_does_not_unpublish_existing_post(monkeypatch, tmp_path):
    settings = Settings(
        root_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_db=tmp_path / "data" / "state.db",
        site=SiteConfig(brand_name="Test Brand"),
    )
    machine = ContentMachine(settings)

    async def fake_collect():
        return [Opportunity(WorkItemType.NEW_ARTICLE, "seo automation", "SEO Automation", 90)]

    async def fake_brief(opportunity):
        return {}

    async def fake_generate(opportunity, research):
        return GeneratedContent(
            title="SEO Automation",
            slug="seo-automation",
            markdown="Weak draft.",
            html="<p>Weak draft.</p>",
            meta_title="SEO automation: Content Systems That Scale",
            meta_description="SEO automation helps lean teams research, create, optimize, and publish stronger search content with repeatable quality controls.",
            focus_keyphrase="seo automation",
            excerpt="Excerpt",
            tags=["seo"],
            categories=["SEO"],
            schema_json={"@type": "Article"},
        )

    def fake_audit(content, opportunity, research):
        return AuditReport(84, PublishDecision.DRAFT, ["unresolved readability issue"], [], [], {"repairable": False})

    captured = {}

    async def fake_find(slug):
        return {"id": 11, "status": "publish"}

    async def fake_upsert(content, decision, existing_post_id=None):
        captured["existing_post_id"] = existing_post_id
        captured["slug"] = content.slug
        return {"id": 12, "status": "draft", "link": "https://example.com/draft"}

    machine.collector.collect = fake_collect
    machine.researcher.brief = fake_brief
    machine.writer.generate = fake_generate
    machine.auditor.audit = fake_audit
    machine.wordpress.find_post_by_slug = fake_find
    machine.wordpress.upsert_post = fake_upsert

    result = await machine.run_once(dry_run=False)

    assert captured["existing_post_id"] is None
    assert captured["slug"].startswith("seo-automation-draft-")
    assert result.wordpress_id == 12


@pytest.mark.asyncio
async def test_pipeline_blocks_below_threshold(monkeypatch, tmp_path):
    settings = Settings(
        root_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_db=tmp_path / "data" / "state.db",
        site=SiteConfig(brand_name="Test Brand"),
    )
    machine = ContentMachine(settings)

    async def fake_collect():
        return [Opportunity(WorkItemType.NEW_ARTICLE, "seo automation", "SEO Automation", 90)]

    async def fake_brief(opportunity):
        return {}

    async def fake_generate(opportunity, research):
        return GeneratedContent(
            title="SEO Automation",
            slug="seo-automation",
            markdown="Bad.",
            html="<p>Bad.</p>",
            meta_title="Bad",
            meta_description="Bad.",
            focus_keyphrase="seo automation",
            excerpt="Bad.",
            tags=["seo"],
            categories=["SEO"],
            schema_json={},
        )

    def fake_audit(content, opportunity, research):
        return AuditReport(60, PublishDecision.BLOCK, ["low quality"], [], [], {"repairable": False})

    async def fail_wp(*args, **kwargs):
        raise AssertionError("Blocked content should not be sent to WordPress")

    machine.collector.collect = fake_collect
    machine.researcher.brief = fake_brief
    machine.writer.generate = fake_generate
    machine.auditor.audit = fake_audit
    machine.wordpress.find_post_by_slug = fail_wp
    machine.wordpress.upsert_post = fail_wp

    result = await machine.run_once(dry_run=False)

    assert result.wordpress_status == "blocked"


@pytest.mark.asyncio
async def test_pipeline_adds_wordpress_internal_links_to_research(tmp_path):
    settings = Settings(
        root_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_db=tmp_path / "data" / "state.db",
        site=SiteConfig(brand_name="Test Brand"),
    )
    machine = ContentMachine(settings)

    async def fake_collect():
        return [Opportunity(WorkItemType.NEW_ARTICLE, "seo automation", "SEO Automation", 90)]

    async def fake_brief(opportunity):
        return {"serp": {"items": []}}

    async def fake_internal_links(limit=20):
        return [{"title": "MeetLyra SEO workflow", "url": "https://blog.meetlyra.app/seo-workflow/", "slug": "seo-workflow"}]

    captured = {}

    async def fake_generate(opportunity, research):
        captured["research"] = research
        return GeneratedContent(
            title="SEO Automation",
            slug="seo-automation",
            markdown="SEO automation draft.",
            html="<p>SEO automation draft.</p>",
            meta_title="SEO automation: Content Systems That Scale",
            meta_description="SEO automation helps lean teams research, create, optimize, and publish stronger search content with repeatable quality controls.",
            focus_keyphrase="seo automation",
            excerpt="Excerpt",
            tags=["seo"],
            categories=["SEO"],
            schema_json={"@type": "Article"},
        )

    def fake_audit(content, opportunity, research):
        return AuditReport(70, PublishDecision.DRAFT, ["draft only"], [], [], {"repairable": False})

    machine.collector.collect = fake_collect
    machine.researcher.brief = fake_brief
    machine.wordpress.internal_link_candidates = fake_internal_links
    machine.writer.generate = fake_generate
    machine.auditor.audit = fake_audit

    await machine.run_once(dry_run=True)

    assert captured["research"]["internal_links"][0]["slug"] == "seo-workflow"
