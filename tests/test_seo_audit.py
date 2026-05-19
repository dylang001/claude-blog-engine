from content_machine.config import Settings, SiteConfig
from content_machine.content_optimizer import optimize_content
from content_machine.models import GeneratedContent, Opportunity, WorkItemType
from content_machine.seo_audit import SEOAuditEngine


def _settings(tmp_path):
    return Settings(root_dir=tmp_path, data_dir=tmp_path, state_db=tmp_path / "db.sqlite", site=SiteConfig())


def _content(markdown: str, **overrides):
    data = dict(
        title="SEO Automation",
        slug="seo-automation",
        markdown=markdown,
        html="",
        meta_title="SEO Automation Guide",
        meta_description="A practical guide.",
        focus_keyphrase="seo automation",
        excerpt="Excerpt",
        tags=["seo"],
        categories=["SEO"],
        schema_json={"@type": "Article"},
        image_alt_text="SEO automation workflow image",
    )
    data.update(overrides)
    return GeneratedContent(**data)


def test_audit_flags_duplicate_h1_and_bad_yoast_fields(tmp_path):
    audit = SEOAuditEngine(_settings(tmp_path)).audit(
        _content("# SEO Automation\n\nThis intro misses the target setup."),
        Opportunity(WorkItemType.NEW_ARTICLE, "seo automation", "SEO Automation", 90),
        {},
    )

    assert any("duplicate H1" in issue for issue in audit.issues)
    assert any("Meta description" in issue for issue in audit.issues)
    assert audit.decision.value != "publish"


def test_audit_accepts_optimized_content_for_publish(tmp_path):
    opportunity = Opportunity(WorkItemType.NEW_ARTICLE, "seo automation", "SEO Automation", 90)
    markdown = "\n\n".join(
        [
            "SEO automation helps teams plan, create, optimize, and publish search content consistently. First, it turns manual research into a repeatable process.",
            "## SEO automation: Quick Answer\n\nSEO automation connects keyword research, content briefs, publishing, and monitoring into one workflow.",
            "## Research\n\nSEO automation keeps the work focused. Also, it makes decisions easier.",
            "## Creation\n\nSEO automation supports clear drafting. Therefore, teams can publish more reliably.",
            "## Optimization\n\nSEO automation improves metadata, links, and structure. However, humans still review strategy.",
            "## Publishing\n\nSEO automation prepares WordPress-ready content. Finally, teams can monitor outcomes.",
            " ".join(["Also, SEO automation helps teams make clear content plans. Therefore, teams publish useful pages with less delay."] * 130),
        ]
    )
    content = optimize_content(_content(markdown), opportunity)
    audit = SEOAuditEngine(_settings(tmp_path)).audit(content, opportunity, {})

    assert audit.details["h1_count"] == 0
    assert audit.details["outbound_link_count"] >= 1
    assert audit.details["rich_block_count"] >= 4
    assert audit.decision.value == "publish"


def test_audit_warns_on_exact_match_internal_anchor(tmp_path):
    opportunity = Opportunity(WorkItemType.NEW_ARTICLE, "seo automation", "SEO Automation", 90)
    markdown = "\n\n".join(
        [
            "SEO automation helps teams plan, create, optimize, and publish search content consistently. First, it turns manual research into a repeatable process.",
            "## SEO automation: Quick Answer\n\nSEO automation connects keyword research, content briefs, publishing, and monitoring into one workflow.",
            "## Research\n\nSEO automation keeps the work focused. Also, it makes decisions easier.",
            "## Creation\n\nSEO automation supports clear drafting. Therefore, teams can publish more reliably.",
            "## Optimization\n\nSEO automation improves metadata, links, and structure. However, humans still review strategy.",
            "## Publishing\n\nSEO automation prepares WordPress-ready content. Finally, teams can monitor outcomes.",
            "[seo automation](https://blog.meetlyra.app/example) adds a risky exact-match internal anchor.",
            " ".join(["Also, SEO automation helps teams make clear content plans. Therefore, teams publish useful pages with less delay."] * 130),
        ]
    )
    content = optimize_content(_content(markdown), opportunity)
    audit = SEOAuditEngine(_settings(tmp_path)).audit(content, opportunity, {})

    assert audit.details["exact_internal_anchor_count"] == 1
    assert any("exact focus keyphrase" in warning for warning in audit.warnings)


