from __future__ import annotations

import json
import sqlite3
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class StateStore:
    """Delegator class that routes calls to SQLiteStateStore or FirestoreStateStore based on config."""
    def __init__(self, db_path: Path | None = None, settings: Any | None = None):
        self.settings = settings
        self.db_path = db_path

        # Determine store type
        self.store_type = "sqlite"
        if settings is not None:
            self.store_type = getattr(settings, "state_store_type", "sqlite").lower()

        if self.store_type == "firestore":
            logger.info("Initializing FirestoreStateStore...")
            self._impl = FirestoreStateStore(settings)
        else:
            logger.info(f"Initializing SQLiteStateStore at {db_path}...")
            self._impl = SQLiteStateStore(db_path or Path(".content-machine/content_machine.db"))

    def save_run(self, run_id: str, started_at: str, payload: dict[str, Any]) -> None:
        self._impl.save_run(run_id, started_at, payload)

    def mark_published(self, key: str, kind: str, keyword: str, run_id: str, updated_at: str, wordpress_id: int | None, wordpress_url: str | None) -> None:
        self._impl.mark_published(key, kind, keyword, run_id, updated_at, wordpress_id, wordpress_url)

    def seen_keywords(self) -> set[str]:
        return self._impl.seen_keywords()

    def save_article(self, article: dict[str, Any]) -> None:
        self._impl.save_article(article)

    def get_article(self, article_id: str) -> dict[str, Any] | None:
        return self._impl.get_article(article_id)

    def save_distribution_asset(self, asset: dict[str, Any]) -> None:
        self._impl.save_distribution_asset(asset)

    def get_distribution_assets(self, article_id: str) -> list[dict[str, Any]]:
        return self._impl.get_distribution_assets(article_id)

    def save_backlink_target(self, target: dict[str, Any]) -> None:
        self._impl.save_backlink_target(target)

    def get_backlink_targets(self, article_id: str) -> list[dict[str, Any]]:
        return self._impl.get_backlink_targets(article_id)

    def save_daily_report(self, report: dict[str, Any]) -> None:
        self._impl.save_daily_report(report)

    def get_daily_report(self, date_str: str) -> dict[str, Any] | None:
        return self._impl.get_daily_report(date_str)

    def recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._impl.recent_runs(limit)

    def inject_refresh_candidate(self, keyword: str, url: str, reason: str, score: float = 80) -> None:
        self._impl.inject_refresh_candidate(keyword, url, reason, score)

    def add_to_content_plan(self, item: dict[str, Any]) -> None:
        self._impl.add_to_content_plan(item)

    def get_next_planned_post(self) -> dict[str, Any] | None:
        return self._impl.get_next_planned_post()

    def mark_planned_post_published(self, keyword: str, wordpress_url: str) -> None:
        self._impl.mark_planned_post_published(keyword, wordpress_url)

    def get_content_plan(self) -> list[dict[str, Any]]:
        return self._impl.get_content_plan()

    def clear_content_plan(self) -> None:
        self._impl.clear_content_plan()

    def get_next_refresh_candidate(self) -> dict[str, Any] | None:
        return self._impl.get_next_refresh_candidate()

    def mark_refresh_candidate_consumed(self, keyword: str) -> None:
        self._impl.mark_refresh_candidate_consumed(keyword)


