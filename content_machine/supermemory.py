from __future__ import annotations

import httpx
import logging
from typing import Any
from .config import Settings

logger = logging.getLogger(__name__)


class SuperMemoryClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.api_key = settings.supermemory_api_key
        self.base_url = "https://api.supermemory.ai/v3"

    async def add_memory(self, content: str, url: str | None = None, tags: list[str] | None = None) -> bool:
        if not self.api_key:
            logger.warning("SuperMemory API key is not set; skipping add_memory.")
            return False

        payload = {
            "content": content,
            "url": url or "",
            "containerTags": tags or []
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base_url}/add",
                    headers=headers,
                    json=payload
                )
                if resp.status_code == 200:
                    logger.info("Successfully added entry to SuperMemory.")
                    return True
                else:
                    logger.error(
                        f"Failed to add entry to SuperMemory. Status: {resp.status_code}, Body: {resp.text}"
                    )
                    return False
        except Exception as e:
            logger.error(f"Error calling SuperMemory add: {e}")
            return False

    async def search_memory(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        if not self.api_key:
            logger.warning("SuperMemory API key is not set; skipping search_memory.")
            return []

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        params = {
            "q": query,
            "limit": limit
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.base_url}/search",
                    headers=headers,
                    params=params
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        return data.get("results", [])
                    return []
                else:
                    logger.error(
                        f"Failed to search SuperMemory. Status: {resp.status_code}, Body: {resp.text}"
                    )
                    return []
        except Exception as e:
            logger.error(f"Error calling SuperMemory search: {e}")
            return []

    async def search_memory_with_tag(self, query: str, tag: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search memory and filter results by tag."""
        results = await self.search_memory(query, limit=limit * 3)
        filtered = []
        for item in results:
            tags = item.get("containerTags") or item.get("tags") or []
            if tag in tags:
                filtered.append(item)
            if len(filtered) >= limit:
                break
        # Fallback if no items matched tag filter
        if not filtered and results:
            return results[:limit]
        return filtered
