from __future__ import annotations

import asyncio
import os
from typing import Any
import httpx
from .config import Settings


class FirecrawlClient:
    """Client for Firecrawl API. No fallback — fails loudly if API key is missing or API is unreachable."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.api_key = settings.firecrawl_api_key or os.getenv("FIRECRAWL_API_KEY", "")
        self.base_url = "https://api.firecrawl.dev/v1"

    def _require_api_key(self) -> None:
        if not self.api_key:
            raise RuntimeError(
                "FIRECRAWL_API_KEY is required for Firecrawl operations. "
                "Set FIRECRAWL_API_KEY in your .env file."
            )

    async def scrape(self, url: str) -> dict[str, Any]:
        """Scrape a single URL. Raises RuntimeError on failure."""
        self._require_api_key()

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base_url}/scrape",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"url": url, "formats": ["markdown", "html"]},
                )
                if resp.status_code == 200:
                    return resp.json()
                else:
                    raise RuntimeError(
                        f"Firecrawl scrape returned status={resp.status_code}: "
                        f"{resp.text[:500]}"
                    )
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Cannot connect to Firecrawl API. Check your internet connection. "
                f"Error: {exc}"
            ) from exc
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"Firecrawl scrape failed: {type(exc).__name__}: {exc}"
            ) from exc

    async def map(self, url: str) -> list[str]:
        """Map a website to discover pages. Raises RuntimeError on failure."""
        self._require_api_key()

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base_url}/map",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"url": url},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and "links" in data:
                        return data["links"]
                    elif isinstance(data, list):
                        return data
                    raise RuntimeError(
                        f"Firecrawl map returned unexpected response shape: {data}"
                    )
                else:
                    raise RuntimeError(
                        f"Firecrawl map returned status={resp.status_code}: "
                        f"{resp.text[:500]}"
                    )
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Cannot connect to Firecrawl API. Check your internet connection. "
                f"Error: {exc}"
            ) from exc
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"Firecrawl map failed: {type(exc).__name__}: {exc}"
            ) from exc

    async def crawl(self, url: str, limit: int = 100, max_depth: int = 3) -> dict[str, Any]:
        """Crawl a website starting at a given URL. Raises RuntimeError on failure."""
        self._require_api_key()

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self.base_url}/crawl",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"url": url, "limit": limit, "maxDepth": max_depth},
                )
                if resp.status_code != 200:
                    raise RuntimeError(
                        f"Firecrawl crawl returned status={resp.status_code}: "
                        f"{resp.text[:500]}"
                    )

                crawl_data = resp.json()
                crawl_id = crawl_data.get("id")
                if not crawl_id:
                    # Some Firecrawl versions return data directly
                    if crawl_data.get("status") == "completed" or crawl_data.get("data"):
                        return crawl_data
                    raise RuntimeError(
                        f"Firecrawl crawl did not return a crawl ID or completed data: {crawl_data}"
                    )

                # Poll for completion (up to 60 seconds with 2s intervals)
                for attempt in range(30):
                    await asyncio.sleep(2)
                    status_resp = await client.get(
                        f"{self.base_url}/crawl/{crawl_id}",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    )
                    if status_resp.status_code == 200:
                        status_data = status_resp.json()
                        if status_data.get("status") == "completed":
                            return status_data
                        elif status_data.get("status") == "failed":
                            raise RuntimeError(
                                f"Firecrawl crawl failed: {status_data}"
                            )

                raise RuntimeError(
                    f"Firecrawl crawl timed out after 60 seconds for crawl_id={crawl_id}"
                )

        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Cannot connect to Firecrawl API. Check your internet connection. "
                f"Error: {exc}"
            ) from exc
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"Firecrawl crawl failed: {type(exc).__name__}: {exc}"
            ) from exc
