"""Enhanced Image Generation with Varied, Topic-Relevant Visuals.

Inspired by therundown.ai and SEO best practices for rich media.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Literal

import aiohttp
from PIL import Image
from io import BytesIO

logger = logging.getLogger("content_machine.images")


@dataclass
class ImageSpec:
    """Specification for an image to generate."""
    prompt: str
    style: Literal["realistic", "minimalist", "tech", "editorial", "abstract", "isometric"]
    aspect_ratio: str = "16:9"
    section: str = "header"  # header, section_1, section_2, etc.
    purpose: str = "hero"  # hero, diagram, illustration, screenshot-style


# Jasper-style abstract visual styles - NO laptops, NO offices, NO people at desks
ABSTRACT_STYLE_MODIFIERS = {
    "gradient_flow": "bold vector illustration, flowing gradient curves, vibrant purple-blue-orange palette, abstract liquid forms, modern SaaS aesthetic, NO text, NO realistic humans, conceptual representation",
    "geometric_nodes": "abstract geometric nodes, interconnected shapes, coral-blue-mint palette, network visualization, clean vector style, NO photography, NO office scenes",
    "abstract_layers": "layered abstract planes, overlapping gradient forms, deep blue-coral-teal palette, dimensional depth, artistic interpretation, NO realistic elements",
    "particle_field": "particle stream visualization, abstract dot patterns, violet-cyan-amber palette, scientific modern look, flowing energy, NO laptops, NO people",
    "wave_interference": "wave pattern interference, moiré effect lines, teal-purple-lime palette, rhythmic harmony, abstract frequencies, conceptual waves",
    "orbital_system": "orbital abstract visualization, radial gradient patterns, space blue-purple-orange palette, celestial concept, expansive visionary feel",
    "fractal_organic": "organic fractal branching, natural growth patterns, green-blue-orange palette, biomorphic abstraction, evolving forms",
    "light_refraction": "prismatic light effects, rainbow refractions, crystal spectrum colors, illuminating clarity, lens flare abstractions",
}

# Abstract conceptual themes by content type - NO generic office imagery
CONTENT_ABSTRACT_STRATEGIES = {
    "listicle": [
        "multiple interconnected elements in harmony",
        "abstract collection of possibilities",
        "diverse unified concepts flowing together",
        "interconnected idea network visualization",
    ],
    "how_to": [
        "step-by-step progression abstraction",
        "building knowledge conceptual layers",
        "transformation journey visualization",
        "learning path abstract flow",
    ],
    "ultimate_guide": [
        "comprehensive knowledge depth layers",
        "mastering complexity abstract system",
        "holistic understanding visualization",
        "complete conceptual ecosystem",
    ],
    "comparison": [
        "balancing options abstract visualization",
        "weighing choices conceptual balance",
        "contrasting paths diverging abstractly",
        "decision points in abstract space",
    ],
    "tutorial": [
        "skill acquisition abstract progression",
        "hands-on learning conceptual flow",
        "mastery building abstract layers",
        "practice visualization in abstract forms",
    ],
    "case_study": [
        "real-world application abstract visualization",
        "success story conceptual representation",
        "transformation abstract journey",
        "proven results in abstract form",
    ],
    "thought_leadership": [
        "innovative thinking abstract concept",
        "forward vision conceptual visualization",
        "strategic insight abstract representation",
        "industry evolution abstract flow",
    ],
    "review": [
        "feature comparison abstract visualization",
        "product concept abstract representation",
        "evaluation abstract balance",
        "assessment conceptual visualization",
    ],
    "beginner_guide": [
        "getting started abstract welcome",
        "simplicity abstract visualization",
        "first steps conceptual journey",
        "learning foundation abstract forms",
    ],
}

# Negative prompts to avoid generic stock photos
NEGATIVE_ELEMENTS = [
    "laptop", "computer", "person working", "office desk", "workspace",
    "business meeting", "hand typing", "person at computer", "corporate office",
    "stock photo", "realistic photography of people", "generic business image",
    "man in suit", "woman at desk", "team meeting", "office environment",
]

# Import abstract style functions
from .image_styles import generate_abstract_prompt, get_negative_prompt


def generate_varied_prompts(
    keyword: str,
    content_type: str,
    num_images: int = 5,
) -> List[ImageSpec]:
    """Generate diverse, abstract image prompts in Jasper style.
    
    Creates colorful, conceptual, non-literal imagery that represents
    ideas abstractly rather than showing generic laptop/office scenes.
    
    Args:
        keyword: Target keyword/topic
        content_type: Type of content (listicle, how_to, etc.)
        num_images: Number of images to generate
        
    Returns:
        List of ImageSpec with abstract visual prompts
    """
    specs = []
    
    # Get abstract strategies for this content type
    concepts = CONTENT_ABSTRACT_STRATEGIES.get(content_type, CONTENT_ABSTRACT_STRATEGIES["ultimate_guide"])
    styles = list(ABSTRACT_STYLE_MODIFIERS.keys())
    
    # Ensure variety
    selected_concepts = random.sample(concepts, min(len(concepts), num_images))
    selected_styles = random.sample(styles, min(len(styles), num_images))
    
    # Header/hero image (first image) - Jasper-style abstract
    concept = selected_concepts[0]
    style = selected_styles[0]
    
    hero_prompt = f"""Abstract conceptual illustration for '{keyword}': {concept}

