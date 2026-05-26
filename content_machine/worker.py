from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import load_settings
from .pipeline import ContentMachine

logger = logging.getLogger("content_machine.worker")


async def run_slot(dry_run: bool | None = None) -> None:
    settings = load_settings()
    missing = settings.missing_required()
    if missing and not (dry_run if dry_run is not None else settings.dry_run_default):
        raise RuntimeError(f"Missing required configuration: {', '.join(missing)}")
    result = await ContentMachine(settings).run_once(dry_run=dry_run)
    logger.info(
        "run_id=%s decision=%s status=%s keyword=%s score=%s",
        result.run_id,
        result.audit.decision.value,
        result.wordpress_status,
        result.opportunity.keyword,
        result.audit.score,
    )


async def run_daily_report() -> None:
    settings = load_settings()
    try:
        from .daily_report import compile_daily_report, send_daily_email_report
        logger.info("Triggering end-of-day daily summary report compilation...")
        report = await compile_daily_report(settings)
        send_daily_email_report(settings, report)
    except Exception as exc:
        logger.error("Failed to compile or send daily report: %s", exc)


async def run_outreach_cycle() -> None:
    settings = load_settings()
    try:
        from .outreach_agent import OutreachAgent
        logger.info("Triggering outreach cycle...")
        agent = OutreachAgent(settings)
        await agent.trigger_cron_job()
    except Exception as exc:
        logger.error("Failed to run outreach cycle: %s", exc)


def start_worker() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()
    scheduler = AsyncIOScheduler(timezone=settings.site.timezone)
    
    # Schedule article publishing slots
    for slot in settings.site.publishing_slots:
        hour, minute = slot.split(":", 1)
        scheduler.add_job(
            lambda: asyncio.create_task(run_slot(dry_run=False)),
            CronTrigger(hour=int(hour), minute=int(minute), timezone=settings.site.timezone),
            id=f"publish-{slot}",
            replace_existing=True,
        )
        
    # Schedule end of day summary email / report (runs at 17:00 daily in site timezone)
    scheduler.add_job(
        lambda: asyncio.create_task(run_daily_report()),
        CronTrigger(hour=17, minute=0, timezone=settings.site.timezone),
        id="daily-report-eod",
        replace_existing=True,
    )

    # Schedule daily outreach processing slot at 10:00 AM daily
    scheduler.add_job(
        lambda: asyncio.create_task(run_outreach_cycle()),
        CronTrigger(hour=10, minute=0, timezone=settings.site.timezone),
        id="outreach-process",
        replace_existing=True,
    )
    
    scheduler.start()
    logger.info(
        "Content Machine worker started. Slots: %s. Daily report scheduled at 17:00 %s. Outreach scheduled at 10:00 %s.",
        ", ".join(settings.site.publishing_slots),
        settings.site.timezone,
        settings.site.timezone
    )
    asyncio.get_event_loop().run_forever()
