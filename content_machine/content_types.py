"""Content Type Strategy for Blog Posts.

Determines the best blog post type based on keyword analysis and intent.
Supports: Listicles, How-To Guides, Ultimate Guides, Comparison Posts, 
Case Studies, Pillar Pages, News/Updates, Thought Leadership, Tutorials, Reviews.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict


class ContentType(str, Enum):
    """Supported blog post types."""
    LISTICLE = "listicle"  # Top 10, Best 15, etc.
    HOW_TO = "how_to"  # Step-by-step instructions
    ULTIMATE_GUIDE = "ultimate_guide"  # Comprehensive resource
    COMPARISON = "comparison"  # A vs B, alternative comparisons
    CASE_STUDY = "case_study"  # Real examples and results
    PILLAR_PAGE = "pillar_page"  # Broad topic coverage with cluster links
    NEWS_UPDATE = "news_update"  # Industry news, trends
    THOUGHT_LEADERSHIP = "thought_leadership"  # Opinions, predictions
    TUTORIAL = "tutorial"  # Hands-on learning with examples
    PRODUCT_REVIEW = "product_review"  # In-depth single product analysis
    ROUNDUP = "roundup"  # Expert opinions, tool collections
    FAQ = "faq"  # Question-answer format
    BEGINNER_GUIDE = "beginner_guide"  # Entry-level explanations


@dataclass
class ContentTypeMatch:
    """Result of content type matching."""
    content_type: ContentType
    confidence: float  # 0.0 to 1.0
    reason: str
    recommended_structure: List[str]
    word_count_range: tuple[int, int]
    image_count: int
    needs_video: bool
    needs_infographic: bool


# Keyword patterns for each content type
CONTENT_TYPE_PATTERNS = {
    ContentType.LISTICLE: {
        "patterns": [
            r"top\s+\d+", r"best\s+\d+", r"\d+\s+best", r"\d+\s+top",
            r"best\s+tools", r"best\s+software", r"best\s+apps",
            r"must-have", r"essential\s+tools", r"alternatives",
        ],
        "indicators": ["list", "tools", "software", "apps", "resources", "examples"],
        "structure": [
            "Introduction (problem + promise)",
            "Selection criteria explained",
            "Item #1 with pros/cons",
            "Item #2 with pros/cons",
            "Item #3-10 with key features",
            "Comparison table",
            "Buyer's guide / How to choose",
            "Final recommendations",
        ],
        "word_count": (2000, 4000),
        "images": 5,
    },
    ContentType.HOW_TO: {
        "patterns": [
            r"how\s+to", r"how\s+do", r"how\s+can", r"how\s+should",
            r"step\s+by\s+step", r"guide\s+to", r"tutorial",
            r"learn\s+to", r"ways\s+to", r"methods?\s+(to|for)",
        ],
        "indicators": ["steps", "process", "method", "technique", "setup"],
        "structure": [
            "Introduction (problem + outcome)",
            "Prerequisites / What you'll need",
            "Step 1: [Action] with screenshots",
            "Step 2: [Action] with screenshots",
            "Step 3-N: Continue with visuals",
            "Troubleshooting section",
            "Pro tips / Advanced techniques",
            "Conclusion with next steps",
        ],
        "word_count": (1500, 3500),
        "images": 6,
    },
    ContentType.ULTIMATE_GUIDE: {
        "patterns": [
            r"ultimate\s+guide", r"complete\s+guide", r"definitive\s+guide",
            r"everything\s+you\s+need\s+to\s+know",
            r"comprehensive", r"master\s+class", r"deep\s+dive",
        ],
        "indicators": ["guide", "complete", "comprehensive", "everything", "master"],
        "structure": [
            "Executive summary / TL;DR",
            "What is [Topic]? (definitions)",
            "Why it matters (benefits + stats)",
            "Core concepts explained",
            "Strategies and approaches",
            "Tools and resources",
            "Best practices",
            "Common mistakes to avoid",
            "Future trends / Predictions",
            "FAQ section",
            "Conclusion + takeaways",
        ],
        "word_count": (3000, 6000),
        "images": 8,
    },
    ContentType.COMPARISON: {
        "patterns": [
            r"vs\.?\s", r"versus", r"comparison", r"compare",
            r"differences?\s+between", r"which\s+is\s+better",
            r"alternatives?\s+to", r"[a-z]+\s+vs\s+[a-z]+",
        ],
        "indicators": ["vs", "comparison", "difference", "better", "alternatives"],
        "structure": [
            "Introduction (decision framework)",
            "Quick comparison table",
            "Option A: Deep dive",
            "Option B: Deep dive",
            "Head-to-head comparison",
            "Use cases (when to choose which)",
            "Pros and cons summary",
            "Verdict / Recommendation",
        ],
        "word_count": (2000, 3500),
        "images": 4,
    },
    ContentType.BEGINNER_GUIDE: {
        "patterns": [
            r"for\s+beginners", r"getting\s+started", r"101",
            r"introduction\s+to", r"basics\s+of", r"what\s+is",
            r"explain\s+like", r"simple\s+guide", r"easy\s+way",
        ],
        "indicators": ["beginner", "start", "basic", "simple", "introduction", "newbie"],
        "structure": [
            "Introduction (relatable hook)",
            "What is [Topic]? (simple definition)",
            "Why should you care?",
            "Key concepts (jargon-free)",
            "Getting started steps",
            "Common questions answered",
            "Resources for further learning",
            "Encouraging conclusion",
        ],
        "word_count": (1200, 2500),
        "images": 4,
    },
    ContentType.CASE_STUDY: {
        "patterns": [
            r"case\s+stud", r"success\s+stor", r"how\s+.+\s+achieved",
            r"how\s+we\s+", r"real\s+results", r"example\s+of",
        ],
        "indicators": ["case study", "results", "achieved", "success", "example"],
        "structure": [
            "Hook with impressive result",
            "Background / Challenge",
            "The solution (approach)",
            "Implementation details",
            "Results with data/proof",
            "Lessons learned",
            "How to apply to your situation",
        ],
        "word_count": (1500, 3000),
        "images": 3,
    },
    ContentType.PRODUCT_REVIEW: {
        "patterns": [
            r"review", r"tested", r"honest\s+review", r"worth\s+it",
            r"should\s+you\s+buy", r"detailed\s+review",
        ],
        "indicators": ["review", "test", "honest", "worth"],
        "structure": [
            "Overview with verdict",
            "What is [Product]?",
            "Key features breakdown",
            "Hands-on experience",
            "Pros and cons",
            "Pricing analysis",
            "Who is it for?",
            "Alternatives considered",
            "Final verdict",
        ],
        "word_count": (2000, 3500),
        "images": 6,
    },
    ContentType.TUTORIAL: {
        "patterns": [
            r"tutorial", r"walkthrough", r"hands.?on", r"practical",
            r"build\s+a", r"create\s+a", r"make\s+a",
        ],
        "indicators": ["tutorial", "walkthrough", "hands-on", "practical", "build"],
        "structure": [
            "Introduction (what you'll build)",
            "Prerequisites",
            "Setup and configuration",
            "Step-by-step implementation",
            "Code examples with explanations",
            "Testing and validation",
            "Deployment / Usage",
            "Troubleshooting",
            "Next steps / Extensions",
        ],
        "word_count": (2000, 4000),
        "images": 8,
    },
    ContentType.FAQ: {
        "patterns": [
            r"faq", r"frequently\s+asked", r"common\s+questions",
            r"questions?\s+about", r"quick\s+answers",
        ],
        "indicators": ["faq", "questions", "answers"],
        "structure": [
            "Introduction (why these questions matter)",
            "Q1 with detailed A",
            "Q2 with detailed A",
            "Q3-N with As",
            "Related questions",
            "Where to learn more",
        ],
        "word_count": (1000, 2000),
        "images": 2,
    },
    ContentType.NEWS_UPDATE: {
        "patterns": [
            r"news", r"update", r"latest", r"announcement",
            r"new\s+feature", r"just\s+released", r"breaking",
        ],
        "indicators": ["news", "latest", "update", "new", "announcement"],
        "structure": [
            "Headline with key news",
            "Summary / TL;DR",
            "Context (why it matters)",
            "Details of the update",
            "Impact analysis",
            "What to do next",
            "Sources and further reading",
        ],
        "word_count": (800, 1500),
        "images": 2,
    },
}


def determine_content_type(
    keyword: str,
    search_volume: Optional[int] = None,
    competitor_titles: Optional[List[str]] = None,
    serp_features: Optional[List[str]] = None,
) -> ContentTypeMatch:
    """Determine the best content type for a keyword.
    
    Args:
        keyword: Target keyword
        search_volume: Monthly search volume
        competitor_titles: Titles of top-ranking pages
        serp_features: SERP features present (videos, images, etc.)
        
    Returns:
        ContentTypeMatch with recommended structure and requirements
    """
    keyword_lower = keyword.lower()
    scores: Dict[ContentType, float] = {ct: 0.0 for ct in ContentType}
    reasons: Dict[ContentType, str] = {}
    
    # Pattern matching
    for content_type, config in CONTENT_TYPE_PATTERNS.items():
        score = 0.0
        matched_patterns = []
        
        # Check regex patterns
        for pattern in config["patterns"]:
            if re.search(pattern, keyword_lower, re.IGNORECASE):
                score += 0.3
                matched_patterns.append(pattern)
        
        # Check keyword indicators
        for indicator in config["indicators"]:
            if indicator in keyword_lower:
                score += 0.2
        
        # Check competitor titles for patterns
        if competitor_titles:
            title_matches = 0
            for title in competitor_titles:
                title_lower = title.lower()
                for pattern in config["patterns"][:3]:  # Top 3 patterns
                    clean_pattern = pattern.replace(r"\s+", " ").replace(r"\d+", "")
                    if clean_pattern in title_lower:
                        title_matches += 1
            if title_matches >= 2:
                score += 0.3
                reasons[content_type] = f"Competitors using {content_type.value} format"
        
        scores[content_type] = min(score, 1.0)
    
    # Determine winner
    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]
    
    # Default fallback
    if best_score < 0.3:
        if any(word in keyword_lower for word in ["what is", "guide", "learn"]):
            best_type = ContentType.BEGINNER_GUIDE
            best_score = 0.5
        else:
            best_type = ContentType.ULTIMATE_GUIDE
            best_score = 0.4
    
    config = CONTENT_TYPE_PATTERNS[best_type]
    
    # Adjust based on search volume
    word_count = config["word_count"]
    if search_volume and search_volume > 10000:
        word_count = (word_count[0] + 500, word_count[1] + 1000)
    
    # Determine rich media needs
    needs_video = best_type in [ContentType.TUTORIAL, ContentType.HOW_TO, ContentType.PRODUCT_REVIEW]
    needs_infographic = best_type in [ContentType.COMPARISON, ContentType.LISTICLE, ContentType.ULTIMATE_GUIDE]
    
    return ContentTypeMatch(
        content_type=best_type,
        confidence=best_score,
        reason=reasons.get(best_type, f"Keyword patterns match {best_type.value} format"),
        recommended_structure=config["structure"],
        word_count_range=word_count,
        image_count=config["images"],
        needs_video=needs_video,
        needs_infographic=needs_infographic,
    )


def get_content_type_prompt(content_type: ContentType) -> str:
    """Get specific writing instructions for a content type.
    
    Args:
        content_type: The type of content to create
        
    Returns:
        Detailed writing instructions for Claude
    """
    prompts = {
        ContentType.LISTICLE: """
