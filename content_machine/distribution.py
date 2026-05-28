from __future__ import annotations
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Any

from .config import Settings
from .models import PipelineResult
from .state import StateStore
from .blogger import BloggerClient
from .anthropic_writer import ContentWriter

logger = logging.getLogger(__name__)

class DistributionEngine:
    def __init__(self, settings: Settings, store: StateStore | None = None):
        self.settings = settings
        self.store = store or StateStore(settings.state_db, settings=settings)
        self.blogger = BloggerClient(settings)
        self.writer = ContentWriter(settings)

    async def distribute(self, result: PipelineResult, research: dict[str, Any]) -> list[dict[str, Any]]:
        """Syndicates content and creates backlink outreach targets.
        
        Saves all details in the database state tables.
        """
        logger.info(f"Starting distribution for article: {result.content.title}")
        created_assets = []

        # 1. Record the original article in the articles table
        article_id = result.wordpress_id or result.content.slug
        article_record = {
            "article_id": str(article_id),
            "title": result.content.title,
            "url": result.wordpress_url,
            "target_keyword": result.opportunity.keyword,
            "topic_cluster": result.opportunity.metadata.get("cluster_name"),
            "seo_score": result.audit.score,
            "publish_date": datetime.now(timezone.utc).isoformat(),
            "status": result.wordpress_status
        }
        try:
            self.store.save_article(article_record)
            logger.info(f"Article saved to articles state: {article_id}")
        except Exception as e:
            logger.error(f"Failed to save article to state database: {e}")

        # 2. Syndicate to Blogger if blog ID is set
        blogger_blog_id = getattr(self.settings, "blogger_blog_id", "").strip()
        blogger_syndicated = False
        if blogger_blog_id:
            try:
                logger.info(f"Adapting post for Blogger: {result.content.title}")
                adapted = await self.writer.adapt_for_blogger(
                    result.content.title,
                    result.content.html or "",
                    result.wordpress_url or self.settings.site.site_url
                )
                
                # Match WordPress status: only publish if WordPress posted it live
                is_draft = (result.wordpress_status != "publish")
                logger.info(f"Publishing to Blogger (is_draft={is_draft})")
                blogger_res = await self.blogger.publish_post(
                    adapted.get("title", result.content.title),
                    adapted.get("content", ""),
                    is_draft=is_draft
                )
                
                asset_id = f"{article_id}:blogger"
                asset_record = {
                    "id": asset_id,
                    "article_id": str(article_id),
                    "platform": "blogger",
                    "content_variant": adapted.get("content", ""),
                    "status": "draft" if is_draft else "published",
                    "published_url": blogger_res.get("url"),
                    "canonical_used": result.wordpress_url,
                    "date_published": datetime.now(timezone.utc).isoformat()
                }
                self.store.save_distribution_asset(asset_record)
                created_assets.append(asset_record)
                blogger_syndicated = True
                logger.info(f"Blogger syndication complete: {blogger_res.get('url')}")
            except Exception as e:
                logger.error(f"Blogger syndication failed: {e}")
                # Save failed distribution asset record
                try:
                    asset_id = f"{article_id}:blogger"
                    asset_record = {
                        "id": asset_id,
                        "article_id": str(article_id),
                        "platform": "blogger",
                        "content_variant": "",
                        "status": "failed",
                        "published_url": None,
                        "canonical_used": result.wordpress_url,
                        "date_published": None
                    }
                    self.store.save_distribution_asset(asset_record)
                except Exception:
                    pass
        else:
            logger.info("Blogger syndication skipped: BLOGGER_BLOG_ID is not configured.")

        # 3. Generate backlink prospects from SERP competitors
        competitor_domains = []
        serp = research.get("serp", {})
        for task in serp.get("tasks", []):
            for task_res in task.get("result") or []:
                for item in task_res.get("items") or []:
                    if item.get("type") == "organic" and item.get("url"):
                        domain = urlparse(item["url"]).netloc
                        if domain and domain not in competitor_domains:
                            # Exclude our own domain
                            if "meetlyra.app" not in domain:
                                competitor_domains.append(domain)

        # Generate outreach for top 5 competitors
        backlinks_created_count = 0
        for domain in competitor_domains[:5]:
            try:
                logger.info(f"Generating backlink outreach pitch for domain: {domain}")
                pitch = await self.writer.generate_backlink_outreach(
                    result.content.title,
                    domain,
                    result.opportunity.keyword
                )
                target_id = f"{article_id}:{domain}"
                target_record = {
                    "id": target_id,
                    "article_id": str(article_id),
                    "target_site": domain,
                    "contact_name": pitch.get("contact_name"),
                    "contact_email": pitch.get("contact_email"),
                    "outreach_angle": pitch.get("outreach_angle"),
                    "status": "pending",
                    "response": None
                }
                self.store.save_backlink_target(target_record)
                backlinks_created_count += 1
            except Exception as e:
                logger.error(f"Failed to generate backlink outreach for {domain}: {e}")

        # 4. Save daily report aggregation
        try:
            date_str = datetime.now(timezone.utc).date().isoformat()
            existing_report = self.store.get_daily_report(date_str) or {
                "date": date_str,
                "posts_published": 0,
                "posts_syndicated": 0,
                "backlinks_created": 0,
                "indexing_status": "pending"
            }
            if result.wordpress_status == "publish":
                existing_report["posts_published"] = existing_report.get("posts_published", 0) + 1
            if blogger_syndicated:
                existing_report["posts_syndicated"] = existing_report.get("posts_syndicated", 0) + 1
            existing_report["backlinks_created"] = existing_report.get("backlinks_created", 0) + backlinks_created_count
            
            self.store.save_daily_report(existing_report)
            logger.info(f"Daily report updated for date {date_str}")
        except Exception as e:
            logger.error(f"Failed to update daily report: {e}")

        return created_assets
