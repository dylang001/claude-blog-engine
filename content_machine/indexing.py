from __future__ import annotations

import json
from pathlib import Path
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
            creds_obj = None
            auth_type = None

            # 1. Try OAuth user credentials first if token file exists, as the user is already verified owner of GSC
            oauth_token_path = Path(self.settings.google_oauth_token_json).expanduser() if self.settings.google_oauth_token_json else None
            if oauth_token_path and oauth_token_path.exists():
                try:
                    creds_obj, auth_type = get_google_credentials(self.settings, scopes=[INDEXING_SCOPE])
                except Exception as e:
                    logger.warning(f"OAuth credentials fallback warning: {e}")

            # 2. Try service account if OAuth didn't yield credentials
            if not creds_obj:
                service_account_value = (self.settings.google_service_account_json or "").strip()
                use_service_account = service_account_value and service_account_value not in {
                    "/absolute/path/to/google-service-account.json",
                    "absolute/path/to/google-service-account.json",
                }
                if use_service_account:
                    from google.oauth2 import service_account
                    if service_account_value.startswith("{"):
                        creds_obj = service_account.Credentials.from_service_account_info(
                            json.loads(service_account_value), scopes=[INDEXING_SCOPE]
                        )
                    else:
                        creds_obj = service_account.Credentials.from_service_account_file(
                            service_account_value, scopes=[INDEXING_SCOPE]
                        )
                    auth_type = "service_account"

            # 3. Fallback to default google credentials if still no credentials
            if not creds_obj:
                try:
                    creds_obj, auth_type = get_google_credentials(self.settings, scopes=[INDEXING_SCOPE])
                except Exception as e:
                    import google.auth
                    try:
                        creds_obj, _project = google.auth.default(scopes=[INDEXING_SCOPE])
                        auth_type = "application_default"
                    except Exception:
                        result["error"] = f"Failed to acquire Google credentials: {e}"
                        return result

            if not creds_obj:
                result["error"] = "Google credentials not available. Configure service account or run google-auth."
                return result

            # Refresh/load token
            import google.auth.transport.requests
            request = google.auth.transport.requests.Request()
            creds_obj.refresh(request)

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {creds_obj.token}"
            }

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
