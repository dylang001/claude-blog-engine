from __future__ import annotations

from collections import Counter
from typing import Any


def schema_improvement_report(internal_links: list[dict[str, str]], claude_seo: dict[str, Any]) -> dict[str, Any]:
    """Recommend Yoast-compatible schema improvements as the site grows."""

    valid_links = [link for link in internal_links if link.get("url") and not link.get("error")]
    slugs = [link.get("slug", "") for link in valid_links]
    title_words = Counter()
    for link in valid_links:
        for word in link.get("title", "").lower().replace(":", " ").split():
            if len(word) > 4 and word not in {"content", "marketing", "agent"}:
                title_words[word] += 1

    recommendations = [
        "Keep Yoast's native schema graph enabled; extend it through Yoast filters rather than adding duplicate standalone JSON-LD when possible.",
        "Use Article schema for every generated post and reference Organization/WebSite graph pieces already emitted by Yoast.",
        "Use Breadcrumb schema on posts so the graph connects blog posts back to the blog and site root.",
        "Only use FAQ schema when the article contains a genuine FAQ block with visible questions and answers.",
    ]

    if len(valid_links) >= 5:
        recommendations.append("Build topic-cluster schema notes from internal-link groups once the blog has 5+ real posts.")
    else:
        recommendations.append("Publish more real posts before relying on cluster-level schema recommendations.")

    if any("faq" in slug for slug in slugs):
        recommendations.append("Audit FAQ pages for Yoast FAQ block compatibility before adding extra FAQ graph pieces.")

    if not claude_seo.get("schema_templates_available"):
        recommendations.append("Restore vendor/claude-seo/schema-templates.json so schema templates remain available.")

    return {
        "strategy": "yoast_schema_api",
        "yoast_hooks": [
            "wpseo_schema_graph_pieces",
            "wpseo_schema_graph",
            "wpseo_schema_article",
            "wpseo_schema_webpage",
            "wpseo_schema_block_<block-type>",
            "wpseo_pre-schema_block-type_<block-type>",
        ],
        "post_count": len(valid_links),
        "dominant_topic_terms": [word for word, _count in title_words.most_common(8)],
        "recommendations": recommendations,
    }