class SQLiteStateStore:
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
                CREATE TABLE IF NOT EXISTS refresh_queue (
                    keyword TEXT PRIMARY KEY,
                    url TEXT,
                    reason TEXT NOT NULL,
                    score REAL NOT NULL DEFAULT 80,
                    created_at TEXT NOT NULL,
                    consumed INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS content_plan (
                    keyword TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    cluster_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    parent_pillar TEXT,
                    anchor_text TEXT,
                    score REAL NOT NULL,
                    volume INTEGER,
                    kd INTEGER,
                    status TEXT NOT NULL DEFAULT 'planned',
                    created_at TEXT NOT NULL,
                    published_at TEXT,
                    wordpress_url TEXT,
                    business_value INTEGER DEFAULT 0,
                    traffic_potential INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS articles (
                    article_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT,
                    target_keyword TEXT,
                    topic_cluster TEXT,
                    seo_score REAL,
                    publish_date TEXT,
                    status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS distribution_assets (
                    id TEXT PRIMARY KEY,
                    article_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    content_variant TEXT NOT NULL,
                    status TEXT NOT NULL,
                    published_url TEXT,
                    canonical_used TEXT,
                    date_published TEXT
                );
                CREATE TABLE IF NOT EXISTS backlink_targets (
                    id TEXT PRIMARY KEY,
                    article_id TEXT NOT NULL,
                    target_site TEXT NOT NULL,
                    contact_name TEXT,
                    contact_email TEXT,
                    outreach_angle TEXT,
                    status TEXT NOT NULL,
                    response TEXT
                );
                CREATE TABLE IF NOT EXISTS daily_reports (
                    date TEXT PRIMARY KEY,
                    posts_published INTEGER NOT NULL DEFAULT 0,
                    posts_syndicated INTEGER NOT NULL DEFAULT 0,
                    backlinks_created INTEGER NOT NULL DEFAULT 0,
                    indexing_status TEXT,
                    clicks INTEGER DEFAULT 0,
                    impressions INTEGER DEFAULT 0,
                    ranking_changes TEXT,
                    repair_update_tasks TEXT
                );
                """
            )
            # Dynamically alter table if columns are missing (for existing databases)
            _ALLOWED_MIGRATION_COLUMNS = {"business_value", "traffic_potential"}
            for col_name in _ALLOWED_MIGRATION_COLUMNS:
                try:
                    conn.execute(f"ALTER TABLE content_plan ADD COLUMN {col_name} INTEGER DEFAULT 0")
                except sqlite3.OperationalError:
                    # Column already exists
                    pass

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

    def inject_refresh_candidate(self, keyword: str, url: str, reason: str, score: float = 80) -> None:
        from datetime import datetime, timezone
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO refresh_queue (
                    keyword, url, reason, score, created_at, consumed
                ) VALUES (?, ?, ?, ?, ?, 0)
                """,
                (keyword, url, reason, score, datetime.now(timezone.utc).isoformat()),
            )

    def add_to_content_plan(self, item: dict[str, Any]) -> None:
        from datetime import datetime, timezone
        created_at = item.get("created_at") or datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO content_plan (
                    keyword, title, intent, cluster_name, role, parent_pillar,
                    anchor_text, score, volume, kd, status, created_at,
                    published_at, wordpress_url, business_value, traffic_potential
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["keyword"],
                    item["title"],
                    item["intent"],
                    item["cluster_name"],
                    item["role"],
                    item.get("parent_pillar"),
                    item.get("anchor_text"),
                    item["score"],
                    item.get("volume"),
                    item.get("kd"),
                    item.get("status", "planned"),
                    created_at,
                    item.get("published_at"),
                    item.get("wordpress_url"),
                    item.get("business_value", 0),
                    item.get("traffic_potential", 0),
                ),
            )

    def get_next_planned_post(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            # 1. Try to get planned pillars
            row = conn.execute(
                """
                SELECT * FROM content_plan
                WHERE status = 'planned' AND role = 'pillar'
                ORDER BY score DESC
                LIMIT 1
                """
            ).fetchone()
            if row:
                return dict(row)
            
            # 2. Try to get planned spokes whose parent pillar is already published (or has no parent)
            row = conn.execute(
                """
                SELECT s.* FROM content_plan s
                LEFT JOIN content_plan p ON s.parent_pillar = p.keyword
                WHERE s.status = 'planned' AND s.role = 'spoke'
                  AND (s.parent_pillar IS NULL OR p.status = 'published')
                ORDER BY s.score DESC
                LIMIT 1
                """
            ).fetchone()
            if row:
                return dict(row)
            return None

    def mark_planned_post_published(self, keyword: str, wordpress_url: str) -> None:
        from datetime import datetime, timezone
        published_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE content_plan
                SET status = 'published', wordpress_url = ?, published_at = ?
                WHERE LOWER(TRIM(keyword)) = LOWER(TRIM(?))
                """,
                (wordpress_url, published_at, keyword),
            )

    def get_content_plan(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM content_plan ORDER BY role DESC, score DESC").fetchall()
        return [dict(row) for row in rows]

    def clear_content_plan(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM content_plan")

    def get_next_refresh_candidate(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM refresh_queue WHERE consumed = 0 ORDER BY score DESC LIMIT 1"
            ).fetchone()
            if row:
                return dict(row)
            return None

    def mark_refresh_candidate_consumed(self, keyword: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE refresh_queue SET consumed = 1 WHERE LOWER(TRIM(keyword)) = LOWER(TRIM(?))",
                (keyword,),
            )

    def save_article(self, article: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO articles (
                    article_id, title, url, target_keyword, topic_cluster, seo_score, publish_date, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article["article_id"],
                    article["title"],
                    article.get("url"),
                    article.get("target_keyword"),
                    article.get("topic_cluster"),
                    article.get("seo_score"),
                    article.get("publish_date"),
                    article["status"]
                ),
            )

    def get_article(self, article_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM articles WHERE article_id = ?", (article_id,)).fetchone()
            return dict(row) if row else None

    def save_distribution_asset(self, asset: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO distribution_assets (
                    id, article_id, platform, content_variant, status, published_url, canonical_used, date_published
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset["id"],
                    asset["article_id"],
                    asset["platform"],
                    asset["content_variant"],
                    asset["status"],
                    asset.get("published_url"),
                    asset.get("canonical_used"),
                    asset.get("date_published")
                ),
            )

    def get_distribution_assets(self, article_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM distribution_assets WHERE article_id = ?", (article_id,)).fetchall()
            return [dict(row) for row in rows]

    def save_backlink_target(self, target: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO backlink_targets (
                    id, article_id, target_site, contact_name, contact_email, outreach_angle, status, response
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target["id"],
                    target["article_id"],
                    target["target_site"],
                    target.get("contact_name"),
                    target.get("contact_email"),
                    target.get("outreach_angle"),
                    target["status"],
                    target.get("response")
                ),
            )

    def get_backlink_targets(self, article_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM backlink_targets WHERE article_id = ?", (article_id,)).fetchall()
            return [dict(row) for row in rows]

    def save_daily_report(self, report: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO daily_reports (
                    date, posts_published, posts_syndicated, backlinks_created, indexing_status, clicks, impressions, ranking_changes, repair_update_tasks
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report["date"],
                    report.get("posts_published", 0),
                    report.get("posts_syndicated", 0),
                    report.get("backlinks_created", 0),
                    report.get("indexing_status"),
                    report.get("clicks", 0),
                    report.get("impressions", 0),
                    report.get("ranking_changes"),
                    report.get("repair_update_tasks")
                ),
            )

    def get_daily_report(self, date_str: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM daily_reports WHERE date = ?", (date_str,)).fetchone()
            return dict(row) if row else None


class FirestoreStateStore:
    def __init__(self, settings: Any):
        self.settings = settings
        self._db = None

    @property
    def db(self) -> Any:
        if self._db is None:
            import firebase_admin
            from firebase_admin import credentials, firestore

            if not firebase_admin._apps:
                svc_account = getattr(self.settings, "google_service_account_json", "").strip()
                if svc_account:
                    if svc_account.startswith("{"):
                        cred = credentials.Certificate(json.loads(svc_account))
                    else:
                        cred = credentials.Certificate(svc_account)
                    firebase_admin.initialize_app(cred)
                else:
                    firebase_admin.initialize_app()
            self._db = firestore.client()
        return self._db

    def save_run(self, run_id: str, started_at: str, payload: dict[str, Any]) -> None:
        doc_ref = self.db.collection("runs").document(run_id)
        doc_ref.set({
            "id": run_id,
            "started_at": started_at,
            "finished_at": payload.get("finished_at") or "",
            "dry_run": bool(payload.get("dry_run")),
            "opportunity_type": payload.get("opportunity", {}).get("kind") or "",
            "keyword": payload.get("opportunity", {}).get("keyword") or "",
            "score": payload.get("audit", {}).get("score") or 0.0,
            "decision": payload.get("audit", {}).get("decision") or "",
            "wordpress_status": payload.get("wordpress_status") or "",
            "wordpress_id": payload.get("wordpress_id") or 0,
            "payload_json": json.dumps(payload, sort_keys=True)
        })

    def mark_published(self, key: str, kind: str, keyword: str, run_id: str, updated_at: str, wordpress_id: int | None, wordpress_url: str | None) -> None:
        doc_ref = self.db.collection("published_items").document(key)
        doc_ref.set({
            "key": key,
            "kind": kind,
            "keyword": keyword,
            "wordpress_id": wordpress_id or 0,
            "wordpress_url": wordpress_url or "",
            "last_run_id": run_id,
            "updated_at": updated_at
        })

    def seen_keywords(self) -> set[str]:
        docs = self.db.collection("published_items").stream()
        keywords = set()
        for doc in docs:
            data = doc.to_dict()
            if "keyword" in data:
                keywords.add(data["keyword"].lower().strip())
        return keywords

    def recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        query = self.db.collection("runs").order_by("started_at", direction="DESCENDING").limit(limit)
        docs = query.stream()
        runs = []
        for doc in docs:
            data = doc.to_dict()
            if "payload_json" in data:
                runs.append(json.loads(data["payload_json"]))
        return runs

    def inject_refresh_candidate(self, keyword: str, url: str, reason: str, score: float = 80) -> None:
        from datetime import datetime, timezone
        doc_ref = self.db.collection("refresh_queue").document(keyword.lower().strip())
        doc_ref.set({
            "keyword": keyword,
            "url": url,
            "reason": reason,
            "score": score,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "consumed": False,
        })

    def add_to_content_plan(self, item: dict[str, Any]) -> None:
        from datetime import datetime, timezone
        key = item["keyword"].lower().strip()
        created_at = item.get("created_at") or datetime.now(timezone.utc).isoformat()
        doc_ref = self.db.collection("content_plan").document(key)
        doc_ref.set({
            "keyword": item["keyword"],
            "title": item["title"],
            "intent": item["intent"],
            "cluster_name": item["cluster_name"],
            "role": item["role"],
            "parent_pillar": item.get("parent_pillar") or "",
            "anchor_text": item.get("anchor_text") or "",
            "score": float(item["score"]),
            "volume": item.get("volume") or 0,
            "kd": item.get("kd") or 0,
            "status": item.get("status") or "planned",
            "created_at": created_at,
            "published_at": item.get("published_at") or "",
            "wordpress_url": item.get("wordpress_url") or "",
            "business_value": int(item.get("business_value", 0)),
            "traffic_potential": int(item.get("traffic_potential", 0)),
        })

    def get_next_planned_post(self) -> dict[str, Any] | None:
        docs = self.db.collection("content_plan").where("status", "==", "planned").stream()
        items = []
        for doc in docs:
            items.append(doc.to_dict())
            
        if not items:
            return None
            
        pillars = [i for i in items if i.get("role") == "pillar"]
        if pillars:
            pillars.sort(key=lambda x: x.get("score", 0.0), reverse=True)
            return pillars[0]
            
        spokes = [i for i in items if i.get("role") == "spoke"]
        if not spokes:
            return None
            
        spokes.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        for spoke in spokes:
            parent = spoke.get("parent_pillar")
            if not parent:
                return spoke
            parent_doc = self.db.collection("content_plan").document(parent.lower().strip()).get()
            if parent_doc.exists:
                parent_data = parent_doc.to_dict()
                if parent_data.get("status") == "published":
                    return spoke
        return None

    def mark_planned_post_published(self, keyword: str, wordpress_url: str) -> None:
        from datetime import datetime, timezone
        key = keyword.lower().strip()
        doc_ref = self.db.collection("content_plan").document(key)
        doc_ref.update({
            "status": "published",
            "wordpress_url": wordpress_url,
            "published_at": datetime.now(timezone.utc).isoformat(),
        })

    def get_content_plan(self) -> list[dict[str, Any]]:
        docs = self.db.collection("content_plan").stream()
        items = []
        for doc in docs:
            items.append(doc.to_dict())
        items.sort(key=lambda x: (x.get("role", ""), x.get("score", 0.0)), reverse=True)
        return items

    def clear_content_plan(self) -> None:
        coll_ref = self.db.collection("content_plan")
        docs = coll_ref.list_documents()
        for doc in docs:
            doc.delete()

    def get_next_refresh_candidate(self) -> dict[str, Any] | None:
        docs = self.db.collection("refresh_queue").where("consumed", "==", False).stream()
        candidates = []
        for doc in docs:
            candidates.append(doc.to_dict())
        if not candidates:
            return None
        candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return candidates[0]

    def mark_refresh_candidate_consumed(self, keyword: str) -> None:
        key = keyword.lower().strip()
        doc_ref = self.db.collection("refresh_queue").document(key)
        doc_ref.update({
            "consumed": True
        })

    def save_article(self, article: dict[str, Any]) -> None:
        doc_ref = self.db.collection("articles").document(article["article_id"])
        doc_ref.set(article)

    def get_article(self, article_id: str) -> dict[str, Any] | None:
        doc = self.db.collection("articles").document(article_id).get()
        return doc.to_dict() if doc.exists else None

    def save_distribution_asset(self, asset: dict[str, Any]) -> None:
        doc_ref = self.db.collection("distribution_assets").document(asset["id"])
        doc_ref.set(asset)

    def get_distribution_assets(self, article_id: str) -> list[dict[str, Any]]:
        docs = self.db.collection("distribution_assets").where("article_id", "==", article_id).stream()
        return [doc.to_dict() for doc in docs]

    def save_backlink_target(self, target: dict[str, Any]) -> None:
        doc_ref = self.db.collection("backlink_targets").document(target["id"])
        doc_ref.set(target)

    def get_backlink_targets(self, article_id: str) -> list[dict[str, Any]]:
        docs = self.db.collection("backlink_targets").where("article_id", "==", article_id).stream()
        return [doc.to_dict() for doc in docs]

    def save_daily_report(self, report: dict[str, Any]) -> None:
        doc_ref = self.db.collection("daily_reports").document(report["date"])
        doc_ref.set(report)

    def get_daily_report(self, date_str: str) -> dict[str, Any] | None:
        doc = self.db.collection("daily_reports").document(date_str).get()
        return doc.to_dict() if doc.exists else None
