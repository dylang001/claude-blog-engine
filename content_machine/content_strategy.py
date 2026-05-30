"""Content Strategy Integration - Connects content types, images, and SEO.

Integrates content type selection, rich media generation, and GEO/SEO best practices
into the pipeline flow.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Dict, Any

from .content_types import determine_content_type, get_content_type_prompt, get_rich_media_plan, ContentType
from .image_generator import ImageGenerator, generate_varied_prompts, determine_image_placement

logger = logging.getLogger("content_machine.strategy")


class ContentStrategyEngine:
    """Orchestrates content type selection and rich media strategy."""
    
    def __init__(self, settings):
        self.settings = settings
        self.image_gen = ImageGenerator()
    
    async def analyze_opportunity(
        self,
        opportunity,
        competitor_titles: Optional[list] = None,
    ) -> Dict[str, Any]:
        """Analyze opportunity and determine best content strategy.
        
        Args:
            opportunity: Keyword opportunity
            competitor_titles: Titles of top-ranking pages
            
        Returns:
            Strategy dict with content type, structure, and media plan
        """
        keyword = opportunity.keyword
        search_volume = getattr(opportunity, 'search_volume', None)
        
        # Determine best content type
        content_match = determine_content_type(
            keyword=keyword,
            search_volume=search_volume,
            competitor_titles=competitor_titles,
        )
        
        logger.info(f"Selected content type: {content_match.content_type.value} "
                   f"(confidence: {content_match.confidence:.2f})")
        
        # Get rich media plan
        media_plan = get_rich_media_plan(content_match.content_type, keyword)
        image_placements = determine_image_placement(
            content_match.content_type.value,
            content_match.word_count_range[1]
        )
        
        # Get writing instructions
        writing_prompt = get_content_type_prompt(content_match.content_type)
        
        return {
            "content_type": content_match.content_type,
            "content_type_name": content_match.content_type.value,
            "confidence": content_match.confidence,
            "reason": content_match.reason,
            "structure": content_match.recommended_structure,
            "word_count_range": content_match.word_count_range,
            "writing_instructions": writing_prompt,
            "media_plan": media_plan,
            "image_placements": image_placements,
            "needs_video": content_match.needs_video,
            "needs_infographic": content_match.needs_infographic,
        }
    
    async def generate_rich_media(
        self,
        keyword: str,
        content_type: ContentType,
        num_images: int = 5,
    ) -> Dict[str, Any]:
        """Generate rich media for the content.
        
        Args:
            keyword: Target keyword
            content_type: Type of content
            num_images: Number of images to generate
            
        Returns:
            Dict with generated media info
        """
        media = {
            "images": [],
            "generated_count": 0,
            "failed_count": 0,
        }
        
        try:
            async with self.image_gen:
                images = await self.image_gen.generate_blog_images(
                    keyword=keyword,
                    content_type=content_type.value,
                    num_images=num_images,
                )
                
                media["images"] = images
                media["generated_count"] = len(images)
                
                logger.info(f"Generated {len(images)} images for '{keyword}'")
                
        except Exception as e:
            logger.error(f"Rich media generation failed: {e}")
            media["error"] = str(e)
            media["failed_count"] = num_images
        
        return media
    
    def enrich_research_with_strategy(
        self,
        research: Dict[str, Any],
        strategy: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Add content strategy to research brief.
        
        Args:
            research: Original research dict
            strategy: Content strategy from analyze_opportunity
            
        Returns:
            Enriched research with strategy
        """
        research["content_strategy"] = {
            "type": strategy["content_type_name"],
            "confidence": strategy["confidence"],
            "structure_outline": strategy["structure"],
            "target_word_count": strategy["word_count_range"][1],
            "writing_instructions": strategy["writing_instructions"],
            "media_requirements": strategy["media_plan"],
        }
        
        # Add specific instructions for Claude
        research["claude_instructions"] = self._build_claude_prompt(strategy)
        
        return research
    
    def _build_claude_prompt(self, strategy: Dict[str, Any]) -> str:
        """Build comprehensive instructions for Claude.
        
        Args:
            strategy: Content strategy dict
            
        Returns:
            Detailed prompt for Claude
        """
        content_type = strategy["content_type_name"]
        structure = strategy["structure"]
        instructions = strategy["writing_instructions"]
        media = strategy["media_plan"]
        
        prompt = f"""CONTENT TYPE: {content_type.upper()}

{instructions}

STRUCTURE TO FOLLOW:
{chr(10).join(f"{i+1}. {section}" for i, section in enumerate(structure))}

RICH MEDIA REQUIREMENTS:
- Header image: {'Yes' if media.get('header_image') else 'No'}
- Inline images: {media.get('inline_images', 3)}
- Screenshots: {'Yes' if media.get('screenshots') else 'No'}
- Diagrams: {'Yes' if media.get('diagrams') else 'No'}
- Video suggestions: {'Yes' if media.get('videos') else 'No'}

SEO & GEO BEST PRACTICES:
- Use semantic HTML (proper h2, h3 hierarchy)
- Include LSI keywords naturally throughout
- Add FAQ section for People Also Ask optimization
- Use short paragraphs (2-3 sentences max)
- Include bullet points for scannability
- Bold key takeaways and important stats
- Add internal links where relevant
- Write compelling meta descriptions
- Optimize for featured snippets (tables, lists, definitions)
- Include expert quotes or citations for E-E-A-T
- Add "Key Takeaways" box after intro
- Use numbered lists for step-by-step content
- Create comparison tables for vs/alternative content
- Include "TL;DR" or summary section

WRITING STYLE:
- Engaging, conversational tone (not academic)
- Use "you" and "your" to address reader directly
- Include personal pronouns (I, we) for authenticity
- Add rhetorical questions to engage readers
- Use power words and emotional triggers appropriately
- Break up text with subheadings every 300 words
- Include real-world examples and scenarios
- End sections with transition sentences

IMPORTANT:
- Do NOT include [Image] placeholders - images will be added automatically
- Do NOT include video embed codes
- Focus on high-quality, comprehensive content
- Aim for the higher end of word count range
"""
        
        return prompt


# Convenience functions for pipeline integration

async def get_content_strategy(
    opportunity,
    settings,
    competitor_titles: Optional[list] = None,
) -> Dict[str, Any]:
    """Get content strategy for an opportunity.
    
    Args:
        opportunity: Keyword opportunity
        settings: Machine settings
        competitor_titles: Optional competitor titles
        
    Returns:
        Content strategy dict
    """
    engine = ContentStrategyEngine(settings)
    return await engine.analyze_opportunity(opportunity, competitor_titles)


async def generate_content_media(
    keyword: str,
    content_type: str,
    settings,
    num_images: int = 5,
) -> Dict[str, Any]:
    """Generate rich media for content.
    
    Args:
        keyword: Target keyword
        content_type: Content type value
        settings: Machine settings
        num_images: Number of images
        
    Returns:
        Media dict with images
    """
    engine = ContentStrategyEngine(settings)
    content_type_enum = ContentType(content_type)
    return await engine.generate_rich_media(keyword, content_type_enum, num_images)
