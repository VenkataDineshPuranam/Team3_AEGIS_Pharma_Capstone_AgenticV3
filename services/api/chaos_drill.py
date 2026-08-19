"""Chaos drill API helpers -- catalog + run orchestration, no FastAPI imports."""
from __future__ import annotations

from services.integration import chaos_drill_store, chaos_harness, user_store


def _last_result_view(latest: dict) -> dict:
    observed = latest.get("observed") or {}
    return {
        "drill_id": latest["drill_id"],
        "passed": latest["passed"],
        "overall_verdict": latest["overall_verdict"],
        "run_at": latest["run_at"],
        "duration_ms": latest["duration_ms"],
        "outcome_summary": chaos_harness.describe_outcome(latest["experiment_id"], observed),
        "observed": observed,
    }


def list_experiments(session: user_store.Session) -> dict:
    catalog = chaos_harness.load_catalog()
    conn = chaos_drill_store.get_connection()
    try:
        items = []
        for exp in catalog:
            latest = chaos_drill_store.latest_for_experiment(conn, exp["id"])
            items.append({
                "id": exp["id"],
                "title": exp.get("title", exp["id"]),
                "adr_row": exp.get("adr_row", ""),
                "ui_runnable": bool(exp.get("ui_runnable", False)),
                "workflow": exp.get("workflow", "batch_review"),
                "runbook": exp.get("runbook"),
                "last_result": _last_result_view(latest) if latest else None,
            })
    finally:
        conn.close()
    return {
        "capabilities": {"can_run": user_store.can_run_chaos(session.role)},
        "experiments": items,
    }


def run_experiment(experiment_id: str, session: user_store.Session) -> dict:
    result = chaos_harness.run_experiment(experiment_id, triggered_by=session, persist=True)
    return {
        "drill_id": result.drill_id,
        "experiment_id": result.experiment_id,
        "passed": result.passed,
        "overall_verdict": result.overall_verdict,
        "assertions": [
            {"name": a.name, "passed": a.passed, "detail": a.detail} for a in result.assertions
        ],
        "observed": result.observed,
        "outcome_summary": result.outcome_summary,
        "duration_ms": result.duration_ms,
        "run_at": result.run_at,
        "run_by_user_id": result.run_by_user_id,
        "run_by_display_name": result.run_by_display_name,
        "run_by_role": result.run_by_role,
    }


def list_history(limit: int = 20) -> list[dict]:
    conn = chaos_drill_store.get_connection()
    try:
        rows = chaos_drill_store.list_drill_runs(conn, limit=limit)
    finally:
        conn.close()
    return [
        {
            "drill_id": r["drill_id"],
            "experiment_id": r["experiment_id"],
            "run_at": r["run_at"],
            "run_by_display_name": r["run_by_display_name"],
            "run_by_role": r["run_by_role"],
            "passed": r["passed"],
            "overall_verdict": r["overall_verdict"],
            "duration_ms": r["duration_ms"],
            "outcome_summary": chaos_harness.describe_outcome(r["experiment_id"], r.get("observed") or {}),
            "observed": r.get("observed") or {},
        }
        for r in rows
    ]
