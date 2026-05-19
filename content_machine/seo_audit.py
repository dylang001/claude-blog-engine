from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .content_optimizer import TRANSITION_WORDS
from .config import Settings
from .human_quality import assess_human_quality
from .models import GeneratedContent, Opportunity
from .scoring import build_audit, composite_quality_score
from .yoast_guidelines import assess_yoast_copywriting


class SEOAuditEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.sources = [
            "claude-blog-engine/topics_pipeline.py",
            "TheCraigHewitt/seomachine:data_sources/modules/seo_quality_rater.py",
            "dylang001/claude-seo:skills/seo-audit,seo-content,seo-technical,seo-schema,seo-geo,seo-google",
        ]

    def audit(self, content: GeneratedContent, opportunity: Opportunity, research: dict[str, Any]) -> Any:
        plain = _plain_text(content.markdown)
        word_count = len(re.findall(r"\b\w+\b", plain))
        h1_count = len(re.findall(r"^#\s+", content.markdown, flags=re.MULTILINE)) + len(re.findall(r"<h1\b", content.markdown, flags=re.IGNORECASE))
        h2_count = len(re.findall(r"^##\s+", content.markdown, flags=re.MULTILINE)) + len(re.findall(r"<h2\b", content.markdown, flags=re.IGNORECASE))
        keyword_mentions = len(re.findall(re.escape(content.focus_keyphrase), plain, flags=re.IGNORECASE))
        markdown_link_pairs = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content.markdown)
        html_link_pairs = re.findall(r"<a\s+[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", content.markdown, flags=re.IGNORECASE | re.DOTALL)
        link_targets = [url for _, url in markdown_link_pairs] + [url for url, _ in html_link_pairs]
        links = len(link_targets)
        outbound_links = [url for url in link_targets if url.startswith("http") and "meetlyra.app" not in url]
        internal_links = [url for url in link_targets if url.startswith("/") or "meetlyra.app" in url]
        internal_link_domains = _internal_link_domains(internal_links)
        exact_internal_anchor_count = sum(
            1
            for anchor, url in markdown_link_pairs
            if (url.startswith("/") or "meetlyra.app" in url) and _plain_text(anchor).lower() == content.focus_keyphrase.lower()
        )
        exact_internal_anchor_count += sum(
            1
            for url, anchor in html_link_pairs
            if (url.startswith("/") or "meetlyra.app" in url) and _plain_text(anchor).lower() == content.focus_keyphrase.lower()
        )
        schema_score = 90 if content.schema_json.get("@type") else 55
        title_len = len(content.meta_title)
        desc_len = len(content.meta_description)
        first_paragraph = _first_paragraph(content.markdown)
        keyphrase_words = [word for word in re.findall(r"[A-Za-z0-9]+", content.focus_keyphrase)]
        keyphrase_in_subheading = bool(re.search(rf"^##+\s+.*{re.escape(content.focus_keyphrase)}", content.markdown, flags=re.IGNORECASE | re.MULTILINE))
        keyphrase_in_alt = content.image_alt_text and content.focus_keyphrase.lower() in content.image_alt_text.lower()
        rich_block_count = len(re.findall(r"seo-machine-", content.markdown))

        issues: list[str] = []
        warnings: list[str] = []

        content_score = 100.0
        if word_count < 1500:
            content_score -= 25
            issues.append("Content is below the 1,500 word minimum for autonomous publishing.")
        if h2_count < 4:
            content_score -= 15
            warnings.append("Article has fewer than 4 H2 sections.")
        if h1_count:
            content_score -= 25
            issues.append("Body content contains a duplicate H1; WordPress title must be the only H1.")
        if rich_block_count < 4:
            content_score -= 10
            warnings.append("Article is missing the required rich Gutenberg content blocks.")

        seo_score = 100.0
        if not 2 <= len(keyphrase_words) <= 4:
            seo_score -= 15
            issues.append("Focus keyphrase must be 2-4 content words.")
        if keyword_mentions < 5:
            seo_score -= 20
            issues.append("Focus keyphrase appears fewer than 5 times.")
        if content.focus_keyphrase.lower() not in first_paragraph.lower():
            seo_score -= 15
            issues.append("Focus keyphrase does not appear in the first paragraph.")
        if content.focus_keyphrase.lower() not in content.meta_title.lower() or not content.meta_title.lower().startswith(content.focus_keyphrase.lower()):
            seo_score -= 15
            issues.append("SEO title must start with the focus keyphrase.")
        if content.focus_keyphrase.lower() not in content.meta_description.lower():
            seo_score -= 15
            issues.append("Meta description must include the focus keyphrase.")
        if content.focus_keyphrase.lower().replace(" ", "-") not in content.slug.lower():
            seo_score -= 10
            warnings.append("Slug should include the focus keyphrase.")
        if not keyphrase_in_subheading:
            seo_score -= 15
            issues.append("Focus keyphrase must appear in at least one H2 or H3 subheading.")
        if not keyphrase_in_alt:
            seo_score -= 10
            issues.append("Image alt text must include the focus keyphrase.")
        if not 45 <= title_len <= 60:
            seo_score -= 15
            issues.append("Meta title length is outside the 45-60 character target.")
        if not 130 <= desc_len <= 155:
            seo_score -= 15
            issues.append("Meta description length is outside the 130-155 character target.")
        if len(outbound_links) < 1:
            seo_score -= 15
            issues.append("Article needs at least one outbound authority link.")
        if len(internal_links) < 2:
            seo_score -= 15
            issues.append("Article must include at least two internal MeetLyra links.")
        if exact_internal_anchor_count:
            seo_score -= 8
            warnings.append("Internal links should not use the exact focus keyphrase as anchor text.")

        technical_score = 85.0
        if opportunity.kind.value == "technical":
            technical_score = 90.0 if research.get("technical_checks") else 65.0

        geo_score = 85.0
        if "summary" not in content.markdown.lower() and "answer" not in content.markdown.lower():
            geo_score -= 5
            warnings.append("Consider adding a concise answer-style section for AI search extraction.")

        readability_score = 88.0
        avg_sentence_words = _avg_sentence_words(content.markdown)
        flesch = _flesch_reading_ease(plain)
        transition_ratio = _transition_ratio(plain)
        if avg_sentence_words > 20:
            readability_score -= 12
            issues.append("Average sentence length is above the 20-word target.")
        if flesch < 50:
            readability_score -= 12
            issues.append("Flesch reading ease is below the 50 target.")
        if transition_ratio < 0.30:
            readability_score -= 10
            issues.append("Transition word usage is below the 30% target.")

        human_report = assess_human_quality(content.markdown)
        human_score = human_report.score
        if human_report.score < 75:
            issues.extend(human_report.issues or ["Content needs a human-quality rewrite before publishing."])
        elif human_report.score < 85:
            warnings.extend(human_report.warnings or ["Content would benefit from more natural rhythm and specificity."])
        else:
            warnings.extend(human_report.warnings)

        yoast_report = assess_yoast_copywriting(content.markdown, content.focus_keyphrase, research)
        if yoast_report.score < 80:
            issues.extend(yoast_report.issues)
            warnings.extend(yoast_report.warnings)
        elif yoast_report.score < 90:
            warnings.extend(yoast_report.warnings)

        factuality_report = _assess_factuality(content.markdown)
        if factuality_report["issues"]:
            issues.extend(factuality_report["issues"])
            content_score -= 25

        composite = composite_quality_score(
            {
                "content": max(content_score, 0),
                "seo": max(seo_score, 0),
                "technical": technical_score,
                "schema": schema_score,
                "geo": geo_score,
                "readability": readability_score,
                "human_quality": human_score,
                "yoast_copywriting": yoast_report.score,
            }
        )
        if factuality_report["issues"]:
            composite = min(composite, self.settings.site.min_draft_score - 1)
        if issues and composite >= self.settings.site.min_publish_score:
            composite = self.settings.site.min_publish_score - 1

        return build_audit(
            score=composite,
            issues=issues,
            warnings=warnings,
            sources=self.sources,
            publish_threshold=self.settings.site.min_publish_score,
            draft_threshold=self.settings.site.min_draft_score,
            details={
                "word_count": word_count,
                "h2_count": h2_count,
                "h1_count": h1_count,
                "keyword_mentions": keyword_mentions,
                "link_count": links,
                "outbound_link_count": len(outbound_links),
                "internal_link_count": len(internal_links),
                "internal_link_domains": internal_link_domains,
                "exact_internal_anchor_count": exact_internal_anchor_count,
                "flesch_reading_ease": round(flesch, 1),
                "transition_ratio": round(transition_ratio, 2),
                "rich_block_count": rich_block_count,
                "human_quality_score": human_report.score,
                "human_quality": human_report.details,
                "yoast_copywriting_score": yoast_report.score,
                "yoast_copywriting": yoast_report.details,
                "factuality": factuality_report["details"],
                "repairable": True,
                "source_reference_dir": str(Path(self.settings.root_dir) / "vendor"),
            },
        )