Create a comprehensive listicle with these requirements:
- Start with a compelling hook that identifies the problem
- Include 8-15 items minimum (more is better for SEO)
- Each item needs: Name, brief description, key features, pros/cons
- Use comparison tables where helpful
- Include specific pricing/tier information when relevant
- End with a buyer's guide on how to choose
- Use h2 for intro, h3 for each item, h4 for subsections
        """,
        ContentType.HOW_TO: """
Create a step-by-step how-to guide with these requirements:
- Clear outcome statement in intro
- Prerequisites section upfront
- Numbered steps with clear action verbs
- Screenshots/visuals placeholders at each step
- Common mistakes section
- Pro tips for advanced users
- Troubleshooting section
        """,
        ContentType.ULTIMATE_GUIDE: """
Create a comprehensive ultimate guide with these requirements:
- Executive summary with key takeaways at top
- Cover what, why, and how
- Include definitions of key terms
- Actionable strategies with examples
- Tool recommendations with links
- Common pitfalls to avoid
- Future predictions/trends
- Extensive FAQ section
        """,
        ContentType.COMPARISON: """
Create a comparison post with these requirements:
- Decision framework in intro
- Quick comparison table at top
- Deep dive into each option
- Head-to-head feature comparison
- Use case scenarios for each
- Clear recommendation with reasoning
- Alternative options mentioned
        """,
        ContentType.BEGINNER_GUIDE: """
