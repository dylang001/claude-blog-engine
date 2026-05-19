from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx

from .content_optimizer import optimize_content
from .config import Settings
from .models import AuditReport, GeneratedContent, Opportunity
from .utils import excerpt, markdown_to_html, slugify


class ContentWriter:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def generate(self, opportunity: Opportunity, research: dict[str, Any]) -> GeneratedContent:
        if not self.settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is required for content generation. "
                "Set ANTHROPIC_API_KEY in your .env file."
            )
        prompt = self._prompt(opportunity, research)
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.settings.anthropic_model,
                        "max_tokens": 12000,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            text = data["content"][0]["text"]
            parsed = self._parse_json(text)
            return optimize_content(self._from_payload(opportunity, parsed), opportunity)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"Anthropic content generation failed: {type(exc).__name__}: {exc}"
            ) from exc

    async def repair(self, content: GeneratedContent, opportunity: Opportunity, research: dict[str, Any], audit: AuditReport) -> GeneratedContent:
        if not self.settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is required for content repair. "
                "Set ANTHROPIC_API_KEY in your .env file."
            )
        prompt = self._repair_prompt(content, opportunity, research, audit)
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.settings.anthropic_model,
                        "max_tokens": 12000,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            parsed = self._parse_json(data["content"][0]["text"])
            return optimize_content(self._from_payload(opportunity, parsed), opportunity)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"Anthropic content repair failed: {type(exc).__name__}: {exc}"
            ) from exc

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

Rules:
- Write publish-ready long-form Markdown.
- Do NOT include a Markdown H1 in markdown. The WordPress title is the only H1.
- Write 1,800-2,200 words.
- Include at least 5 H2s, concise paragraphs, and internal links where useful.
- Follow Yoast-style SEO copywriting: plan around audience, mission fit, search intent, a unique angle, and a clear article structure.
- Use an inverted-pyramid opening: answer the main query in the first paragraph before expanding.
- Start most paragraphs with a clear topic sentence and keep paragraphs short enough to scan.
- Use 3-5 contextual internal links from Research JSON when available. Link to `blog.meetlyra.app` for other blog posts, guides, comparisons, and articles. Link to `meetlyra.app` for the app, product pages, features, use cases, industries, pricing, signup, or platform pages. Never use `meetlyra.com`. Do not use the exact focus keyphrase as internal-link anchor text.
- Keep most sentences under 20 words and use transition words in at least 30% of sentences.
- Avoid generic AI-style filler, summary padding, and formulaic endings. Every paragraph should add a concrete point, example, proof source, or decision rule.
- Use a 2-4 word Yoast focus keyphrase.
- Meta title must be 45-60 characters and start with the focus keyphrase.
- Meta description must be 130-155 characters and include the focus keyphrase.
- Include the focus keyphrase in the first paragraph, at least one H2/H3, and 5+ times in the body.
- Include at least one relevant outbound authority link and at least two internal MeetLyra links. Blog/article links should use `blog.meetlyra.app`; product, feature, use-case, industry, pricing, signup, and app links should use `meetlyra.app`.
- Include Gutenberg-compatible HTML blocks for reading time, table of contents, pull quote, proof/source callout, key takeaways, comparison table, simple chart/workflow, related articles, and FAQ.
- Use Gutenberg-compatible image/link markup when a source screenshot or analytics image URL exists in Research JSON. Image alt text must be descriptive and contain the focus keyphrase.
- Image prompts must follow the MeetLyra house style: Pixar-meets-reality cinematic 3D realism, warm expressive original characters, a subtle Lyra AI operator/software presence, real SaaS workspace lighting, no readable text inside the image, no logos, and no copied characters from existing films.
- No invented statistics, fake case studies, anonymous customer examples, or unsupported performance claims. Attribute specific claims from research or remove them.
- Optimize for Google search and AI answer engines.
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
- Make the opening paragraph a direct inverted-pyramid answer that contains the focus keyphrase.
- Improve article structure, headings, short paragraphs, and topic sentences according to Yoast SEO copywriting guidance.
- focus_keyphrase must be 2-4 content words.
- meta_title must be 45-60 characters and start with focus_keyphrase.
- meta_description must be 130-155 characters and include focus_keyphrase.
- focus_keyphrase must appear in first paragraph, one H2/H3, image_alt_text, slug, and at least 5 body mentions.
- Add at least one outbound authority link and at least two internal MeetLyra links. Use `blog.meetlyra.app` for blog/articles and `meetlyra.app` for app, product, feature, use-case, industry, pricing, signup, and platform links. Avoid exact-match focus-keyphrase internal anchors.
- Preserve or improve image_prompt so it follows the MeetLyra house style: Pixar-meets-reality cinematic 3D realism, warm expressive original characters, a subtle Lyra AI operator/software presence, real SaaS workspace lighting, no readable text inside the image, no logos, and no copied characters from existing films.
- Improve sentence clarity and add transition words naturally.
- Remove generic AI-style filler, formulaic summaries, fake case studies, anonymous performance examples, unsupported quantified claims, and any sentence that only explains that the article is easy to scan.
- Preserve factual accuracy and do not invent statistics.
- Expand the article to at least 1,800 words if it is too short.
- Rewrite difficult sentences into shorter, clearer sentences.
- Target a grade 8-10 reading level: shorter words, fewer clauses, active voice, and no long chained sentences.
- Keep most sentences under 16 words during readability repair.
- Replace jargon with plain language when the meaning stays accurate.
- Add transition words naturally to at least 30% of sentences.
- Add or preserve Gutenberg-compatible reading time, table of contents, related articles, proof/source callout, FAQ, quote, table, and chart/workflow blocks.

Opportunity: {json.dumps(opportunity.__dict__, default=str)}
Research JSON: {json.dumps(research, default=str)[:5000]}
Current content JSON: {json.dumps(content.__dict__, default=str)[:12000]}
"""

    def _parse_json(self, text: str) -> dict[str, Any]:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("No JSON object found")
        return json.loads(text[start : end + 1])

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

    # _fallback_content removed — the system must never silently produce
    # fabricated placeholder articles. If Anthropic fails, the pipeline
    # raises RuntimeError so the operator can diagnose and fix the issue.
