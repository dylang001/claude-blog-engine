import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from content_machine.config import Settings, SiteConfig
from content_machine.screenshots import process_inline_screenshots

async def main():
    settings = Settings(
        root_dir=Path("."),
        data_dir=Path("."),
        state_db=Path("db.sqlite"),
        site=SiteConfig(),
    )
    
    # Mock capture_screenshot to always succeed
    import content_machine.screenshots
    content_machine.screenshots.capture_screenshot = AsyncMock(return_value=True)
    
    # Mock WordPress client
    mock_wp_client = MagicMock()
    mock_wp_client.upload_media = AsyncMock(return_value={
        "id": 42,
        "url": "https://example.com/wp-content/uploads/screenshot.png"
    })
    
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
    
    out = await process_inline_screenshots(input_html, mock_wp_client, settings)
    print("OUTPUT:")
    print(repr(out))

asyncio.run(main())
