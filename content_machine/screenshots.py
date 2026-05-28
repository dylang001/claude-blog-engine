import os
import re
import uuid
import logging
import asyncio
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

async def capture_screenshot(url: str, output_path: Path) -> bool:
    """
    Launches headless Chromium via Playwright, navigates to the URL,
    and saves a high-quality viewport screenshot.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error(
            "Playwright is not installed in the python environment. "
            "Please run: pip install playwright && playwright install chromium"
        )
        return False

    try:
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with async_playwright() as p:
            logger.info(f"Launching browser to capture screenshot of {url}...")
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                device_scale_factor=2.0, # High DPI screenshot
            )
            page = await context.new_page()
            
            # Go to page with 30s timeout
            await page.goto(url, wait_until="load", timeout=30000)
            
            # Wait for any lazy animations or dynamic components to finish rendering
            await asyncio.sleep(2.0)
            
            # Take screenshot of the viewport
            await page.screenshot(path=str(output_path), full_page=False)
            logger.info(f"Saved screenshot to {output_path}")
            
            await browser.close()
            return True
    except Exception as e:
        logger.exception(f"Failed to capture screenshot for {url}: {e}")
        return False


async def process_inline_screenshots(html: str, wordpress_client: Any, settings: Any) -> str:
    """
    Scans HTML for screenshot:URL placeholders, takes screenshots of those URLs,
    uploads them to WordPress, and updates the image tags and Gutenberg block comments.
    """
    if not html:
        return html

    images_dir = settings.data_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # 1. Process Gutenberg-wrapped screenshot image blocks
    # Pattern: <!-- wp:image {attrs} -->...<img src="screenshot:URL" alt="Alt"...>...<!-- /wp:image -->
    block_pattern = re.compile(
        r"(<!--\s*wp:image\s*(?P<attrs>\{.*?\})?\s*-->.*?<img\b(?P<img_attrs>[^>]*?)src=[\"']screenshot:(?P<url>https?://[^\"']+)[\"'](?P<img_attrs_end>[^>]*?)>.*?<!--\s*/wp:image\s*-->)",
        re.DOTALL | re.IGNORECASE
    )

    async def replace_block(match) -> str:
        full_block = match.group(1)
        attrs_str = match.group("attrs") or ""
        url = match.group("url")
        img_attrs = match.group("img_attrs") or ""
        img_attrs_end = match.group("img_attrs_end") or ""

        # Extract alt text if present
        alt_match = re.search(r'alt=["\']([^"\']*)["\']', img_attrs + img_attrs_end, re.IGNORECASE)
        alt_text = alt_match.group(1) if alt_match else f"Screenshot of {urlparse(url).netloc}"

        # Generate a unique path for the screenshot
        safe_domain = urlparse(url).netloc.replace(".", "_")
        filename = f"screenshot-{safe_domain}-{uuid.uuid4().hex[:8]}.png"
        screenshot_path = images_dir / filename

        success = await capture_screenshot(url, screenshot_path)
        if not success:
            logger.warning(f"Could not capture screenshot for {url}, leaving placeholder.")
            return full_block

        try:
            logger.info(f"Uploading captured screenshot for {url} to WordPress...")
            media_info = await wordpress_client.upload_media(str(screenshot_path), alt_text=alt_text)
            if not media_info or not media_info.get("id") or not media_info.get("url"):
                logger.warning(f"Failed to upload media to WordPress for {url}, leaving placeholder.")
                return full_block

            media_id = media_info["id"]
            media_url = media_info["url"]

            # Update block JSON attributes with new media ID
            new_attrs_str = attrs_str
            if attrs_str:
                import json
                try:
                    attrs = json.loads(attrs_str)
                    attrs["id"] = media_id
                    new_attrs_str = json.dumps(attrs, separators=(',', ':'))
                except Exception:
                    new_attrs_str = re.sub(r'("id"\s*:\s*)\d+', rf'\g<1>{media_id}', attrs_str)
            else:
                new_attrs_str = f'{{"id":{media_id},"sizeSlug":"large","linkDestination":"none"}}'

            # Reconstruct the image tag with new src and wp-image class
            new_img_attrs = img_attrs
            new_img_attrs_end = img_attrs_end

            # Replace class wp-image-xxx or insert one
            class_pattern = r'(class\s*=\s*["\'])([^"\']*wp-image-)?(\d+)?([^"\']*["\'])'
            if re.search(class_pattern, new_img_attrs + new_img_attrs_end, re.IGNORECASE):
                def class_replacer(m):
                    prefix = m.group(2) or "wp-image-"
                    # Append screenshot-inline class if not present
                    classes_part = m.group(2) or ""
                    suffix_part = m.group(4)
                    if "screenshot-inline" not in classes_part and "screenshot-inline" not in suffix_part:
                        return f'{m.group(1)}{prefix}{media_id} screenshot-inline{m.group(4)}'
                    return f'{m.group(1)}{prefix}{media_id}{m.group(4)}'
                new_img_attrs = re.sub(class_pattern, class_replacer, new_img_attrs)
                new_img_attrs_end = re.sub(class_pattern, class_replacer, new_img_attrs_end)
            else:
                # Add class if not present
                stripped = new_img_attrs_end.rstrip()
                if stripped.endswith("/"):
                    new_img_attrs_end = stripped[:-1].rstrip() + f' class="wp-image-{media_id} screenshot-inline" /'
                else:
                    new_img_attrs_end += f' class="wp-image-{media_id} screenshot-inline"'


            # Assemble the new HTML block
            new_block = full_block
            if attrs_str:
                new_block = new_block.replace(attrs_str, new_attrs_str, 1)
            else:
                new_block = new_block.replace("<!-- wp:image -->", f"<!-- wp:image {new_attrs_str} -->", 1)
                
            # Replace the source URL
            placeholder_src = f'src="screenshot:{url}"'
            placeholder_src_single = f"src='screenshot:{url}'"
            new_src = f'src="{media_url}"'
            new_block = new_block.replace(placeholder_src, new_src).replace(placeholder_src_single, new_src)
            
            # Update any other attributes (classes, etc.)
            new_block = new_block.replace(img_attrs, new_img_attrs, 1).replace(img_attrs_end, new_img_attrs_end, 1)

            logger.info(f"Successfully processed block screenshot for {url} (ID: {media_id})")
            return new_block
        except Exception as e:
            logger.exception(f"Error processing WordPress upload/replace for screenshot {url}: {e}")
            return full_block

    # Run asynchronous replacements for Gutenberg blocks
    processed_html = html
    matches = list(block_pattern.finditer(html))
    # Process matches in reverse order to keep indices valid during replacement
    for match in reversed(matches):
        replacement = await replace_block(match)
        start, end = match.span(0)
        processed_html = processed_html[:start] + replacement + processed_html[end:]

    # 2. Process raw/naked screenshot img tags outside Gutenberg blocks
    raw_pattern = re.compile(
        r'<img\b(?P<before>[^>]*?)src=["\']screenshot:(?P<url>https?://[^"\']+)["\'](?P<after>[^>]*?)>',
        re.IGNORECASE
    )

    async def replace_raw_img(match) -> str:
        full_tag = match.group(0)
        url = match.group("url")
        before = match.group("before") or ""
        after = match.group("after") or ""

        alt_match = re.search(r'alt=["\']([^"\']*)["\']', before + after, re.IGNORECASE)
        alt_text = alt_match.group(1) if alt_match else f"Screenshot of {urlparse(url).netloc}"

        filename = f"screenshot-{urlparse(url).netloc.replace('.', '_')}-{uuid.uuid4().hex[:8]}.png"
        screenshot_path = images_dir / filename

        success = await capture_screenshot(url, screenshot_path)
        if not success:
            return full_tag

        try:
            media_info = await wordpress_client.upload_media(str(screenshot_path), alt_text=alt_text)
            if not media_info or not media_info.get("url"):
                return full_tag
            
            media_url = media_info["url"]
            media_id = media_info.get("id")

            # Replace screenshot:URL with media URL
            new_tag = re.sub(
                r'src=["\']screenshot:https?://[^"\']+["\']',
                f'src="{media_url}"',
                full_tag,
                flags=re.IGNORECASE
            )
            # Add wp-image class if we have an ID
            if media_id:
                if "class=" in new_tag:
                    new_tag = re.sub(
                        r'(class\s*=\s*["\'])([^"\']*?)(\bwp-image-\d+\b)?([^"\']*?["\'])',
                        rf'\1\2 wp-image-{media_id} screenshot-inline \4',
                        new_tag
                    )
                else:
                    new_tag = new_tag.rstrip(">").rstrip("/") + f' class="wp-image-{media_id} screenshot-inline">'
            return new_tag
        except Exception:
            return full_tag

    raw_matches = list(raw_pattern.finditer(processed_html))
    for match in reversed(raw_matches):
        replacement = await replace_raw_img(match)
        start, end = match.span(0)
        processed_html = processed_html[:start] + replacement + processed_html[end:]

    return processed_html
