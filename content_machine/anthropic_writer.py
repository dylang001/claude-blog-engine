from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from .content_optimizer import optimize_content
from .config import Settings
from .models import AuditReport, GeneratedContent, Opportunity
from .supermemory import SuperMemoryClient
from .utils import excerpt, load_agent_instructions, markdown_to_html, slugify

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class ContentWriter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._seo_content_rules = load_agent_instructions("seo-content")
        self._seo_geo_rules = load_agent_instructions("seo-geo")
        self._seo_schema_rules = load_agent_instructions("seo-schema")
        self._seo_sxo_rules = load_agent_instructions("seo-sxo")
        self._seo_ecommerce_rules = load_agent_instructions("seo-ecommerce")

    async def generate(self, opportunity: Opportunity, research: dict[str, Any]) -> GeneratedContent:
        # Pre-load audit-failure learnings from SuperMemory so the writer avoids past mistakes
        research = await self._enrich_with_audit_failures(research)
        if self.settings.writer_provider == "gemini":
            return await self._generate_gemini(opportunity, research)
        return await self._generate_anthropic(opportunity, research)

    async def _enrich_with_audit_failures(self, research: dict[str, Any]) -> dict[str, Any]:
        """Pull recent audit-failure learnings from SuperMemory to inject into the writer context."""
        try:
            sm = SuperMemoryClient(self.settings)
            failures = await sm.search_memory_with_tag(
                query="common SEO audit failures writing mistakes",
                tag="audit-failures",
                limit=5,
            )
            if failures:
                research = dict(research)
                research["audit_failure_learnings"] = [
                    item.get("content", item.get("text", ""))[:500]
                    for item in failures
                    if item.get("content") or item.get("text")
                ]
        except Exception as exc:
            logger.warning("Failed to enrich research with audit failures: %s", exc)
        return research

    async def repair(self, content: GeneratedContent, opportunity: Opportunity, research: dict[str, Any], audit: AuditReport) -> GeneratedContent:
        if self.settings.writer_provider == "gemini":
            return await self._repair_gemini(content, opportunity, research, audit)
        return await self._repair_anthropic(content, opportunity, research, audit)

    async def _generate_gemini(self, opportunity: Opportunity, research: dict[str, Any]) -> GeneratedContent:
        if not self.settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is required for Gemini content generation. "
                "Set GEMINI_API_KEY in your .env file."
            )

        try:
            url = f"{GEMINI_API_BASE}/{self.settings.gemini_model}:generateContent"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": "Generate the content now. Return ONLY valid JSON."}]
                    }
                ],
                "systemInstruction": {
                    "parts": [{"text": self._system_prompt(opportunity, research)}]
                },
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING"},
                            "slug": {"type": "STRING"},
                            "markdown": {"type": "STRING"},
                            "meta_title": {"type": "STRING"},
                            "meta_description": {"type": "STRING"},
                            "focus_keyphrase": {"type": "STRING"},
                            "excerpt": {"type": "STRING"},
                            "tags": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"}
                            },
                            "categories": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"}
                            },
                            "schema_json": {
                                "type": "OBJECT"
                            },
                            "image_prompt": {"type": "STRING"},
                            "image_alt_text": {"type": "STRING"},
                            "rich_blocks": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"}
                            }
                        },
                        "required": [
                            "title", "slug", "markdown", "meta_title", "meta_description",
                            "focus_keyphrase", "excerpt", "tags", "categories", "schema_json",
                            "image_prompt", "image_alt_text"
                        ]
                    },
                    "temperature": 0.2
                }
            }

            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    url,
                    params={"key": self.settings.gemini_api_key},
                    headers={"content-type": "application/json"},
                    json=payload,
                )
                if resp.status_code >= 400:
                    try:
                        err_detail = resp.json()
                        err_msg = err_detail.get("error", {}).get("message", resp.text)
                    except Exception:
                        err_msg = resp.text
                    raise RuntimeError(f"Gemini API returned {resp.status_code}: {err_msg}")
                data = resp.json()

            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = self._parse_json(text)
            return optimize_content(self._from_payload(opportunity, parsed), opportunity)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"Gemini content generation failed: {type(exc).__name__}: {exc}"
            ) from exc

    async def _repair_gemini(self, content: GeneratedContent, opportunity: Opportunity, research: dict[str, Any], audit: AuditReport) -> GeneratedContent:
        if not self.settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is required for Gemini content repair. "
                "Set GEMINI_API_KEY in your .env file."
            )

        try:
            url = f"{GEMINI_API_BASE}/{self.settings.gemini_model}:generateContent"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": "Repair the content now. Return ONLY valid JSON."}]
                    }
                ],
                "systemInstruction": {
                    "parts": [{"text": self._system_repair_prompt(content, opportunity, research, audit)}]
                },
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING"},
                            "slug": {"type": "STRING"},
                            "markdown": {"type": "STRING"},
                            "meta_title": {"type": "STRING"},
                            "meta_description": {"type": "STRING"},
                            "focus_keyphrase": {"type": "STRING"},
                            "excerpt": {"type": "STRING"},
                            "tags": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"}
                            },
                            "categories": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"}
                            },
                            "schema_json": {
                                "type": "OBJECT"
                            },
                            "image_prompt": {"type": "STRING"},
                            "image_alt_text": {"type": "STRING"},
                            "rich_blocks": {
                                "type": "ARRAY",
                                "items": {"type": "STRING"}
                            }
                        },
                        "required": [
                            "title", "slug", "markdown", "meta_title", "meta_description",
                            "focus_keyphrase", "excerpt", "tags", "categories", "schema_json",
                            "image_prompt", "image_alt_text"
                        ]
                    },
                    "temperature": 0.2
                }
            }

            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    url,
                    params={"key": self.settings.gemini_api_key},
                    headers={"content-type": "application/json"},
                    json=payload,
                )
                if resp.status_code >= 400:
                    try:
                        err_detail = resp.json()
                        err_msg = err_detail.get("error", {}).get("message", resp.text)
                    except Exception:
                        err_msg = resp.text
                    raise RuntimeError(f"Gemini API returned {resp.status_code}: {err_msg}")
                data = resp.json()

            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = self._parse_json(text)
            return optimize_content(self._from_payload(opportunity, parsed), opportunity)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"Gemini content repair failed: {type(exc).__name__}: {exc}"
            ) from exc

    async def _generate_anthropic(self, opportunity: Opportunity, research: dict[str, Any]) -> GeneratedContent:
        if not self.settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is required for content generation. "
                "Set ANTHROPIC_API_KEY in your .env file."
            )

        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "anthropic-beta": "prompt-caching-2024-07-31",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.settings.anthropic_model,
                        "max_tokens": 8000,
                        "system": [
                            {
                                "type": "text",
                                "text": self._system_prompt(opportunity, research),
                                "cache_control": {"type": "ephemeral"}
                            }
                        ],
                        "messages": [{"role": "user", "content": "Generate the content now. Return ONLY valid JSON."}],
                    },
                )
                if resp.status_code >= 400:
                    try:
                        err_detail = resp.json()
                        err_msg = err_detail.get("error", {}).get("message", resp.text)
                    except Exception:
                        err_msg = resp.text
                    raise RuntimeError(f"Anthropic API returned {resp.status_code}: {err_msg}")
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

    async def _repair_anthropic(self, content: GeneratedContent, opportunity: Opportunity, research: dict[str, Any], audit: AuditReport) -> GeneratedContent:
        if not self.settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is required for content repair. "
                "Set ANTHROPIC_API_KEY in your .env file."
            )

        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "anthropic-beta": "prompt-caching-2024-07-31",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.settings.anthropic_model,
                        "max_tokens": 8000,
                        "system": [
                            {
                                "type": "text",
                                "text": self._system_repair_prompt(content, opportunity, research, audit),
                                "cache_control": {"type": "ephemeral"}
                            }
                        ],
                        "messages": [{"role": "user", "content": "Repair the content now. Return ONLY valid JSON."}],
                    },
                )
                if resp.status_code >= 400:
                    try:
                        err_detail = resp.json()
                        err_msg = err_detail.get("error", {}).get("message", resp.text)
                    except Exception:
                        err_msg = resp.text
                    raise RuntimeError(f"Anthropic API returned {resp.status_code}: {err_msg}")
                data = resp.json()
            parsed = self._parse_json(data["content"][0]["text"])
            return optimize_content(self._from_payload(opportunity, parsed), opportunity)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"Anthropic content repair failed: {type(exc).__name__}: {exc}"
            ) from exc


    def _system_prompt(self, opportunity: Opportunity, research: dict[str, Any]) -> str:
        site = self.settings.site
        
        parent_link_instruction = ""
        target_link = research.get("target_internal_link")
        if target_link:
            parent_link_instruction = f"""
=========================================
CRITICAL MANDATORY REQUIREMENT: PARENT PILLAR LINK INJECTION
You MUST include exactly one HTML link to the parent pillar page in the main body text (e.g. inside the introduction or under the first H2 heading).
- Target URL: {target_link['url']}
- Exact Anchor Text: {target_link['anchor_text']}
- Exact HTML to inject: <a href="{target_link['url']}">{target_link['anchor_text']}</a>
=========================================
"""

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
{parent_link_instruction}
Return ONLY valid JSON. The main content body must be returned in the 'markdown' key. However, despite the key being named 'markdown', the value MUST be publish-ready Gutenberg-formatted HTML (NOT Markdown).

