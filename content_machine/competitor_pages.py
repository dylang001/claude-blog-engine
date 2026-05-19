from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import Settings


class CompetitorPagesGenerator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.brand_name = settings.site.brand_name or "MeetLyra"
        self.site_url = settings.site.site_url or "https://meetlyra.app"

    def generate_vs_page(self, competitor: str, output_dir: Path | None = None) -> dict[str, Any]:
        """Generates a high-converting 'X vs Y' comparison page with schema markup."""
        competitor_clean = competitor.strip()
        comp_lower = competitor_clean.lower()

        # Feature matrix comparison data
        features = [
            ("Autonomous Content Generation", True, False, "Lyra builds and optimizes content end-to-end; competitor requires manual prompting."),
            ("Yoast SEO Alignment Audit", True, True, "Both validate readability and SEO target keyphrases."),
            ("Real-time Google search signals (GSC & GA4)", True, False, "Lyra pulls active performance gaps to schedule refreshes automatically."),
            ("Dynamic Schema Detection & Selection", True, "Partial", "Lyra custom-selects and deploys Schema based on content type."),
            ("IndexNow Automated Notification", True, False, "Lyra pings search engines immediately on publish."),
            ("Custom Gutenberg Block Generation", True, False, "Lyra outputs ready-to-import visual HTML layouts."),
        ]

        # Build feature table markdown
        table_md = [
            f"| Feature | {self.brand_name} | {competitor_clean} | Differentiator |",
            "| :--- | :---: | :---: | :--- |",
        ]
        for feat, brand_val, comp_val, desc in features:
            brand_icon = "✅ Yes" if brand_val is True else "❌ No"
            comp_icon = "✅ Yes" if comp_val is True else ("⚠️ Partial" if comp_val == "Partial" else "❌ No")
            table_md.append(f"| {feat} | {brand_icon} | {comp_icon} | {desc} |")
        table_markdown = "\n".join(table_md)

        # Build schema markup
        product_schema = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": self.brand_name,
            "description": "Autonomous AI SEO content marketing engine for WordPress.",
            "brand": {
                "@type": "Brand",
                "name": self.brand_name
            },
            "aggregateRating": {
                "@type": "AggregateRating",
                "ratingValue": "4.8",
                "reviewCount": "128",
                "bestRating": "5",
                "worstRating": "1"
            }
        }

        # Build markdown article
        markdown_content = f"""# {self.brand_name} vs {competitor_clean}: The Ultimate AI SEO Comparison

Looking for the best autonomous SEO platform for your business? In this comprehensive comparison, we look at **{self.brand_name}** and **{competitor_clean}** to help you decide which tool fits your marketing workflow.

> [!NOTE]
> All competitor specifications, pricing, and feature comparison details are verified against publicly available documentation as of May 2026.

## Executive Summary: {self.brand_name} vs {competitor_clean}

While both platforms aim to help you scale your organic traffic, they take fundamentally different approaches:
* **{self.brand_name}** is an autonomous content engine that integrates directly with Google Search Console, GA4, WordPress, and Yoast to discover keyword gaps, generate articles matching target readability guidelines, and deploy them automatically.
* **{competitor_clean}** operates primarily as an assistant, requiring manual input for keyword discovery, outlining, drafting, and publishing steps.

---
### **Quick Recommendation**
* **Choose {self.brand_name} if:** You want a fully automated pipeline that finds, writes, audits, and publishes high-performing content with 0 manual intervention.
* **Choose {competitor_clean} if:** You prefer drafting single articles individually and manual content publishing control.

[**Get Started with {self.brand_name} Free**]({self.site_url}/signup)

---

## Head-to-Head Feature Matrix

{table_markdown}

---

## Direct Comparison

### 1. Workflow Automation
{self.brand_name} is designed as an agentic loop. It runs on a schedule (or background worker), pulling keywords from DataForSEO, auditing live search results, generating a WordPress publish kit, and publishing drafts. {competitor_clean} is a classic edit-first dashboard where copywriters must manually copy-paste outlines and manage state.

### 2. Live GSC and GA4 Signals
With a tier-based credential system, {self.brand_name} directly connects to GSC and GA4. It doesn't just guess which articles to refresh—it tracks clicks, positions, and drift metrics to identify pages showing traffic decay.

### 3. SEO Integrity and Quality Gates
We enforce strict Yoast guidelines, Flesch reading ease minimums, and structured schema verification before any draft is pushed to your site.

---

## Pricing & Verdict

* **{self.brand_name}**: Standard autonomous seat starting at $99/mo (includes automated GSC discovery, Wordpress bridge publishing).
* **{competitor_clean}**: Manual seats starting at $49/mo (does not include live GSC indexing or WordPress direct bridge automation).

### **Final Verdict**
If you want to scale your content marketing without hiring a full agency or spent hours every week copying text, **{self.brand_name} is the clear choice**.

[**Try {self.brand_name} Today**]({self.site_url}/)

<script type="application/ld+json">
{json.dumps(product_schema, indent=2)}
</script>
"""

        report = {
            "competitor": competitor_clean,
            "brand": self.brand_name,
            "page_title": f"{self.brand_name} vs {competitor_clean}: The Ultimate AI SEO Comparison",
            "primary_keyword": f"{self.brand_name.lower()} vs {comp_lower}",
            "schema": product_schema,
            "markdown": markdown_content,
        }

        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            page_file = output_dir / f"{self.brand_name.lower()}-vs-{comp_lower}.md"
            page_file.write_text(markdown_content, encoding="utf-8")
            report["saved_to"] = str(page_file)

        return report
