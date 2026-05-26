from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class StateStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    dry_run INTEGER NOT NULL,
                    opportunity_type TEXT,
                    keyword TEXT,
                    score REAL,
                    decision TEXT,
                    wordpress_status TEXT,
                    wordpress_id INTEGER,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS published_items (
                    key TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    keyword TEXT NOT NULL,
                    wordpress_id INTEGER,
                    wordpress_url TEXT,
                    last_run_id TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS kv (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outreach_campaigns (
                    id TEXT PRIMARY KEY,
                    post_slug TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outreach_prospects (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    email TEXT NOT NULL,
                    name TEXT NOT NULL,
                    company TEXT NOT NULL,
                    niche TEXT NOT NULL,
                    outreach_angle TEXT NOT NULL,
                    status TEXT NOT NULL,
                    next_action_due_at TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(campaign_id) REFERENCES outreach_campaigns(id)
                );
                CREATE TABLE IF NOT EXISTS outreach_logs (
                    id TEXT PRIMARY KEY,
                    prospect_id TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY(prospect_id) REFERENCES outreach_prospects(id)
                );
                """
            )

    def save_run(self, run_id: str, started_at: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO runs (
                    id, started_at, finished_at, dry_run, opportunity_type, keyword,
                    score, decision, wordpress_status, wordpress_id, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    started_at,
                    payload.get("finished_at"),
                    int(bool(payload.get("dry_run"))),
                    payload.get("opportunity", {}).get("kind"),
                    payload.get("opportunity", {}).get("keyword"),
                    payload.get("audit", {}).get("score"),
                    payload.get("audit", {}).get("decision"),
                    payload.get("wordpress_status"),
                    payload.get("wordpress_id"),
                    json.dumps(payload, sort_keys=True),
                ),
            )

    def mark_published(self, key: str, kind: str, keyword: str, run_id: str, updated_at: str, wordpress_id: int | None, wordpress_url: str | None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO published_items (
                    key, kind, keyword, wordpress_id, wordpress_url, last_run_id, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (key, kind, keyword, wordpress_id, wordpress_url, run_id, updated_at),
            )

    def seen_keywords(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT keyword FROM published_items").fetchall()
        return {row["keyword"].lower().strip() for row in rows}

    def recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def create_campaign(self, campaign_id: str, post_slug: str, created_at: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO outreach_campaigns (id, post_slug, created_at, status) VALUES (?, ?, ?, ?)",
                (campaign_id, post_slug, created_at, status),
            )

    def add_prospect(self, prospect_id: str, campaign_id: str, email: str, name: str, company: str, niche: str, outreach_angle: str, status: str, next_action_due_at: str | None, updated_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO outreach_prospects (
                    id, campaign_id, email, name, company, niche, outreach_angle, status, next_action_due_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (prospect_id, campaign_id, email, name, company, niche, outreach_angle, status, next_action_due_at, updated_at),
            )

    def get_campaign_by_slug(self, slug: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM outreach_campaigns WHERE post_slug = ?", (slug,)).fetchone()
        return dict(row) if row else None

    def get_active_campaigns(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM outreach_campaigns WHERE status = 'active'").fetchall()
        return [dict(r) for r in rows]

    def get_campaign_prospects(self, campaign_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM outreach_prospects WHERE campaign_id = ?", (campaign_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_prospect_by_email(self, email: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM outreach_prospects WHERE LOWER(email) = LOWER(?)", (email.strip(),)).fetchone()
        return dict(row) if row else None

    def update_prospect_status(self, prospect_id: str, status: str, next_action_due_at: str | None) -> None:
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE outreach_prospects SET status = ?, next_action_due_at = ?, updated_at = ? WHERE id = ?",
                (status, next_action_due_at, now, prospect_id),
            )

    def log_outreach_message(self, log_id: str, prospect_id: str, direction: str, subject: str, body: str, timestamp: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO outreach_logs (id, prospect_id, direction, subject, body, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (log_id, prospect_id, direction, subject, body, timestamp),
            )

    def get_due_prospects(self, now_iso: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM outreach_prospects WHERE status NOT IN ('replied', 'unsubscribed') AND next_action_due_at <= ?",
                (now_iso,),
            ).fetchall()
        return [dict(r) for r in rows]