Rules:
- Write publish-ready Gutenberg-formatted HTML (NOT Markdown). Wrap all text in proper WordPress block comments (e.g., <!-- wp:paragraph --><p>...</p><!-- /wp:paragraph -->).
- Do NOT include an H1 tag. The WordPress title is the only H1.
- Word count requirement: The value of the 'markdown' key in the JSON response MUST be a detailed, long-form, comprehensive, and complete article of 1,800 to 2,200 words. Do not write a summary or a short overview. Write multiple long-form paragraphs under each of the 5+ H2 headings, expanding on definitions, step-by-step instructions, practical applications, and strategic advice.
- Include at least 5 H2s, short scannable paragraphs, and internal links where useful.
- Copywriting Style (Ahrefs-style):
  - Use extremely short, scannable paragraphs (1-3 sentences max).
  - Bold key terms, core takeaways, and action items to support skimming.
  - Use bulleted/numbered lists and structured tables for comparisons.
  - Create visual takeaway callouts or warning boxes.
- Link Requirements:
  - Use 3-5 contextual internal links from Research JSON when available.
  - Link to `blog.meetlyra.app` for other blog posts, guides, comparisons, and articles.
  - Any links to the main product, app, features, pricing, signup, or login MUST point to the waitlist: `https://waitlist.meetlyra.app`. Do NOT link to `meetlyra.app` directly or `meetlyra.com`.
  - Do not use the exact focus keyphrase as internal-link anchor text.
  - Include at least one relevant outbound authority link and at least two internal MeetLyra links. Outbound links should have rel="nofollow" if they target external tools, software, or platforms.