Style: {ABSTRACT_STYLE_MODIFIERS[style]}

Requirements:
- Bold vector illustration aesthetic with vibrant gradients
- NO laptops, NO office scenes, NO people at desks
- NO realistic photography of people working
- Abstract conceptual representation only
- Modern SaaS blog header style
- High visual impact and contrast
- Clean composition suitable for hero image
- 16:9 wide format, 1200x675 pixels

Negative: {', '.join(NEGATIVE_ELEMENTS)}
"""
    
    specs.append(ImageSpec(
        prompt=hero_prompt,
        style=style,
        aspect_ratio="16:9",
        section="header",
        purpose="hero"
    ))
    
    # Section images - rotate through different abstract styles
    for i in range(1, num_images):
        concept = selected_concepts[i % len(selected_concepts)]
        style = selected_styles[i % len(selected_styles)]
        
        section_prompt = f"""Abstract illustration for section {i} about '{keyword}': {concept}

Style: {ABSTRACT_STYLE_MODIFIERS[style]}

Requirements:
- Conceptual abstract visualization
- NO realistic photography, NO office imagery
- NO people, NO laptops, NO corporate scenes
- Bold colors, vector-style illustration
- Represents the concept metaphorically
- Modern SaaS blog illustration style
- Clean and professional aesthetic
- 16:9 format, 800px wide

Negative: {', '.join(NEGATIVE_ELEMENTS)}
"""
        
        # Alternate aspect ratios for variety
        aspect = "16:9" if i % 2 == 0 else "4:3"
        
        specs.append(ImageSpec(
            prompt=section_prompt,
            style=style,
            aspect_ratio=aspect,
            section=f"section_{i}",
            purpose="illustration"
        ))
    
    return specs


def enhance_prompt_for_banana(prompt: str, aspect_ratio: str = "16:9") -> Dict:
    """Enhance prompt for Banana.dev/Gemini image generation.
    
    Args:
        prompt: Base prompt
        aspect_ratio: Target aspect ratio
        
    Returns:
        Enhanced prompt dict for API
    """
    # Add quality and style enhancements
    enhanced = f"""Create a professional blog header image for: {prompt}