def test_audit_requires_two_internal_links_for_publish(tmp_path):
    opportunity = Opportunity(WorkItemType.NEW_ARTICLE, "seo automation", "SEO Automation", 90)
    markdown = "\n\n".join(
        [
            "SEO automation helps teams plan, create, optimize, and publish search content consistently. First, it turns manual research into a repeatable process.",
            "## SEO automation: Quick Answer\n\nSEO automation connects keyword research, content briefs, publishing, and monitoring into one workflow.",
            "## Research\n\nSEO automation keeps the work focused. Also, it makes decisions easier.",
            "## Creation\n\nSEO automation supports clear drafting. Therefore, teams can publish more reliably.",
            "## Optimization\n\nSEO automation improves metadata, links, and structure. However, humans still review strategy.",
            "## Publishing\n\nSEO automation prepares WordPress-ready content. Finally, teams can monitor outcomes.",
            "[Read the MeetLyra workflow](https://blog.meetlyra.app/example).",
            " ".join(["Also, SEO automation helps teams make clear content plans. Therefore, teams publish useful pages with less delay."] * 130),
        ]
    )
    content = _content(
        markdown,
        meta_title="SEO automation: Systems That Scale",
        meta_description="SEO automation helps teams research, create, optimize, and publish stronger search content with reliable quality controls.",
    )
    audit = SEOAuditEngine(_settings(tmp_path)).audit(content, opportunity, {})

    assert audit.details["internal_link_count"] == 1
    assert any("at least two internal" in issue for issue in audit.issues)
    assert audit.decision.value != "publish"


def test_audit_reports_blog_and_product_internal_link_domains(tmp_path):
    opportunity = Opportunity(WorkItemType.NEW_ARTICLE, "seo automation", "SEO Automation", 90)
    markdown = "\n\n".join(
        [
            "SEO automation helps teams plan, create, optimize, and publish search content consistently. First, it turns manual research into a repeatable process.",
            "## SEO automation: Quick Answer\n\nSEO automation connects keyword research, content briefs, publishing, and monitoring into one workflow.",
            "## Research\n\nSEO automation keeps the work focused. Also, it makes decisions easier.",
            "## Creation\n\nSEO automation supports clear drafting. Therefore, teams can publish more reliably.",
            "## Optimization\n\nSEO automation improves metadata, links, and structure. However, humans still review strategy.",
            "## Publishing\n\nSEO automation prepares WordPress-ready content. Finally, teams can monitor outcomes.",
            "[Read the blog guide](https://blog.meetlyra.app/example). [Explore the app workflow](https://meetlyra.app/features/content-engine).",
            " ".join(["Also, SEO automation helps teams make clear content plans. Therefore, teams publish useful pages with less delay."] * 130),
        ]
    )
    content = _content(
        markdown,
        meta_title="SEO automation: Systems That Scale",
        meta_description="SEO automation helps teams research, create, optimize, and publish stronger search content with reliable quality controls.",
    )
    audit = SEOAuditEngine(_settings(tmp_path)).audit(content, opportunity, {})

    assert audit.details["internal_link_count"] == 2
    assert audit.details["internal_link_domains"]["blog.meetlyra.app"] == 1
    assert audit.details["internal_link_domains"]["meetlyra.app"] == 1


def test_audit_blocks_unsupported_case_study_claims(tmp_path):
    opportunity = Opportunity(WorkItemType.NEW_ARTICLE, "seo automation", "SEO Automation", 90)
    markdown = "\n\n".join(
        [
            "SEO automation helps teams plan, create, optimize, and publish search content consistently. First, it turns manual research into a repeatable process.",
            "## SEO automation: Quick Answer\n\nSEO automation connects keyword research, content briefs, publishing, and monitoring into one workflow.",
            "## Research\n\nSEO automation keeps the work focused. Also, it makes decisions easier.",
            "## Creation\n\nSEO automation supports clear drafting. Therefore, teams can publish more reliably.",
            "## Optimization\n\nSEO automation improves metadata, links, and structure. However, humans still review strategy.",
            "## Publishing\n\nSEO automation prepares WordPress-ready content. Finally, teams can monitor outcomes.",
            "## Real-World Results\n\nA B2B SaaS Company increased organic traffic 340% within six months after publishing 20 articles monthly.",
            "[Read the MeetLyra workflow](https://blog.meetlyra.app/example). [Explore the content engine](https://meetlyra.app/).",
            " ".join(["Also, SEO automation helps teams make clear content plans. Therefore, teams publish useful pages with less delay."] * 130),
        ]
    )
    content = optimize_content(_content(markdown), opportunity)
    audit = SEOAuditEngine(_settings(tmp_path)).audit(content, opportunity, {})

    assert any("case-study" in issue for issue in audit.issues)
    assert any("quantified performance" in issue for issue in audit.issues)
    assert audit.details["factuality"]["unsupported_metric_claim_count"] >= 1
    assert audit.decision.value == "block"
