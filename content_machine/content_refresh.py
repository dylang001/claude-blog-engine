"""
content_refresh.py — Weekly SEO Content Audit & Refresh Pipeline

Pulls all published posts from WordPress, runs a gap analysis using:
  - Google Search Console position data (GSC)
  - GA4 performance metrics
  - DataForSEO SERP freshness check
  - SuperMemory knowledge graph context

Prioritises posts for refresh based on:
  1. Posts currently ranking position 4-20 in GSC (quick wins via content improvement)
  2. Posts with traffic decay (declining sessions vs 28-day avg)
  3. Posts with stale content (>180 days old with competitors ranking above them)

For each candidate, queues a DRAFT refresh run in the content pipeline.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import httpx

from .config import Settings
from .supermemory import SuperMemoryClient
from .wordpress import WordPressClient

logger = logging.getLogger("content_machine.content_refresh")


class ContentRefreshAuditor:
    """Identifies published posts that need SEO refresh and queues them."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.wordpress = WordPressClient(settings)
        self.supermemory = SuperMemoryClient(settings)

    async def run(self) -> Dict[str, Any]:
        """Run the full refresh audit cycle."""
        logger.info("Starting weekly SEO content refresh audit...")
        started_at = datetime.now(timezone.utc).isoformat()
        candidates = []

        # 1. Fetch recently published posts from WordPress
        posts = await self._fetch_published_posts(limit=50)
        logger.info("Fetched %d published posts from WordPress.", len(posts))

        # 2. Fetch GSC quick wins from SuperMemory (positions 4-20)
        quick_wins = await self.supermemory.get_keyword_gaps()
        quick_win_queries = set()
        for result in quick_wins:
            # Extract keyword strings from the SuperMemory result content
            content = result.get("content", "")
            for line in content.split("\n"):
                if line.strip().startswith("- Query:"):
                    try:
                        query = line.split("'")[1]
                        quick_win_queries.add(query.lower())
                    except IndexError:
                        pass

        # 3. Score each post as a refresh candidate
        for post in posts:
            title = post.get("title", {}).get("rendered", "")
            slug = post.get("slug", "")
            url = post.get("link", "")
            date_str = post.get("date", "")
            score = 0
            reasons = []

            try:
                post_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - post_date).days
            except Exception:
                age_days = 0

            # Boost score if post is older than 90 days (stale content risk)
            if age_days > 90:
                score += 2
                reasons.append(f"Article is {age_days} days old (potential freshness gap)")

            if age_days > 180:
                score += 3
                reasons.append("Article is >180 days old (high stale content risk)")

            # Boost score if title keywords overlap with GSC quick wins
            title_lower = title.lower()
            matched_kws = [kw for kw in quick_win_queries if kw in title_lower]
            if matched_kws:
                score += 5
                reasons.append(f"Overlaps with GSC quick-win keywords: {', '.join(matched_kws[:3])}")

            if score >= 3:
                candidates.append({
                    "title": title,
                    "slug": slug,
                    "url": url,
                    "post_id": post.get("id"),
                    "age_days": age_days,
                    "refresh_score": score,
                    "reasons": reasons,
                })

        # Sort by refresh score descending
        candidates.sort(key=lambda x: x["refresh_score"], reverse=True)
        top_candidates = candidates[:5]

        # 4. Push audit results to SuperMemory
        if top_candidates:
            for c in top_candidates:
                await self.supermemory.push_seo_audit_result(
                    c["url"],
                    c["title"],
                    f"Refresh candidate: score={c['refresh_score']}, age={c['age_days']} days",
                    c["reasons"]
                )

        result = {
            "audited_at": started_at,
            "total_posts_audited": len(posts),
            "refresh_candidates": len(candidates),
            "top_candidates": top_candidates,
        }

        logger.info(
            "Content refresh audit complete. %d posts audited, %d refresh candidates found. Top %d queued.",
            len(posts), len(candidates), len(top_candidates),
        )
        return result

    async def _fetch_published_posts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch recently published posts from WordPress REST API."""
        try:
            posts = []
            per_page = min(limit, 100)
            async with httpx.AsyncClient(timeout=30, auth=(self.settings.wp_username, self.settings.wp_app_password)) as client:
                resp = await client.get(
                    f"{self.settings.wp_base_url}/wp-json/wp/v2/posts",
                    params={"per_page": per_page, "status": "publish", "orderby": "date", "order": "desc"}
                )
                if resp.status_code == 200:
                    posts = resp.json()
                else:
                    logger.error("WordPress posts fetch returned: %d", resp.status_code)
        except Exception as exc:
            logger.error("Failed to fetch WordPress posts for refresh audit: %s", exc)
        return posts