Create a beginner-friendly guide with these requirements:
- Assume zero prior knowledge
- Define all jargon/terms
- Use analogies and simple explanations
- Step-by-step getting started
- Resource links for learning more
- Encouraging, supportive tone
- Common beginner mistakes
        """,
        ContentType.TUTORIAL: """
Create a hands-on tutorial with these requirements:
- Clear statement of what user will build/create
- Complete prerequisites list
- Step-by-step with code/command examples
- Expected output at each step
- Testing/validation steps
- Troubleshooting common issues
- Extension ideas for advanced users
        """,
    }
    
    return prompts.get(content_type, "Create comprehensive, well-structured content with clear headings and actionable information.")


def get_rich_media_plan(content_type: ContentType, keyword: str) -> Dict:
    """Determine rich media needs for a content type.
    
    Args:
        content_type: Type of content
        keyword: Target keyword
        
    Returns:
        Dict with rich media requirements
    """
    base_plan = {
        "header_image": True,
        "inline_images": 3,
        "screenshots": False,
        "diagrams": False,
        "infographics": False,
        "videos": False,
        "gif_examples": False,
    }
    
    if content_type == ContentType.LISTICLE:
        base_plan.update({
            "inline_images": 5,
            "infographics": True,  # Comparison chart
        })
    elif content_type == ContentType.HOW_TO:
        base_plan.update({
            "inline_images": 6,
            "screenshots": True,
            "gif_examples": True,
        })
    elif content_type == ContentType.TUTORIAL:
        base_plan.update({
            "inline_images": 8,
            "screenshots": True,
            "code_snippets": True,
        })
    elif content_type == ContentType.COMPARISON:
        base_plan.update({
            "inline_images": 4,
            "diagrams": True,
            "infographics": True,  # Comparison table as image
        })
    elif content_type == ContentType.ULTIMATE_GUIDE:
        base_plan.update({
            "inline_images": 8,
            "diagrams": True,
            "infographics": True,
            "videos": True,
        })
    elif content_type == ContentType.PRODUCT_REVIEW:
        base_plan.update({
            "inline_images": 6,
            "screenshots": True,
            "videos": True,
        })
    
    return base_plan