- Multimedia & Screenshot Snippets:
  - You MUST include 2-3 inline screenshots of external documentation, tools, or websites referenced in the post.
  - Format screenshot placeholders exactly as follows using Gutenberg image comments:
    <!-- wp:image {{"sizeSlug":"large","linkDestination":"none"}} -->
    <figure class="wp-block-image"><img src="screenshot:https://url-to-screenshot.com" alt="Detailed description of the screenshot" loading="lazy" /></figure>
    <!-- /wp:image -->
    For example, if referencing Playwright, use `screenshot:https://playwright.dev/docs/getting-started-mcp`. The URLs must be valid, active public URLs.
- Keep most sentences under 16-20 words and use transition words in at least 30% of sentences.
- **Flesch Reading Ease target: 50 or higher.** Write at a Grade 8-10 level: short sentences, active voice, one idea per sentence. If a sentence exceeds 20 words, split it into two sentences.
- **Transition words:** Start at least 1 in 3 sentences with a transition word such as: However, Additionally, For example, That said, Furthermore, In contrast, As a result, Similarly, Therefore, Meanwhile, First, Next, Finally.
- Avoid generic AI-style filler, summary padding, and formulaic endings. Every paragraph should add a concrete point, example, proof source, or decision rule.
- **GEO Quick-Answer Block:** Immediately after the introduction paragraph, add a 134-167 word self-contained definition block using `<!-- wp:html -->` with class `seo-machine-quick-answer`. This block must define the focus keyphrase in plain, authoritative language with at least one specific integration detail or statistic. It should be parseable standalone by AI search engines.
- Use a 2-4 word Yoast focus keyphrase.
- Meta title must be 45-60 characters and start with the focus keyphrase.
- Meta description must be 130-155 characters and include the focus keyphrase.
- Include the focus keyphrase in the first paragraph, at least one H2/H3, and 5+ times in the body.
- ALWAYS add `rel="nofollow"` to outbound links pointing to external tools, software, or companies.
- For FAQs, ALWAYS use the exact Yoast FAQ block format: `<!-- wp:yoast/faq-block -->` containing `<!-- wp:yoast/faq-question -->` blocks.
- NEVER include a "Reading Time" text or block—the WordPress theme handles this automatically.
- Include multi-format media: table of contents, comparison tables, code snippets, and image placeholders (wrapped in `<!-- wp:image -->`). Image alt text must be descriptive and contain the focus keyphrase.
- Image Prompt Style:
  - Generate a prompt for a high-quality featured header image in the 'image_prompt' field.
  - The style must follow the premium tech desk workspace photography style: a clean workspace setup, a MacBook showing SaaS dashboards/graphs, realistic office or studio lighting with soft shadows, shallow depth of field, modern millennial workspace vibe, warm natural tones, no cartoonish/Pixar characters, no logos, no distorted elements, and no readable text.
