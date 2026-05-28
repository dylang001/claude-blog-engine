from __future__ import annotations
import logging
from typing import Any
from googleapiclient.discovery import build
from .config import Settings
from .google_auth import get_google_credentials

logger = logging.getLogger(__name__)

class BloggerClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def publish_post(self, title: str, content_html: str, is_draft: bool = False) -> dict[str, Any]:
        """Publish a post to Google Blogger using Blogger API v3.
        
        Returns the API response dict with key details like 'url' and 'id'.
        """
        blog_id = getattr(self.settings, "blogger_blog_id", "").strip()
        if not blog_id:
            raise RuntimeError("Blogger blog ID is not configured. Set BLOGGER_BLOG_ID in .env.")

        # blogger scope: https://www.googleapis.com/auth/blogger
        credentials, auth_mode = get_google_credentials(self.settings, ["https://www.googleapis.com/auth/blogger"])
        
        # Build service in executor since it's blocking
        import asyncio
        loop = asyncio.get_event_loop()
        
        def _build_and_publish():
            service = build("blogger", "v3", credentials=credentials, cache_discovery=False)
            posts = service.posts()
            body = {
                "kind": "blogger#post",
                "title": title,
                "content": content_html,
            }
            return posts.insert(blogId=blog_id, body=body, isDraft=is_draft).execute()

        try:
            result = await loop.run_in_executor(None, _build_and_publish)
            logger.info(f"Successfully posted to Blogger: {result.get('url')} (Auth mode: {auth_mode})")
            return result
        except Exception as exc:
            logger.error(f"Blogger API call failed: {exc}")
            raise RuntimeError(f"Blogger publishing failed: {exc}") from exc
