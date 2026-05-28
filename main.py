from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from firebase_functions import scheduler_fn, https_fn
from firebase_admin import initialize_app

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("content_machine_functions")

# Initialize firebase admin
initialize_app()

from content_machine.config import load_settings
from content_machine.pipeline import ContentMachine
from content_machine.reporter import EmailReporter
from content_machine.performance_analyst import PerformanceAnalyst

# Load settings from root
settings = load_settings(root_dir=Path(__file__).resolve().parent)
timezone = settings.site.timezone or "America/New_York"

logger.info(f"Loaded Firebase function settings. Timezone: {timezone}")


@scheduler_fn.on_schedule(schedule="0 9,15 * * *", timezone=timezone, timeout_sec=900)
def content_machine_worker(event) -> None:
    """Scheduled worker to run the Content Machine pipeline twice a day."""
    logger.info("Starting scheduled Content Machine run...")
    machine = ContentMachine(settings)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(machine.run_once(dry_run=False))
        logger.info(f"Scheduled run completed. Result: {result.wordpress_status} (ID: {result.wordpress_id})")
    finally:
        loop.close()


@scheduler_fn.on_schedule(schedule="0 20 * * *", timezone=timezone, timeout_sec=300)
def daily_email_report(event) -> None:
    """Scheduled worker to send the daily email report at 20:00."""
    logger.info("Starting scheduled daily email report...")
    reporter = EmailReporter(settings)
    success = reporter.send_daily_report()
    logger.info(f"Daily email report sent. Success: {success}")


@scheduler_fn.on_schedule(schedule="0 23 * * 0", timezone=timezone, timeout_sec=900)
def weekly_performance_review(event) -> None:
    """Autonomous weekly reviewer: audits GSC/GA4 metrics, detects content drift,
    identifies page-2 ranking opportunities, and injects refresh candidates
    back into the pipeline queue."""
    logger.info("Starting weekly performance review...")
    analyst = PerformanceAnalyst(settings)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        report = loop.run_until_complete(analyst.run_weekly_review())
        logger.info(
            f"Weekly review complete. "
            f"Drift pages: {len(report.get('drift_pages', []))}, "
            f"Ranking opportunities: {len(report.get('ranking_opportunities', []))}, "
            f"Refresh candidates injected: {report.get('refresh_candidates_injected', 0)}, "
            f"Learnings stored: {report.get('learnings_stored', 0)}"
        )
    except Exception as exc:
        logger.exception(f"Weekly performance review failed: {exc}")
    finally:
        loop.close()


@https_fn.on_request(timeout_sec=900)
def run_now(req: https_fn.Request) -> https_fn.Response:
    """HTTPS trigger to manually run the pipeline immediately."""
    logger.info("HTTP request received to run pipeline immediately...")
    
    # Simple key authentication (first 8 characters of WP App Password, ignoring spaces)
    expected_raw = (settings.wp_app_password or "").replace(" ", "")
    expected_key = expected_raw[:8] if expected_raw else "default_secret"
    provided_key = (req.args.get("key") or "").replace(" ", "")
    if provided_key != expected_key:
         logger.warning(f"Unauthorized request to run_now HTTPS trigger. Expected prefix: {expected_key}")
         return https_fn.Response("Unauthorized", status=401)
         
    machine = ContentMachine(settings)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(machine.run_once(dry_run=False))
        return https_fn.Response(
            f"Pipeline executed successfully!\n"
            f"Opportunity: {result.opportunity.keyword}\n"
            f"Status: {result.wordpress_status}\n"
            f"URL: {result.wordpress_url}\n"
            f"Audit Decision: {result.audit.decision.value}\n"
        )
    except Exception as e:
        logger.exception("Error running manual pipeline trigger:")
        return https_fn.Response(f"Error running pipeline: {str(e)}", status=500)
    finally:
        loop.close()

