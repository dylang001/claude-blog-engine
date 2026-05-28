from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
import httpx

from .config import Settings, load_settings

class SEOGEOAuditor:
    """Performs Generative Engine Optimization (GEO) analysis for a website."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.brand_name = settings.site.brand_name or "MeetLyra"
        self.site_url = settings.site.site_url or "https://blog.meetlyra.app"
        self.products = settings.site.products or [
            "Autonomous AI Marketing Agent",
            "AI SEO and GEO Content Engine",
            "AI Campaign Planning and Execution System",
        ]
        self.competitors = settings.site.competitors or ["jasper.ai", "copy.ai", "surferseo.com"]

    async def run_analysis(self, target_url: str | None = None, strict: bool = False) -> dict[str, Any]:
        url = target_url or self.site_url
        api_key = self.settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")

        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is required for GEO analysis. "
                "Set ANTHROPIC_API_KEY in your .env file."
            )

        print(f"[*] Calling Claude API for GEO analysis of {url}...")
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "anthropic-beta": "prompt-caching-2024-07-31",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.settings.anthropic_model or "claude-sonnet-4-5",
                        "max_tokens": 4000,
                        "system": [
                            {
                                "type": "text",
                                "text": "You are an expert Generative Engine Optimization (GEO) agent.\n" + self._build_prompt(url),
                                "cache_control": {"type": "ephemeral"}
                            }
                        ],
                        "messages": [{"role": "user", "content": "Run the GEO analysis now and return the JSON."}]
                    }
                )
                resp.raise_for_status()
                data = resp.json()
                api_response_text = data["content"][0]["text"]
            print("[+] Successfully generated GEO plan via Claude API.")
        except Exception as exc:
            raise RuntimeError(
                f"Claude API call for GEO analysis failed. "
                f"Check your internet connection and ANTHROPIC_API_KEY. "
                f"Error: {type(exc).__name__}: {exc}"
            ) from exc

        report_data = self._parse_claude_response(api_response_text, url)

        # Write reports
        self._write_reports(report_data)
        return report_data

    def _build_prompt(self, url: str) -> str:
        return f"""
Analyze the website {url} for Generative Engine Optimization (GEO) and AI search visibility.
Brand details:
- Brand Name: {self.brand_name}
- Products: {", ".join(self.products)}
- Competitors: {", ".join(self.competitors)}

Please perform a comprehensive GEO audit and generate a full report covering:
1. Citability Score (optimal 134-167 word passages, direct answer blocks, facts & stats)
2. Structural Readability (headings, list, tables, FAQ)
3. Multi-Modal elements (images, videos, graphics)
4. Authority & Brand Mentions (Wikipedia, Reddit, YouTube, LinkedIn)
5. Technical accessibility (SSR check, robots.txt AI rules, llms.txt file, RSL 1.0 license)

Generate:
- GEO Readiness Score (0-100) with dimension breakdowns.
- Platform breakdown (Google AIO, ChatGPT, Perplexity, Bing Copilot).
- AI Crawler Access Status (allowed/blocked rules).
- A complete, copy-pasteable llms.txt template optimized for the site structure.
- Brand mention analysis and entity mapping recommendations.
- Top 5 highest-impact changes.
- Specific text reformatting suggestions (134-167 words passages) for product pages or blog posts.

Provide the response in two distinct JSON sections:
1. "GEO-ANALYSIS": A comprehensive markdown report.
2. "GEO-PLAN": A step-by-step optimization roadmap markdown text.
Wrap both under a single JSON object matching:
{{
  "analysis_md": "...",
  "plan_md": "...",
  "readiness_score": 75,
  "platform_scores": {{"google_aio": 80, "chatgpt": 72, "perplexity": 70, "copilot": 78}}
}}
"""

    def _parse_claude_response(self, text: str, url: str) -> dict[str, Any]:
        # Try to find JSON block in Claude's response
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                return {
                    "url": url,
                    "readiness_score": data.get("readiness_score", 75),
                    "platform_scores": data.get("platform_scores", {}),
                    "analysis_md": data.get("analysis_md", text),
                    "plan_md": data.get("plan_md", ""),
                }
            except Exception:
                pass

        # If Claude did not return clean JSON, return raw text as analysis
        return {
            "url": url,
            "readiness_score": 0,
            "platform_scores": {},
            "analysis_md": text,
            "plan_md": "Claude response could not be parsed as structured JSON. See analysis_md for raw output.",
            "parse_warning": "Response was not valid JSON. Manual review required.",
        }

    # _generate_simulated_data removed — the system must never produce
    # fabricated GEO reports. If Claude API fails, the pipeline raises
    # RuntimeError so the operator can diagnose and fix the issue.

    def _write_reports(self, data: dict[str, Any]) -> None:
        """Writes GEO-ANALYSIS.md and GEO-PLAN.md to root and reports folder."""
        # 1. Write to root directory
        analysis_path = Path("GEO-ANALYSIS.md")
        plan_path = Path("GEO-PLAN.md")

        analysis_path.write_text(data["analysis_md"], encoding="utf-8")
        plan_path.write_text(data["plan_md"], encoding="utf-8")

        # 2. Write a JSON copy to the reports folder
        reports_dir = self.settings.data_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        json_path = reports_dir / "geo-report.json"
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        print(f"[+] Saved reports:")
        print(f"    - {analysis_path.absolute()}")
        print(f"    - {plan_path.absolute()}")
        print(f"    - {json_path.absolute()}")
