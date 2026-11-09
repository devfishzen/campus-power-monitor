from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Reading

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fetched_at    TEXT    NOT NULL,
    room          TEXT    NOT NULL,
    remaining_kwh REAL    NOT NULL,
    today_kwh     REAL,
    raw_json      TEXT
);
CREATE INDEX IF NOT EXISTS idx_readings_fetched_at ON readings(fetched_at);

CREATE TABLE IF NOT EXISTS alerts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT    NOT NULL,
    kind       TEXT    NOT NULL,
    message    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alerts_kind ON alerts(kind, id);
"""


class Store:
    """极简 SQLite 存储，一次查询一个连接，足够每天几次的写入量。"""

    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._conn()) as conn, conn:
            conn.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def save_reading(self, reading: Reading) -> None:
        fetched = reading.fetched_at.astimezone(timezone.utc).isoformat()
        with closing(self._conn()) as conn, conn:
            conn.execute(
                """
                INSERT INTO readings(fetched_at, room, remaining_kwh, today_kwh, raw_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    fetched,
                    reading.room,
                    reading.remaining_kwh,
                    reading.today_kwh,
                    json.dumps(reading.raw, ensure_ascii=False),
                ),
            )

    def latest(self) -> Reading | None:
        with closing(self._conn()) as conn:
            row = conn.execute(
                "SELECT * FROM readings ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return self._to_reading(row) if row else None

    def history(self, days: int = 30) -> list[Reading]:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with closing(self._conn()) as conn:
            rows = conn.execute(
                "SELECT * FROM readings WHERE fetched_at >= ? ORDER BY id ASC",
                (since,),
            ).fetchall()
        return [self._to_reading(row) for row in rows]

    def last_alert_at(self, kind: str) -> datetime | None:
        with closing(self._conn()) as conn:
            row = conn.execute(
                "SELECT created_at FROM alerts WHERE kind = ? ORDER BY id DESC LIMIT 1",
                (kind,),
            ).fetchone()
        if not row:
            return None
        return datetime.fromisoformat(row["created_at"])

    def record_alert(self, kind: str, message: str) -> None:
        with closing(self._conn()) as conn, conn:
            conn.execute(
                "INSERT INTO alerts(created_at, kind, message) VALUES (?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), kind, message),
            )

    @staticmethod
    def _to_reading(row: sqlite3.Row) -> Reading:
        fetched = datetime.fromisoformat(row["fetched_at"])
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        return Reading(
            room=row["room"],
            remaining_kwh=row["remaining_kwh"],
            today_kwh=row["today_kwh"],
            fetched_at=fetched,
            raw=json.loads(row["raw_json"] or "{}"),
        )
