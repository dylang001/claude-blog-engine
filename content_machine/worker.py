from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import load_settings
from .pipeline import ContentMachine

logger = logging.getLogger("content_machine.worker")


# =============================================================================
# DAILY TASKS
# =============================================================================

async def run_slot(dry_run: bool | None = None) -> None:
    """Generate and publish a blog article slot."""
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
    """Compile and email the 17:00 SAST daily operations summary."""
    settings = load_settings()
    try:
        from .daily_report import compile_daily_report, send_daily_email_report
        logger.info("Triggering end-of-day daily summary report compilation...")
        report = await compile_daily_report(settings)
        send_daily_email_report(settings, report)
    except Exception as exc:
        logger.error("Failed to compile or send daily report: %s", exc)


async def run_outreach_cycle() -> None:
    """Trigger Next.js cron to process pending SMTP sends and scan IMAP replies."""
    settings = load_settings()
    try:
        from .outreach_agent import OutreachAgent
        logger.info("Triggering outreach cycle...")
        agent = OutreachAgent(settings)
        await agent.trigger_cron_job()
    except Exception as exc:
        logger.error("Failed to run outreach cycle: %s", exc)


# =============================================================================
# WEEKLY TASKS (Sunday 08:00 SAST)
# =============================================================================

async def run_weekly_seo_sync() -> None:
    """Weekly: Pull GSC + GA4 data, sync to SuperMemory, run content refresh audit,
    run DataForSEO discovery for next 14 topics, run OpenSEO keyword research."""
    settings = load_settings()
    logger.info("Starting weekly SEO intelligence sync...")

    from .supermemory import SuperMemoryClient
    sm = SuperMemoryClient(settings)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # -- 1. Pull GSC data and sync to SuperMemory --
    try:
        from .discovery import _run_gsc_query
        logger.info("Pulling Google Search Console data (last 28 days)...")
        rows, auth_mode = await _run_gsc_query(settings, days=28)
        if rows:
            await sm.push_gsc_keywords(f"{today} (last 28 days)", rows)
            # Push quick wins separately for easy retrieval
            quick_wins = [r for r in rows if 4 <= float(r.get("position", 99)) <= 20]
            if quick_wins:
                await sm.push_gsc_quick_wins(quick_wins)
            logger.info("GSC data pushed to SuperMemory. %d rows, %d quick wins.", len(rows), len(quick_wins))
    except Exception as exc:
        logger.error("Failed to pull/push GSC data: %s", exc)

    # -- 2. Pull GA4 article performance and sync to SuperMemory --
    try:
        from .discovery import _run_ga4_report
        logger.info("Pulling GA4 article performance (last 7 days)...")
        ga4 = await _run_ga4_report(settings, days=7)
        top_pages = ga4.get("rows", [])
        if top_pages:
            await sm.push_article_performance(f"{today} (last 7 days)", top_pages)
            logger.info("GA4 performance data pushed to SuperMemory. %d page rows.", len(top_pages))
    except Exception as exc:
        logger.error("Failed to pull/push GA4 data: %s", exc)

    # -- 3. Run content refresh audit (identifies stale posts / quick-win opportunities) --
    try:
        from .content_refresh import ContentRefreshAuditor
        logger.info("Running content refresh SEO audit...")
        auditor = ContentRefreshAuditor(settings)
        audit_result = await auditor.run()
        logger.info(
            "Content refresh audit finished. %d candidates. Top 5 flagged in SuperMemory.",
            audit_result.get("refresh_candidates", 0),
        )
    except Exception as exc:
        logger.error("Failed to run content refresh audit: %s", exc)

    # -- 4. Run DataForSEO keyword discovery for next 14 topic slots --
    try:
        from .discovery import DiscoveryReporter
        logger.info("Running DataForSEO keyword discovery for next week's topics...")
        reporter = DiscoveryReporter(settings)
        discovery = await reporter.run(limit=14, days=28)
        # Sync top keyword opportunities to SuperMemory
        opportunities = discovery.get("opportunities", [])
        keyword_data = [
            {"keyword": opp.get("keyword"), "opportunity_score": opp.get("score"), "funnel": opp.get("kind"), "volume": opp.get("volume"), "kd": opp.get("kd")}
            for opp in opportunities
        ]
        if keyword_data:
            await sm.push_keyword_plan(today, keyword_data)
            logger.info("Next week's %d keyword targets pushed to SuperMemory.", len(keyword_data))
    except Exception as exc:
        logger.error("Failed to run keyword discovery or push to SuperMemory: %s", exc)

    # -- 5. Ping OpenSEO for competitor keyword insights --
    try:
        if settings.open_seo_url:
            import httpx as _httpx
            logger.info("Triggering OpenSEO competitive keyword scan...")
            async with _httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{settings.open_seo_url}/api/competitor-keywords",
                    json={"site": settings.site.site_url, "competitors": settings.site.competitors[:3]},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for comp in data.get("results", []):
                        domain = comp.get("domain", "unknown")
                        kws = comp.get("keywords", [])
                        if kws:
                            await sm.push_competitor_keywords(domain, kws)
                            logger.info("Pushed %d competitor keywords for %s to SuperMemory.", len(kws), domain)
                else:
                    logger.warning("OpenSEO competitor scan returned: %d", resp.status_code)
    except Exception as exc:
        logger.error("Failed to run OpenSEO competitor scan: %s", exc)

    logger.info("Weekly SEO intelligence sync complete.")


