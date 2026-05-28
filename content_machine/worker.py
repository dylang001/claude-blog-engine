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


def start_worker() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()
    
    async def _run():
        scheduler = AsyncIOScheduler(timezone=settings.site.timezone)
        for slot in settings.site.publishing_slots:
            hour, minute = slot.split(":", 1)
            scheduler.add_job(
                lambda: asyncio.create_task(run_slot(dry_run=False)),
                CronTrigger(hour=int(hour), minute=int(minute), timezone=settings.site.timezone),
                id=f"publish-{slot}",
                replace_existing=True,
            )
        scheduler.start()
        logger.info("Content Machine worker started with slots: %s", ", ".join(settings.site.publishing_slots))
        
        # Keep the event loop running
        await asyncio.Event().wait()

    asyncio.run(_run())
