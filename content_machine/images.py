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

        # 2. Parse and Generate Inline Images
        markdown = content.markdown
        html = content.html
        inline_matches = list(re.finditer(r"!\[([^\]]*)\]\(placeholder:inline-image-(\d+)\)", markdown))
        
        for match in inline_matches:
            alt_text = match.group(1).strip()
            index = match.group(2)
            placeholder = f"placeholder:inline-image-{index}"
            
            # Extract context
            sect_title, sect_text = self._get_placeholder_context(markdown, placeholder)
            logger.info(f"Found inline image placeholder {index} in section '{sect_title}'")
            
            # Brainstorm concept brief
            inline_concept = await self._generate_concept(
                title=content.title,
                section_title=sect_title,
                section_text=sect_text,
                alt_text=alt_text
            )
            
            # Generate Image
            inline_path = out_dir / f"{run_id}-inline-{index}-{slugify(sect_title or 'section')}.png"
            logger.info(f"Generating inline image {index} with concept prompt: {inline_concept}")
            inline_banana_prompt = self._build_banana_prompt(content.title, inline_concept)
            inline_ok = await self._generate_image_file(inline_banana_prompt, inline_path, aspect_ratio, resolution)
            
            if inline_ok:
                # Replace placeholder in markdown with the local file path
                markdown = markdown.replace(f"({placeholder})", f"({inline_path})")
                html = html.replace(placeholder, str(inline_path))
                logger.info(f"Replaced placeholder {index} with local image path: {inline_path}")
            else:
                # Fallback: remove placeholder or replace with empty string
                markdown = markdown.replace(f"![{alt_text}]({placeholder})", "")
                markdown = markdown.replace(f"![\"{alt_text}\"]({placeholder})", "")
                html = re.sub(rf'<img\b[^>]*?\bsrc=["\']{re.escape(placeholder)}["\'][^>]*?>', '', html)

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
   - Camera & Lighting: Sony A7R IV, 85mm f/1.4 lens, natural golden hour lighting, shallow depth of field, premium magazine look.
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
