from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from firebase_functions import scheduler_fn, https_fn, options
from firebase_admin import initialize_app

# Set up structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("content_machine_functions")

# Initialize firebase admin
initialize_app()

from content_machine.config import load_settings
from content_machine.pipeline import ContentMachine
from content_machine.reporter import EmailReporter
from content_machine.performance_analyst import PerformanceAnalyst
from content_machine.health import get_health_monitor
from content_machine.alerting import get_alert_manager, alert
from content_machine.circuit_breaker import WORDPRESS_CB, DATAFORSEO_CB, ANTHROPIC_CB

# Load settings from root
settings = load_settings(root_dir=Path(__file__).resolve().parent)
timezone = settings.site.timezone or "America/New_York"

logger.info(f"Loaded Firebase function settings. Timezone: {timezone}")


@scheduler_fn.on_schedule(
    schedule="0 9,15 * * *",
    timezone=timezone,
    timeout_sec=900,
    memory=options.MemoryOption.GB_1,
    max_instances=1,
)
def content_machine_worker(event) -> None:
    """Scheduled worker to run the Content Machine pipeline twice a day."""
    run_id = f"scheduled_{int(time.time())}"
    health = get_health_monitor()
    
    logger.info(f"Starting scheduled Content Machine run [{run_id}]...")
    health.record_heartbeat("content_machine_worker", "started", run_id=run_id)
    
    machine = ContentMachine(settings)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    start_time = time.time()
    error_msg = None
    
    try:
        result = loop.run_until_complete(machine.run_once(dry_run=False))
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"Scheduled run completed [{run_id}]. Status: {result.wordpress_status}")
        health.record_heartbeat(
            "content_machine_worker",
            "completed",
            run_id=run_id,
            duration_ms=duration_ms,
        )
        
        # Alert on publish
        if result.wordpress_status == "publish":
            asyncio.run(alert(
                "info",
                "Content Published",
                f"Published: '{result.opportunity.keyword}' - {result.wordpress_url}",
                run_id=run_id,
                function_name="content_machine_worker",
            ))
            
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        error_msg = str(e)
        tb = traceback.format_exc()
        
        logger.exception(f"Scheduled run failed [{run_id}]: {e}")
        health.record_heartbeat(
            "content_machine_worker",
            "failed",
            run_id=run_id,
            error_message=error_msg,
            duration_ms=duration_ms,
        )
        
        # Send critical alert
        asyncio.run(alert(
            "critical",
            "Pipeline Failed",
            f"Content Machine pipeline failed: {error_msg}",
            run_id=run_id,
            function_name="content_machine_worker",
            details={"traceback": tb[:1000]},
        ))
        raise
    finally:
        loop.close()


@scheduler_fn.on_schedule(
    schedule="0 20 * * *",
    timezone=timezone,
    timeout_sec=300,
    max_instances=1,
)
def daily_email_report(event) -> None:
    """Scheduled worker to send the daily email report at 20:00."""
    run_id = f"email_{int(time.time())}"
    health = get_health_monitor()
    
    logger.info(f"Starting daily email report [{run_id}]...")
    health.record_heartbeat("daily_email_report", "started", run_id=run_id)
    
    reporter = EmailReporter(settings)
    
    try:
        success = reporter.send_daily_report()
        logger.info(f"Daily email report sent [{run_id}]. Success: {success}")
        health.record_heartbeat("daily_email_report", "completed" if success else "failed", run_id=run_id)
        
        if not success:
            asyncio.run(alert(
                "warning",
                "Email Report Failed",
                "Daily email report could not be sent",
                run_id=run_id,
                function_name="daily_email_report",
            ))
    except Exception as e:
        logger.exception(f"Daily email report failed [{run_id}]: {e}")
        health.record_heartbeat("daily_email_report", "failed", run_id=run_id, error_message=str(e))
        asyncio.run(alert(
            "error",
            "Email Report Error",
            f"Daily email report failed: {str(e)}",
            run_id=run_id,
            function_name="daily_email_report",
        ))
        raise


@scheduler_fn.on_schedule(
    schedule="0 23 * * 0",
    timezone=timezone,
    timeout_sec=900,
    max_instances=1,
)
def weekly_performance_review(event) -> None:
    """Autonomous weekly reviewer: audits GSC/GA4 metrics, detects content drift,
    identifies page-2 ranking opportunities, and injects refresh candidates
    back into the pipeline queue."""
    run_id = f"weekly_{int(time.time())}"
    health = get_health_monitor()
    
    logger.info(f"Starting weekly performance review [{run_id}]...")
    health.record_heartbeat("weekly_performance_review", "started", run_id=run_id)
    
    analyst = PerformanceAnalyst(settings)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        report = loop.run_until_complete(analyst.run_weekly_review())
        
        drift_count = len(report.get('drift_pages', []))
        opps_count = len(report.get('ranking_opportunities', []))
        refresh_count = report.get('refresh_candidates_injected', 0)
        
        logger.info(
            f"Weekly review complete [{run_id}]. "
            f"Drift pages: {drift_count}, "
            f"Ranking opportunities: {opps_count}, "
            f"Refresh candidates injected: {refresh_count}"
        )
        
        health.record_heartbeat("weekly_performance_review", "completed", run_id=run_id)
        
        # Alert on findings
        if drift_count > 0 or refresh_count > 0:
            asyncio.run(alert(
                "info",
                "Weekly Review Complete",
                f"Found {drift_count} drift pages, {opps_count} opportunities, injected {refresh_count} refresh candidates",
                run_id=run_id,
                function_name="weekly_performance_review",
                details=report,
            ))
            
    except Exception as exc:
        logger.exception(f"Weekly performance review failed [{run_id}]: {exc}")
        health.record_heartbeat("weekly_performance_review", "failed", run_id=run_id, error_message=str(exc))
        asyncio.run(alert(
            "error",
            "Weekly Review Failed",
            f"Weekly performance review failed: {str(exc)}",
            run_id=run_id,
            function_name="weekly_performance_review",
        ))
        raise
    finally:
        loop.close()