- No invented statistics, fake case studies, anonymous customer examples, or unsupported performance claims. Attribute specific claims from research or remove them.
- Product Availability Guardrail: {site.brand_name} is currently in PRIVATE BETA and NOT publicly available to the general public yet. Do NOT write about how to try, sign up, use, log in, or run the product. Do not describe specific product screens, pricing plans, or step-by-step product usage. Any CTAs or references to acquiring the product must strictly refer to joining the private beta waitlist or signing up for early access updates (using `https://waitlist.meetlyra.app`).
- Optimize for Google search and AI answer engines.
- **Schema JSON requirement:** Always include an Article schema with:
  - `"inLanguage": "en"`
  - `"publisher": {{"@type": "Organization", "name": "MeetLyra", "url": "https://meetlyra.app", "sameAs": ["https://www.linkedin.com/company/meetlyra"]}}`
  - Include a `mainEntity` with FAQPage entries matching the FAQ block questions.

--- DYNAMIC SEO GUIDELINES (loaded from claude-seo agents) ---

{self._format_dynamic_rules()}
"""

    def _format_dynamic_rules(self) -> str:
        """Format dynamically loaded SEO agent rules for prompt injection."""
        sections = []
        if self._seo_content_rules:
            sections.append(f"### E-E-A-T & Content Quality (seo-content)\n{self._seo_content_rules[:1500]}")
        if self._seo_geo_rules:
            sections.append(f"### Generative Engine Optimization (seo-geo)\n{self._seo_geo_rules[:1500]}")
        if self._seo_schema_rules:
            sections.append(f"### Schema Markup (seo-schema)\n{self._seo_schema_rules[:1200]}")
        if self._seo_sxo_rules:
            sections.append(f"### Search Experience Optimization (seo-sxo)\n{self._seo_sxo_rules[:1500]}")
        if self._seo_ecommerce_rules:
            sections.append(f"### E-commerce & Product page SEO (seo-ecommerce)\n{self._seo_ecommerce_rules[:1500]}")
        return "\n\n".join(sections) if sections else "No dynamic rules loaded."

    def _system_repair_prompt(self, content: GeneratedContent, opportunity: Opportunity, research: dict[str, Any], audit: AuditReport) -> str:
        parent_link_instruction = ""
        target_link = research.get("target_internal_link")
        if target_link:
            parent_link_instruction = f"""