# =============================================================================
# MONTHLY TASKS (1st of month, 02:00 SAST)
# =============================================================================

async def run_monthly_report() -> None:
    """Monthly: Compile GA4 ROI report, backlink counts, domain authority,
    and email a strategic PDF-formatted summary to Dylan."""
    settings = load_settings()
    logger.info("Starting monthly strategic performance report...")
    today = datetime.now(timezone.utc).strftime("%Y-%m")

    from .supermemory import SuperMemoryClient
    sm = SuperMemoryClient(settings)

    # -- 1. Collect 30-day GA4 traffic data --
    ga4_30 = {}
    try:
        from .discovery import _run_ga4_report
        ga4_30 = await _run_ga4_report(settings, days=30)
        logger.info("Monthly GA4 data collected.")
    except Exception as exc:
        logger.error("Monthly GA4 pull failed: %s", exc)

    # -- 2. Collect 30-day GSC data --
    gsc_rows = []
    try:
        from .discovery import _run_gsc_query
        gsc_rows, _ = await _run_gsc_query(settings, days=30)
        logger.info("Monthly GSC data collected. %d rows.", len(gsc_rows))
        if gsc_rows:
            await sm.push_gsc_keywords(f"{today} (30-day monthly)", gsc_rows)
    except Exception as exc:
        logger.error("Monthly GSC pull failed: %s", exc)

    # -- 3. Compile monthly email to Dylan --
    try:
        from .daily_report import send_daily_email_report
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from pathlib import Path

        ga4_totals = ga4_30.get("totals", {})
        gsc_top = gsc_rows[:10]
        gsc_text = "\n".join([
            f"  #{i+1}  {r.get('query', '')} — Pos {r.get('position', '')} | {r.get('clicks', '')} clicks"
            for i, r in enumerate(gsc_top)
        ])

        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>MeetLyra Monthly SEO Report — {today}</title></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f1f5f9;padding:24px;margin:0;">
  <div style="max-width:680px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 6px rgba(0,0,0,.1);">
    <div style="background:linear-gradient(135deg,#0f172a,#1e293b);padding:32px 24px;text-align:center;color:#fff;">
      <h1 style="margin:0;font-size:22px;font-weight:800;">MeetLyra — Monthly SEO Report</h1>
      <p style="margin:8px 0 0;color:#94a3b8;font-size:14px;">Compiled automatically by the Content Machine</p>
      <div style="display:inline-block;margin-top:12px;background:#3b82f6;color:#fff;padding:4px 12px;border-radius:100px;font-size:12px;font-weight:600;">{today}</div>
    </div>
    <div style="padding:24px;">
      <h3 style="color:#0f172a;border-bottom:2px solid #e2e8f0;padding-bottom:8px;">📊 30-Day Organic Performance (GA4)</h3>
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
        <tr>
          <td width="30%" style="background:#f0fdf4;padding:18px;border-radius:8px;border:1px solid #bbf7d0;text-align:center;">
            <div style="font-size:28px;font-weight:800;color:#14532d;">{int(ga4_totals.get('sessions', 0)):,}</div>
            <div style="font-size:11px;color:#15803d;margin-top:4px;font-weight:600;">SESSIONS</div>
          </td>
          <td width="4%">&nbsp;</td>
          <td width="30%" style="background:#f8fafc;padding:18px;border-radius:8px;border:1px solid #e2e8f0;text-align:center;">
            <div style="font-size:28px;font-weight:800;color:#0f172a;">{int(ga4_totals.get('users', 0)):,}</div>
            <div style="font-size:11px;color:#64748b;margin-top:4px;font-weight:600;">USERS</div>
          </td>
          <td width="4%">&nbsp;</td>
          <td width="30%" style="background:#f8fafc;padding:18px;border-radius:8px;border:1px solid #e2e8f0;text-align:center;">
            <div style="font-size:28px;font-weight:800;color:#0f172a;">{int(ga4_totals.get('pageviews', 0)):,}</div>
            <div style="font-size:11px;color:#64748b;margin-top:4px;font-weight:600;">PAGEVIEWS</div>
          </td>
        </tr>
      </table>
      <h3 style="color:#0f172a;border-bottom:2px solid #e2e8f0;padding-bottom:8px;">🔍 Top 10 GSC Keywords (30 Days)</h3>
      <pre style="background:#f8fafc;padding:16px;border-radius:8px;font-size:12px;color:#334155;overflow-x:auto;">{gsc_text}</pre>
      <h3 style="color:#0f172a;border-bottom:2px solid #e2e8f0;padding-bottom:8px;">🧠 Intelligence Notes</h3>
      <p style="color:#475569;font-size:14px;">All performance data, keyword opportunities, content gaps, and outreach logs are continuously synced to the SuperMemory knowledge graph. This ensures every new article and email campaign is informed by the full context of what is working and what needs improvement.</p>
    </div>
    <div style="background:#f8fafc;padding:24px;text-align:center;border-top:1px solid #e2e8f0;font-size:12px;color:#64748b;">
      Sent automatically by the MeetLyra SEO Content Machine. Site: <a href="{settings.site.site_url}" style="color:#4f46e5;">{settings.site.site_url}</a>
    </div>
  </div>
