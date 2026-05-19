from __future__ import annotations

import base64

from .config import Settings


def dataforseo_headers(settings: Settings) -> dict[str, str]:
    token = settings.dataforseo_auth_base64.strip()
    if not token:
        token = base64.b64encode(f"{settings.dataforseo_login}:{settings.dataforseo_password}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}
