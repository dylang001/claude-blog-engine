from __future__ import annotations

from typing import Any
from urllib.parse import urlencode, urlparse

import httpx

from .config import Settings
from .dataforseo_auth import dataforseo_headers
from .indexnow import IndexNowClient


async def live_checks(settings: Settings) -> dict:
    checks = {
        "anthropic": await _check_anthropic(settings),
        "dataforseo": await _check_dataforseo(settings),
        "wordpress": await _check_wordpress(settings),
        "banana": await _check_banana(settings),
        "google_config": _check_google_config(settings),
        "indexnow": await _check_indexnow(settings),
    }
    return {"ok": all(item["ok"] for item in checks.values()), "checks": checks}


async def _check_anthropic(settings: Settings) -> dict:
    if not settings.anthropic_api_key:
        return {"ok": False, "message": "ANTHROPIC_API_KEY is empty"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.anthropic_model,
                    "max_tokens": 20,
                    "messages": [{"role": "user", "content": "Reply OK"}],
                },
            )
        if resp.status_code >= 400:
            body = resp.json()
            err = body.get("error", {})
            return {"ok": False, "status": resp.status_code, "message": err.get("message", resp.text[:200])}
        return {"ok": True, "status": resp.status_code, "model": settings.anthropic_model}
    except Exception as exc:
        return {"ok": False, "message": f"{type(exc).__name__}: {str(exc)[:200]}"}


async def _check_dataforseo(settings: Settings) -> dict:
    if not settings.dataforseo_auth_base64 and not (settings.dataforseo_login and settings.dataforseo_password):
        return {"ok": False, "message": "Set DATAFORSEO_AUTH_BASE64/DATAFORSEO_BASE_64 or DATAFORSEO_LOGIN plus DATAFORSEO_PASSWORD"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://api.dataforseo.com/v3/appendix/user_data",
                headers=dataforseo_headers(settings),
            )
        body = resp.json()
        if resp.status_code >= 400 or body.get("status_code") != 20000:
            return {"ok": False, "status": resp.status_code, "message": body.get("status_message") or body.get("message", resp.text[:200])}
        return {"ok": True, "status": resp.status_code, "auth_mode": "base64" if settings.dataforseo_auth_base64 else "login_password"}
    except Exception as exc:
        return {"ok": False, "message": f"{type(exc).__name__}: {str(exc)[:200]}"}


