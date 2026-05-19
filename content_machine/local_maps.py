from __future__ import annotations

import httpx
from typing import Any
from .config import Settings
from .dataforseo_auth import dataforseo_headers


class LocalMapsClient:
    """Client for Google Maps / GBP Local SEO Intelligence. No fallback — fails loudly if API is unreachable."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.headers = dataforseo_headers(settings)
        self.base_url = "https://api.dataforseo.com"

    def _require_auth(self) -> None:
        has_auth = (
            self.settings.dataforseo_auth_base64
            or (self.settings.dataforseo_login and self.settings.dataforseo_password)
        )
        if not has_auth:
            raise RuntimeError(
                "DataForSEO credentials are required for Local Maps intelligence. "
                "Set DATAFORSEO_LOGIN + DATAFORSEO_PASSWORD or DATAFORSEO_BASE_64 in .env"
            )

    async def get_gmb_reviews(self, business_id: str) -> dict[str, Any]:
        """Fetch business reviews and rating info from Google Maps.
        
        Raises RuntimeError if credentials are missing or the API call fails.
        """
        self._require_auth()

        payload = [{"keyword": business_id, "location_name": "United States", "language_name": "English"}]
        try:
            async with httpx.AsyncClient(timeout=30, headers=self.headers) as client:
                resp = await client.post(
                    f"{self.base_url}/v3/business_data/google/my_business_info/task_post",
                    json=payload
                )
                if resp.status_code == 200:
                    data = resp.json()
                    tasks = data.get("tasks", [])
                    if tasks:
                        task = tasks[0]
                        # For async tasks, return the task metadata so we can poll later
                        result = task.get("result")
                        if result:
                            return result[0] if isinstance(result, list) and result else result
                        # Return task info if the result needs polling
                        return {
                            "task_id": task.get("id"),
                            "status_code": task.get("status_code"),
                            "status_message": task.get("status_message"),
                            "note": "Task posted successfully. Poll for results using task_id.",
                        }
                    raise RuntimeError(
                        f"DataForSEO GMB returned empty tasks for '{business_id}'. "
                        f"Response: {data}"
                    )
                else:
                    raise RuntimeError(
                        f"DataForSEO GMB API returned status={resp.status_code}: "
                        f"{resp.text[:500]}"
                    )
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Cannot connect to DataForSEO GMB API. Check your internet connection. "
                f"Error: {exc}"
            ) from exc
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"DataForSEO GMB API call failed: {type(exc).__name__}: {exc}"
            ) from exc

    async def search_local_competitors(self, keyword: str, location: str) -> dict[str, Any]:
        """Search local competitors on Google Maps.
        
        Raises RuntimeError if credentials are missing or the API call fails.
        """
        self._require_auth()

        payload = [{"keyword": keyword, "location_name": location, "language_name": "English", "depth": 10}]
        try:
            async with httpx.AsyncClient(timeout=30, headers=self.headers) as client:
                resp = await client.post(
                    f"{self.base_url}/v3/business_data/google/my_business_search/task_post",
                    json=payload
                )
                if resp.status_code == 200:
                    data = resp.json()
                    tasks = data.get("tasks", [])
                    if tasks:
                        task = tasks[0]
                        result = task.get("result")
                        if result:
                            return result[0] if isinstance(result, list) and result else result
                        return {
                            "task_id": task.get("id"),
                            "status_code": task.get("status_code"),
                            "status_message": task.get("status_message"),
                            "note": "Task posted successfully. Poll for results using task_id.",
                        }
                    raise RuntimeError(
                        f"DataForSEO local search returned empty tasks for '{keyword}' in '{location}'. "
                        f"Response: {data}"
                    )
                else:
                    raise RuntimeError(
                        f"DataForSEO local search API returned status={resp.status_code}: "
                        f"{resp.text[:500]}"
                    )
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Cannot connect to DataForSEO local search API. Check your internet connection. "
                f"Error: {exc}"
            ) from exc
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"DataForSEO local search API call failed: {type(exc).__name__}: {exc}"
            ) from exc
