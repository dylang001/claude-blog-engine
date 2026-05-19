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
    assert "seo-machine-reading-time" in optimized.markdown
    assert "seo-machine-toc" in optimized.markdown
    assert "seo-machine-proof" in optimized.markdown
    assert "seo-machine-chart" in optimized.markdown
    assert "seo-machine-faq" in optimized.markdown
    assert "seo-machine-related" in optimized.markdown
    assert optimized.markdown.index("seo-machine-reading-time") < optimized.markdown.index("## First Section")
    assert optimized.markdown.index("seo-machine-proof") < optimized.markdown.index("## Second Section")


def test_optimizer_does_not_append_transition_padding_snippet():
    opportunity = Opportunity(WorkItemType.NEW_ARTICLE, "seo automation", "Title", 90)
    optimized = optimize_content(_content("Opening paragraph.", focus_keyphrase="seo automation"), opportunity)

    assert "this workflow should stay easy to scan" not in optimized.markdown.lower()