</body>
</html>"""

        if not settings.smtp_host or not settings.smtp_username:
            logger.info("SMTP not configured. Skipping monthly report email.")
            return

        recipients = [settings.smtp_to or settings.smtp_username, "dylanangloher@gmail.com"]
        recipients = list(dict.fromkeys(r for r in recipients if r))

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"MeetLyra Monthly SEO Report — {today}"
        msg["From"] = settings.smtp_from or settings.smtp_username
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(f"MeetLyra Monthly SEO Report - {today}\n\nSessions: {ga4_totals.get('sessions', 0)}\nUsers: {ga4_totals.get('users', 0)}", "plain"))
        msg.attach(MIMEText(html, "html"))

        if settings.smtp_port == 465:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()

        if settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(msg["From"], recipients, msg.as_string())
        server.quit()
        logger.info("Monthly report emailed to: %s", recipients)

    except Exception as exc:
        logger.error("Failed to send monthly report: %s", exc)

    logger.info("Monthly strategic report complete.")


# =============================================================================
# SCHEDULER SETUP
# =============================================================================

def start_worker() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()
    scheduler = AsyncIOScheduler(timezone=settings.site.timezone)

    # ---- Daily: Article publishing slots (09:00 and 15:00 SAST) ----
    for slot in settings.site.publishing_slots:
        hour, minute = slot.split(":", 1)
        slot_hour = int(hour)
        slot_minute = int(minute)
        scheduler.add_job(
            lambda h=slot_hour, m=slot_minute: asyncio.create_task(run_slot(dry_run=False)),
            CronTrigger(hour=slot_hour, minute=slot_minute, timezone=settings.site.timezone),
            id=f"publish-{slot}",
            replace_existing=True,
        )

    # ---- Daily: Outreach SMTP + IMAP cycle (10:00 SAST) ----
    scheduler.add_job(
        lambda: asyncio.create_task(run_outreach_cycle()),
        CronTrigger(hour=10, minute=0, timezone=settings.site.timezone),
        id="outreach-process",
        replace_existing=True,
    )

    # ---- Daily: EOD summary email (17:00 SAST) ----
    scheduler.add_job(
        lambda: asyncio.create_task(run_daily_report()),
        CronTrigger(hour=17, minute=0, timezone=settings.site.timezone),
        id="daily-report-eod",
        replace_existing=True,
    )

    # ---- Weekly: Sunday 08:00 SAST — GSC/GA4 sync, content refresh audit, discovery ----
    scheduler.add_job(
        lambda: asyncio.create_task(run_weekly_seo_sync()),
        CronTrigger(day_of_week="sun", hour=8, minute=0, timezone=settings.site.timezone),
        id="weekly-seo-sync",
        replace_existing=True,
    )

    # ---- Monthly: 1st of month 02:00 SAST — ROI + domain authority report ----
    scheduler.add_job(
        lambda: asyncio.create_task(run_monthly_report()),
        CronTrigger(day=1, hour=2, minute=0, timezone=settings.site.timezone),
        id="monthly-report",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Content Machine worker started.\n"
        "  DAILY:   Article slots %s | Outreach 10:00 | EOD report 17:00 (%s)\n"
        "  WEEKLY:  SEO sync + content refresh audit — Sunday 08:00 (%s)\n"
        "  MONTHLY: Strategic report — 1st of month 02:00 (%s)",
        ", ".join(settings.site.publishing_slots),
        settings.site.timezone,
        settings.site.timezone,
        settings.site.timezone,
    )
    asyncio.get_event_loop().run_forever()
