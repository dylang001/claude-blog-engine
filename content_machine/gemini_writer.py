"""
gemini_writer.py — Gemini 2.5 Pro fallback content writer.

Used automatically when the Anthropic API returns a credit/quota error.
Implements the identical ContentWriter interface (generate + repair) using
Google's Gemini API so the pipeline can switch seamlessly.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from .content_optimizer import optimize_content
from .config import Settings
from .models import AuditReport, GeneratedContent, Opportunity
from .utils import excerpt, markdown_to_html, slugify

logger = logging.getLogger("content_machine.gemini_writer")

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiWriter:
    """Gemini-powered blog post writer. Drop-in replacement for ContentWriter."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = settings.gemini_writing_model or "gemini-2.5-pro-preview-05-06"

    def is_configured(self) -> bool:
        return bool(self.settings.gemini_api_key)

    async def generate(self, opportunity: Opportunity, research: dict[str, Any]) -> GeneratedContent:
        if not self.is_configured():
            raise RuntimeError(
                "GEMINI_API_KEY is required for Gemini fallback writing. "
                "Set GEMINI_API_KEY in your environment."
            )
        prompt = self._prompt(opportunity, research)
        text = await self._call(prompt)
        parsed = self._parse_json(text)
        return optimize_content(self._from_payload(opportunity, parsed), opportunity)

    async def repair(self, content: GeneratedContent, opportunity: Opportunity, research: dict[str, Any], audit: AuditReport) -> GeneratedContent:
        if not self.is_configured():
            raise RuntimeError("GEMINI_API_KEY required for Gemini fallback repair.")
        prompt = self._repair_prompt(content, opportunity, research, audit)
        text = await self._call(prompt)
        parsed = self._parse_json(text)
        return optimize_content(self._from_payload(opportunity, parsed), opportunity)

    async def _call(self, prompt: str) -> str:
        url = f"{GEMINI_API_BASE}/{self.model}:generateContent?key={self.settings.gemini_api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 12000,
                "responseMimeType": "application/json",
            },
        }
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
                resp.raise_for_status()
                data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError(f"Gemini returned no candidates. Response: {json.dumps(data)[:500]}")
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise RuntimeError("Gemini candidate has no parts.")
            return parts[0].get("text", "")
        except Exception as exc:
            raise RuntimeError(f"Gemini content generation failed: {type(exc).__name__}: {exc}") from exc

    def _prompt(self, opportunity: Opportunity, research: dict[str, Any]) -> str:
        site = self.settings.site
        return f"""You are the autonomous writer for an SEO content machine.

Brand: {site.brand_name}
Site: {site.site_url}
Audience: {site.audience}
Voice: {site.voice}
CTA: {site.cta}
Target keyword: {opportunity.keyword}
Work type: {opportunity.kind.value}
Current date: {datetime.now(timezone.utc).date().isoformat()}
Research JSON: {json.dumps(research, default=str)[:8000]}

Return ONLY valid JSON with:
title, slug, markdown, meta_title, meta_description, focus_keyphrase,
excerpt, tags array, categories array, schema_json object, image_prompt,
image_alt_text, rich_blocks array.

Rules for Copywriting Quality & Style:
- Write publish-ready long-form Markdown in a natural, highly engaging human-like editorial voice. Emulate the tone and style of leading professional tech publications like WIRED or Fast Company.
- Use active voice, clear structures, and short, punchy paragraphs. First-person plural ("we") or second-person ("you") should be used naturally.
- CRITICAL: Strictly forbid common AI jargon and transition clichés. Do NOT use words like "delve", "tapestry", "revolutionize", "moreover", "furthermore", "in conclusion", "it is important to remember", "testament", "beacon", or phrases like "in today's fast-paced digital world".
- Write 1,800-2,200 words. Do NOT include a Markdown H1 in markdown. The WordPress title is the only H1.
- Include at least 5 H2s. Keep headings focused on user-intent.
- Follow Yoast-style SEO copywriting: plan around audience, mission fit, search intent, a unique angle, and a clear article structure.
- Use an inverted-pyramid opening: answer the main query in the first paragraph before expanding.
- Cite your sources: Include at least 3-4 natural outbound links to authoritative websites.
- Use 3-5 contextual internal links from Research JSON when available. Link to blog.meetlyra.app for blog posts and meetlyra.app for product pages. Never use meetlyra.com.
- Tool Reference Linking: Link the first mention of any software or tool to its official homepage.
- Keep sentences short and punchy: most under 15 words. Flesch Reading Ease 60+.
- Use modern clean transition words in at least 30% of sentences.
- Use a 2-4 word Yoast focus keyphrase. Include it in the first paragraph, at least one H2/H3, and 5+ times in the body.
- Meta title must be 45-60 characters and start with the focus keyphrase.
- Meta description must be 130-155 characters and include the focus keyphrase.
- Excerpt: Generate a high-quality plain-text summary of exactly 130-155 characters.

Rules for Inline Images:
- Featured Image Metaphor (image_prompt): Describe a detailed, creative, realistic visual scene. No logos, no illustration, no 3D animation. Specify subject, action, setting, natural light, shallow depth of field, shot on Sony A7R IV 85mm.
- Insert exactly 5 inline image placeholders: ![Alt text](placeholder:inline-image-1) through placeholder:inline-image-5.
- FORBIDDEN: cogs, gears, clocks, watchmakers, compasses. All images must depict modern B2B SaaS environments.

CRITICAL JSON COMPLIANCE:
1. The entire response must be a single valid JSON object.
2. Use single quotes for HTML attributes inside string values.
3. Escape all newlines inside string values as \\n.
"""

    def _repair_prompt(self, content: GeneratedContent, opportunity: Opportunity, research: dict[str, Any], audit: AuditReport) -> str:
        return f"""Repair this SEO article so it clears all required Yoast-style and readability checks.

Return ONLY valid JSON with the same fields:
title, slug, markdown, meta_title, meta_description, focus_keyphrase,
excerpt, tags array, categories array, schema_json object, image_prompt,
image_alt_text, rich_blocks array.

Required fixes:
{json.dumps({"issues": audit.issues, "warnings": audit.warnings, "details": audit.details}, default=str)}

Hard requirements:
- markdown must not start with # or contain any H1.
- Make the opening paragraph a direct inverted-pyramid answer containing the focus keyphrase.
- Write in a natural, human-like editorial voice (WIRED/Fast Company style).
- Remove all AI clichés: "delve", "tapestry", "revolutionize", "moreover", "furthermore".
- Include at least 3-4 natural outbound links to authoritative websites.
- Link mentioned tools to their official homepages.
- Ensure exactly 5 inline image placeholders (placeholder:inline-image-1 through 5).
- FORBIDDEN IMAGE METAPHORS: cogs, gears, clocks, magnifying glasses, compasses.
- focus_keyphrase must be 2-4 content words.
- meta_title must be 45-60 characters starting with focus_keyphrase.
- meta_description must be 130-155 characters including focus_keyphrase.
- excerpt must be exactly 130-155 characters plain text with focus_keyphrase. No markdown.

CRITICAL JSON COMPLIANCE:
1. The entire response must be a single valid JSON object.
2. Use single quotes for HTML attributes inside string values.
3. Escape all newlines inside string values as \\n.

Opportunity: {json.dumps(opportunity.__dict__, default=str)}
Research JSON: {json.dumps(research, default=str)[:5000]}
Current content JSON: {json.dumps(content.__dict__, default=str)[:12000]}
"""

    def _parse_json(self, text: str) -> dict[str, Any]:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(f"No JSON object found in Gemini response. Got: {text[:500]}")
        try:
            return json.loads(text[start: end + 1], strict=False)
        except json.JSONDecodeError as exc:
            try:
                debug_path = self.settings.data_dir / "gemini_failed_json_raw.txt"
                self.settings.data_dir.mkdir(parents=True, exist_ok=True)
                debug_path.write_text(text, encoding="utf-8")
            except Exception:
                pass
            raise exc

    def _from_payload(self, opportunity: Opportunity, payload: dict[str, Any]) -> GeneratedContent:
        markdown = payload.get("markdown", "")
        title = payload.get("title") or opportunity.title
        return GeneratedContent(
            title=title,
            slug=payload.get("slug") or slugify(title),
            markdown=markdown,
            html=markdown_to_html(markdown),
            meta_title=payload.get("meta_title") or title[:60],
            meta_description=payload.get("meta_description") or excerpt(markdown),
            focus_keyphrase=payload.get("focus_keyphrase") or opportunity.keyword,
            excerpt=payload.get("excerpt") or excerpt(markdown),
            tags=list(payload.get("tags") or [opportunity.keyword]),
            categories=list(payload.get("categories") or ["SEO"]),
            schema_json=dict(payload.get("schema_json") or {}),
            image_prompt=payload.get("image_prompt"),
            image_alt_text=payload.get("image_alt_text"),
            rich_blocks=list(payload.get("rich_blocks") or []),
        )
