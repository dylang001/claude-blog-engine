from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .config import Settings


GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
GA4_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"


def get_google_credentials(settings: Settings, scopes: list[str]) -> tuple[Any, str]:
    """Return Google credentials, preferring OAuth user access over service accounts."""

    oauth_token = Path(settings.google_oauth_token_json).expanduser() if settings.google_oauth_token_json else None
    if oauth_token and oauth_token.exists():
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        credentials = Credentials.from_authorized_user_file(str(oauth_token), scopes=scopes)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            oauth_token.write_text(credentials.to_json(), encoding="utf-8")
        return credentials, "oauth_user"

    service_account_value = (settings.google_service_account_json or "").strip()
    if service_account_value and service_account_value not in {
        "/absolute/path/to/google-service-account.json",
        "absolute/path/to/google-service-account.json",
    }:
        from google.oauth2 import service_account

        if service_account_value.startswith("{"):
            return service_account.Credentials.from_service_account_info(json.loads(service_account_value), scopes=scopes), "service_account"
        return service_account.Credentials.from_service_account_file(service_account_value, scopes=scopes), "service_account"

    import google.auth

    credentials, _project = google.auth.default(scopes=scopes)
    return credentials, "application_default"


def run_installed_app_oauth(settings: Settings, scopes: list[str]) -> Path:
    """Create/update the local OAuth token used for GSC and GA4 discovery."""

    if not settings.google_oauth_client_secrets_json:
        raise RuntimeError("GOOGLE_OAUTH_CLIENT_SECRETS_JSON is not configured")

    from google_auth_oauthlib.flow import InstalledAppFlow

    client_secrets = Path(settings.google_oauth_client_secrets_json).expanduser()
    if not client_secrets.exists():
        raise RuntimeError(f"OAuth client secrets file not found: {client_secrets}")

    token_path = Path(settings.google_oauth_token_json).expanduser()
    token_path.parent.mkdir(parents=True, exist_ok=True)

    # Google can return a superset of previously granted scopes for the same
    # OAuth client. oauthlib treats that as a warning exception unless relaxed.
    os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), scopes=scopes)
    credentials = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    token_path.chmod(0o600)
    return token_path
