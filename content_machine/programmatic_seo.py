from __future__ import annotations

from typing import Any


class ProgrammaticSEOPlanner:
    def __init__(self):
        pass

    def calculate_uniqueness(self, text_a: str, text_b: str) -> float:
        """Simple word-level uniqueness percentage calculation.
        
        Unique content % = (words unique to text_a) / (total words in text_a) * 100
        """
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())
        if not words_a:
            return 0.0
        unique_words = words_a - words_b
        return (len(unique_words) / len(words_a)) * 100

    def analyze_planning(self, page_count: int, templates: list[dict[str, Any]], data_records: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyzes a programmatic SEO configuration for thin content risk, indexability, and doorway page penalties."""
        report = {
            "page_count": page_count,
            "status": "pass",
            "score": 100.0,
            "issues": [],
            "warnings": [],
            "action_items": [],
        }

        # Quality Gate 1: Page Count Limits
        if page_count >= 500:
            report["status"] = "hard_stop"
            report["score"] -= 40
            report["issues"].append(
                f"🛑 HARD STOP: {page_count} pages requested. Scaled Content Abuse policy limits simultaneous publish sets to under 500 pages without human audit."
            )
        elif page_count >= 100:
            report["status"] = "warning"
            report["score"] -= 15
            report["warnings"].append(
                f"⚠️ WARNING: {page_count} pages requested. High risk of search engine indexing delay or manual action. content audit required."
            )

        # Quality Gate 2: Location doorway page checking
        location_patterns = [t for t in templates if "location" in t.get("name", "").lower() or "[city]" in t.get("pattern", "").lower()]
        if location_patterns:
            if page_count >= 50:
                report["status"] = "hard_stop"
                report["score"] -= 30
                report["issues"].append(
                    f"🛑 HARD STOP Location Gate: {page_count} location pages planned. Safe programmatic SEO limit is 50 location pages to prevent doorway penalties."
                )
            elif page_count >= 30:
                report["status"] = "warning"
                report["score"] -= 10
                report["warnings"].append(
                    f"⚠️ WARNING Location Gate: {page_count} location pages planned. Enforce >=60% unique content per page to prevent spam action."
                )

        # Quality Gate 3: Thin Content checks per template
        for t in templates:
            word_count = t.get("expected_word_count", 0)
            uniqueness = t.get("uniqueness_percentage", 100.0)

            if word_count < 300:
                report["score"] -= 15
                report["warnings"].append(
                    f"Template '{t.get('name')}' expected word count ({word_count}) is below 300 words. High risk of thin content flag."
                )
            
            if uniqueness < 30.0:
                report["status"] = "hard_stop"
                report["score"] -= 25
                report["issues"].append(
                    f"🛑 HARD STOP Uniqueness Gate: Template '{t.get('name')}' has {uniqueness}% unique content, which is below the 30% absolute limit."
                )
            elif uniqueness < 40.0:
                report["score"] -= 10
                report["warnings"].append(
                    f"Template '{t.get('name')}' has {uniqueness}% unique content. Enforce at least 40% uniqueness to prevent duplication flags."
                )

        # Evaluate Data Source Quality
        empty_rows = sum(1 for r in data_records if not r)
        if empty_rows:
            report["score"] -= 5
            report["warnings"].append(f"Data source contains {empty_rows} empty rows/records.")

        # Ensure unique slugs
        slugs = [r.get("slug") for r in data_records if r.get("slug")]
        if len(slugs) != len(set(slugs)):
            report["score"] -= 10
            report["issues"].append("Duplicate URL slugs detected in programmatic data source. URLs must be fully unique.")

        # Cap score at 0
        report["score"] = max(0.0, report["score"])

        # Prioritize action items
        if report["issues"]:
            report["action_items"].append("Resolve all critical hard stops by partitioning page generation batches or increasing template uniqueness.")
        if report["warnings"]:
            report["action_items"].append("Enrich dynamic content sections and variables to boost uniqueness score.")
        
        return report
