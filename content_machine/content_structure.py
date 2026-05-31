"""Content Structure Module - Enforces rich blog formatting standards.

Provides structure templates for blog posts including reading time,
CTA blocks, internal/external linking rules, and SEO/GEO best practices.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import re


@dataclass
class ContentStructure:
    """Defines required structure elements for a blog post."""
    reading_time: bool = True
    cta_blocks: int = 2
    internal_links_per_section: int = 2
    external_references_per_section: int = 1
    proof_points: int = 1
    table_or_list_requirement: bool = True
    h2_h3_hierarchy: bool = True


class StructureEnforcer:
    """Enforces content structure standards on generated content."""
    
    # Internal link anchor text patterns for SEO
    INTERNAL_LINK_PATTERNS = [
        "we've covered this in our guide to",
        "learn more about",
        "read our complete guide on",
        "see our article about",
        "explore our insights on",
        "find detailed strategies in our",
    ]
    
    # External authority domains for outbound links
    EXTERNAL_AUTHORITY_DOMAINS = [
        "google.com",
        "search.google.com",
        "developers.google.com",
        "schema.org",
        "w3.org",
        "moz.com",
        "ahrefs.com",
        "semrush.com",
    ]
    
    @staticmethod
    def calculate_reading_time(word_count: int) -> str:
        """Calculate reading time in minutes."""
        words_per_minute = 200
        minutes = max(1, round(word_count / words_per_minute))
        return f"{minutes} minute{'s' if minutes > 1 else ''}"
    
    @staticmethod
    def create_cta_block(quote: str, cta_text: str, url: str = "#") -> str:
        """Create a CTA block with quote and button."""
        return f"""
<div class="cta-block">
<blockquote>
"{quote}"
</blockquote>
<a href="{url}" class="cta-button">{cta_text}</a>
</div>
"""
    
    @staticmethod
    def create_proof_point(statement: str, source: str, url: str) -> str:
        """Create a proof point section."""
        return f"""
#### Proof Point

{statement}

