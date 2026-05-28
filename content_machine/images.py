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
        if not self.settings.gemini_api_key or not content.image_prompt or content.featured_image_path:
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
        subject_theme = content.focus_keyphrase or content.title
        return f"""Create a premium, realistic header image for a technology blog post titled "{content.title}".

Subject: A modern workspace or desk setup showing realistic elements related to: {subject_theme}.
Composition: Wide 16:9 editorial header image, crisp focus on a MacBook or modern display showing clean SaaS dashboards, graphs, or code. Elegant workspace details (e.g. coffee mug, notebook, plants), premium studio lighting with soft shadows.
House style: {self.settings.banana_style_prompt}
Visual language: Real photography look, millennial pop-culture tech aesthetic, warm natural lighting, high-end professional editorial design. Subtle violet, blue, or graphite accents. No cartoonish/childish characters, and no fake or distorted elements.

Additional direction from the content brief: {content.image_prompt}

NEVER include readable text. Requirements: no readable text, no labels, no watermarks, no distorted hands, no logos, and no competitor marks.
"""

    def _extract_image(self, data: dict) -> str | None:
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    return inline["data"]
        return None
