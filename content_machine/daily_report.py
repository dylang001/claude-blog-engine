from __future__ import annotations

import json
import logging
import sqlite3
import smtplib
from pathlib import Path
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from .config import Settings
from .discovery import _run_ga4_report

logger = logging.getLogger("content_machine.daily_report")


def get_daily_metrics(db_path: Path, timezone_str: str) -> dict[str, Any]:
    """Retrieve run stats from SQLite db for today (in site's timezone) and last 24h."""
    # Find ZoneInfo for local time
    tz = None
    try:
        import zoneinfo
        if timezone_str:
            tz = zoneinfo.ZoneInfo(timezone_str)
    except Exception:
        pass

    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(tz) if tz else now_utc

    # Today boundary in local time, converted to UTC for DB matching
    if tz:
        start_of_today_local = datetime(now_local.year, now_local.month, now_local.day, 0, 0, 0, tzinfo=tz)
        start_of_today_utc = start_of_today_local.astimezone(timezone.utc)
    else:
        start_of_today_utc = datetime(now_utc.year, now_utc.month, now_utc.day, 0, 0, 0, tzinfo=timezone.utc)

    last_24h_utc = now_utc - timedelta(hours=24)

    metrics = {
        "today_local_date": now_local.strftime("%Y-%m-%d"),
        "timezone": timezone_str or "UTC",
        "today": _query_runs(db_path, start_of_today_utc.isoformat()),
        "last_24h": _query_runs(db_path, last_24h_utc.isoformat()),
    }
    return metrics


