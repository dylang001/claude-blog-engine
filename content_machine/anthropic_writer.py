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

Rules for Copywriting Quality & Style:
- Write publish-ready long-form Markdown in a natural, highly engaging human-like editorial voice. Emulate the tone and style of leading professional tech publications like WIRED or Fast Company.
- Use active voice, clear structures, and short, punchy paragraphs. First-person plural ("we") or second-person ("you") should be used naturally.
- CRITICAL: Strictly forbid common AI jargon and transition clichés. Do NOT use words like "delve", "tapestry", "revolutionize", "moreover", "furthermore", "in conclusion", "it is important to remember", "testament", "beacon", or phrases like "in today's fast-paced digital world".
- Write 1,800-2,200 words. Do NOT include a Markdown H1 in markdown. The WordPress title is the only H1.
- Include at least 5 H2s. Keep headings focused on user-intent.
- Follow Yoast-style SEO copywriting: plan around audience, mission fit, search intent, a unique angle, and a clear article structure.
- Use an inverted-pyramid opening: answer the main query in the first paragraph before expanding. Start most paragraphs with a clear topic sentence.
- Cite your sources: Include at least 3-4 natural outbound links to authoritative websites (e.g. Wikipedia, primary research papers, major news publications, official documentation) in the text to verify facts/data.
- Use 3-5 contextual internal links from Research JSON when available. Link to `blog.meetlyra.app` for other blog posts and `meetlyra.app` for product/app pages. Never use `meetlyra.com`.
- Tool Reference Linking: You MUST link the first mention of any software, app, tool, platform, or service (e.g. n8n, Claude, HubSpot, Google Analytics, Ahrefs, WordPress, Yoast, GA4, GSC, etc.) to its official homepage or documentation website (e.g. [n8n](https://n8n.io/), [Claude](https://www.anthropic.com/), [Ahrefs](https://ahrefs.com/)).
- Keep sentences short and punchy: keep most sentences under 15 words. Use simple, clear vocabulary to achieve a grade-level reading ease of 60+ (Flesch Reading Ease score).
- Use modern, clean transition words/phrases in at least 30% of sentences (e.g., "also", "because", "but", "finally", "first", "for example", "however", "instead", "meanwhile", "next", "therefore", "this means", "while"). Do NOT use "moreover" or "furthermore".
- Use a 2-4 word Yoast focus keyphrase. Include it in the first paragraph, at least one H2/H3, and 5+ times in the body.
- Meta title must be 45-60 characters and start with the focus keyphrase.
- Meta description must be 130-155 characters and include the focus keyphrase.
- Excerpt: Generate a high-quality plain-text summary of exactly 130-155 characters that captures the reader's attention and includes the focus keyphrase. Do NOT include markdown styling, link formatting, or images in the excerpt string.

Rules for Inline Images and Featured Metaphors:
- **Featured Image Metaphor (`image_prompt`):** Describe a detailed, highly creative, and realistic visual concept/metaphor directly related to the article's specific headline and sub-headline. Specify subject, action, setting, natural light, shallow depth of field, premium magazine look (e.g. shot on Sony A7R IV, 85mm lens). Avoid all generic tech clichés like "laptop on desk" or "abstract data brain". MUST be text-free, no logos, no illustration, no 3D animation.
- **Inline Image Placeholders:** You MUST insert exactly 5 inline image placeholders in the markdown, distributed naturally across different body sections. Use the exact markdown format:
  `![Alt text describing a specific visual metaphor for this section](placeholder:inline-image-1)`
  `![Alt text describing a specific visual metaphor for this section](placeholder:inline-image-2)`
  `![Alt text describing a specific visual metaphor for this section](placeholder:inline-image-3)`
  `![Alt text describing a specific visual metaphor for this section](placeholder:inline-image-4)`
  `![Alt text describing a specific visual metaphor for this section](placeholder:inline-image-5)`
  The concept prompts inside these placeholders must describe realistic physical scenes or actions representing the section's topic (e.g., a startup team mapping a strategy on a whiteboard, a designer wireframing on an iPad with a stylus, a close-up of a high-contrast screen showing dashboard analytics graphs).
  FORBIDDEN IMAGE METAPHORS: Never use clunky physical/mechanical metaphors like clocks, watchmakers, gears, cogs, mechanical engines, compasses, scales, magnifying glasses, or old-world craftsmen. All images must depict modern, high-tech, digital-first B2B/SaaS work environments, collaborative whiteboarding sessions, high-contrast digital analytics dashboards on clean screens, modern design workspaces, or professional marketing presentations.

CRITICAL JSON COMPLIANCE RULES:
1. The entire response must be a single valid JSON object.
2. Escape all double quotes inside string values as \\\" (e.g., HTML class=\\\"wp-block-pullquote\\\"). Alternatively and preferably, use single quotes for HTML attributes (e.g., class='wp-block-pullquote') to avoid escaping issues entirely.
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
- Make the opening paragraph a direct inverted-pyramid answer that contains the focus keyphrase.
- Write in a natural, highly engaging human-like editorial voice (WIRED or Fast Company style). Active voice, punchy paragraphs.
- CRITICAL: Remove all AI jargon/clichés like "delve", "tapestry", "revolutionize", "moreover", "furthermore", "in conclusion", "it is important to remember".
- Include at least 3-4 natural outbound links to authoritative websites (e.g. Wikipedia, research papers, major news, official documentation) in the text.
- Link mentioned tools (e.g. n8n, Claude, HubSpot, GA4) to their official homepages/docs using markdown links.
- Ensure exactly 5 inline image placeholders are placed in the markdown using the format:
  `![Alt Text](placeholder:inline-image-1)`
  `![Alt Text](placeholder:inline-image-2)`
  `![Alt Text](placeholder:inline-image-3)`
  `![Alt Text](placeholder:inline-image-4)`
  `![Alt Text](placeholder:inline-image-5)`
  with specific, realistic physical metaphor descriptions.
  FORBIDDEN IMAGE METAPHORS: Never use cogs, gears, watchmakers, clock towers, magnifying glasses, engines, compasses, or physical tools. All concepts must be modern B2B SaaS digital layouts, collaborative meetings, whiteboards, or digital-first dashboards.
- focus_keyphrase must be 2-4 content words.
- meta_title must be 45-60 characters and start with focus_keyphrase.
- meta_description must be 130-155 characters and include focus_keyphrase.
- excerpt must be exactly 130-155 characters plain text, including focus_keyphrase. No markdown or links.
- focus_keyphrase must appear in first paragraph, one H2/H3, image_alt_text, slug, and at least 5 body mentions.
- Add at least one outbound authority link and at least two internal MeetLyra links. Use `blog.meetlyra.app` for blog/articles and `meetlyra.app` for app/product pages.
- Preserve or improve image_prompt metaphor so it describes a detailed, highly creative, and realistic visual scene (Sony A7R IV, 85mm, natural lighting, no text, no illustration).
- Target a grade 8-10 reading level: shorter words, fewer clauses, active voice.
- Keep sentences short and punchy: keep most sentences under 14 words. Use simple, clear vocabulary to achieve a grade-level reading ease of 60+ (Flesch Reading Ease score).
- Use modern, clean transition words/phrases in at least 35% of sentences (e.g., "also", "because", "but", "finally", "first", "for example", "however", "instead", "meanwhile", "next", "therefore", "this means", "while"). Do NOT use "moreover" or "furthermore".

CRITICAL JSON COMPLIANCE RULES:
1. The entire response must be a single valid JSON object.
2. Escape all double quotes inside string values as \\\" (e.g., HTML class=\\\"wp-block-pullquote\\\"). Alternatively and preferably, use single quotes for HTML attributes (e.g., class='wp-block-pullquote') to avoid escaping issues entirely.
3. Escape all newlines inside string values as \\n.

Opportunity: {json.dumps(opportunity.__dict__, default=str)}
Research JSON: {json.dumps(research, default=str)[:5000]}
Current content JSON: {json.dumps(content.__dict__, default=str)[:12000]}
"""

    def _parse_json(self, text: str) -> dict[str, Any]:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("No JSON object found")
        json_str = text[start : end + 1]
        try:
            return json.loads(json_str, strict=False)
        except json.JSONDecodeError as exc:
            try:
                debug_path = self.settings.data_dir / "failed_json_raw.txt"
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

    # _fallback_content removed — the system must never silently produce
    # fabricated placeholder articles. If Anthropic fails, the pipeline
    # raises RuntimeError so the operator can diagnose and fix the issue.