=========================================
CRITICAL MANDATORY REQUIREMENT: PARENT PILLAR LINK INJECTION
You MUST include exactly one HTML link to the parent pillar page in the main body text (e.g. inside the introduction or under the first H2 heading).
- Target URL: {target_link['url']}
- Exact Anchor Text: {target_link['anchor_text']}
- Exact HTML to inject: <a href="{target_link['url']}">{target_link['anchor_text']}</a>
=========================================
"""

        return f"""Repair this SEO article so it clears all required Yoast-style and readability checks.

Return ONLY valid JSON with the same fields:
title, slug, markdown, meta_title, meta_description, focus_keyphrase,
excerpt, tags array, categories array, schema_json object, image_prompt,
image_alt_text, rich_blocks array.
{parent_link_instruction}
Required fixes:
{json.dumps({"issues": audit.issues, "warnings": audit.warnings, "details": audit.details}, default=str)}

Hard requirements:
- markdown must not start with # or contain any H1.
- Make the opening paragraph a direct inverted-pyramid answer that contains the focus keyphrase.
- Copywriting Style (Ahrefs-style):
  - Use extremely short, scannable paragraphs (1-3 sentences max).
  - Bold key terms, core takeaways, and action items to support skimming.
  - Use bulleted/numbered lists and structured tables for comparisons.
  - Create visual takeaway callouts or warning boxes.
- Improve article structure, headings, short paragraphs, and topic sentences according to Yoast SEO copywriting guidance.
- focus_keyphrase must be 2-4 content words.
- meta_title must be 45-60 characters and start with focus_keyphrase.
- meta_description must be 130-155 characters and include focus_keyphrase.
- focus_keyphrase must appear in first paragraph, one H2/H3, image_alt_text, slug, and at least 5 body mentions.
- Link Requirements:
  - Use 3-5 contextual internal links from Research JSON when available. Use `blog.meetlyra.app` for blog/articles.
  - Any links to the main product, app, features, pricing, signup, or login MUST point to the waitlist: `https://waitlist.meetlyra.app`. Do NOT link to `meetlyra.app` directly or `meetlyra.com`.
  - Avoid exact-match focus-keyphrase internal anchors.
  - Include at least one relevant outbound authority link and at least two internal MeetLyra links. Outbound links must have rel="nofollow" if they target external tools, software, or platforms.
- Multimedia & Screenshot Snippets:
  - You MUST include 2-3 inline screenshots of external documentation, tools, or websites referenced in the post.
  - Format screenshot placeholders exactly as follows using Gutenberg image comments:
    <!-- wp:image {{"sizeSlug":"large","linkDestination":"none"}} -->
    <figure class="wp-block-image"><img src="screenshot:https://url-to-screenshot.com" alt="Detailed description of the screenshot" /></figure>
    <!-- /wp:image -->
    For example, if referencing Playwright, use `screenshot:https://playwright.dev/docs/getting-started-mcp`. The URLs must be valid, active public URLs.
- Image Prompt Style:
  - Preserve or improve image_prompt so it follows the premium tech desk workspace photography style: a clean workspace setup, a MacBook showing SaaS dashboards/graphs, realistic office or studio lighting with soft shadows, shallow depth of field, modern millennial workspace vibe, warm natural tones, no cartoonish/Pixar characters, no logos, no distorted elements, and no readable text.