async def _check_wordpress(settings: Settings) -> dict:
    if not settings.wp_base_url:
        return {"ok": False, "message": "WP_BASE_URL is empty"}
    parsed = urlparse(settings.wp_base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"ok": False, "message": "WP_BASE_URL must include scheme and hostname, e.g. https://example.com"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp, rest_style = await _wp_get_json(
                client,
                settings,
                "/types",
            )
        if resp.status_code >= 400:
            return {"ok": False, "status": resp.status_code, "message": resp.text[:200]}
        body = resp.json()
        if "post" not in body:
            return {"ok": False, "status": resp.status_code, "message": "WordPress REST API reachable but post type is missing", "rest_style": rest_style}

        bridge = await _check_yoast_bridge(settings)
        return {
            "ok": bool(bridge["ok"]),
            "status": resp.status_code,
            "message": bridge["message"] if not bridge["ok"] else "WordPress REST API reachable and Yoast bridge detected",
            "rest_style": rest_style,
            "rest_api_ok": True,
            "yoast_bridge": bridge,
        }
    except Exception as exc:
        return {"ok": False, "message": f"{type(exc).__name__}: {str(exc)[:200]}"}


async def _wp_get_json(client: httpx.AsyncClient, settings: Settings, path: str, **kwargs) -> tuple[httpx.Response, str]:
    base = settings.wp_base_url.rstrip("/")
    pretty_url = f"{base}/wp-json/wp/v2{path}"
    params = kwargs.pop("params", None)
    query_url = _wp_rest_route_url(base, path, params)
    resp = await client.get(pretty_url, auth=(settings.wp_username, settings.wp_app_password), params=params, **kwargs)
    if "application/json" not in resp.headers.get("content-type", "").lower():
        resp = await client.get(query_url, auth=(settings.wp_username, settings.wp_app_password), **kwargs)
        return resp, "query"
    return resp, "pretty"


def _wp_rest_route_url(base_url: str, path: str, params: dict[str, Any] | None = None) -> str:
    return _site_rest_route_url(base_url, f"/wp/v2{path}", params)


def _site_rest_route_url(base_url: str, route: str, params: dict[str, Any] | None = None) -> str:
    query = {"rest_route": route}
    if params:
        query.update(params)
    return f"{base_url.rstrip('/')}/?{urlencode(query)}"


async def _check_yoast_bridge(settings: Settings) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            status_resp = await client.get(
                _site_rest_route_url(settings.wp_base_url, "/seo-machine/v1/yoast/status"),
                auth=(settings.wp_username, settings.wp_app_password),
            )
            if "application/json" in status_resp.headers.get("content-type", "").lower() and status_resp.status_code < 400:
                status = status_resp.json()
                return {
                    "ok": bool(status.get("yoast_active") and status.get("rest_field") == "yoast_seo"),
                    "rest_style": "query",
                    "message": "SEO Machine Yoast bridge diagnostic route is installed.",
                    "yoast_version": status.get("yoast_version"),
                    "yoast_premium_active": status.get("yoast_premium_active"),
                    "post_types": status.get("post_types", []),
                    "rest_field": status.get("rest_field"),
                }

            resp, rest_style = await _wp_get_json(
                client,
                settings,
                "/posts",
                params={"per_page": 1, "context": "edit"},
            )
        if resp.status_code >= 400:
            return {
                "ok": False,
                "status": resp.status_code,
                "rest_style": rest_style,
                "message": "Could not inspect posts for Yoast REST bridge.",
            }
        posts = resp.json()
        if not posts:
            return {
                "ok": False,
                "rest_style": rest_style,
                "message": "No posts available to verify the custom yoast_seo REST field.",
            }
        has_bridge = "yoast_seo" in posts[0]
        return {
            "ok": has_bridge,
            "rest_style": rest_style,
            "message": (
                "Custom yoast_seo REST field is installed."
                if has_bridge
                else "Yoast appears active, but the custom yoast_seo REST bridge is not installed. Install wordpress/seo-machine-yoast-rest.php as an MU plugin."
            ),
        }
    except Exception as exc:
        return {"ok": False, "message": f"{type(exc).__name__}: {str(exc)[:200]}"}


async def _check_banana(settings: Settings) -> dict:
    if not settings.gemini_api_key:
        return {"ok": True, "message": "GEMINI_API_KEY/GOOGLE_AI_API_KEY not set; image generation will be skipped"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"https://generativelanguage.googleapis.com/v1beta/models/{settings.banana_model}",
                params={"key": settings.gemini_api_key},
            )
        if resp.status_code >= 400:
            try:
                body = resp.json()
                message = body.get("error", {}).get("message", resp.text[:200])
            except Exception:
                message = resp.text[:200]
            return {"ok": False, "status": resp.status_code, "message": message}
        return {"ok": True, "status": resp.status_code, "model": settings.banana_model}
    except Exception as exc:
        return {"ok": False, "message": f"{type(exc).__name__}: {str(exc)[:200]}"}


def _check_google_config(settings: Settings) -> dict:
    warnings = []
    if settings.google_service_account_json in {"/absolute/path/to/google-service-account.json", "absolute/path/to/google-service-account.json"}:
        warnings.append("GOOGLE_SERVICE_ACCOUNT_JSON is still the placeholder path; set it to a real service-account JSON path or inline JSON.")
    if settings.google_oauth_client_secrets_json and not settings.google_oauth_token_json:
        warnings.append("GOOGLE_OAUTH_TOKEN_JSON is empty; google-auth will not know where to save the user OAuth token.")
    if settings.ga4_property_id.startswith("G-"):
        warnings.append("GA4_PROPERTY_ID should be the numeric property ID, not the Measurement ID that starts with G-.")
    if not (settings.gsc_site_url.startswith("sc-domain:") or settings.gsc_site_url.startswith("http")):
        warnings.append("GSC_SITE_URL should look like sc-domain:example.com or https://example.com/.")
    if not settings.pagespeed_api_key:
        warnings.append("PAGESPEED_API_KEY/GOOGLE_PAGESPEED_API_KEY is not set; PageSpeed discovery may hit unauthenticated quota.")
    return {"ok": not [warning for warning in warnings if "PageSpeed discovery may hit" not in warning], "warnings": warnings}


async def _check_indexnow(settings: Settings) -> dict:
    if not settings.indexnow_key or not settings.indexnow_key_location:
        return {"ok": True, "configured": False, "message": "IndexNow is disabled until INDEXNOW_KEY and INDEXNOW_KEY_LOCATION are set."}
    result = await IndexNowClient(settings).verify_key_location()
    result["configured"] = True
    if not result.get("ok"):
        result["message"] = result.get("message") or "IndexNow key location is not reachable or does not match INDEXNOW_KEY."
    return result
