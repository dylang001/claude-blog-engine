import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from content_machine.config import Settings, SiteConfig
from content_machine.screenshots import capture_screenshot, process_inline_screenshots

@pytest.mark.asyncio
async def test_capture_screenshot_failure_when_playwright_fails(tmp_path):
    # Tests that when Playwright is mocked to raise an error, it returns False.
    result = await capture_screenshot("https://nonexistent-url.local", tmp_path / "screenshot.png")
    assert result is False

@pytest.mark.asyncio
async def test_process_inline_screenshots(tmp_path, monkeypatch):
    settings = Settings(
        root_dir=tmp_path,
        data_dir=tmp_path,
        state_db=tmp_path / "db.sqlite",
        site=SiteConfig(),
        wp_base_url="https://example.com",
        wp_username="user",
        wp_app_password="pass",
    )

    # Mock capture_screenshot to always succeed without actual headless browser launch
    mock_capture = AsyncMock(return_value=True)
    monkeypatch.setattr("content_machine.screenshots.capture_screenshot", mock_capture)

    # Mock WordPress client
    mock_wp_client = MagicMock()
    mock_wp_client.upload_media = AsyncMock(side_effect=lambda path, alt_text: {
        "id": 42,
        "url": "https://example.com/wp-content/uploads/screenshot.png"
    })

    # Gutenberg block screenshot placeholder
    input_html = """
<!-- wp:paragraph -->
<p>Check the documentation below.</p>
<!-- /wp:paragraph -->

<!-- wp:image {"sizeSlug":"large","linkDestination":"none"} -->
<figure class="wp-block-image"><img src="screenshot:https://playwright.dev/docs/getting-started-mcp" alt="Playwright Docs" /></figure>
<!-- /wp:image -->

<!-- wp:paragraph -->
<p>And here is another naked image.</p>
<!-- /wp:paragraph -->

<img src="screenshot:https://github.com" alt="GitHub Homepage" />
"""

    output_html = await process_inline_screenshots(input_html, mock_wp_client, settings)

    # Verify capture_screenshot was called twice with correct URLs
    from unittest.mock import ANY
    assert mock_capture.call_count == 2
    mock_capture.assert_any_call("https://playwright.dev/docs/getting-started-mcp", ANY)
    mock_capture.assert_any_call("https://github.com", ANY)


    # Verify upload_media was called twice
    assert mock_wp_client.upload_media.call_count == 2

    # Verify Gutenberg block comment has the ID and sizeSlug/linkDestination, but without asserting exact JSON key order
    import re
    comment_match = re.search(r'<!--\s*wp:image\s*(\{.*?\})\s*-->', output_html)
    assert comment_match is not None
    import json
    attrs = json.loads(comment_match.group(1))
    assert attrs.get("id") == 42
    assert attrs.get("sizeSlug") == "large"
    assert attrs.get("linkDestination") == "none"

    # Verify the image tags have the updated src
    assert 'src="https://example.com/wp-content/uploads/screenshot.png"' in output_html
    # Verify class is updated with wp-image-42 and correctly formatted without malformed slash placement
    assert 'wp-image-42' in output_html
    assert 'screenshot-inline' in output_html
    assert 'alt="Playwright Docs" class="wp-image-42 screenshot-inline" /' in output_html
    assert 'alt="Playwright Docs" / class="wp-image-42' not in output_html

