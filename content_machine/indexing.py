from __future__ import annotations

import json
from typing import Any
import httpx

from .config import Settings
from .google_auth import get_google_credentials

INDEXING_SCOPE = "https://www.googleapis.com/auth/indexing"


class GoogleIndexingClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def notify(self, url: str, action: str = "URL_UPDATED", dry_run: bool = False) -> dict[str, Any]:
        """Notifies Google of URL updates or removals using the Google Indexing API."""
        result = {
            "url": url,
            "action": action,
            "success": False,
            "dry_run": dry_run,
            "response": None,
            "error": None,
        }

        if dry_run:
            result["success"] = True
            result["response"] = {
                "urlNotificationMetadata": {
                    "latestUpdate": {
                        "url": url,
                        "type": action,
                        "notifyTime": "2026-05-19T12:00:00Z"
                    }
                }
            }
            return result

        try:
            # Attempt to acquire credentials using GSC scopes + Indexing scope
            creds = get_google_credentials(self.settings, scopes=[INDEXING_SCOPE])
            if not creds:
                result["error"] = "Google OAuth credentials not available. Run google-auth command first."
                return result

            # Obtain authorization header from creds
            headers = {"Content-Type": "application/json"}
            
            # Since credentials could be google.oauth2.credentials.Credentials, we apply them to header:
            # We can use httpx with standard bearer token
            if hasattr(creds, "token") and creds.token:
                headers["Authorization"] = f"Bearer {creds.token}"
            elif hasattr(creds, "valid") and not creds.valid:
                # Refresh if expired
                import google.auth.transport.requests
                request = google.auth.transport.requests.Request()
                creds.refresh(request)
                headers["Authorization"] = f"Bearer {creds.token}"

            body = {
                "url": url,
                "type": action,
            }

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://indexing.googleapis.com/v3/urlNotifications:publish",
                    headers=headers,
                    json=body,
                )

            if resp.status_code >= 400:
                result["error"] = f"API Error (Status {resp.status_code}): {resp.text}"
            else:
                result["success"] = True
                result["response"] = resp.json()

        except Exception as exc:
            result["error"] = f"Exception: {exc}"

        return result
