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
        self.settings = settings
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
            resp = await client.post(f"{self.api_base}/media", auth=self._auth(), headers=headers, files={"file": (path.name, path.read_bytes())})
            if not _is_json(resp):
                resp = await client.post(_rest_route_url(self.base_url, "/media"), auth=self._auth(), headers=headers, files={"file": (path.name, path.read_bytes())})
            resp.raise_for_status()
            media = resp.json()
            media_id = int(media["id"])
            media_url = media.get("source_url")
            if alt_text:
                update = {"alt_text": alt_text[:500], "title": path.stem.replace("-", " ")[:200]}
                update_resp = await client.post(f"{self.api_base}/media/{media_id}", auth=self._auth(), json=update)
                if not _is_json(update_resp):
                    update_resp = await client.post(_rest_route_url(self.base_url, f"/media/{media_id}"), auth=self._auth(), json=update)
                update_resp.raise_for_status()
                updated_media = update_resp.json()
                if isinstance(updated_media, dict) and "source_url" in updated_media:
                    media_url = updated_media["source_url"]
            return {"id": media_id, "url": media_url}

    async def upsert_post(self, content: GeneratedContent, decision: PublishDecision, existing_post_id: int | None = None) -> dict[str, Any]:
        status = "publish" if decision == PublishDecision.PUBLISH else "draft"
        html = _strip_h1_html(content.html)
        
        # Process inline screenshot placeholders early
        from .screenshots import process_inline_screenshots
        html = await process_inline_screenshots(html, self, self.settings)
        
        # Upload media early to get correct ID and source URL for body replacements
        media_info = await self.upload_media(content.featured_image_path, alt_text=content.image_alt_text or content.image_prompt or content.title) if content.featured_image_path else None
        
        if media_info and media_info.get("id") and media_info.get("url"):
            media_id = media_info["id"]
            media_url = media_info["url"]
            
            # Replace placeholder image blocks inside content body
            html = _replace_image_placeholders(html, media_id, media_url)
            
            # Fallback for raw img tags outside formal Gutenberg block comments
            def replace_placeholder_src(img_match):
                img_tag = img_match.group(0)
                if "screenshot-inline" in img_tag:
                    return img_tag
                if any(x in img_tag for x in ["meetlyra.app/wp-content/uploads", "placeholder"]):
                    img_tag = re.sub(r'(src\s*=\s*["\'])([^"\']*)(["\'])', rf'\g<1>{media_url}\g<3>', img_tag)
                    img_tag = re.sub(r'(class\s*=\s*["\'][^"\']*wp-image-)(\d+)([^"\']*["\'])', rf'\g<1>{media_id}\g<3>', img_tag)
                return img_tag
            
            html = re.sub(r'<img\b[^>]*>', replace_placeholder_src, html)

        # Run HTML gutenbergization (FAQ blocks, code blocks, lists)
        html = gutenbergize_html_content(html)

        if content.schema_json:
            schema = json.dumps(content.schema_json, ensure_ascii=False)
            html = f'{html}\n\n<script type="application/ld+json">{schema}</script>'
            
        from datetime import datetime, timezone
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
        if status == "publish":
            payload["date_gmt"] = datetime.now(timezone.utc).isoformat()

        
        if media_info:
            payload["featured_media"] = media_info["id"]

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


