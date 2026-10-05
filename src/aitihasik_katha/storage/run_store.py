import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

from ..core.settings import settings


@dataclass
class RunRecord:
    run_id: str
    topic: str | None
    status: str
    error: str | None
    final_video_path: str | None
    media_uri: str | None
    video_ready: bool
    instagram_uploaded: bool
    created_at: str
    updated_at: str
    visual_style: str | None = None


def _db_path() -> str:
    return os.path.join(settings.RUNS_PATH, "pipeline.db")


@contextmanager
def _connect():
    db_path = _db_path()
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                topic TEXT,
                status TEXT NOT NULL,
                error TEXT,
                final_video_path TEXT,
                media_uri TEXT,
                video_ready INTEGER NOT NULL DEFAULT 0,
                instagram_uploaded INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                visual_style TEXT
            )
            """
        )
        columns = [row[1] for row in conn.execute("PRAGMA table_info(runs)").fetchall()]
        if "visual_style" not in columns:
            conn.execute("ALTER TABLE runs ADD COLUMN visual_style TEXT")


def _row_to_record(row: sqlite3.Row) -> RunRecord:
    return RunRecord(
        run_id=row["run_id"],
        topic=row["topic"],
        status=row["status"],
        error=row["error"],
        final_video_path=row["final_video_path"],
        media_uri=row["media_uri"],
        video_ready=bool(row["video_ready"]),
        instagram_uploaded=bool(row["instagram_uploaded"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        visual_style=row["visual_style"] if "visual_style" in row.keys() else None,
    )


def upsert_run(run_id: str, **fields_to_set) -> None:
    """Create or update a run record. Fields left out of `fields_to_set` are unchanged."""
    init_db()
    now = datetime.now(timezone.utc).isoformat()

    with _connect() as conn:
        existing = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if existing is None:
            record = {
                "run_id": run_id,
                "topic": None,
                "status": "running",
                "error": None,
                "final_video_path": None,
                "media_uri": None,
                "video_ready": 0,
                "instagram_uploaded": 0,
                "created_at": now,
                "updated_at": now,
                "visual_style": None,
                **fields_to_set,
            }
            conn.execute(
                """
                INSERT INTO runs (run_id, topic, status, error, final_video_path, media_uri,
                                   video_ready, instagram_uploaded, created_at, updated_at, visual_style)
                VALUES (:run_id, :topic, :status, :error, :final_video_path, :media_uri,
                        :video_ready, :instagram_uploaded, :created_at, :updated_at, :visual_style)
                """,
                record,
            )
        else:
            merged = dict(existing)
            merged.update(fields_to_set)
            merged["updated_at"] = now
            conn.execute(
                """
                UPDATE runs SET topic=:topic, status=:status, error=:error,
                                final_video_path=:final_video_path, media_uri=:media_uri,
                                video_ready=:video_ready, instagram_uploaded=:instagram_uploaded,
                                updated_at=:updated_at, visual_style=:visual_style
                WHERE run_id=:run_id
                """,
                merged,
            )


def get_run(run_id: str) -> RunRecord | None:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return _row_to_record(row) if row else None


def list_runs() -> list[RunRecord]:
    init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
        return [_row_to_record(row) for row in rows]


def list_pending_publish() -> list[RunRecord]:
    """Runs whose video is ready but haven't been published to Instagram yet."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM runs WHERE video_ready = 1 AND instagram_uploaded = 0 ORDER BY created_at"
        ).fetchall()
        return [_row_to_record(row) for row in rows]