Requirements:
- High quality, suitable for professional publication
- Clear focal point with good composition
- Modern, clean aesthetic
- Engaging and click-worthy
- Optimized for web use
- No text overlays (image only)
- Professional lighting and color grading
"""
    
    return {
        "prompt": enhanced,
        "aspect_ratio": aspect_ratio,
        "resolution": "2K",
        "negative_prompt": "text, watermark, logo, signature, blurry, low quality, distorted, amateur, cluttered, busy"
    }


class ImageGenerator:
    """Enhanced image generation with variety and relevance."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize image generator.
        
        Args:
            api_key: Banana.dev API key (or from BANANA_API_KEY env var)
        """
        self.api_key = api_key or os.environ.get("BANANA_API_KEY")
        self.base_url = "https://api.banana.dev/v1"
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def generate_image(
        self,
        spec: ImageSpec,
        model: str = "gemini-2.0-flash-exp",
    ) -> Optional[bytes]:
        """Generate a single image.
        
        Args:
            spec: Image specification
            model: Model to use
            
        Returns:
            Image bytes or None if failed
        """
        if not self.session:
            raise RuntimeError("Use async context manager (async with)")
        
        try:
            payload = enhance_prompt_for_banana(spec.prompt, spec.aspect_ratio)
            payload["model"] = model
            
            async with self.session.post(
                f"{self.base_url}/images",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Download image
                    image_url = data.get("image_url")
                    if image_url:
                        async with self.session.get(image_url) as img_resp:
                            if img_resp.status == 200:
                                return await img_resp.read()
                else:
                    logger.error(f"Image generation failed: {resp.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Image generation error: {e}")
            return None
        
        return None
    
    async def generate_blog_images(
        self,
        keyword: str,
        content_type: str,
        num_images: int = 5,
    ) -> List[Dict]:
        """Generate complete set of images for a blog post.
        
        Args:
            keyword: Target keyword
            content_type: Type of content
            num_images: Number of images to generate
            
        Returns:
            List of dicts with image data and metadata
        """
        specs = generate_varied_prompts(keyword, content_type, num_images)
        results = []
        
        logger.info(f"Generating {len(specs)} images for '{keyword}' ({content_type})")
        
        for i, spec in enumerate(specs):
            logger.info(f"Generating image {i+1}/{len(specs)}: {spec.section} ({spec.style})")
            
            image_data = await self.generate_image(spec)
            
            if image_data:
                results.append({
                    "section": spec.section,
                    "style": spec.style,
                    "aspect_ratio": spec.aspect_ratio,
                    "prompt": spec.prompt,
                    "purpose": spec.purpose,
                    "data": image_data,
                    "filename": f"{spec.section}_{spec.style}.png",
                })
            else:
                logger.warning(f"Failed to generate image {i+1}")
            
            # Small delay between requests
            if i < len(specs) - 1:
                await asyncio.sleep(2)
        
        return results
    
    def save_images(
        self,
        images: List[Dict],
        output_dir: Path,
    ) -> List[str]:
        """Save generated images to disk.
        
        Args:
            images: List of image dicts from generate_blog_images
            output_dir: Directory to save images
            
        Returns:
            List of saved file paths
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        saved_paths = []
        
        for img in images:
            filepath = output_dir / img["filename"]
            try:
                # Open and process image
                image = Image.open(BytesIO(img["data"]))
                
                # Optimize for web
                if image.mode in ('RGBA', 'LA', 'P'):
                    image = image.convert('RGB')
                
                # Save with optimization
                image.save(
                    filepath,
                    format='JPEG',
                    quality=85,
                    optimize=True,
                    progressive=True
                )
                
                saved_paths.append(str(filepath))
                logger.info(f"Saved image: {filepath}")
                
            except Exception as e:
                logger.error(f"Failed to save image {img['filename']}: {e}")
        
        return saved_paths


# Legacy support - keep old function signature
def generate_image_prompt(
    keyword: str,
    content_type: str = "blog_post",
    section: str = "header",
    style: str = "modern",
) -> str:
    """Legacy function - generate a single image prompt.
    
    Args:
        keyword: Target keyword
        content_type: Type of content
        section: Section of post
        style: Visual style
        
    Returns:
        Enhanced prompt string
    """
    spec = generate_varied_prompts(keyword, content_type, 1)[0]
    return spec.prompt


# New rich media insertion helper
def determine_image_placement(
    content_type: str,
    word_count: int,
) -> List[Dict]:
    """Determine optimal image placement throughout post.
    
    Args:
        content_type: Type of content
        word_count: Estimated word count
        
    Returns:
        List of placement instructions
    """
    placements = []
    
    # Header image always first
    placements.append({
        "position": "after_h1",
        "type": "hero",
        "description": "Main header/hero image"
    })
    
    # Calculate intervals based on content length
    if word_count < 1500:
        intervals = [0.5]  # Middle of post
    elif word_count < 3000:
        intervals = [0.33, 0.66]  # Thirds
    else:
        intervals = [0.25, 0.5, 0.75]  # Quarters
    
    # Add section images at intervals
    for i, interval in enumerate(intervals):
        placements.append({
            "position": f"section_{i+1}",
            "type": "inline",
            "description": f"Supporting image at {int(interval*100)}% of content",
            "insert_after_paragraph": int(interval * 10)  # Approximate
        })
    
    # Add special images based on content type
    if content_type == "listicle":
        placements.append({
            "position": "before_conclusion",
            "type": "comparison_chart",
            "description": "Comparison table as image"
        })
    elif content_type == "how_to":
        placements.insert(1, {
            "position": "after_intro",
            "type": "diagram",
            "description": "Process overview diagram"
        })
    elif content_type == "comparison":
        placements.insert(1, {
            "position": "after_intro",
            "type": "comparison_table",
            "description": "Visual comparison chart"
        })
    
    return placements
