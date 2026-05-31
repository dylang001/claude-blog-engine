"""Image Style Module - Jasper-style abstract conceptual imagery.

Provides stylized, abstract, colorful image prompts that avoid generic
office/laptop photography in favor of conceptual illustrations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any
import random


@dataclass
class ImageStyle:
    """Defines an abstract visual style for image generation."""
    name: str
    description: str
    color_palette: List[str]
    visual_elements: List[str]
    mood: str
    

# Jasper-inspired abstract visual styles
ABSTRACT_STYLES = {
    "gradient_flow": ImageStyle(
        name="Gradient Flow",
        description="Flowing abstract gradients representing concepts",
        color_palette=["deep purple", "electric blue", "vibrant orange", "soft pink"],
        visual_elements=["flowing curves", "gradient waves", "abstract streams", "liquid forms"],
        mood="dynamic and energetic",
    ),
    "geometric_nodes": ImageStyle(
        name="Geometric Nodes",
        description="Connected geometric shapes representing systems and networks",
        color_palette=["cobalt blue", "coral orange", "mint green", "lavender"],
        visual_elements=["interconnected nodes", "geometric shapes", "network patterns", "abstract connections"],
        mood="structured yet creative",
    ),
    "abstract_layers": ImageStyle(
        name="Abstract Layers",
        description="Layered abstract forms creating depth and dimension",
        color_palette=["midnight blue", "warm coral", "soft teal", "golden yellow"],
        visual_elements=["layered planes", "overlapping shapes", "depth gradients", "dimensional forms"],
        mood="deep and thoughtful",
    ),
    "particle_field": ImageStyle(
        name="Particle Field",
        description="Field of particles or dots creating patterns",
        color_palette=["deep violet", "bright cyan", "soft magenta", "warm amber"],
        visual_elements=["particle streams", "dot patterns", "flowing particles", "abstract constellation"],
        mood="scientific and modern",
    ),
    "wave_interference": ImageStyle(
        name="Wave Interference",
        description="Overlapping wave patterns creating moiré effects",
        color_palette=["electric teal", "soft purple", "bright lime", "warm peach"],
        visual_elements=["wave patterns", "interference lines", "ripple effects", "frequency waves"],
        mood="rhythmic and harmonious",
    ),
    "orbital_system": ImageStyle(
        name="Orbital System",
        description="Celestial or orbital abstract representations",
        color_palette=["deep space blue", "nebula purple", "starlight white", "cosmic orange"],
        visual_elements=["orbiting elements", "circular patterns", "radial gradients", "celestial bodies"],
        mood="expansive and visionary",
    ),
    "fractal_organic": ImageStyle(
        name="Fractal Organic",
        description="Organic fractal patterns inspired by nature",
        color_palette=["forest green", "ocean blue", "sunset orange", "earth brown"],
        visual_elements=["branching patterns", "organic fractals", "natural growth", "biomorphic shapes"],
        mood="natural and evolving",
    ),
    "light_refraction": ImageStyle(
        name="Light Refraction",
        description="Prismatic light effects and refractions",
        color_palette=["prismatic rainbow", "crystal blue", "lens flare gold", "spectrum colors"],
        visual_elements=["light rays", "prismatic effects", "lens flares", "light refractions"],
        mood="illuminating and clear",
    ),
}


# Content type to style mapping with conceptual themes
CONTENT_STYLE_THEMES = {
    "listicle": {
        "styles": ["gradient_flow", "geometric_nodes"],
        "concepts": [
            "multiple elements in harmony",
            "interconnected ideas",
            "collection of possibilities",
            "options flowing together",
            "diverse elements unified",
        ],
    },
    "how_to": {
        "styles": ["abstract_layers", "particle_field"],
        "concepts": [
            "step-by-step progression",
            "building knowledge",
            "process visualization",
            "transformation journey",
            "learning path",
        ],
    },
    "ultimate_guide": {
        "styles": ["orbital_system", "fractal_organic"],
        "concepts": [
            "comprehensive knowledge",
            "deep understanding",
            "mastering complexity",
            "complete system",
            "holistic view",
        ],
    },
    "comparison": {
        "styles": ["wave_interference", "light_refraction"],
        "concepts": [
            "balancing options",
            "weighing choices",
            "comparative analysis",
            "decision points",
            "contrasting paths",
        ],
    },
    "tutorial": {
        "styles": ["gradient_flow", "particle_field"],
        "concepts": [
            "skill acquisition",
            "practicing technique",
            "building expertise",
            "hands-on learning",
            "mastery progression",
        ],
    },
    "case_study": {
        "styles": ["geometric_nodes", "abstract_layers"],
        "concepts": [
            "real-world application",
            "success visualization",
            "results in action",
            "proven outcomes",
            "transformation story",
        ],
    },
    "thought_leadership": {
        "styles": ["orbital_system", "wave_interference"],
        "concepts": [
            "innovative thinking",
            "forward vision",
            "strategic insight",
            "industry perspective",
            "thought evolution",
        ],
    },
}


def get_style_for_content(content_type: str) -> ImageStyle:
    """Get appropriate abstract style for content type."""
    theme = CONTENT_STYLE_THEMES.get(content_type, CONTENT_STYLE_THEMES["listicle"])
    style_name = random.choice(theme["styles"])
    return ABSTRACT_STYLES[style_name]


def get_concept_for_content(content_type: str) -> str:
    """Get conceptual theme for content type."""
    theme = CONTENT_STYLE_THEMES.get(content_type, CONTENT_STYLE_THEMES["listicle"])
    return random.choice(theme["concepts"])


def generate_abstract_prompt(
    content_type: str,
    topic: str,
    width: int = 1200,
    height: int = 675,
) -> str:
    """Generate a Jasper-style abstract image prompt.
    
    Creates colorful, conceptual, non-literal imagery that represents
    ideas abstractly rather than showing literal office/laptop scenes.
    """
    style = get_style_for_content(content_type)
    concept = get_concept_for_content(content_type)
    
    # Select random elements
    colors = random.sample(style.color_palette, 3)
    elements = random.sample(style.visual_elements, 2)
    
    # Build the prompt - NO laptops, NO offices, NO people at desks
    prompt_parts = [
        f"Abstract conceptual illustration representing '{concept}' for '{topic}'",
        f"Style: {style.name} - {style.description}",
        f"Visual elements: {elements[0]} and {elements[1]}",
        f"Color palette: {colors[0]}, {colors[1]}, and {colors[2]} gradients",
        f"Mood: {style.mood}",
        "Composition: Clean, modern, suitable for blog header image",
        "Style qualities:",
        "- Bold vector illustration aesthetic",
        "- Smooth gradients and transitions",
        "- Abstract geometric or organic forms",
        "- NO realistic photography",
        "- NO laptops, computers, or office equipment",
        "- NO people working at desks",
        "- NO generic stock photo elements",
        "- Modern SaaS/tech blog illustration style",
        "- High contrast and visual impact",
        f"Resolution: {width}x{height} pixels",
        "Aspect ratio: 16:9 wide format",
    ]
    
    return "\n".join(prompt_parts)


def generate_featured_image_prompt(
    content_type: str,
    topic: str,
    keyword: str,
) -> str:
    """Generate featured image prompt with abstract style."""
    return generate_abstract_prompt(
        content_type=content_type,
        topic=topic,
        width=1200,
        height=675,
    )


def generate_inline_image_prompt(
    content_type: str,
    section_topic: str,
    section_number: int,
) -> str:
    """Generate inline image prompt with abstract style."""
    # Rotate through styles for variety
    style_names = list(ABSTRACT_STYLES.keys())
    style_name = style_names[section_number % len(style_names)]
    style = ABSTRACT_STYLES[style_name]
    
    colors = random.sample(style.color_palette, 3)
    elements = random.sample(style.visual_elements, 2)
    
    prompt_parts = [
        f"Abstract illustration for section {section_number}: '{section_topic}'",
        f"Style: {style.name}",
        f"Represents: Conceptual visualization of key idea",
        f"Visual elements: {elements[0]} and {elements[1]}",
        f"Colors: {colors[0]}, {colors[1]}, {colors[2]}",
        "Abstract, non-literal representation",
        "NO realistic photography",
        "NO office scenes or laptop computers",
        "Bold colors, modern vector style",
        "Width: 800px, suitable for inline blog image",
    ]
    
    return "\n".join(prompt_parts)


# Negative prompts to avoid generic imagery
NEGATIVE_PROMPTS = [
    "laptop",
    "computer",
    "person working",
    "office desk",
    "workspace",
    "business meeting",
    "hand typing",
    "person at computer",
    "corporate office",
    "stock photo",
    "generic business image",
    "realistic photography of people",
]


def get_negative_prompt() -> str:
    """Get negative prompt to avoid unwanted elements."""
    return "Do not include: " + ", ".join(NEGATIVE_PROMPTS)