def _avg_sentence_words(text: str) -> float:
    sentences = [s for s in re.split(r"[.!?]+", _plain_text(text)) if s.strip()]
    if not sentences:
        return 0.0
    return sum(len(s.split()) for s in sentences) / len(sentences)


def _plain_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = re.sub(r"[#*_>`\[\]\(\)]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _first_paragraph(markdown: str) -> str:
    for part in re.split(r"\n{2,}", markdown or ""):
        clean = part.strip()
        if clean and not clean.lstrip().startswith(("#", "<", "-", "|")):
            return _plain_text(clean)
    return ""


def _flesch_reading_ease(text: str) -> float:
    sentences = max(1, len([s for s in re.split(r"[.!?]+", text) if s.strip()]))
    words = re.findall(r"\b\w+\b", text)
    if not words:
        return 0.0
    syllables = sum(_syllable_count(word) for word in words)
    return 206.835 - 1.015 * (len(words) / sentences) - 84.6 * (syllables / len(words))


def _syllable_count(word: str) -> int:
    word = word.lower()
    groups = re.findall(r"[aeiouy]+", word)
    count = len(groups)
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def _transition_ratio(text: str) -> float:
    sentences = [s.lower() for s in re.split(r"[.!?]+", text) if s.strip()]
    if not sentences:
        return 0.0
    hits = sum(1 for sentence in sentences if any(word in sentence for word in TRANSITION_WORDS))
    return hits / len(sentences)


def _assess_factuality(markdown: str) -> dict[str, Any]:
    plain = _plain_text(markdown)
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", markdown or "") if part.strip()]
    generic_case_study_markers = [
        r"\bB2B SaaS Company\b",
        r"\bE-commerce Brand\b",
        r"\bProfessional Services Firm\b",
        r"\bReal-World Results\b",
        r"\bCase Stud(?:y|ies)\b",
        r"\ba consulting firm\b",
        r"\ba startup\b",
        r"\ban e-commerce brand\b",
        r"\ba B2B software company\b",
    ]
    metric_claim_pattern = re.compile(
        r"\b(?:increased|improved|grew|reduced|decreased|lifted|ranked|generated|saved|replaced|cut)\b"
        r"[^.!?]{0,120}?(?:\b\d+(?:\.\d+)?%|\b\d+\s+(?:keywords|articles|months|days|hours|leads|sessions)|\$\d)",
        flags=re.IGNORECASE,
    )
    generic_case_hits = sorted({match.group(0) for pattern in generic_case_study_markers for match in re.finditer(pattern, plain, flags=re.IGNORECASE)})
    unsupported_metric_claims = []
    for paragraph in paragraphs:
        clean = _plain_text(paragraph)
        if not metric_claim_pattern.search(clean):
            continue
        if _has_source_link(paragraph):
            continue
        unsupported_metric_claims.append(clean[:240])

    issues = []
    if generic_case_hits:
        issues.append("Content contains generic case-study examples that look invented or unsupported.")
    if unsupported_metric_claims:
        issues.append("Content contains unsupported quantified performance claims.")

    return {
        "issues": issues,
        "details": {
            "generic_case_study_markers": generic_case_hits[:12],
            "unsupported_metric_claim_count": len(unsupported_metric_claims),
            "unsupported_metric_claims": unsupported_metric_claims[:5],
        },
    }


def _has_source_link(markdown_fragment: str) -> bool:
    if re.search(r"\[[^\]]+\]\(https?://[^)]+\)", markdown_fragment):
        return True
    if re.search(r"<a\s+[^>]*href=[\"']https?://", markdown_fragment, flags=re.IGNORECASE):
        return True
    return False


def _internal_link_domains(urls: list[str]) -> dict[str, int]:
    domains = {"blog.meetlyra.app": 0, "meetlyra.app": 0, "relative": 0}
    for url in urls:
        if url.startswith("/"):
            domains["relative"] += 1
        elif "blog.meetlyra.app" in url:
            domains["blog.meetlyra.app"] += 1
        elif "meetlyra.app" in url:
            domains["meetlyra.app"] += 1
    return domains