Source: [{source}]({url})
"""
    
    @classmethod
    def get_internal_link_template(cls, topic: str) -> str:
        """Get internal link template for a topic."""
        import random
        pattern = random.choice(cls.INTERNAL_LINK_PATTERNS)
        return f"{pattern} {topic}."
    
    @classmethod
    def get_external_reference_template(cls, topic: str) -> str:
        """Get external reference suggestion."""
        return f"Review {topic} from official sources."


# Content type structure requirements
CONTENT_TYPE_STRUCTURES = {
    "listicle": ContentStructure(
        reading_time=True,
        cta_blocks=2,
        internal_links_per_section=1,
        external_references_per_section=1,
        proof_points=1,
        table_or_list_requirement=True,
        h2_h3_hierarchy=True,
    ),
    "how_to": ContentStructure(
        reading_time=True,
        cta_blocks=3,
        internal_links_per_section=2,
        external_references_per_section=1,
        proof_points=2,
        table_or_list_requirement=True,
        h2_h3_hierarchy=True,
    ),
    "ultimate_guide": ContentStructure(
        reading_time=True,
        cta_blocks=3,
        internal_links_per_section=3,
        external_references_per_section=2,
        proof_points=2,
        table_or_list_requirement=True,
        h2_h3_hierarchy=True,
    ),
    "comparison": ContentStructure(
        reading_time=True,
        cta_blocks=2,
        internal_links_per_section=2,
        external_references_per_section=1,
        proof_points=1,
        table_or_list_requirement=True,
        h2_h3_hierarchy=True,
    ),
    "tutorial": ContentStructure(
        reading_time=True,
        cta_blocks=2,
        internal_links_per_section=2,
        external_references_per_section=1,
        proof_points=1,
        table_or_list_requirement=True,
        h2_h3_hierarchy=True,
    ),
    "case_study": ContentStructure(
        reading_time=True,
        cta_blocks=2,
        internal_links_per_section=1,
        external_references_per_section=1,
        proof_points=3,
        table_or_list_requirement=True,
        h2_h3_hierarchy=True,
    ),
    "thought_leadership": ContentStructure(
        reading_time=True,
        cta_blocks=2,
        internal_links_per_section=2,
        external_references_per_section=2,
        proof_points=2,
        table_or_list_requirement=False,
        h2_h3_hierarchy=True,
    ),
}


def get_structure_for_content_type(content_type: str) -> ContentStructure:
    """Get structure requirements for a content type."""
    return CONTENT_TYPE_STRUCTURES.get(content_type, ContentStructure())


def generate_structure_prompt(content_type: str) -> str:
    """Generate a prompt section enforcing content structure."""
    structure = get_structure_for_content_type(content_type)
    
    prompt_parts = [
        "## REQUIRED CONTENT STRUCTURE",
        "",
        "Your response MUST follow this exact structure:",
        "",
        "1. **Reading Time**: Start with 'Reading time: X minutes' after the intro paragraph",
        "",
        "2. **Heading Hierarchy**: Use proper H2 > H3 > H4 structure",
        "   - Main sections: ## (H2)",
        "   - Sub-sections: ### (H3)",
        "   - Details: #### (H4)",
        "",
        f"3. **CTA Blocks**: Include exactly {structure.cta_blocks} CTA blocks throughout",
        "   Format: Quote block followed by button text",
        "   Example: > 'Quote text here' followed by [Button Text]",
        "",
        f"4. **Internal Links**: {structure.internal_links_per_section} per section",
        "   Use natural anchor text like 'we've covered this in our guide to X'",
        "   or 'learn more about X in our detailed article'",
        "",
        f"5. **External References**: {structure.external_references_per_section} per major section",
        "   Link to authoritative sources (Google documentation, industry standards)",
        "   Use format: 'According to [Source Name](URL)...'",
        "",
    ]
    
    if structure.proof_points > 0:
        prompt_parts.extend([
            f"6. **Proof Points**: Include {structure.proof_points} 'Proof Point' sections",
            "   Format as H4 heading with supporting evidence",
            "   Example: #### Proof Point\n\nSupporting statement with [source](url)",
            "",
        ])
    
    if structure.table_or_list_requirement:
        prompt_parts.extend([
            "7. **Visual Elements**: Include at least ONE of:",
            "   - Comparison table",
            "   - Timeline/process list",
            "   - Feature comparison",
            "   - Step-by-step breakdown",
            "",
        ])
    
    prompt_parts.extend([
        "8. **Intro Structure**:",
        "   - Hook paragraph (why this matters)",
        "   - Context paragraph (what they'll learn)",
        "   - Reading time",
        "",
        "9. **Conclusion Requirements**:",
        "   - Summary of key takeaways",
        "   - Clear next step or CTA",
        "   - No new information introduced",
        "",
        "## FORMATTING RULES",
        "",
        "- Use **bold** for emphasis on key terms",
        "- Use bullet lists for 3+ related items",
        "- Use numbered lists for sequential steps",
        "- Keep paragraphs under 4 sentences",
        "- Transition smoothly between sections",
        "",
    ])
    
    return "\n".join(prompt_parts)


def count_structure_elements(content: str) -> Dict[str, Any]:
    """Count structure elements in generated content for validation."""
    return {
        "has_reading_time": bool(re.search(r'reading time:\s*\d+', content, re.IGNORECASE)),
        "h2_count": len(re.findall(r'^## ', content, re.MULTILINE)),
        "h3_count": len(re.findall(r'^### ', content, re.MULTILINE)),
        "h4_count": len(re.findall(r'^#### ', content, re.MULTILINE)),
        "cta_blocks": len(re.findall(r'cta-block|cta-button|blockquote', content, re.IGNORECASE)),
        "internal_links": len(re.findall(r'\[.*?\]\(.*?\)', content)),
        "bullet_lists": len(re.findall(r'^\s*[-*] ', content, re.MULTILINE)),
        "numbered_lists": len(re.findall(r'^\s*\d+\. ', content, re.MULTILINE)),
        "proof_points": len(re.findall(r'####? proof point', content, re.IGNORECASE)),
    }
