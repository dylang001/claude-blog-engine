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
