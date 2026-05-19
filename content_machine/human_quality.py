from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field


AI_FLOSCULES = {
    "in today's digital landscape",
    "delve into",
    "it is important to note",
    "game changer",
    "seamlessly",
    "robust",
    "unlock the power",
    "take your business to the next level",
    "comprehensive solution",
    "ever-evolving",
    "leverage",
    "at the end of the day",
    "in conclusion",
}

GENERIC_ENTITIES = {
    "many businesses",
    "some experts",
    "a recent study",
    "industry leaders",
    "modern teams",
    "companies today",
}


@dataclass(frozen=True)
class HumanQualityReport:
    score: float
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, float | int | list[str]] = field(default_factory=dict)


def assess_human_quality(markdown: str) -> HumanQualityReport:
    plain = _plain_text(markdown)
    sentences = _sentences(plain)
    paragraphs = _paragraphs(markdown)
    words = re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", plain)
    lower = plain.lower()

    score = 100.0
    issues: list[str] = []
    warnings: list[str] = []

    non_english_fragments = re.findall(r"[\u4e00-\u9fff\u3040-\u30ff\u0400-\u04ff]+", plain)
    if non_english_fragments:
        score -= 18
        issues.append("Content contains non-English fragments in an English article.")

    phrase_hits = sorted({phrase for phrase in AI_FLOSCULES if phrase in lower})
    if phrase_hits:
        score -= min(36, 6 * len(phrase_hits))
        issues.append("Content contains generic AI-style filler phrases.")

    repeated_starts = _repeated_sentence_starts(sentences)
    if repeated_starts >= 4:
        score -= 12
        issues.append("Too many sentences begin with the same phrase pattern.")
    elif repeated_starts >= 2:
        score -= 6
        warnings.append("Sentence openings are starting to feel repetitive.")

    burstiness = _sentence_burstiness(sentences)
    if len(sentences) >= 8 and burstiness < 0.25:
        score -= 12
        issues.append("Sentence rhythm is too uniform; vary short and medium sentences.")

    paragraph_cv = _paragraph_length_variation(paragraphs)
    if len(paragraphs) >= 5 and paragraph_cv < 0.35:
        score -= 8
        warnings.append("Paragraph lengths are too even; mix quick beats with deeper sections.")

    vague_hits = sorted({phrase for phrase in GENERIC_ENTITIES if phrase in lower})
    specificity = _specificity_score(plain)
    if vague_hits and specificity < 0.03:
        score -= 10
        warnings.append("Claims need more concrete names, numbers, examples, or source references.")

    repeated_terms = _overused_terms(words)
    if repeated_terms:
        score -= min(12, 3 * len(repeated_terms))
        warnings.append("A few non-keyword terms are repeated too often.")

    return HumanQualityReport(
        score=max(0.0, min(100.0, round(score, 1))),
        issues=issues,
        warnings=warnings,
        details={
            "filler_phrases": phrase_hits,
            "generic_entities": vague_hits,
            "non_english_fragments": non_english_fragments[:5],
            "repeated_sentence_starts": repeated_starts,
            "sentence_burstiness": round(burstiness, 2),
            "paragraph_length_variation": round(paragraph_cv, 2),
            "specificity_score": round(specificity, 3),
            "overused_terms": repeated_terms[:8],
        },
    )


def _plain_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = re.sub(r"[#*_>`\[\]\(\)]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]


def _paragraphs(markdown: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n{2,}", markdown or "") if part.strip() and not part.lstrip().startswith(("#", "<", "-", "|"))]


def _repeated_sentence_starts(sentences: list[str]) -> int:
    starts: dict[str, int] = {}
    for sentence in sentences:
        words = re.findall(r"[A-Za-z]+", sentence.lower())[:3]
        if len(words) >= 2:
            key = " ".join(words[:2])
            starts[key] = starts.get(key, 0) + 1
    return sum(count - 1 for count in starts.values() if count > 1)


def _sentence_burstiness(sentences: list[str]) -> float:
    lengths = [len(re.findall(r"\b\w+\b", sentence)) for sentence in sentences if sentence.strip()]
    if len(lengths) < 2:
        return 1.0
    mean = statistics.mean(lengths)
    if mean == 0:
        return 0.0
    return statistics.pstdev(lengths) / mean


def _paragraph_length_variation(paragraphs: list[str]) -> float:
    lengths = [len(re.findall(r"\b\w+\b", paragraph)) for paragraph in paragraphs]
    if len(lengths) < 2:
        return 1.0
    mean = statistics.mean(lengths)
    if mean == 0:
        return 0.0
    return statistics.pstdev(lengths) / mean


def _specificity_score(text: str) -> float:
    numbers = len(re.findall(r"\b\d+(?:\.\d+)?%?\b", text))
    dates = len(re.findall(r"\b(?:20\d{2}|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", text))
    proper_nouns = len(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text))
    words = max(1, len(re.findall(r"\b\w+\b", text)))
    return (numbers + dates + proper_nouns) / words


def _overused_terms(words: list[str]) -> list[str]:
    ignored = {
        "content",
        "marketing",
        "seo",
        "agent",
        "agents",
        "automation",
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "your",
    }
    counts: dict[str, int] = {}
    for word in words:
        key = word.lower().strip("'")
        if len(key) < 5 or key in ignored:
            continue
        counts[key] = counts.get(key, 0) + 1
    total = max(1, len(words))
    return [word for word, count in sorted(counts.items(), key=lambda item: item[1], reverse=True) if count / total > 0.018 and count >= 8]
