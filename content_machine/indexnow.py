from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from .config import Settings


INDEXNOW_ENDPOINTS = {
    "bing": "https://www.bing.com/indexnow",
    "yandex": "https://yandex.com/indexnow",
    "naver": "https://searchadvisor.naver.com/indexnow",
    "seznam": "https://search.seznam.cz/indexnow",
    "indexnow": "https://api.indexnow.org/indexnow",
}


@dataclass(frozen=True)
class IndexNowResult:
    engine: str
    status: int
    success: bool
    message: str


class IndexNowClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.indexnow_key and self.settings.indexnow_key_location)

    async def submit(self, urls: list[str], engines: list[str] | None = None) -> list[IndexNowResult]:
        clean_urls = _dedupe_urls(urls)
        if not self.configured:
            return [IndexNowResult("indexnow", 0, False, "INDEXNOW_KEY and INDEXNOW_KEY_LOCATION must be configured.")]
        if not clean_urls:
            return []
        host = _host_for_urls(clean_urls)
        if not host:
            return [IndexNowResult("indexnow", 0, False, "No valid URL host found.")]
        payload: dict[str, Any] = {
            "host": host,
            "key": self.settings.indexnow_key,
            "keyLocation": self.settings.indexnow_key_location,
            "urlList": clean_urls[:10000],
        }
        targets = engines or self.settings.indexnow_engines
        results: list[IndexNowResult] = []
        async with httpx.AsyncClient(timeout=20) as client:
            for engine in targets:
                endpoint = INDEXNOW_ENDPOINTS.get(engine)
                if not endpoint:
                    results.append(IndexNowResult(engine, 0, False, f"Unknown engine. Available: {', '.join(INDEXNOW_ENDPOINTS)}"))
                    continue
                try:
                    resp = await client.post(endpoint, json=payload, headers={"content-type": "application/json"})
                    results.append(IndexNowResult(engine, resp.status_code, 200 <= resp.status_code < 300, _status_message(resp.status_code)))
                except Exception as exc:
                    results.append(IndexNowResult(engine, 0, False, f"{type(exc).__name__}: {str(exc)[:200]}"))
        return results

    async def verify_key_location(self) -> dict[str, Any]:
        if not self.settings.indexnow_key_location:
            return {"ok": False, "message": "INDEXNOW_KEY_LOCATION is empty"}
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(self.settings.indexnow_key_location)
            body = resp.text.strip()
            return {
                "ok": resp.status_code == 200 and body == self.settings.indexnow_key,
                "status": resp.status_code,
                "key_location": self.settings.indexnow_key_location,
                "matches_key": body == self.settings.indexnow_key,
            }
        except Exception as exc:
            return {"ok": False, "message": f"{type(exc).__name__}: {str(exc)[:200]}", "key_location": self.settings.indexnow_key_location}


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen = set()
    clean = []
    for raw in urls:
        url = (raw or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        if url not in seen:
            clean.append(url)
            seen.add(url)
    return clean


def _host_for_urls(urls: list[str]) -> str:
    for url in urls:
        parsed = urlparse(url)
        if parsed.netloc:
            return parsed.netloc
    return ""


def _status_message(status: int) -> str:
    return {
        200: "URLs submitted successfully.",
        202: "URLs accepted for processing.",
        400: "Bad request: invalid payload.",
        403: "Forbidden: key file could not be validated for this host.",
        422: "Unprocessable: URL does not belong to this host.",
        429: "Rate limited.",
    }.get(status, f"HTTP {status}")
