from __future__ import annotations

import asyncio
import json
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from typing import Any
from .config import Settings
from .state import StateStore

logger = logging.getLogger(__name__)


async def _gemini_strategic_summary(settings: Settings, runs: list[dict[str, Any]]) -> str:
    """Ask Gemini to write a 2-paragraph strategic digest of today's publishing activity."""
    if not settings.gemini_api_key or not runs:
        return ""
    try:
        import httpx
        posts_summary = "\n".join(
            f"- '{r.get('content', {}).get('title', r.get('opportunity', {}).get('keyword', 'N/A'))}' "
            f"(keyword: {r.get('opportunity', {}).get('keyword', 'N/A')}, "
            f"kind: {r.get('opportunity', {}).get('kind', 'N/A')}, "
            f"score: {r.get('audit', {}).get('score', 0):.1f}, "
            f"status: {r.get('wordpress_status', 'unknown')})"
            for r in runs
        )
        prompt = (
            f"You are the editorial strategist for MeetLyra's autonomous SEO content machine. "
            f"Today's autonomous content engine published the following articles:\n\n{posts_summary}\n\n"
            f"Write exactly 2 short paragraphs (max 60 words each) for the founder's daily email:\n"
            f"Paragraph 1: What topics were covered today and why they are strategically relevant to MeetLyra's target audience (B2B SaaS operators and marketers).\n"
            f"Paragraph 2: The quality outlook — average audit score, any draft vs. published distribution, and one actionable recommendation for tomorrow's content strategy.\n"
            f"Be specific, professional, and concise. No fluff."
        )
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}"
            f":generateContent?key={settings.gemini_api_key}"
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 512},
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers={"content-type": "application/json"}, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as exc:
        logger.warning(f"Gemini strategic summary failed: {exc}")
    return ""


