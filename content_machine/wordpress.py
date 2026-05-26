from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re
from urllib.parse import urlencode

import httpx

from .config import Settings
from .models import GeneratedContent, PublishDecision
from .utils import slugify


class WordPressClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.wp_base_url.rstrip("/")
        self.username = settings.wp_username
        self.app_password = settings.wp_app_password
        self.api_base = f"{self.base_url}/wp-json/wp/v2"

    def _auth(self) -> tuple[str, str]:
        return (self.username, self.app_password)

    async def healthcheck(self) -> dict[str, Any]:
        return await self._request_json("GET", "/types")

    async def list_posts(self, limit: int = 100) -> list[dict[str, Any]]:
        return await self._request_json(
            "GET",
            "/posts",
            params={"per_page": min(limit, 100), "status": "publish,draft,future"},
        )

    async def internal_link_candidates(self, limit: int = 20) -> list[dict[str, str]]:
        posts = await self._request_json(
            "GET",
            "/posts",
            params={"per_page": min(limit, 100), "status": "publish", "context": "view"},
        )
        pages = await self._request_json(
            "GET",
            "/pages",
            params={"per_page": min(limit, 100), "status": "publish", "context": "view"},
        )
        candidates: list[dict[str, str]] = []
        for item in list(posts or []) + list(pages or []):
            title = item.get("title", {}).get("rendered") if isinstance(item.get("title"), dict) else item.get("title", "")
            link = item.get("link", "")
            slug = item.get("slug", "")
            if title and link:
                candidates.append({"title": _strip_tags(str(title)), "url": str(link), "slug": str(slug)})
        return candidates[:limit]

    async def find_post_by_slug(self, slug: str) -> dict[str, Any] | None:
        posts = await self._request_json(
            "GET",
            "/posts",
            params={"slug": slug, "status": "publish,draft,future,pending,private", "context": "edit"},
        )
        if isinstance(posts, list) and posts:
            return posts[0]
        return None

    async def upload_media(self, image_path: str, alt_text: str = "") -> dict[str, Any] | None:
        path = Path(image_path)
        if not path.exists():
            return None
        headers = {"Content-Disposition": f'attachment; filename="{path.name}"'}
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.request("POST", f"{self.api_base}/media", auth=self._auth(), headers=headers, files={"file": (path.name, path.read_bytes())})
            if not _is_json(resp):
                resp = await client.request("POST", _rest_route_url(self.base_url, "/media"), auth=self._auth(), headers=headers, files={"file": (path.name, path.read_bytes())})
            resp.raise_for_status()
            media = resp.json()
            media_id = int(media["id"])
            source_url = media.get("source_url") or media.get("guid", {}).get("rendered", "")
            if alt_text:
                update = {"alt_text": alt_text[:500], "title": path.stem.replace("-", " ")[:200]}
                update_resp = await client.request("POST", f"{self.api_base}/media/{media_id}", auth=self._auth(), json=update)
                if not _is_json(update_resp):
                    update_resp = await client.request("POST", _rest_route_url(self.base_url, f"/media/{media_id}"), auth=self._auth(), json=update)
                update_resp.raise_for_status()
            return {"id": media_id, "url": source_url}

    async def upsert_post(self, content: GeneratedContent, decision: PublishDecision, existing_post_id: int | None = None) -> dict[str, Any]:
        status = "publish" if decision == PublishDecision.PUBLISH else "draft"
        html = _strip_h1_html(content.html)
        
        # Scan and upload inline images
        img_tags = list(re.finditer(r'<img\b[^>]*?>', html))
        for match in img_tags:
            img_tag = match.group(0)
            src_match = re.search(r'src=["\']([^"\']+)["\']', img_tag)
            if not src_match:
                continue
            src_path = src_match.group(1)
            # Check if it's a local file path
            path_obj = Path(src_path)
            if path_obj.exists():
                alt_match = re.search(r'alt=["\']([^"\']*)["\']', img_tag)
                alt_text = alt_match.group(1) if alt_match else ""
                
                media_info = await self.upload_media(str(path_obj), alt_text=alt_text)
                if media_info:
                    media_id = media_info["id"]
                    media_url = media_info["url"]
                    # Format as Gutenberg Image Block
                    gutenberg_img = (
                        f'<!-- wp:image {{"id":{media_id},"sizeSlug":"large","linkDestination":"none"}} -->\n'
                        f'<figure class="wp-block-image size-large"><img src="{media_url}" alt="{alt_text}" class="wp-image-{media_id}"/></figure>\n'
                        f'<!-- /wp:image -->'
                    )
                    # Check if the img tag is enclosed in a paragraph <p>...</p>
                    pattern = rf'<p>\s*{re.escape(img_tag)}\s*</p>'
                    if re.search(pattern, html):
                        html = re.sub(pattern, gutenberg_img, html, count=1)
                    else:
                        html = html.replace(img_tag, gutenberg_img, 1)

        if content.schema_json:
            schema = json.dumps(content.schema_json, ensure_ascii=False)
            html = f'{html}\n\n<script type="application/ld+json">{schema}</script>'
            
        payload: dict[str, Any] = {
            "title": content.title,
            "slug": content.slug,
            "content": html,
            "excerpt": content.excerpt,
            "status": status,
            "yoast_seo": {
                "focus_keyphrase": content.focus_keyphrase,
                "seo_title": content.meta_title,
                "meta_description": content.meta_description,
            },
        }
        
        featured_media_info = await self.upload_media(content.featured_image_path, alt_text=content.image_alt_text or content.image_prompt or content.title) if content.featured_image_path else None
        if featured_media_info:
            payload["featured_media"] = featured_media_info["id"]

        category_ids = await self._resolve_terms("categories", content.categories)
        tag_ids = await self._resolve_terms("tags", content.tags)
        if category_ids:
            payload["categories"] = category_ids
        if tag_ids:
            payload["tags"] = tag_ids

        path = f"/posts/{existing_post_id}" if existing_post_id else "/posts"
        return await self._request_json("POST", path, json=payload, timeout=120)

    async def configure_indexnow_key(self, key: str) -> dict[str, Any]:
        return await self._site_request_json("POST", "/seo-machine/v1/indexnow/key", json={"key": key})

    async def _resolve_terms(self, endpoint: str, names: list[str]) -> list[int]:
        ids: list[int] = []
        for raw_name in names:
            name = raw_name.strip()
            if not name:
                continue
            term_id = await self._find_or_create_term(endpoint, name)
            if term_id and term_id not in ids:
                ids.append(term_id)
        return ids

    async def _find_or_create_term(self, endpoint: str, name: str) -> int | None:
        slug = slugify(name)
        found = await self._request_json("GET", f"/{endpoint}", params={"slug": slug, "per_page": 1})
        if isinstance(found, list) and found:
            return int(found[0]["id"])

        created = await self._request_json("POST", f"/{endpoint}", json={"name": name, "slug": slug})
        if isinstance(created, dict) and "id" in created:
            return int(created["id"])
        return None

    async def _request_json(self, method: str, path: str, timeout: int = 30, **kwargs) -> Any:
        pretty_url = f"{self.api_base}{path}"
        params = kwargs.pop("params", None)
        fallback_url = _rest_route_url(self.base_url, path, params)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method, pretty_url, auth=self._auth(), params=params, **kwargs)
            if not _is_json(resp):
                resp = await client.request(method, fallback_url, auth=self._auth(), **kwargs)
            resp.raise_for_status()
            return resp.json()

    async def _site_request_json(self, method: str, route: str, timeout: int = 30, **kwargs) -> Any:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method, _site_rest_route_url(self.base_url, route), auth=self._auth(), **kwargs)
            resp.raise_for_status()
            return resp.json()


def _is_json(resp: httpx.Response) -> bool:
    return "application/json" in resp.headers.get("content-type", "").lower()


def _strip_h1_html(html: str) -> str:
    return re.sub(r"<h1\b[^>]*>.*?</h1>\s*", "", html or "", flags=re.IGNORECASE | re.DOTALL).lstrip()


def _strip_tags(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def _rest_route_url(base_url: str, path: str, params: dict[str, Any] | None = None) -> str:
    query = {"rest_route": f"/wp/v2{path}"}
    if params:
        query.update(params)
    return f"{base_url.rstrip('/')}/?{urlencode(query)}"


def _site_rest_route_url(base_url: str, route: str) -> str:
    return f"{base_url.rstrip('/')}/?{urlencode({'rest_route': route})}"