def _query_runs(db_path: Path, start_iso: str) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "total": 0,
            "published": 0,
            "drafts": 0,
            "blocked": 0,
            "failed": 0,
            "dry_run": 0,
            "runs": [],
        }

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT started_at, wordpress_status, wordpress_id, keyword, decision, payload_json 
            FROM runs 
            WHERE started_at >= ?
            ORDER BY started_at DESC
            """,
            (start_iso,),
        ).fetchall()
    except Exception as exc:
        logger.error("Failed to query runs database: %s", exc)
        rows = []
    finally:
        conn.close()

    published = 0
    drafts = 0
    blocked = 0
    failed = 0
    dry_run = 0
    runs_list = []

    for row in rows:
        status = row["wordpress_status"]
        if status == "publish":
            published += 1
        elif status == "draft":
            drafts += 1
        elif status == "blocked":
            blocked += 1
        elif status == "failed":
            failed += 1
        elif status == "dry_run":
            dry_run += 1

        payload = {}
        try:
            payload = json.loads(row["payload_json"])
        except Exception:
            pass

        runs_list.append({
            "started_at": row["started_at"],
            "keyword": row["keyword"] or payload.get("opportunity", {}).get("keyword", "Unknown Opportunity"),
            "wordpress_status": status,
            "wordpress_id": row["wordpress_id"],
            "decision": row["decision"] or payload.get("audit", {}).get("decision", "Unknown"),
            "score": payload.get("audit", {}).get("score", 0.0),
            "error": payload.get("error", ""),
        })

    return {
        "total": len(rows),
        "published": published,
        "drafts": drafts,
        "blocked": blocked,
        "failed": failed,
        "dry_run": dry_run,
        "runs": runs_list,
    }


async def compile_daily_report(settings: Settings) -> dict[str, Any]:
    """Fetch GA4 stats, SQLite metrics, and Next.js outreach stats to build a complete report structure."""
    # 1. Fetch runs metrics
    db_metrics = get_daily_metrics(settings.state_db, settings.site.timezone)

    # 2. Fetch GA4 metrics (yesterday and last 7 days)
    ga4_yesterday = {"ok": False, "error": "GA4 Property ID not set"}
    ga4_last7days = {"ok": False, "error": "GA4 Property ID not set"}

    if settings.ga4_property_id:
        try:
            ga4_yesterday = await _run_ga4_report(settings, days=1)
            ga4_yesterday["ok"] = True
        except Exception as exc:
            ga4_yesterday = {"ok": False, "error": str(exc)}

        try:
            ga4_last7days = await _run_ga4_report(settings, days=7)
            ga4_last7days["ok"] = True
        except Exception as exc:
            ga4_last7days = {"ok": False, "error": str(exc)}

    # 3. Fetch outreach stats from Next.js outbound agent
    outreach_stats = {"ok": False, "error": "Outbound Email Agent URL not set"}
    if settings.outbound_email_agent_url:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{settings.outbound_email_agent_url}/api/outreach/stats")
                if resp.status_code == 200:
                    outreach_stats = resp.json()
                    outreach_stats["ok"] = True
                else:
                    outreach_stats = {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as exc:
            outreach_stats = {"ok": False, "error": str(exc)}

    report = {
        "brand_name": settings.site.brand_name,
        "site_url": settings.site.site_url,
        "compiled_at": datetime.now(timezone.utc).isoformat(),
        "database": db_metrics,
        "ga4": {
            "yesterday": ga4_yesterday,
            "last_7_days": ga4_last7days,
        },
        "outreach": outreach_stats
    }
    return report


def build_email_body(report: dict[str, Any]) -> tuple[str, str]:
    """Build premium HTML and plain text email bodies."""
    brand = report["brand_name"]
    site_url = report["site_url"]
    date_str = report["database"]["today_local_date"]
    timezone_name = report["database"]["timezone"]

    today_stats = report["database"]["today"]
    last24h_stats = report["database"]["last_24h"]
    outreach = report.get("outreach", {})

    # Retrieve GA4 Totals
    yesterday_totals = report["ga4"]["yesterday"].get("totals", {}) if report["ga4"]["yesterday"].get("ok") else {}
    last7_totals = report["ga4"]["last_7_days"].get("totals", {}) if report["ga4"]["last_7_days"].get("ok") else {}

    # Helper for numbers
    def fmt_num(val) -> str:
        if val is None or val == "":
            return "0"
        try:
            return f"{int(val):,}"
        except Exception:
            return str(val)

    # 1. Plain Text Body
    text_lines = [
        f"=== {brand} Daily Content Engine Summary ===",
        f"Date: {date_str} (Timezone: {timezone_name})",
        f"Site: {site_url}",
        "",
        "--- TODAY'S RUN SUMMARY ---",
        f"Total Slots Triggered: {today_stats['total']}",
        f"  - Published: {today_stats['published']}",
        f"  - Drafts Saved: {today_stats['drafts']}",
        f"  - Blocked by Audit: {today_stats['blocked']}",
        f"  - Failed/Error: {today_stats['failed']}",
        f"  - Dry Runs: {today_stats['dry_run']}",
        "",
        "--- LAST 24 HOURS RUN SUMMARY ---",
        f"Total Runs: {last24h_stats['total']}",
        f"  - Published: {last24h_stats['published']}",
        f"  - Drafts Saved: {last24h_stats['drafts']}",
        f"  - Blocked by Audit: {last24h_stats['blocked']}",
        f"  - Failed/Error: {last24h_stats['failed']}",
        "",
        "--- COLD OUTREACH & BACKLINK STATS ---",
        f"Emails Sent Today: {fmt_num(outreach.get('emailsSentToday')) if outreach.get('ok') else 'N/A'}",
        f"Replies Received Today: {fmt_num(outreach.get('repliesReceivedToday')) if outreach.get('ok') else 'N/A'}",
        f"Unsubscribes / Spam: {fmt_num(outreach.get('unsubscribesToday')) if outreach.get('ok') else 'N/A'}",
        f"Active Prospects in Queue: {fmt_num(outreach.get('activeProspects')) if outreach.get('ok') else 'N/A'}",
        "",
        "--- GOOGLE ANALYTICS 4 STATS (ORGANIC SEARCH) ---",
        "Yesterday:",
        f"  - Sessions: {fmt_num(yesterday_totals.get('sessions'))}",
        f"  - Users: {fmt_num(yesterday_totals.get('users'))}",
        f"  - Pageviews: {fmt_num(yesterday_totals.get('pageviews'))}",
        "Last 7 Days:",
        f"  - Sessions: {fmt_num(last7_totals.get('sessions'))}",
        f"  - Users: {fmt_num(last7_totals.get('users'))}",
        f"  - Pageviews: {fmt_num(last7_totals.get('pageviews'))}",
        "",
        "--- TODAY'S RUN LIST ---"
    ]

    for i, r in enumerate(today_stats["runs"], 1):
        err_msg = f" (Error: {r['error'][:80]})" if r["error"] else ""
        text_lines.append(f"  {i}. Kw: {r['keyword']} | Status: {r['wordpress_status']} | Decision: {r['decision']} | Score: {r['score']}{err_msg}")

    text_body = "\n".join(text_lines)

    # 2. HTML Body (sleek, high-contrast slate dashboard)
    runs_html_rows = ""
    if not today_stats["runs"]:
        runs_html_rows = """
        <tr>
            <td colspan="4" style="padding: 16px; text-align: center; color: #94a3b8; font-style: italic;">
                No runs triggered today.
            </td>
        </tr>
        """
    else:
        for r in today_stats["runs"]:
            status = r["wordpress_status"]
            # Color coding for status
            if status == "publish":
                bg, text = "#dcfce7", "#166534"
            elif status == "draft":
                bg, text = "#fef9c3", "#854d0e"
            elif status == "blocked":
                bg, text = "#ffe4e6", "#991b1b"
            elif status == "failed":
                bg, text = "#fee2e2", "#991b1b"
            else:
                bg, text = "#f1f5f9", "#475569"

            error_cell = ""
            if r["error"]:
                error_cell = f"<div style='font-size: 11px; color: #ef4444; margin-top: 4px;'><strong>Error:</strong> {r['error']}</div>"

            runs_html_rows += f"""
            <tr style="border-bottom: 1px solid #f1f5f9;">
                <td style="padding: 12px; font-weight: 600; color: #1e293b;">
                    {r['keyword']}
                </td>
                <td style="padding: 12px;">
                    <span style="background-color: {bg}; color: {text}; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; text-transform: uppercase;">
                        {status}
                    </span>
                    {error_cell}
                </td>
                <td style="padding: 12px; font-weight: 500; color: #475569;">
                    {r['decision']}
                </td>
                <td style="padding: 12px; font-weight: 600; color: #4f46e5; text-align: right;">
                    {r['score']:.1f}
                </td>
            </tr>
            """

    ga4_block = ""
    if report["ga4"]["yesterday"].get("ok") or report["ga4"]["last_7_days"].get("ok"):
        ga4_block = f"""
        <h3 style="margin-top: 32px; color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">📊 Organic Search Performance (GA4)</h3>
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 24px;">
            <tr>
                <!-- Yesterday Stats Card -->
                <td width="48%" valign="top" style="background-color: #f8fafc; padding: 18px; border-radius: 8px; border: 1px solid #e2e8f0;">
                    <h4 style="margin: 0 0 12px 0; color: #475569; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">Yesterday's Traffic</h4>
                    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="text-align: center;">
                        <tr>
                            <td width="33%">
                                <div style="font-size: 18px; font-weight: 700; color: #0f172a;">{fmt_num(yesterday_totals.get('sessions'))}</div>
                                <div style="font-size: 10px; color: #64748b; margin-top: 4px;">Sessions</div>
                            </td>
                            <td width="33%">
                                <div style="font-size: 18px; font-weight: 700; color: #0f172a;">{fmt_num(yesterday_totals.get('users'))}</div>
                                <div style="font-size: 10px; color: #64748b; margin-top: 4px;">Users</div>
                            </td>
                            <td width="33%">
                                <div style="font-size: 18px; font-weight: 700; color: #0f172a;">{fmt_num(yesterday_totals.get('pageviews'))}</div>
                                <div style="font-size: 10px; color: #64748b; margin-top: 4px;">Views</div>
                            </td>
                        </tr>
                    </table>
                </td>
                <td width="4%">&nbsp;</td>
                <!-- Last 7 Days Traffic Card -->
                <td width="48%" valign="top" style="background-color: #f0fdf4; padding: 18px; border-radius: 8px; border: 1px solid #bbf7d0;">
                    <h4 style="margin: 0 0 12px 0; color: #166534; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">Last 7 Days Traffic</h4>
                    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="text-align: center;">
                        <tr>
                            <td width="33%">
                                <div style="font-size: 18px; font-weight: 700; color: #14532d;">{fmt_num(last7_totals.get('sessions'))}</div>
                                <div style="font-size: 10px; color: #15803d; margin-top: 4px;">Sessions</div>
                            </td>
                            <td width="33%">
                                <div style="font-size: 18px; font-weight: 700; color: #14532d;">{fmt_num(last7_totals.get('users'))}</div>
                                <div style="font-size: 10px; color: #15803d; margin-top: 4px;">Users</div>
                            </td>
                            <td width="33%">
                                <div style="font-size: 18px; font-weight: 700; color: #14532d;">{fmt_num(last7_totals.get('pageviews'))}</div>
                                <div style="font-size: 10px; color: #15803d; margin-top: 4px;">Views</div>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
        """
    else:
        ga4_block = f"""
        <h3 style="margin-top: 32px; color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">📊 Organic Search Performance (GA4)</h3>
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 24px; text-align: center;">
            <tr>
                <td style="padding: 16px; color: #64748b; font-style: italic;">
                    Google Analytics 4 is not configured or failed to connect.<br/>
                    <span style="font-size: 11px; color: #94a3b8; font-family: monospace;">{report["ga4"]["yesterday"].get("error")}</span>
                </td>
            </tr>
        </table>
        """

    outreach_block = ""
    if outreach.get("ok"):
        outreach_block = f"""
        <h3 style="margin-top: 32px; color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">✉️ Cold Outreach & Backlink Campaigns</h3>
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 24px;">
            <tr>
                <!-- Sent Card -->
                <td width="23.5%" style="background-color: #f8fafc; padding: 18px; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;">
                    <div style="font-size: 20px; font-weight: 800; color: #0f172a; line-height: 1.2;">{fmt_num(outreach.get('emailsSentToday'))}</div>
                    <div style="font-size: 10px; color: #64748b; margin-top: 4px; font-weight: 600;">Sent Today</div>
                </td>
                <td width="2%">&nbsp;</td>
                <!-- Replies Card -->
                <td width="23.5%" style="background-color: #f0fdf4; padding: 18px; border-radius: 8px; border: 1px solid #bbf7d0; text-align: center;">
                    <div style="font-size: 20px; font-weight: 800; color: #166534; line-height: 1.2;">{fmt_num(outreach.get('repliesReceivedToday'))}</div>
                    <div style="font-size: 10px; color: #15803d; margin-top: 4px; font-weight: 600;">Replies</div>
                </td>
                <td width="2%">&nbsp;</td>
                <!-- Unsub/Spam Card -->
                <td width="23.5%" style="background-color: #fee2e2; padding: 18px; border-radius: 8px; border: 1px solid #fca5a5; text-align: center;">
                    <div style="font-size: 20px; font-weight: 800; color: #991b1b; line-height: 1.2;">{fmt_num(outreach.get('unsubscribesToday'))}</div>
                    <div style="font-size: 10px; color: #b91c1c; margin-top: 4px; font-weight: 600;">Unsubs / Spam</div>
                </td>
                <td width="2%">&nbsp;</td>
                <!-- Active Prospects Card -->
                <td width="23.5%" style="background-color: #f8fafc; padding: 18px; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;">
                    <div style="font-size: 20px; font-weight: 800; color: #475569; line-height: 1.2;">{fmt_num(outreach.get('activeProspects'))}</div>
                    <div style="font-size: 10px; color: #64748b; margin-top: 4px; font-weight: 600;">Active Prospects</div>
                </td>
            </tr>
        </table>
        """
    else:
        outreach_block = f"""
        <h3 style="margin-top: 32px; color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">✉️ Cold Outreach & Backlink Campaigns</h3>
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 24px; text-align: center;">
            <tr>
                <td style="padding: 16px; color: #64748b; font-style: italic;">
                    Outbound Email Agent is not configured or failed to connect.<br/>
                    <span style="font-size: 11px; color: #94a3b8; font-family: monospace;">{outreach.get('error', 'URL empty')}</span>
                </td>
            </tr>
        </table>
        """

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{brand} SEO Content Machine Daily Report</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; padding: 24px; margin: 0;">
        <div style="max-width: 680px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1); overflow: hidden;">
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 32px 24px; text-align: center; color: #ffffff;">
                <h1 style="margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -0.5px;">{brand} Content Machine</h1>
                <p style="margin: 8px 0 0 0; color: #94a3b8; font-size: 14px;">Daily Execution & Analytics Summary</p>
                <div style="display: inline-block; margin-top: 16px; background-color: #3b82f6; color: #ffffff; padding: 4px 12px; border-radius: 100px; font-size: 12px; font-weight: 600;">
                    {date_str} ({timezone_name})
                </div>
            </div>

            <!-- Content Area -->
            <div style="padding: 24px;">
                <!-- High Level Slots Counter -->
                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 24px;">
                    <tr>
                        <td width="23%" style="background-color: #f8fafc; padding: 12px; border-radius: 6px; text-align: center; border: 1px solid #f1f5f9;">
                            <div style="font-size: 24px; font-weight: 800; color: #0f172a; line-height: 1.2;">{today_stats['total']}</div>
                            <div style="font-size: 11px; color: #64748b; margin-top: 4px; font-weight: 600;">Slots Run</div>
                        </td>
                        <td width="2%">&nbsp;</td>
                        <td width="23%" style="background-color: #f0fdf4; padding: 12px; border-radius: 6px; text-align: center; border: 1px solid #dcfce7;">
                            <div style="font-size: 24px; font-weight: 800; color: #166534; line-height: 1.2;">{today_stats['published']}</div>
                            <div style="font-size: 11px; color: #15803d; margin-top: 4px; font-weight: 600;">Published</div>
                        </td>
                        <td width="2%">&nbsp;</td>
                        <td width="23%" style="background-color: #fefdf0; padding: 12px; border-radius: 6px; text-align: center; border: 1px solid #fef9c3;">
                            <div style="font-size: 24px; font-weight: 800; color: #854d0e; line-height: 1.2;">{today_stats['drafts']}</div>
                            <div style="font-size: 11px; color: #a16207; margin-top: 4px; font-weight: 600;">Drafts</div>
                        </td>
                        <td width="2%">&nbsp;</td>
                        <td width="23%" style="background-color: #fef2f2; padding: 12px; border-radius: 6px; text-align: center; border: 1px solid #fee2e2;">
                            <div style="font-size: 24px; font-weight: 800; color: #991b1b; line-height: 1.2;">{today_stats['failed'] + today_stats['blocked']}</div>
                            <div style="font-size: 11px; color: #b91c1c; margin-top: 4px; font-weight: 600;">Failed/Blocked</div>
                        </td>
                    </tr>
                </table>

                <!-- GA4 Block -->
                {ga4_block}

                <!-- Outreach Block -->
                {outreach_block}

                <!-- Today's Runs list -->
                <h3 style="margin-top: 32px; color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">📋 Publishing Operations List</h3>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse; text-align: left;">
                        <thead>
                            <tr style="border-bottom: 2px solid #f1f5f9;">
                                <th style="padding: 12px; font-size: 12px; text-transform: uppercase; color: #64748b;">Keyword</th>
                                <th style="padding: 12px; font-size: 12px; text-transform: uppercase; color: #64748b;">Status</th>
                                <th style="padding: 12px; font-size: 12px; text-transform: uppercase; color: #64748b;">Decision</th>
                                <th style="padding: 12px; font-size: 12px; text-transform: uppercase; color: #64748b; text-align: right;">SEO Score</th>
                            </tr>
                        </thead>
                        <tbody>
                            {runs_html_rows}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Footer -->
            <div style="background-color: #f8fafc; padding: 24px; text-align: center; border-top: 1px solid #e2e8f0; font-size: 12px; color: #64748b;">
                This report was compiled and sent automatically by the <strong>{brand} SEO Content Machine</strong>.<br/>
                For settings and updates, check <a href="{site_url}" style="color: #4f46e5; text-decoration: none; font-weight: 500;">{site_url}</a>.
            </div>
        </div>
    </body>
    </html>
    """

    return html_body, text_body


