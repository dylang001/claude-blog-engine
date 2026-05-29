from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import load_settings
from .health import get_health_monitor

logger = logging.getLogger("content_machine.worker")

# Firebase Functions base URL
# Format: https://<region>-<project-id>.cloudfunctions.net
FIREBASE_FUNCTIONS_URL = os.environ.get(
    "FIREBASE_FUNCTIONS_URL",
    "https://us-central1-aeo-seo-agents-team.cloudfunctions.net"
)

# Auth key for Firebase functions (first 8 chars of WP password)
def get_auth_key():
    settings = load_settings()
    pwd = (settings.wp_app_password or "").replace(" ", "")
    return pwd[:8] if pwd else "default_secret"


async def call_firebase_function(session: aiohttp.ClientSession, function_name: str) -> dict:
    """Call a Firebase HTTP function."""
    url = f"{FIREBASE_FUNCTIONS_URL}/{function_name}"
    params = {"key": get_auth_key()}
    
    start_time = datetime.now()
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=600)) as resp:
            duration = (datetime.now() - start_time).total_seconds()
            
            if resp.status == 200:
                data = await resp.json()
                logger.info(
                    "Firebase function %s succeeded in %.1fs: run_id=%s",
                    function_name, duration, data.get("run_id", "unknown")
                )
                return {"success": True, "data": data, "duration": duration}
            else:
                text = await resp.text()
                logger.error(
                    "Firebase function %s failed in %.1fs: status=%s, response=%s",
                    function_name, duration, resp.status, text[:200]
                )
                return {"success": False, "status": resp.status, "error": text[:500]}
                
    except asyncio.TimeoutError:
        logger.error("Firebase function %s timed out after 600s", function_name)
        return {"success": False, "error": "Timeout after 600s"}
    except Exception as e:
        logger.error("Firebase function %s error: %s", function_name, str(e))
        return {"success": False, "error": str(e)}


async def run_pipeline_slot(session: aiohttp.ClientSession) -> None:
    """Trigger the content machine pipeline via Firebase HTTP endpoint."""
    logger.info("Triggering content_machine_worker via Firebase HTTP...")
    result = await call_firebase_function(session, "content_machine_worker")
    
    if result["success"]:
        logger.info("Pipeline triggered successfully: %s", result["data"].get("run_id"))
    else:
        logger.error("Failed to trigger pipeline: %s", result.get("error"))
        # Record failure in health monitor
        health = get_health_monitor()
        health.record_heartbeat(
            "content_machine_worker",
            "failed",
            run_id=f"worker_{int(asyncio.get_event_loop().time())}",
            error_message=result.get("error", "Unknown error"),
        )


async def run_email_report_slot(session: aiohttp.ClientSession) -> None:
    """Trigger daily email report via Firebase HTTP endpoint."""
    logger.info("Triggering daily_email_report via Firebase HTTP...")
    result = await call_firebase_function(session, "daily_email_report")
    
    if result["success"]:
        logger.info("Email report triggered successfully")
    else:
        logger.error("Failed to trigger email report: %s", result.get("error"))


async def run_weekly_review_slot(session: aiohttp.ClientSession) -> None:
    """Trigger weekly performance review via Firebase HTTP endpoint."""
    logger.info("Triggering weekly_performance_review via Firebase HTTP...")
    result = await call_firebase_function(session, "weekly_performance_review")
    
    if result["success"]:
        data = result["data"]
        logger.info(
            "Weekly review complete: drift=%s, opportunities=%s, refresh=%s",
            data.get("drift_count", 0),
            data.get("opportunities_count", 0),
            data.get("refresh_injected", 0),
        )
    else:
        logger.error("Failed to trigger weekly review: %s", result.get("error"))


def start_worker() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    settings = load_settings()
    
    async def _run():
        # Create aiohttp session for making HTTP calls
        timeout = aiohttp.ClientTimeout(total=600)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            scheduler = AsyncIOScheduler(timezone=settings.site.timezone)
            
            # Content pipeline slots from settings
            for slot in settings.site.publishing_slots:
                hour, minute = slot.split(":", 1)
                scheduler.add_job(
                    lambda s=session: asyncio.create_task(run_pipeline_slot(s)),
                    CronTrigger(hour=int(hour), minute=int(minute), timezone=settings.site.timezone),
                    id=f"publish-{slot}",
                    replace_existing=True,
                    misfire_grace_time=300,  # 5 minute grace period
                )
                logger.info("Scheduled pipeline trigger at %s:%s", hour, minute)
            
            # Daily email report at 20:00
            scheduler.add_job(
                lambda s=session: asyncio.create_task(run_email_report_slot(s)),
                CronTrigger(hour=20, minute=0, timezone=settings.site.timezone),
                id="daily-email-report",
                replace_existing=True,
                misfire_grace_time=300,
            )
            logger.info("Scheduled daily email report at 20:00")
            
            # Weekly performance review at 23:00 on Sunday
            scheduler.add_job(
                lambda s=session: asyncio.create_task(run_weekly_review_slot(s)),
                CronTrigger(day_of_week="sun", hour=23, minute=0, timezone=settings.site.timezone),
                id="weekly-performance-review",
                replace_existing=True,
                misfire_grace_time=600,  # 10 minute grace for weekly job
            )
            logger.info("Scheduled weekly performance review at 23:00 on Sunday")
            
            scheduler.start()
            logger.info(
                "Content Machine Render worker started - calling Firebase functions at %s",
                FIREBASE_FUNCTIONS_URL
            )
            logger.info("Publishing slots: %s", ", ".join(settings.site.publishing_slots))
            
            # Keep the event loop running
            await asyncio.Event().wait()

    asyncio.run(_run())


async def run_once_local():
    """Run the pipeline locally once (for testing/debugging)."""
    from .pipeline import ContentMachine
    
    settings = load_settings()
    missing = settings.missing_required()
    if missing:
        raise RuntimeError(f"Missing required configuration: {', '.join(missing)}")
    
    result = await ContentMachine(settings).run_once(dry_run=False)
    logger.info(
        "Local run complete: run_id=%s decision=%s status=%s keyword=%s score=%s",
        result.run_id,
        result.audit.decision.value,
        result.wordpress_status,
        result.opportunity.keyword,
        result.audit.score,
    )
    return result
