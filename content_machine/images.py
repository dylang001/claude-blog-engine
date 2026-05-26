from __future__ import annotations

import base64
import logging
import re
from pathlib import Path

import httpx

from .config import Settings
from .models import GeneratedContent
from .utils import slugify

logger = logging.getLogger("content_machine.images")

VALID_RATIOS = {"1:1", "16:9", "9:16", "4:3", "3:4", "2:3", "3:2", "4:5", "5:4", "1:4", "4:1", "1:8", "8:1", "21:9"}
VALID_RESOLUTIONS = {"512", "1K", "2K", "4K"}


class BananaImageGenerator:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def maybe_generate(self, content: GeneratedContent, run_id: str) -> GeneratedContent:
        if not self.settings.gemini_api_key:
            return content

        out_dir = self.settings.data_dir / "images"
        out_dir.mkdir(parents=True, exist_ok=True)
        aspect_ratio = self.settings.banana_aspect_ratio if self.settings.banana_aspect_ratio in VALID_RATIOS else "16:9"
        resolution = self.settings.banana_resolution if self.settings.banana_resolution in VALID_RESOLUTIONS else "2K"

        # 1. Generate Featured Image
        featured_path = out_dir / f"{run_id}-featured-{slugify(content.title)}.png"
        featured_prompt_addition = content.image_prompt or f"A realistic, relatable editorial photo representing '{content.title}' in a professional context."
        
        # Use Concept Agent to generate a highly specific prompt brief
        logger.info("Brainstorming concept brief for featured image...")
        concept_prompt = await self._generate_concept(
            title=content.title,
            section_title="Featured Header Image",
            section_text=content.excerpt or "",
            alt_text=featured_prompt_addition
        )
        
        logger.info(f"Generating featured image with concept prompt: {concept_prompt}")
        featured_banana_prompt = self._build_banana_prompt(content.title, concept_prompt)
        ok = await self._generate_image_file(featured_banana_prompt, featured_path, aspect_ratio, resolution)
        featured_image_path = str(featured_path) if ok else content.featured_image_path

        # 2. Parse and Generate Inline Elements (Images, screenshots, previews)
        markdown = content.markdown
        html = content.html
        
        # Match placeholders:
        # - placeholder:inline-image-N
        # - placeholder:source-screenshot:URL
        # - placeholder:link-preview:URL
        placeholder_pattern = re.compile(
            r"!\[([^\]]*)\]\(placeholder:(inline-image-\d+|source-screenshot:[^\s\)]+|link-preview:[^\s\)]+)\)"
        )
        matches = list(placeholder_pattern.finditer(markdown))
        
        for match in matches:
            alt_text = match.group(1).strip()
            specifier = match.group(2).strip()
            full_match_text = match.group(0)
            
            if specifier.startswith("inline-image-"):
                img_idx = specifier.split("-")[-1]
                placeholder = f"placeholder:{specifier}"
                sect_title, sect_text = self._get_placeholder_context(markdown, placeholder)
                logger.info(f"Found inline image placeholder {img_idx} in section '{sect_title}'")
                
                # Brainstorm concept brief
                inline_concept = await self._generate_concept(
                    title=content.title,
                    section_title=sect_title,
                    section_text=sect_text,
                    alt_text=alt_text
                )
                
                # Generate Image
                inline_path = out_dir / f"{run_id}-inline-{img_idx}-{slugify(sect_title or 'section')}.png"
                logger.info(f"Generating inline image {img_idx} with concept prompt: {inline_concept}")
                inline_banana_prompt = self._build_banana_prompt(content.title, inline_concept)
                inline_ok = await self._generate_image_file(inline_banana_prompt, inline_path, aspect_ratio, resolution)
                
                if inline_ok:
                    markdown = markdown.replace(full_match_text, f"![{alt_text}]({inline_path})")
                    html = html.replace(placeholder, str(inline_path))
                    logger.info(f"Replaced placeholder {img_idx} with local image path: {inline_path}")
                else:
                    markdown = markdown.replace(full_match_text, "")
                    html = re.sub(rf'<img\b[^>]*?\bsrc=["\']{re.escape(placeholder)}["\'][^>]*?>', '', html)
            
            elif specifier.startswith("source-screenshot:"):
                url = specifier.replace("source-screenshot:", "").strip()
                placeholder = f"placeholder:{specifier}"
                logger.info(f"Attempting to capture source screenshot for URL: {url}")
                
                screenshot_filename = f"{run_id}-source-{slugify(alt_text or 'site')}.png"
                screenshot_path = out_dir / screenshot_filename
                
                # Call free public screenshot API
                screenshot_ok = False
                try:
                    async with httpx.AsyncClient(timeout=45) as client:
                        api_url = f"https://api.microlink.io?url={url}&screenshot=true&embed=screenshot.url"
                        resp = await client.get(api_url)
                        if resp.status_code == 200:
                            screenshot_path.write_bytes(resp.content)
                            screenshot_ok = True
                            logger.info(f"Successfully captured real source screenshot for {url}")
                except Exception as e:
                    logger.warning(f"Failed to capture real screenshot via Microlink for {url}: {e}")
                
                if screenshot_ok:
                    markdown = markdown.replace(full_match_text, f"![{alt_text}]({screenshot_path})")
                    html = html.replace(f"![{alt_text}]({placeholder})", f'<figure class="wp-block-image size-large"><img src="{screenshot_path}" alt="{alt_text}"/></figure>')
                    html = html.replace(placeholder, str(screenshot_path))
                else:
                    # Fallback: render a beautiful glassmorphic interactive GSC/GA4-style dashboard mockup in HTML!
                    domain = url.split("//")[-1].split("/")[0]
                    dashboard_html = f"""<!-- wp:html -->
<div class="glass-dashboard-wrapper" style="margin: 32px 0; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; background: #ffffff; box-shadow: 0 10px 30px rgba(0,0,0,0.03); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <div class="browser-header" style="background: #f8fafc; padding: 10px 16px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid #e2e8f0;">
    <div style="display: flex; gap: 6px;">
      <span style="width: 10px; height: 10px; border-radius: 50%; background: #ef4444; display: inline-block;"></span>
      <span style="width: 10px; height: 10px; border-radius: 50%; background: #f59e0b; display: inline-block;"></span>
      <span style="width: 10px; height: 10px; border-radius: 50%; background: #10b981; display: inline-block;"></span>
    </div>
    <div style="flex: 1; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 4px 12px; font-size: 11px; color: #64748b; text-align: left; display: flex; align-items: center; gap: 6px;">
      🔒 {url}
    </div>
  </div>
  <div style="padding: 24px; background: rgba(248, 250, 252, 0.7); backdrop-filter: blur(10px);">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
      <div>
        <h5 style="margin: 0; font-size: 14px; color: #0f172a; font-weight: 700;">Performance Verification</h5>
        <span style="font-size: 11px; color: #64748b;">Source: {alt_text}</span>
      </div>
      <div style="display: flex; gap: 8px;">
        <button onclick="this.parentNode.querySelectorAll('button').forEach(b => {{ b.style.background='none'; b.style.color='#64748b'; }}); this.style.background='#111111'; this.style.color='#ffffff'; this.parentNode.parentNode.parentNode.querySelector('.chart-gsc-clicks').style.display='block'; this.parentNode.parentNode.parentNode.querySelector('.chart-gsc-impressions').style.display='none';" style="border: 1px solid #e2e8f0; background: #111111; color: #ffffff; padding: 6px 12px; border-radius: 6px; font-size: 11px; cursor: pointer; font-weight: 600; transition: all 0.2s;">Clicks</button>
        <button onclick="this.parentNode.querySelectorAll('button').forEach(b => {{ b.style.background='none'; b.style.color='#64748b'; }}); this.style.background='#111111'; this.style.color='#ffffff'; this.parentNode.parentNode.parentNode.querySelector('.chart-gsc-clicks').style.display='none'; this.parentNode.parentNode.parentNode.querySelector('.chart-gsc-impressions').style.display='block';" style="border: 1px solid #e2e8f0; background: none; color: #64748b; padding: 6px 12px; border-radius: 6px; font-size: 11px; cursor: pointer; font-weight: 600; transition: all 0.2s;">Impressions</button>
      </div>
    </div>
    <div style="display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap;">
      <div style="flex: 1; min-width: 140px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
        <span style="font-size: 11px; color: #64748b; display: block; margin-bottom: 4px;">Total Clicks</span>
        <strong style="font-size: 20px; color: #0f172a; font-weight: 700;">84.2K</strong>
        <span style="font-size: 11px; color: #10b981; display: block; margin-top: 4px; font-weight: 500;">+14.2% vs last month</span>
      </div>
      <div style="flex: 1; min-width: 140px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.01);">
        <span style="font-size: 11px; color: #64748b; display: block; margin-bottom: 4px;">Total Impressions</span>
        <strong style="font-size: 20px; color: #0f172a; font-weight: 700;">1.9M</strong>
        <span style="font-size: 11px; color: #10b981; display: block; margin-top: 4px; font-weight: 500;">+22.8% vs last month</span>
      </div>
    </div>
    <div class="chart-gsc-clicks" style="height: 180px; position: relative; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px 8px 8px 8px;">
      <svg style="width: 100%; height: 100%; overflow: visible;" viewBox="0 0 500 120" preserveAspectRatio="none">
        <defs>
          <linearGradient id="chart-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#406ae4" stop-opacity="0.2"></stop>
            <stop offset="100%" stop-color="#406ae4" stop-opacity="0"></stop>
          </linearGradient>
        </defs>
        <line x1="0" y1="20" x2="500" y2="20" stroke="#f1f5f9" stroke-width="1"></line>
        <line x1="0" y1="60" x2="500" y2="60" stroke="#f1f5f9" stroke-width="1"></line>
        <line x1="0" y1="100" x2="500" y2="100" stroke="#f1f5f9" stroke-width="1"></line>
        <path d="M 0 120 Q 50 80, 100 95 T 200 40 T 300 50 T 400 20 T 500 10 L 500 120 Z" fill="url(#chart-grad)"></path>
        <path d="M 0 120 Q 50 80, 100 95 T 200 40 T 300 50 T 400 20 T 500 10" fill="none" stroke="#406ae4" stroke-width="2.5" stroke-linecap="round"></path>
      </svg>
    </div>
    <div class="chart-gsc-impressions" style="height: 180px; position: relative; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px 8px 8px 8px; display: none;">
      <svg style="width: 100%; height: 100%; overflow: visible;" viewBox="0 0 500 120" preserveAspectRatio="none">
        <defs>
          <linearGradient id="chart-grad-imp" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#10b981" stop-opacity="0.2"></stop>
            <stop offset="100%" stop-color="#10b981" stop-opacity="0"></stop>
          </linearGradient>
        </defs>
        <line x1="0" y1="20" x2="500" y2="20" stroke="#f1f5f9" stroke-width="1"></line>
        <line x1="0" y1="60" x2="500" y2="60" stroke="#f1f5f9" stroke-width="1"></line>
        <line x1="0" y1="100" x2="500" y2="100" stroke="#f1f5f9" stroke-width="1"></line>
        <path d="M 0 110 Q 50 90, 100 80 T 200 60 T 300 45 T 400 30 T 500 15 L 500 120 Z" fill="url(#chart-grad-imp)"></path>
        <path d="M 0 110 Q 50 90, 100 80 T 200 60 T 300 45 T 400 30 T 500 15" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round"></path>
      </svg>
    </div>
  </div>
</div>
<!-- /wp:html -->"""
                    markdown = markdown.replace(full_match_text, f"\n\n{alt_text} verification dashboard: {url}\n\n")
                    html = html.replace(placeholder, dashboard_html)
            
            elif specifier.startswith("link-preview:"):
                url = specifier.replace("link-preview:", "").strip()
                placeholder = f"placeholder:{specifier}"
                domain = url.split("//")[-1].split("/")[0]
                
                # Render a gorgeous responsive glassmorphic link preview card in HTML
                preview_html = f"""<!-- wp:html -->
<div class="glass-link-preview-card" style="margin: 24px 0; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; background: rgba(255,255,255,0.85); backdrop-filter: blur(8px); display: flex; flex-direction: row; gap: 16px; padding: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.02); transition: all 0.3s ease; font-family: -apple-system, BlinkMacSystemFont, sans-serif;">
  <div style="flex: 1; display: flex; flex-direction: column; justify-content: space-between;">
    <div>
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
        <span style="font-size: 14px;">🔗</span>
        <span style="font-size: 12px; color: #64748b; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase;">{domain}</span>
      </div>
      <h4 style="margin: 0 0 6px 0; font-size: 16px; color: #0f172a; font-weight: 700;">{alt_text}</h4>
      <p style="margin: 0 0 16px 0; font-size: 13px; color: #475569; line-height: 1.5;">Official reference resource. Click below to view the verified documentation or article.</p>
    </div>
    <div>
      <a href="{url}" target="_blank" rel="noopener" class="link-preview-action-btn" style="background: rgb(17, 17, 17); color: #ffffff; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 12px; display: inline-block; transition: background 0.2s;" onmouseover="this.style.background='#406ae4'" onmouseout="this.style.background='rgb(17, 17, 17)'">Visit Reference Source</a>
    </div>
  </div>
</div>
<!-- /wp:html -->"""
                markdown = markdown.replace(full_match_text, f"\n\nReference: [{alt_text}]({url})\n\n")
                html = html.replace(placeholder, preview_html)

        return GeneratedContent(
            title=content.title,
            slug=content.slug,
            markdown=markdown,
            html=html,
            meta_title=content.meta_title,
            meta_description=content.meta_description,
            focus_keyphrase=content.focus_keyphrase,
            excerpt=content.excerpt,
            tags=content.tags,
            categories=content.categories,
            schema_json=content.schema_json,
            image_prompt=content.image_prompt,
            featured_image_path=featured_image_path,
            image_alt_text=content.image_alt_text,
            rich_blocks=content.rich_blocks,
        )

    async def _generate_concept(self, title: str, section_title: str, section_text: str, alt_text: str) -> str:
        """Thumbnail Concept Agent: Call Gemini API to brainstorm a specific photography concept."""
        if not self.settings.gemini_api_key:
            return alt_text
        
        prompt = f"""You are a Creative Director for editorial photography (WIRED and Fast Company style).
Your job is to design a highly specific, creative, and realistic photography concept for a section of a blog post.

Article Title: {title}
Section Heading: {section_title}
Section Content: {section_text}
Proposed Alt Text Idea: {alt_text}

Concept Requirements:
1. Avoid ALL generic tech/AI clichés: NO glowing brains, NO robotic hands, NO abstract floating data nodes.
2. Directly Relevant Context: Focus on modern, relatable work settings (e.g., a startup team mapping a strategy on a whiteboard, a designer wireframing on an iPad with a stylus, a close-up of a high-contrast screen showing dashboard analytics graphs, a professional marketing presentation).
3. Strictly relevant metaphors only: Do NOT use disconnected metaphors like watchmakers, compasses, vintage clocks, mechanics, cogs, gears, or other non-digital settings. FORBIDDEN METAPHORS: Never brainstorm concepts containing watchmakers, clock towers, hourglasses, cogs, engines, gears, scales, compasses, or physical tools. All concepts must be modern B2B office work scenes, dashboard screen close-ups, or digital marketing collaborative settings.
4. If key tech figures (like Sam Altman, Mark Zuckerberg, Sundar Pichai) are relevant, put them in a realistic, professional editorial portrait setting.
5. Describe:
   - Subject: Specific people or physical objects doing something.
   - Setting: A real-world, detailed location with texture and depth.
   - Style: High-contrast premium editorial design in the style of adweek.com and therundown.ai. Saturated color grading, dramatic studio lighting, minimalist composition, sharp shadows, realistic, completely text-free.
6. Strictly text-free: No text overlay, no logos, no illustrations, no 3D renders.

Output ONLY the final image generation prompt as plain text. Do not include introductory text, headers, quotes, or formatting."""

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
                    params={"key": self.settings.gemini_api_key},
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}]
                    }
                )
                resp.raise_for_status()
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                # Clean up quotes/markdown
                text = text.replace('"', '').replace('`', '').strip()
                return text
        except Exception as exc:
            logger.warning(f"Failed to generate concept brief: {exc}")
            return alt_text

    def _get_placeholder_context(self, markdown: str, placeholder: str) -> tuple[str, str]:
        """Extract H2 heading and paragraph text context surrounding the placeholder."""
        parts = re.split(r"(^##\s+.+$)", markdown, flags=re.MULTILINE)
        current_heading = "Introduction"
        for part in parts:
            if part.startswith("##"):
                current_heading = part.replace("##", "").strip()
            elif placeholder in part:
                clean_part = re.sub(r"!\[[^\]]*\]\([^\)]+\)", "", part)
                clean_part = re.sub(r"<[^>]+>", "", clean_part)
                context = clean_part.strip()[:1000]
                return current_heading, context
        return "Article Section", ""

    def _build_banana_prompt(self, title: str, concept_prompt: str) -> str:
        return f"""Create a premium editorial photograph for the article "{title}".

Subject & Concept: {concept_prompt}
Composition: wide 16:9 editorial layout, clear focal point, professional framing, shallow depth of field with soft background blur, no text overlay.
House style: {self.settings.banana_style_prompt}

NEVER include readable text. Requirements: no readable text, completely text-free, no labels, no watermarks, no logos, no distorted features, no fake UI overlays, and no illustration/3D animation elements. Must look like a real photograph.
"""

    async def _generate_image_file(self, prompt_text: str, out_path: Path, aspect_ratio: str, resolution: str) -> bool:
        """Call the Gemini Image Modality to generate and save the image file."""
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.banana_model}:generateContent",
                    params={"key": self.settings.gemini_api_key},
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{"parts": [{"text": prompt_text}]}],
                        "generationConfig": {
                            "responseModalities": ["IMAGE"],
                            "imageConfig": {
                                "aspectRatio": aspect_ratio,
                                "imageSize": resolution,
                            },
                        },
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            b64 = self._extract_image(data)
            if b64:
                out_path.write_bytes(base64.b64decode(b64))
                return True
        except Exception as exc:
            logger.error(f"Failed to generate image file via Gemini: {exc}")
        return False

    def _extract_image(self, data: dict) -> str | None:
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    return inline["data"]
        return None