- Improve sentence clarity and add transition words naturally.
- Remove generic AI-style filler, formulaic summaries, fake case studies, anonymous performance examples, unsupported quantified claims, and any sentence that only explains that the article is easy to scan.
- Preserve factual accuracy and do not invent statistics.
- Word count requirement: The value of the 'markdown' key in the JSON response MUST be a detailed, long-form, comprehensive, and complete article of 1,800 to 2,200 words. Do not write a summary or a short overview. Write multiple long-form paragraphs under each of the 5+ H2 headings, expanding on definitions, step-by-step instructions, practical applications, and strategic advice.
- Rewrite difficult sentences into shorter, clearer sentences.
- Target a grade 8-10 reading level: shorter words, fewer clauses, active voice, and no long chained sentences.
- Keep most sentences under 16 words during readability repair.
- Replace jargon with plain language when the meaning stays accurate.
- Add transition words naturally to at least 30% of sentences.
- Ensure ALL content is wrapped in valid WordPress block HTML (e.g., <!-- wp:paragraph --><p>...</p><!-- /wp:paragraph -->). Markdown is NOT allowed.
- Remove any "Reading Time" text or blocks.
- Format FAQs using the Yoast FAQ block comment syntax.
- Ensure all outbound tool/software links have rel="nofollow".

Opportunity: {json.dumps(opportunity.__dict__, default=str)}
Research JSON: {json.dumps(research, default=str)[:8000]}
Current content JSON: {json.dumps(content.__dict__, default=str)[:12000]}
"""

    def _parse_json(self, text: str) -> dict[str, Any]:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("No JSON object found")
        json_str = text[start : end + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as exc:
            try:
                # Attempt to escape unescaped control characters inside JSON strings
                cleaned = re.sub(
                    r'(?<=[:,\s"\[])"([^"\\]*(?:\\.[^"\\]*)*)"',
                    lambda m: m.group(0).replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t'),
                    json_str
                )
                return json.loads(cleaned)
            except Exception:
                raise ValueError(f"Failed to parse JSON: {exc}. Original text snippet: {text[:200]}...")

    def _from_payload(self, opportunity: Opportunity, payload: dict[str, Any]) -> GeneratedContent:
        markdown = payload.get("markdown", "")
        title = payload.get("title") or opportunity.title
        return GeneratedContent(
            title=title,
            slug=payload.get("slug") or slugify(title),
            markdown=markdown,
            html=markdown_to_html(markdown),
            meta_title=payload.get("meta_title") or title[:60],
            meta_description=excerpt(payload.get("meta_description") or markdown),
            focus_keyphrase=payload.get("focus_keyphrase") or opportunity.keyword,
            excerpt=excerpt(payload.get("excerpt") or markdown),
            tags=list(payload.get("tags") or [opportunity.keyword]),
            categories=list(payload.get("categories") or ["SEO"]),
            schema_json=dict(payload.get("schema_json") or {}),
            image_prompt=payload.get("image_prompt"),
            image_alt_text=payload.get("image_alt_text"),
            rich_blocks=list(payload.get("rich_blocks") or []),
        )

    async def adapt_for_blogger(self, title: str, html_body: str, original_url: str) -> dict[str, str]:
        """Adapt a WordPress post into a Blogger summary post with a link back to the source."""
        system_instruction = f"""You are a content syndication assistant for the AI brand {self.settings.site.brand_name}.
Your job is to adapt a long-form blog article into a lightweight, engaging, and professional summary post for Blogger.

Rules:
1. Summarize the key concepts, main insights, and actionable items of the original article in 400 to 600 words.
2. Maintain a helpful, educational, and professional tone.
3. Incorporate a clear call to action at the end directing readers to read the full guide.
4. Integrate a clickable HTML link back to the original article as the canonical source of truth using the provided URL.
5. Provide your response in JSON format with exactly two keys:
   - 'title': A modified, engaging title for the Blogger post.
   - 'content': The summary post formatted in clean HTML (no <html>, <head>, or <body> tags, only paragraph, heading, list tags, and the link back to {original_url}).