class EmailReporter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = StateStore(settings.state_db, settings=settings)

    def generate_html_report(self, runs: list[dict[str, Any]], ai_summary: str = "") -> str:
        rows_html = ""
        if not runs:
            rows_html = """
            <tr>
                <td colspan="5" style="padding: 15px; text-align: center; color: #6b7280; font-style: italic;">
                    No pipeline runs recorded in the last 24 hours.
                </td>
            </tr>
            """
        else:
            for run in runs:
                status = run.get("wordpress_status", "unknown")
                status_color = "#10b981"  # green
                if status in ["blocked", "failed", "error"]:
                    status_color = "#ef4444"  # red
                elif status in ["draft", "dry_run"]:
                    status_color = "#f59e0b"  # yellow

                wp_url = run.get("wordpress_url")
                wp_id = run.get("wordpress_id")
                view_link = f'<a href="{wp_url}" style="color: #3b82f6;">View</a>' if wp_url else ""
                # Build WP admin edit link
                wp_base = run.get("settings_wp_base_url", "")
                edit_link = ""
                if wp_id and wp_base:
                    edit_link = f' &bull; <a href="{wp_base}/wp-admin/post.php?post={wp_id}&action=edit" style="color: #6366f1;">Edit</a>'
                link_html = (view_link + edit_link) if (view_link or edit_link) else "N/A"

                opp = run.get("opportunity", {})
                keyword = opp.get("keyword", "N/A")
                kind = opp.get("kind", "N/A")
                title = run.get("content", {}).get("title") or keyword

                audit = run.get("audit", {})
                audit_details = audit.get("details", {})
                score = audit.get("score", 0.0)
                decision = audit.get("decision", "N/A")
                word_count = audit_details.get("word_count", "—")
                internal_links = audit_details.get("internal_link_count", "—")
                issues = audit.get("issues", [])
                issue_html = ""
                if issues:
                    issue_html = (
                        '<br><span style="color:#ef4444;font-size:11px;">'
                        + " · ".join(issues[:2])
                        + (" +more" if len(issues) > 2 else "")
                        + "</span>"
                    )

                # Fetch distribution assets and backlinks for this post
                article_id = wp_id or run.get("content", {}).get("slug")
                syndicated_html = ""
                backlinks_html = ""
                if article_id:
                    try:
                        assets = self.store.get_distribution_assets(str(article_id))
                        if assets:
                            asset_links = []
                            for a in assets:
                                plat = a.get("platform", "N/A").title()
                                p_url = a.get("published_url")
                                p_status = a.get("status", "unknown")
                                if p_url:
                                    asset_links.append(f'<a href="{p_url}" style="color:#059669;text-decoration:none;">{plat} ({p_status})</a>')
                                else:
                                    asset_links.append(f'<span style="color:#6b7280;">{plat} ({p_status})</span>')
                            syndicated_html = '<div style="margin-top:4px;font-size:11px;color:#059669;">Syndicated: ' + " | ".join(asset_links) + '</div>'
                    except Exception as e:
                        logger.error(f"Error reading distribution assets for email: {e}")

                    try:
                        backlink_targets = self.store.get_backlink_targets(str(article_id))
                        if backlink_targets:
                            target_list = []
                            for b in backlink_targets:
                                site = b.get("target_site", "N/A")
                                name = b.get("contact_name") or "Editor"
                                email = b.get("contact_email") or "N/A"
                                target_list.append(f'{site} ({name} &lt;{email}&gt;)')
                            backlinks_html = '<div style="margin-top:4px;font-size:11px;color:#4b5563;">Backlink Targets: ' + ", ".join(target_list[:3]) + ('...' if len(target_list) > 3 else '') + '</div>'
                    except Exception as e:
                        logger.error(f"Error reading backlink targets for email: {e}")

                rows_html += f"""
                <tr style="border-bottom: 1px solid #e5e7eb;">
                    <td style="padding: 12px; font-weight: 500; color: #1f2937; font-size: 13px;">{title}{issue_html}{syndicated_html}{backlinks_html}</td>
                    <td style="padding: 12px; color: #4b5563; text-transform: uppercase; font-size: 11px;">{kind}</td>
                    <td style="padding: 12px; color: #374151; font-size: 13px;">{score:.1f}<br><span style="font-size:11px;color:#9ca3af;">{word_count}w · {internal_links} int. links</span></td>
                    <td style="padding: 12px;"><span style="background-color: {status_color}20; color: {status_color}; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; text-transform: uppercase;">{status}</span></td>
                    <td style="padding: 12px; font-size: 13px;">{link_html}</td>
                </tr>
                """

        # AI summary block
        ai_block = ""
        if ai_summary:
            # Convert newlines to paragraphs
            paragraphs = [p.strip() for p in ai_summary.split("\n") if p.strip()]
            ai_block = "".join(f'<p style="margin: 0 0 12px 0; color: #374151; line-height: 1.65; font-size: 15px;">{p}</p>' for p in paragraphs)
            ai_block = f"""
            <div style="background: linear-gradient(135deg, #eef2ff, #f5f3ff); border-left: 4px solid #6366f1; border-radius: 6px; padding: 20px 24px; margin-bottom: 24px;">
                <p style="margin: 0 0 8px 0; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #6366f1;">AI Strategic Digest</p>
                {ai_block}
            </div>
            """

        # Stats row
        published_count = sum(1 for r in runs if r.get("wordpress_status") == "publish")
        draft_count = sum(1 for r in runs if r.get("wordpress_status") == "draft")
        blocked_count = sum(1 for r in runs if r.get("wordpress_status") in ["blocked", "failed"])
        avg_score = (sum(r.get("audit", {}).get("score", 0) for r in runs) / len(runs)) if runs else 0

        # Query syndicated posts and backlinks from the runs
        syndicated_count = 0
        backlinks_created_count = 0
        for r in runs:
            wp_id = r.get("wordpress_id")
            article_id = wp_id or r.get("content", {}).get("slug")
            if article_id:
                try:
                    assets = self.store.get_distribution_assets(str(article_id))
                    syndicated_count += sum(1 for a in assets if a.get("status") in ["published", "draft"])
                except Exception:
                    pass
                try:
                    bts = self.store.get_backlink_targets(str(article_id))
                    backlinks_created_count += len(bts)
                except Exception:
                    pass

        stats_block = f"""
        <div style="display:flex; gap:16px; margin-bottom:24px; flex-wrap:wrap;">
            <div style="flex:1; min-width:120px; background:#f0fdf4; border-radius:8px; padding:16px; text-align:center;">
                <div style="font-size:28px; font-weight:800; color:#16a34a;">{published_count}</div>
                <div style="font-size:12px; color:#15803d; font-weight:600;">Published</div>
            </div>
            <div style="flex:1; min-width:120px; background:#fffbeb; border-radius:8px; padding:16px; text-align:center;">
                <div style="font-size:28px; font-weight:800; color:#d97706;">{draft_count}</div>
                <div style="font-size:12px; color:#b45309; font-weight:600;">Drafts</div>
            </div>
            <div style="flex:1; min-width:120px; background:#fef2f2; border-radius:8px; padding:16px; text-align:center;">
                <div style="font-size:28px; font-weight:800; color:#dc2626;">{blocked_count}</div>
                <div style="font-size:12px; color:#b91c1c; font-weight:600;">Blocked</div>
            </div>
            <div style="flex:1; min-width:120px; background:#ecfdf5; border-radius:8px; padding:16px; text-align:center;">
                <div style="font-size:28px; font-weight:800; color:#059669;">{syndicated_count}</div>
                <div style="font-size:12px; color:#047857; font-weight:600;">Syndicated</div>
            </div>
            <div style="flex:1; min-width:120px; background:#eff6ff; border-radius:8px; padding:16px; text-align:center;">
                <div style="font-size:28px; font-weight:800; color:#2563eb;">{backlinks_created_count}</div>
                <div style="font-size:12px; color:#1d4ed8; font-weight:600;">Backlinks</div>
            </div>
            <div style="flex:1; min-width:120px; background:#f5f3ff; border-radius:8px; padding:16px; text-align:center;">
                <div style="font-size:28px; font-weight:800; color:#7c3aed;">{avg_score:.0f}</div>
                <div style="font-size:12px; color:#6d28d9; font-weight:600;">Avg Score</div>
            </div>
        </div>
        """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    background-color: #f3f4f6;
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    max-width: 650px;
                    background-color: #ffffff;
                    margin: 0 auto;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
                }}
                .header {{
                    background: linear-gradient(135deg, #4f46e5, #4338ca);
                    color: #ffffff;
                    padding: 30px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 24px;
                    font-weight: 700;
                    letter-spacing: -0.025em;
                }}
                .header p {{
                    margin: 5px 0 0 0;
                    font-size: 14px;
                    opacity: 0.9;
                }}
                .content {{
                    padding: 30px;
                }}
                .table-container {{
                    width: 100%;
                    overflow-x: auto;
                    margin-top: 20px;
                    border: 1px solid #e5e7eb;
                    border-radius: 6px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    text-align: left;
                }}
                th {{
                    background-color: #f9fafb;
                    color: #374151;
                    font-weight: 600;
                    font-size: 12px;
                    text-transform: uppercase;
                    padding: 12px;
                    border-bottom: 1px solid #e5e7eb;
                }}
                .footer {{
                    background-color: #f9fafb;
                    padding: 20px;
                    text-align: center;
                    font-size: 12px;
                    color: #9ca3af;
                    border-top: 1px solid #f3f4f6;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>MeetLyra SEO Machine</h1>
                    <p>Daily Execution Report &bull; {datetime.now(timezone.utc).strftime("%B %d, %Y")}</p>
                </div>
                <div class="content">
                    <p style="margin-top: 0; color: #374151; line-height: 1.5; font-size: 16px;">
                        Here is today's autonomous SEO publishing summary:
                    </p>
                    {ai_block}
                    {stats_block}
                    <div class="table-container">
                        <table>
                            <thead>
                                <tr>
                                    <th>Article Title</th>
                                    <th>Kind</th>
                                    <th>Score / Stats</th>
                                    <th>Status</th>
                                    <th>Links</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows_html}
                            </tbody>
                        </table>
                    </div>
                </div>
                <div class="footer">
                    This is an automated email from the autonomous MeetLyra SEO Content Machine.<br>
                    Project ID: {getattr(self.settings, "firebase_project_id", "aeo-seo-agents-team")}
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def send_daily_report(self) -> bool:
        if not self.settings.smtp_host:
            logger.warning("SMTP Host is not configured; skipping daily email report.")
            return False

        # Fetch runs in the last 24 hours
        recent = self.store.recent_runs(limit=20)
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)

        runs_last_24h = []
        for run in recent:
            started_at_str = run.get("started_at")
            if started_at_str:
                try:
                    started_at = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
                    if started_at >= cutoff:
                        runs_last_24h.append(run)
                except Exception as e:
                    logger.error(f"Error parsing date {started_at_str}: {e}")

        # Generate AI strategic summary via Gemini
        ai_summary = ""
        try:
            ai_summary = asyncio.run(_gemini_strategic_summary(self.settings, runs_last_24h))
        except RuntimeError:
            # If an event loop is already running (e.g. in Firebase), create task instead
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    future = asyncio.ensure_future(_gemini_strategic_summary(self.settings, runs_last_24h))
                    # Best-effort: can't block in running loop, so ai_summary stays ""
                else:
                    ai_summary = loop.run_until_complete(_gemini_strategic_summary(self.settings, runs_last_24h))
            except Exception as exc:
                logger.warning(f"Could not generate AI summary: {exc}")
        except Exception as exc:
            logger.warning(f"AI summary skipped: {exc}")

        published = sum(1 for r in runs_last_24h if r.get("wordpress_status") == "publish")
        draft = sum(1 for r in runs_last_24h if r.get("wordpress_status") == "draft")

        html_content = self.generate_html_report(runs_last_24h, ai_summary=ai_summary)

        subject = (
            f"MeetLyra SEO · Daily Report: {published} published, {draft} draft"
            f" · {datetime.now(timezone.utc).strftime('%b %d')}"
        )
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.settings.smtp_from or self.settings.smtp_user
        msg["To"] = self.settings.smtp_to

        msg.attach(MIMEText(html_content, "html"))

        try:
            logger.info(f"Connecting to SMTP server {self.settings.smtp_host}:{self.settings.smtp_port}...")
            if self.settings.smtp_port == 465:
                server_ctx = smtplib.SMTP_SSL(self.settings.smtp_host, self.settings.smtp_port)
            else:
                server_ctx = smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port)

            with server_ctx as server:
                if self.settings.smtp_port == 587:
                    server.starttls()
                if self.settings.smtp_user and self.settings.smtp_password:
                    server.login(self.settings.smtp_user, self.settings.smtp_password)
                server.sendmail(
                    self.settings.smtp_from or self.settings.smtp_user,
                    [self.settings.smtp_to],
                    msg.as_string()
                )
            logger.info("Daily email report sent successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to send email report: {e}")
            return False


def run_reporter() -> None:
    from pathlib import Path
    from .config import load_settings
    settings = load_settings()
    reporter = EmailReporter(settings)
    reporter.send_daily_report()
