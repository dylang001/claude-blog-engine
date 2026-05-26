from content_machine.config import Settings, SiteConfig
from content_machine.images import BananaImageGenerator
from content_machine.models import GeneratedContent


def _settings(tmp_path):
    return Settings(root_dir=tmp_path, data_dir=tmp_path, state_db=tmp_path / "db.sqlite", site=SiteConfig())


def test_banana_prompt_uses_lyra_house_style(tmp_path):
    content = GeneratedContent(
        title="AI Marketing Agent",
        slug="ai-marketing-agent",
        markdown="Body",
        html="",
        meta_title="AI Marketing Agent Guide",
        meta_description="AI Marketing Agent guide for SEO workflows.",
        focus_keyphrase="AI marketing agent",
        excerpt="Excerpt",
        tags=["seo"],
        categories=["SEO"],
        schema_json={"@type": "Article"},
        image_prompt="Show a content planning workflow.",
        image_alt_text="AI marketing agent workflow",
    )

    prompt = BananaImageGenerator(_settings(tmp_path))._build_banana_prompt(content.title, content.image_prompt)

    assert "Premium editorial photography" in prompt
    assert "no readable text" in prompt.lower()
    assert "no logos" in prompt.lower()
    assert "completely text-free" in prompt.lower()
    assert "no illustration" in prompt.lower()
