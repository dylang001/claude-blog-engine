from __future__ import annotations

import httpx
from typing import Any
from .config import Settings
from .dataforseo_auth import dataforseo_headers


class BacklinkClient:
    """Client for DataForSEO Backlinks API. No fallback — fails loudly if API is unreachable."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.headers = dataforseo_headers(settings)
        self.base_url = "https://api.dataforseo.com"

    async def get_summary(self, target: str) -> dict[str, Any]:
        """Fetch backlink profile summary for a target domain/URL.
        
        Raises RuntimeError if credentials are missing or the API call fails.
        """
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
                        results = tasks[0].get("result", [])
                        if results:
                            return results[0]
                    raise RuntimeError(
                        f"DataForSEO Backlinks returned empty results for '{target}'. "
                        f"Response: {data}"
                    )
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
