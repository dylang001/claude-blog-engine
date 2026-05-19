from __future__ import annotations

import base64

import httpx

from .config import Settings
from .models import GeneratedContent
from .utils import slugify


VALID_RATIOS = {"1:1", "16:9", "9:16", "4:3", "3:4", "2:3", "3:2", "4:5", "5:4", "1:4", "4:1", "1:8", "8:1", "21:9"}
VALID_RESOLUTIONS = {"512", "1K", "2K", "4K"}


class BananaImageGenerator:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def maybe_generate(self, content: GeneratedContent, run_id: str) -> GeneratedContent:
        if not self.settings.gemini_api_key or not content.image_prompt:
            return content

        out_dir = self.settings.data_dir / "images"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{run_id}-{slugify(content.title)}.png"
        aspect_ratio = self.settings.banana_aspect_ratio if self.settings.banana_aspect_ratio in VALID_RATIOS else "16:9"
        resolution = self.settings.banana_resolution if self.settings.banana_resolution in VALID_RESOLUTIONS else "2K"
        prompt = self._banana_prompt(content)

        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.banana_model}:generateContent",
                    params={"key": self.settings.gemini_api_key},
                    headers={
                        "Content-Type": "application/json",
                    },
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
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
            if not b64:
                return content
            out_path.write_bytes(base64.b64decode(b64))
            return GeneratedContent(
                title=content.title,
                slug=content.slug,
                markdown=content.markdown,
                html=content.html,
                meta_title=content.meta_title,
                meta_description=content.meta_description,
                focus_keyphrase=content.focus_keyphrase,
                excerpt=content.excerpt,
                tags=content.tags,
                categories=content.categories,
                schema_json=content.schema_json,
                image_prompt=content.image_prompt,
                featured_image_path=str(out_path),
                image_alt_text=content.image_alt_text,
                rich_blocks=content.rich_blocks,
            )
        except Exception:
            return content

    def _banana_prompt(self, content: GeneratedContent) -> str:
        return f"""Create a blog header image for the article "{content.title}".

Subject: an autonomous AI marketing command center represented by clean interface panels, content workflows, SEO graphs, and publishing signals.
Action: a friendly original Lyra AI operator character is actively coordinating keyword research, article drafting, optimization, and WordPress publishing as connected workflow nodes.
Location/Context: inside a bright modern SaaS workspace with a polished editorial dashboard on glass-like monitors, suitable for a founder-led marketing product.
Composition: wide 16:9 editorial hero image, clear focal point in the center-left, generous negative space on the right for possible overlay text, no visible brand logos.
House style: {self.settings.banana_style_prompt}
Visual language: realism blended with polished animated-feature character warmth, expressive but not childish, premium software editorial, crisp 3D interface elements, soft daylight, subtle violet and blue accents on a clean white and graphite palette.

Additional direction from the content brief: {content.image_prompt}

NEVER include readable text. Requirements: no readable text, no labels, no watermarks, no distorted hands, no fake UI words, no logos, no competitor marks, and no copied characters from existing films.
"""

    def _extract_image(self, data: dict) -> str | None:
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    return inline["data"]
        return None