def _replace_image_placeholders(html: str, media_id: int, media_url: str) -> str:
    # A block pattern: from <!-- wp:image to <!-- /wp:image -->
    pattern = re.compile(
        r"(<!--\s*wp:image\s*(?P<attrs>\{.*?\})?\s*-->.*?<!--\s*/wp:image\s*-->)",
        re.DOTALL
    )
    
    def replace_block(match):
        block_content = match.group(1)
        if "screenshot-inline" in block_content:
            return block_content
        attrs = match.group("attrs") or ""
        
        # Replace id in the Gutenberg comment JSON attributes
        if attrs:
            new_attrs = re.sub(r'("id"\s*:\s*)\d+', rf'\g<1>{media_id}', attrs)
            block_content = block_content.replace(attrs, new_attrs)
            
        def replace_img_tag(img_match):
            img_tag = img_match.group(0)
            img_tag = re.sub(r'(src\s*=\s*["\'])([^"\']*)(["\'])', rf'\g<1>{media_url}\g<3>', img_tag)
            img_tag = re.sub(r'(class\s*=\s*["\'][^"\']*wp-image-)(\d+)([^"\']*["\'])', rf'\g<1>{media_id}\g<3>', img_tag)
            return img_tag

        block_content = re.sub(r'<img\b[^>]*>', replace_img_tag, block_content)
        return block_content

    return pattern.sub(replace_block, html)


def gutenbergize_lists(html: str) -> str:
    # First, strip existing list block comments to avoid double-wrapping
    html = re.sub(r'<!--\s*wp:list(?:-item)?\b.*?-->|<!--\s*/wp:list(?:-item)?\s*-->', '', html)
    
    # Split by list tags
    pattern = re.compile(r'(</?(?:ul|ol|li)\b[^>]*>)', re.IGNORECASE)
    parts = pattern.split(html)
    
    result = []
    for part in parts:
        lower_part = part.lower()
        if lower_part.startswith('<ul') or lower_part.startswith('<ol'):
            ordered = lower_part.startswith('<ol')
            comment_attr = ' {"ordered":true}' if ordered else ''
            result.append(f'<!-- wp:list{comment_attr} -->\n' + part)
        elif lower_part.startswith('</ul>') or lower_part.startswith('</ol>'):
            result.append(part + '\n<!-- /wp:list -->')
        elif lower_part.startswith('<li'):
            result.append('<!-- wp:list-item -->\n' + part)
        elif lower_part.startswith('</li>'):
            result.append(part + '\n<!-- /wp:list-item -->')
        else:
            result.append(part)
            
    return "".join(result)


def gutenbergize_code_blocks(html: str) -> str:
    # Strip any existing wp:code block comments to avoid double-wrapping
    html = re.sub(r'<!--\s*wp:code\s*-->|<!--\s*/wp:code\s*-->', '', html)
    
    # Match <pre><code>...</code></pre>
    pre_pattern = re.compile(r'(<pre\b[^>]*>.*?<code>.*?</code>.*?</pre>)', re.DOTALL | re.IGNORECASE)
    
    def replace_pre(match):
        pre_content = match.group(1)
        # Ensure it has class="wp-block-code"
        if 'class=' not in pre_content.lower():
            pre_content = re.sub(r'<pre\b', '<pre class="wp-block-code"', pre_content, flags=re.IGNORECASE)
        elif 'wp-block-code' not in pre_content.lower():
            pre_content = re.sub(r'class\s*=\s*["\']([^"\']*)(["\'])', r'class="\1 wp-block-code\2', pre_content, flags=re.IGNORECASE)
            
        return f'<!-- wp:code -->\n{pre_content}\n<!-- /wp:code -->'
        
    return pre_pattern.sub(replace_pre, html)


