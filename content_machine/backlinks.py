from __future__ import annotations

import logging
import httpx
from typing import Any
from .config import Settings
from .dataforseo_auth import dataforseo_headers
from .open_seo_client import OpenSeoClient

logger = logging.getLogger(__name__)


class BacklinkClient:
    """Client for DataForSEO Backlinks API, preferring OpenSEO when available."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.headers = dataforseo_headers(settings)
        self.base_url = "https://api.dataforseo.com"
        self.open_seo = OpenSeoClient(settings)

    async def get_summary(self, target: str) -> dict[str, Any]:
        """Fetch backlink profile summary for a target domain/URL.
        
        Tries OpenSEO first, then falls back to direct DataForSEO API.
        Raises RuntimeError if both fail and DataForSEO credentials are missing/fail.
        """
        # 1. Try OpenSEO first
        if self.open_seo._enabled:
            try:
                res = await self.open_seo.backlinks_summary(target)
                if res:
                    logger.info(f"Successfully fetched backlinks summary for {target} via OpenSEO")
                    return res
            except Exception as exc:
                logger.debug(f"OpenSEO backlinks lookup failed for {target}: {exc} — falling back to direct DataForSEO")
        has_auth = (
            self.settings.dataforseo_auth_base64
            or (self.settings.dataforseo_login and self.settings.dataforseo_password)
        )
        if not has_auth:
            raise RuntimeError(
                "DataForSEO credentials are required for backlink analysis. "
                "Set DATAFORSEO_LOGIN + DATAFORSEO_PASSWORD or DATAFORSEO_BASE_64 in .env"
            )

        payload = [{"target": target}]
        try:
            async with httpx.AsyncClient(timeout=30, headers=self.headers) as client:
                resp = await client.post(
                    f"{self.base_url}/v3/backlinks/summary/live",
                    json=payload
                )
                if resp.status_code == 200:
                    data = resp.json()
                    tasks = data.get("tasks", [])
                    if tasks:
                        # Check for API errors like "Access denied" (40204)
                        task = tasks[0]
                        if task.get("status_code", 0) >= 40000:
                            raise RuntimeError(
                                f"DataForSEO Backlinks API Error: {task.get('status_message', 'Unknown Error')}"
                            )
                        
                        results = task.get("result", [])
                        if results:
                            # If items exist, great. If not, it just means 0 backlinks.
                            return results[0]
                    # Valid response but no backlinks found
                    return {"target": target, "rank": 0, "backlinks": 0, "referring_domains": 0}
                else:
                    raise RuntimeError(
                        f"DataForSEO Backlinks API returned status={resp.status_code}: "
                        f"{resp.text[:500]}"
                    )
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Cannot connect to DataForSEO Backlinks API. Check your internet connection. "
                f"Error: {exc}"
            ) from exc
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"DataForSEO Backlinks API call failed: {type(exc).__name__}: {exc}"
            ) from exc
