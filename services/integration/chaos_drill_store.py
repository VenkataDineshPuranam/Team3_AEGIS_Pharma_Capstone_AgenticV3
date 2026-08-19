"""chaos_drill_store -- persistence for ADR-007 chaos drill results.

Same physical SQLite file as audit_store / user_store (`evidence/audit_store.sqlite3`),
but its own table. Drill rows are observability about resilience posture, not compliance
records of governed decisions (ADR-006). Do not fold this into agent_run schema.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from services.integration.audit_store import DEFAULT_DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chaos_drill_run (
    drill_id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    run_at TEXT NOT NULL,
    run_by_user_id TEXT NOT NULL,
    run_by_display_name TEXT NOT NULL,
    run_by_role TEXT NOT NULL,
    passed INTEGER NOT NULL,
    overall_verdict TEXT NOT NULL,
    assertions TEXT NOT NULL,
    observed TEXT NOT NULL,
    duration_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chaos_drill_run_at ON chaos_drill_run(run_at DESC);
CREATE INDEX IF NOT EXISTS idx_chaos_drill_experiment ON chaos_drill_run(experiment_id, run_at DESC);
"""


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    # check_same_thread=False and nolock=1 -- see audit_store.get_connection's identical
    # fix. Same physical DB file, same Azure Files (SMB) mount, where SQLite's POSIX
    # locking calls aren't reliably honored -- this module was missed when that fix was
    # applied elsewhere, which is exactly why every chaos-drill endpoint 500'd with
    # "database is locked" in production while audit_store/user_store worked fine.
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?nolock=1", uri=True, check_same_thread=False)
    conn.executescript(_SCHEMA)
    return conn


def write_drill_run(
    conn: sqlite3.Connection,
    *,
    drill_id: str,
    experiment_id: str,
    run_at: str,
    run_by_user_id: str,
    run_by_display_name: str,
    run_by_role: str,
    passed: bool,
    overall_verdict: str,
    assertions: list[dict],
    observed: dict,
    duration_ms: int,
) -> None:
    conn.execute(
        "INSERT INTO chaos_drill_run ("
        "drill_id, experiment_id, run_at, run_by_user_id, run_by_display_name, run_by_role, "
        "passed, overall_verdict, assertions, observed, duration_ms"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            drill_id,
            experiment_id,
            run_at,
            run_by_user_id,
            run_by_display_name,
            run_by_role,
            1 if passed else 0,
            overall_verdict,
            json.dumps(assertions),
            json.dumps(observed),
            duration_ms,
        ),
    )
    conn.commit()


def _row_to_dict(row: sqlite3.Row | tuple) -> dict:
    if not isinstance(row, sqlite3.Row):
        keys = (
            "drill_id", "experiment_id", "run_at", "run_by_user_id", "run_by_display_name",
            "run_by_role", "passed", "overall_verdict", "assertions", "observed", "duration_ms",
        )
        row = dict(zip(keys, row))
    else:
        row = dict(row)
    return {
        "drill_id": row["drill_id"],
        "experiment_id": row["experiment_id"],
        "run_at": row["run_at"],
        "run_by_user_id": row["run_by_user_id"],
        "run_by_display_name": row["run_by_display_name"],
        "run_by_role": row["run_by_role"],
        "passed": bool(row["passed"]),
        "overall_verdict": row["overall_verdict"],
        "assertions": json.loads(row["assertions"]),
        "observed": json.loads(row["observed"]),
        "duration_ms": row["duration_ms"],
    }


def list_drill_runs(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM chaos_drill_run ORDER BY run_at DESC, drill_id DESC LIMIT ?",
        (max(1, min(limit, 100)),),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def latest_for_experiment(conn: sqlite3.Connection, experiment_id: str) -> dict | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM chaos_drill_run WHERE experiment_id = ? "
        "ORDER BY run_at DESC, drill_id DESC LIMIT 1",
        (experiment_id,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def get_drill_run(conn: sqlite3.Connection, drill_id: str) -> dict | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM chaos_drill_run WHERE drill_id = ?", (drill_id,)
    ).fetchone()
    return _row_to_dict(row) if row else None