Original Article Title: {title}
Original URL: {original_url}

Return ONLY valid JSON.
"""
        if self.settings.writer_provider == "gemini":
            if not self.settings.gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY is required for Gemini content generation.")
            url = f"{GEMINI_API_BASE}/{self.settings.gemini_model}:generateContent"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": f"Adapt this article content now:\n\n{html_body[:12000]}\n\nReturn ONLY valid JSON."}]
                    }
                ],
                "systemInstruction": {
                    "parts": [{"text": system_instruction}]
                },
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING"},
                            "content": {"type": "STRING"}
                        },
                        "required": ["title", "content"]
                    },
                    "temperature": 0.3
                }
            }
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    url,
                    params={"key": self.settings.gemini_api_key},
                    headers={"content-type": "application/json"},
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return self._parse_json(text)
        else:
            if not self.settings.anthropic_api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is required for content generation.")
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.settings.anthropic_model,
                        "max_tokens": 4000,
                        "system": [
                            {
                                "type": "text",
                                "text": system_instruction
                            }
                        ],
                        "messages": [{"role": "user", "content": f"Adapt this article content now:\n\n{html_body[:12000]}\n\nReturn ONLY valid JSON. Your response must be parseable as raw JSON."}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            text = data["content"][0]["text"]
            return self._parse_json(text)

    async def generate_backlink_outreach(self, title: str, target_site: str, keyword: str) -> dict[str, str]:
        """Generate an outreach pitch for a target site and keyword using the LLM."""
        system_instruction = f"""You are a PR and outreach assistant for {self.settings.site.brand_name}.
We have just published a new article titled "{title}" targeting the keyword "{keyword}".
We want to reach out to the site "{target_site}" to pitch a mention, collaboration, or backlink.

Rules:
1. Write a compelling, highly personalized, and non-spammy outreach email pitch (approx 150-250 words) from the perspective of our brand's founder.
2. Recommend a realistic, professional editor contact name and email address as placeholders (e.g. contact name 'Editorial Team' or a realistic name, and contact email like 'editor@{target_site}' or 'info@{target_site}').
3. Return your response in JSON format with exactly three keys:
   - 'contact_name': The estimated contact name.
   - 'contact_email': The estimated contact email.
   - 'outreach_angle': The email pitch content (in plain text with appropriate line breaks).

Return ONLY valid JSON.
"""
        if self.settings.writer_provider == "gemini":
            if not self.settings.gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY is required for Gemini content generation.")
            url = f"{GEMINI_API_BASE}/{self.settings.gemini_model}:generateContent"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": f"Generate outreach pitch for {target_site} now. Return ONLY valid JSON."}]
                    }
                ],
                "systemInstruction": {
                    "parts": [{"text": system_instruction}]
                },
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": {
                        "type": "OBJECT",
                        "properties": {
                            "contact_name": {"type": "STRING"},
                            "contact_email": {"type": "STRING"},
                            "outreach_angle": {"type": "STRING"}
                        },
                        "required": ["contact_name", "contact_email", "outreach_angle"]
                    },
                    "temperature": 0.3
                }
            }
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    url,
                    params={"key": self.settings.gemini_api_key},
                    headers={"content-type": "application/json"},
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return self._parse_json(text)
        else:
            if not self.settings.anthropic_api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is required for content generation.")
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.settings.anthropic_model,
                        "max_tokens": 2000,
                        "system": [
                            {
                                "type": "text",
                                "text": system_instruction
                            }
                        ],
                        "messages": [{"role": "user", "content": f"Generate outreach pitch for {target_site} now. Return ONLY valid JSON."}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            text = data["content"][0]["text"]
            return self._parse_json(text)

    # _fallback_content removed — the system must never silently produce
    # fabricated placeholder articles. If Anthropic fails, the pipeline
    # raises RuntimeError so the operator can diagnose and fix the issue.
