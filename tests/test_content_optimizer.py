from content_machine.content_optimizer import derive_focus_keyphrase, optimize_content, strip_leading_h1
from content_machine.models import GeneratedContent, Opportunity, WorkItemType


def _content(markdown: str, **overrides):
    data = dict(
        title="AI Marketing Agent for SEO Content: Long Title",
        slug="ai-marketing-agent-for-seo-content",
        markdown=markdown,
        html="",
        meta_title="AI Marketing Agent for SEO Content: Autonomous Content Systems That Scale",
        meta_description="Learn how autonomous systems replace entire content workflows for lean teams.",
        focus_keyphrase="AI marketing agent for SEO content",
        excerpt="Excerpt",
        tags=["seo"],
        categories=["SEO"],
        schema_json={"@type": "Article"},
        image_prompt="AI marketing workflow dashboard",
    )
    data.update(overrides)
    return GeneratedContent(**data)


def test_strip_leading_h1_removes_duplicate_body_title():
    markdown = "# Duplicate Title\n\nFirst paragraph.\n\n## Section\n\nBody."

    assert strip_leading_h1(markdown).startswith("First paragraph.")


def test_optimizer_shortens_keyphrase_and_metadata():
    opportunity = Opportunity(WorkItemType.NEW_ARTICLE, "AI marketing agent for SEO content", "Title", 90)
    optimized = optimize_content(_content("# Duplicate\n\nOpening paragraph."), opportunity)

    assert optimized.focus_keyphrase == "AI marketing agent"
    assert optimized.meta_title.startswith("AI marketing agent")
    assert 45 <= len(optimized.meta_title) <= 60
    assert "AI marketing agent" in optimized.meta_description
    assert 130 <= len(optimized.meta_description) <= 155
    assert not optimized.markdown.startswith("# ")


def test_optimizer_adds_rich_gutenberg_blocks():
    opportunity = Opportunity(WorkItemType.NEW_ARTICLE, "seo automation", "Title", 90)
    optimized = optimize_content(_content("Opening paragraph.\n\n## First Section\n\nBody.\n\n## Second Section\n\nBody.", focus_keyphrase="seo automation"), opportunity)

    assert "wp:quote" in optimized.markdown
    # seo-machine-reading-time block is intentionally removed (writer prompt bans it)
    assert "seo-machine-reading-time" not in optimized.markdown
    assert "seo-machine-quick-answer" in optimized.markdown
    assert "seo-machine-toc" in optimized.markdown
    assert "seo-machine-proof" in optimized.markdown
    assert "seo-machine-chart" in optimized.markdown
    assert "seo-machine-faq" in optimized.markdown
    assert "seo-machine-related" in optimized.markdown
    # seo-machine-quick-answer is now the first structural block (before First Section)
    assert optimized.markdown.index("seo-machine-quick-answer") < optimized.markdown.index("## First Section")
    assert optimized.markdown.index("seo-machine-proof") < optimized.markdown.index("## Second Section")


def test_optimizer_does_not_append_transition_padding_snippet():
    opportunity = Opportunity(WorkItemType.NEW_ARTICLE, "seo automation", "Title", 90)
    optimized = optimize_content(_content("Opening paragraph.", focus_keyphrase="seo automation"), opportunity)

    assert "this workflow should stay easy to scan" not in optimized.markdown.lower()


def test_optimizer_handles_gutenberg_html():
    opportunity = Opportunity(WorkItemType.NEW_ARTICLE, "seo automation", "Title", 90)
    gutenberg_html = (
        "<!-- wp:paragraph -->\n"
        "<p>This is the opening paragraph containing some information about seo automation.</p>\n"
        "<!-- /wp:paragraph -->\n\n"
        "<!-- wp:heading {\"level\":2} -->\n"
        "<h2>First Section</h2>\n"
        "<!-- /wp:heading -->\n\n"
        "<!-- wp:paragraph -->\n"
        "<p>This is the first body paragraph about seo automation optimization.</p>\n"
        "<!-- /wp:paragraph -->\n\n"
        "<!-- wp:heading {\"level\":2} -->\n"
        "<h2>Second Section</h2>\n"
        "<!-- /wp:heading -->\n\n"
        "<!-- wp:paragraph -->\n"
        "<p>This is the second body paragraph about seo automation tools.</p>\n"
        "<!-- /wp:paragraph -->"
    )
    optimized = optimize_content(_content(gutenberg_html, focus_keyphrase="seo automation"), opportunity)

    # Verify that the Gutenberg HTML is preserved and rich blocks are inserted correctly
    assert "wp:paragraph" in optimized.markdown
    # seo-machine-reading-time block is intentionally removed (writer prompt bans it)
    assert "seo-machine-reading-time" not in optimized.markdown
    assert "seo-machine-quick-answer" in optimized.markdown
    assert "seo-machine-toc" in optimized.markdown
    assert "seo-machine-proof" in optimized.markdown
    assert "seo-machine-chart" in optimized.markdown
    assert "seo-machine-faq" in optimized.markdown
    assert "seo-machine-related" in optimized.markdown
    assert "wp:heading" in optimized.markdown
    assert "<h2>First Section</h2>" in optimized.markdown
    assert "<h2>Second Section</h2>" in optimized.markdown
    assert "is the opening paragraph" in optimized.markdown  # transition word may lowercase the first letter
