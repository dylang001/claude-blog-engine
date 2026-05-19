from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class YoastExpertReport:
    score: float
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, float | int | bool | list[str]] = field(default_factory=dict)


def assess_yoast_copywriting(markdown: str, focus_keyphrase: str, research: dict | None = None) -> YoastExpertReport:
    """Apply Yoast-inspired copywriting and WordPress SEO checks.

    This deliberately keeps the checks deterministic: the LLM can write, but
    the engine enforces planning, structure, readability, internal linking, and
    schema-oriented content signals before publish.
    """

    plain = _plain_text(markdown)
    first_paragraph = _first_paragraph(markdown)
    headings = _headings(markdown)
    paragraphs = _paragraphs(markdown)
    sentences = _sentences(plain)
    score = 100.0
    issues: list[str] = []
    warnings: list[str] = []

    first_100_words = " ".join(re.findall(r"\b\w+\b", first_paragraph)[:100]).lower()
    if focus_keyphrase.lower() not in first_100_words:
        score -= 12
        issues.append("Yoast copywriting: focus keyphrase must appear in the first 100 words.")

    if first_paragraph and not _looks_like_direct_answer(first_paragraph, focus_keyphrase):
        score -= 8
        warnings.append("Yoast copywriting: open with an inverted-pyramid answer before expanding.")

    if len(headings) < 5:
        score -= 8
        warnings.append("Yoast copywriting: article needs a clearer heading structure.")

    long_headings = [heading for heading in headings if len(heading) > 80]
    if long_headings:
        score -= 6
        warnings.append("Yoast copywriting: shorten long headings so readers can scan the structure.")

    generic_headings = [
        heading
        for heading in headings
        if heading.lower().strip(": ") in {"introduction", "conclusion", "next steps", "summary", "overview"}
    ]
    if generic_headings:
        score -= 5
        warnings.append("Yoast copywriting: replace generic headings with descriptive topic headings.")

    long_paragraphs = [len(re.findall(r"\b\w+\b", paragraph)) for paragraph in paragraphs if len(re.findall(r"\b\w+\b", paragraph)) > 130]
    if long_paragraphs:
        score -= 10
        issues.append("Yoast readability: paragraphs over 130 words are too hard to scan.")

    topic_sentence_ratio = _topic_sentence_ratio(paragraphs)
    if topic_sentence_ratio < 0.65 and len(paragraphs) >= 5:
        score -= 8
        warnings.append("Yoast readability: more paragraphs should start with a clear topic sentence.")

    if _question_answer_coverage(markdown) < 1:
        score -= 8
        warnings.append("Yoast SEO: add at least one concise answer-style FAQ or Q&A section for search intent.")

    if research:
        requirements = " ".join(research.get("requirements", []))
        if "search intent" not in requirements.lower():
            score -= 4
            warnings.append("Yoast planning: research brief should explicitly include search-intent matching.")

    return YoastExpertReport(
        score=max(0.0, round(score, 1)),
        issues=issues,
        warnings=warnings,
        details={
            "heading_count": len(headings),
            "long_heading_count": len(long_headings),
            "generic_headings": generic_headings,
            "long_paragraph_count": len(long_paragraphs),
            "topic_sentence_ratio": round(topic_sentence_ratio, 2),
            "answer_sections": _question_answer_coverage(markdown),
            "first_paragraph_has_direct_answer": _looks_like_direct_answer(first_paragraph, focus_keyphrase),
        },
    )


def yoast_research_requirements() -> list[str]:
    return [
        "Define the audience, mission fit, and unique angle before drafting.",
        "Classify search intent as informational, navigational, commercial, or transactional.",
        "Match the article format and CTA to the dominant search intent.",
        "Use an inverted-pyramid opening: answer the main question immediately, then expand.",
        "Plan a clear heading structure before drafting and check it again during repair.",
        "Keep paragraphs short, scannable, and led by clear topic sentences.",
        "Add internal links so visitors can navigate related posts and pages.",
        "Add Article schema and relevant FAQ/Breadcrumb/Organization schema opportunities where appropriate.",
        "Use AI as a drafting and structuring aid, then run human-quality and factual repair before publishing.",
    ]


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


def _headings(markdown: str) -> list[str]:
    markdown_headings = [match.group(1).strip() for match in re.finditer(r"^##+\s+(.+)$", markdown or "", flags=re.MULTILINE)]
    html_headings = [re.sub(r"<[^>]+>", "", match).strip() for match in re.findall(r"<h[23][^>]*>.*?</h[23]>", markdown or "", flags=re.IGNORECASE | re.DOTALL)]
    return [heading for heading in markdown_headings + html_headings if heading]


def _paragraphs(markdown: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n{2,}", markdown or "") if part.strip() and not part.lstrip().startswith(("#", "<", "-", "|"))]


def _sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]


def _looks_like_direct_answer(paragraph: str, focus_keyphrase: str) -> bool:
    if not paragraph:
        return False
    first_sentence = _sentences(paragraph)[0] if _sentences(paragraph) else paragraph
    words = len(re.findall(r"\b\w+\b", first_sentence))
    return focus_keyphrase.lower() in first_sentence.lower() and words <= 35


def _topic_sentence_ratio(paragraphs: list[str]) -> float:
    if not paragraphs:
        return 1.0
    clear = 0
    for paragraph in paragraphs:
        sentences = _sentences(_plain_text(paragraph))
        if not sentences:
            continue
        first_words = len(re.findall(r"\b\w+\b", sentences[0]))
        if first_words <= 28:
            clear += 1
    return clear / len(paragraphs)


def _question_answer_coverage(markdown: str) -> int:
    faq_markers = len(re.findall(r"\bFAQ\b|<details\b|<summary\b|^##+\s+.*(?:question|answer|faq)", markdown or "", flags=re.IGNORECASE | re.MULTILINE))
    return faq_markers
