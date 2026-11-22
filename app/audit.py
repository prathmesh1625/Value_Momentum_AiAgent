"""Append-only audit log in SQLite: who/what decided each step, and when.

Regulators and auditors ask "why was this risk declined?" - this table answers it.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from app import config


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.AUDIT_DB)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, run_id TEXT, "
        "actor TEXT, event TEXT, detail TEXT)"
    )
    return conn


def event(run_id: str, actor: str, event_name: str, detail: dict | str | None = None) -> dict:
    row = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_id": run_id,
        "actor": actor,
        "event": event_name,
        "detail": detail if isinstance(detail, str) else json.dumps(detail or {}, default=str),
    }
    with _conn() as conn:
        conn.execute("INSERT INTO audit (ts, run_id, actor, event, detail) VALUES (?,?,?,?,?)",
                     (row["ts"], run_id, actor, event_name, row["detail"]))
    return row


def history(run_id: str) -> list[dict]:
    with _conn() as conn:
        cur = conn.execute("SELECT ts, actor, event, detail FROM audit WHERE run_id=? ORDER BY id", (run_id,))
        return [dict(zip(["ts", "actor", "event", "detail"], r)) for r in cur.fetchall()]