def _normalize_faq_blocks(html: str) -> str:
    # Match the faq-block
    faq_block_pattern = re.compile(
        r'<!--\s*wp:yoast/faq-block\s*-->.*?<!--\s*/wp:yoast/faq-block\s*-->',
        re.DOTALL | re.IGNORECASE
    )
    
    def replace_faq_block(block_match):
        block_content = block_match.group(0)
        
        # Now find all faq-questions inside
        question_pattern = re.compile(
            r'<!--\s*wp:yoast/faq-question\s*(?P<attrs>\{.*?\})?\s*-->.*?<!--\s*/wp:yoast/faq-question\s*-->',
            re.DOTALL | re.IGNORECASE
        )
        
        questions_html = []
        for q_match in question_pattern.finditer(block_content):
            q_content = q_match.group(0)
            
            # Let's extract question text
            question_text = ""
            strong_match = re.search(r'<strong\b[^>]*>(.*?)</strong>', q_content, re.DOTALL | re.IGNORECASE)
            if strong_match:
                question_text = _strip_tags(strong_match.group(1))
            else:
                h_match = re.search(r'<h[3-6]\b[^>]*>(.*?)</h[3-6]>', q_content, re.DOTALL | re.IGNORECASE)
                if h_match:
                    question_text = _strip_tags(h_match.group(1))
                else:
                    b_match = re.search(r'<b\b[^>]*>(.*?)</b>', q_content, re.DOTALL | re.IGNORECASE)
                    if b_match:
                        question_text = _strip_tags(b_match.group(1))
            
            # Let's extract answer text
            answer_text = ""
            p_match = re.search(r'<p\b[^>]*class="[^"]*schema-faq-answer[^"]*"[^>]*>(.*?)</p>', q_content, re.DOTALL | re.IGNORECASE)
            if p_match:
                answer_text = _strip_tags(p_match.group(1))
            else:
                p_tags = re.findall(r'<p\b[^>]*>(.*?)</p>', q_content, re.DOTALL | re.IGNORECASE)
                if p_tags:
                    valid_answers = [_strip_tags(p) for p in p_tags if _strip_tags(p) != question_text]
                    if valid_answers:
                        answer_text = " ".join(valid_answers)
                else:
                    plain = _strip_tags(q_content)
                    if question_text and question_text in plain:
                        answer_text = plain.replace(question_text, "", 1).strip()
                    else:
                        answer_text = plain
            
            question_text = question_text.strip()
            answer_text = answer_text.strip()
            
            if not question_text:
                continue
                
            q_json = json.dumps({"questionName": question_text}, ensure_ascii=False)
            questions_html.append(
                f'  <!-- wp:yoast/faq-question {q_json} -->\n'
                f'  <div class="schema-faq-section">\n'
                f'    <strong class="schema-faq-question">{question_text}</strong>\n'
                f'    <!-- wp:paragraph -->\n'
                f'    <p class="schema-faq-answer">{answer_text}</p>\n'
                f'    <!-- /wp:paragraph -->\n'
                f'  </div>\n'
                f'  <!-- /wp:yoast/faq-question -->'
            )
            
        if not questions_html:
            return ""
            
        questions_joined = "\n".join(questions_html)
        return (
            f'<!-- wp:yoast/faq-block -->\n'
            f'<div class="schema-faq wp-block-yoast-faq-block">\n'
            f'{questions_joined}\n'
            f'</div>\n'
            f'<!-- /wp:yoast/faq-block -->'
        )
        
    return faq_block_pattern.sub(replace_faq_block, html)


def gutenbergize_html_content(html: str) -> str:
    # First, let's normalize FAQ blocks and code blocks
    html = _normalize_faq_blocks(html)
    html = gutenbergize_code_blocks(html)
    
    # Identify parts to preserve (like wp:html, wp:yoast/faq-block, script tags, and pre tags)
    preserve_pattern = re.compile(
        r'(<!--\s*wp:html\b.*?-->.*?<!--\s*/wp:html\s*-->|'
        r'<!--\s*wp:yoast/faq-block\b.*?-->.*?<!--\s*/wp:yoast/faq-block\s*-->|'
        r'<script\b[^>]*>.*?</script>|'
        r'<pre\b[^>]*>.*?</pre>)',
        re.DOTALL | re.IGNORECASE
    )
    
    parts = preserve_pattern.split(html)
    processed_parts = []
    
    for i, part in enumerate(parts):
        # Even indices are plain HTML where we should process lists
        if i % 2 == 0:
            processed_parts.append(gutenbergize_lists(part))
        else:
            processed_parts.append(part)
            
    return "".join(processed_parts)