def send_daily_email_report(settings: Settings, report: dict[str, Any]) -> bool:
    """Send compiled daily report email if SMTP is configured."""
    if not settings.smtp_host or not settings.smtp_username:
        logger.info("SMTP settings not fully configured (SMTP_HOST/SMTP_USERNAME is empty). Skipping email send.")
        return False

    date_str = report["database"]["today_local_date"]
    to_email = settings.smtp_to or settings.smtp_username
    from_email = settings.smtp_from or settings.smtp_username

    html_body, text_body = build_email_body(report)

    # Compile recipient list. Send to smtp_to and also dylanangloher@gmail.com
    recipients = [to_email]
    if "dylanangloher@gmail.com" not in [r.strip().lower() for r in recipients]:
        recipients.append("dylanangloher@gmail.com")

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"MeetLyra SEO Content Machine — Daily Report ({date_str})"
    msg['From'] = from_email
    msg['To'] = ", ".join(recipients)

    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    logger.info("Connecting to SMTP server %s:%s...", settings.smtp_host, settings.smtp_port)
    try:
        if settings.smtp_port == 465:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()

        if settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)

        server.sendmail(from_email, recipients, msg.as_string())
        server.quit()
        logger.info("Daily report email sent successfully to %s", recipients)
        return True
    except Exception as exc:
        logger.error("Failed to send daily report email via SMTP: %s", exc)
        return False