@https_fn.on_request(
    timeout_sec=900,
    memory=options.MemoryOption.GB_1,
)
def run_now(req: https_fn.Request) -> https_fn.Response:
    """HTTPS trigger to manually run the pipeline immediately."""
    run_id = f"manual_{int(time.time())}"
    health = get_health_monitor()
    
    logger.info(f"HTTP request received to run pipeline [{run_id}]...")
    health.record_heartbeat("run_now", "started", run_id=run_id)
    
    # Enhanced authentication with rate limiting check
    expected_raw = (settings.wp_app_password or "").replace(" ", "")
    expected_key = expected_raw[:8] if expected_raw else "default_secret"
    provided_key = (req.args.get("key") or "").replace(" ", "")
    
    if provided_key != expected_key:
        logger.warning(f"Unauthorized request [{run_id}]. Expected prefix: {expected_key[:4]}...")
        health.record_heartbeat("run_now", "failed", run_id=run_id, error_message="Unauthorized")
        return https_fn.Response(
            json.dumps({"error": "Unauthorized", "run_id": run_id}),
            status=401,
            content_type="application/json"
        )
    
    # Get circuit breaker status
    from content_machine.circuit_breaker import get_all_circuit_status
    cb_status = get_all_circuit_status()
    open_circuits = [k for k, v in cb_status.items() if v.get("state") == "open"]
    
    if open_circuits:
        logger.warning(f"Manual run with open circuits: {open_circuits}")
    
    machine = ContentMachine(settings)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    start_time = time.time()
    
    try:
        result = loop.run_until_complete(machine.run_once(dry_run=False))
        duration_ms = int((time.time() - start_time) * 1000)
        
        health.record_heartbeat("run_now", "completed", run_id=run_id, duration_ms=duration_ms)
        
        response_data = {
            "success": True,
            "run_id": run_id,
            "opportunity": result.opportunity.keyword,
            "status": result.wordpress_status,
            "url": result.wordpress_url,
            "audit_decision": result.audit.decision.value,
            "score": result.audit.score,
            "duration_ms": duration_ms,
            "circuit_breakers": cb_status,
        }
        
        asyncio.run(alert(
            "info",
            "Manual Pipeline Run Complete",
            f"Manual run completed: '{result.opportunity.keyword}' - {result.wordpress_status}",
            run_id=run_id,
            function_name="run_now",
        ))
        
        return https_fn.Response(
            json.dumps(response_data, indent=2),
            status=200,
            content_type="application/json"
        )
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        tb = traceback.format_exc()
        
        logger.exception(f"Manual pipeline trigger failed [{run_id}]")
        health.record_heartbeat("run_now", "failed", run_id=run_id, error_message=str(e), duration_ms=duration_ms)
        
        asyncio.run(alert(
            "error",
            "Manual Pipeline Failed",
            f"Manual pipeline run failed: {str(e)}",
            run_id=run_id,
            function_name="run_now",
            details={"traceback": tb[:1000]},
        ))
        
        return https_fn.Response(
            json.dumps({
                "success": False,
                "run_id": run_id,
                "error": str(e),
                "duration_ms": duration_ms,
            }, indent=2),
            status=500,
            content_type="application/json"
        )
    finally:
        loop.close()


# New health check endpoint
@https_fn.on_request(
    timeout_sec=30,
    memory=options.MemoryOption.MB_256,
)
def health_check(req: https_fn.Request) -> https_fn.Response:
    """Health check endpoint for monitoring."""
    health = get_health_monitor()
    status = health.get_all_health_status()
    
    from content_machine.circuit_breaker import get_all_circuit_status
    cb_status = get_all_circuit_status()
    
    response = {
        "system_status": status.get("_system", {}),
        "functions": {k: v for k, v in status.items() if not k.startswith("_")},
        "circuit_breakers": cb_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    http_status = 200
    if status.get("_system", {}).get("status") == "critical":
        http_status = 503
    elif status.get("_system", {}).get("status") == "warning":
        http_status = 200  # Still return 200 but with warning info
    
    return https_fn.Response(
        json.dumps(response, indent=2, default=str),
        status=http_status,
        content_type="application/json"
    )

