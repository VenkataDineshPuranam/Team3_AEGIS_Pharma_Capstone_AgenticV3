"""Resilience: ADR-007 chaos harness injectors (offline — no Neo4j/Redis required)."""
from __future__ import annotations

import pytest

from services.integration import audit_store, chaos_harness


UI_EXPERIMENTS = [
    "CHAOS-LLM-01",
    "CHAOS-REDIS-01",
    "CHAOS-NEO4J-01",
    "CHAOS-HITL-01",
    "CHAOS-POLICY-01",
]


@pytest.mark.parametrize("experiment_id", UI_EXPERIMENTS)
def test_chaos_experiment_passes_offline(experiment_id: str):
    result = chaos_harness.run_experiment(experiment_id, persist=False)
    failed = [a for a in result.assertions if not a.passed]
    assert result.passed, f"{experiment_id} failed: {[(a.name, a.detail) for a in failed]}"
    assert result.observed.get("run_id", "").startswith("DRILL-")
    assert result.outcome_summary
    assert "graph" in result.outcome_summary.lower() or "injected" in result.outcome_summary.lower() or "simulated" in result.outcome_summary.lower() or "policy" in result.outcome_summary.lower()


def test_ops_only_experiment_rejected_from_harness():
    with pytest.raises(ValueError, match="ops-only"):
        chaos_harness.run_experiment("CHAOS-CKPT-01", persist=False)


def test_exclude_drills_hides_drill_agent_runs():
    # Persist one drill so finalize may write DRILL-* into agent_run, then prove list filter.
    result = chaos_harness.run_experiment("CHAOS-POLICY-01", persist=True)
    run_id = result.observed["run_id"]
    assert run_id.startswith("DRILL-")

    conn = audit_store.get_connection()
    try:
        # Some drills write agent_run via finalize; POLICY always does.
        row = audit_store.get_agent_run(conn, run_id)
        assert row is not None, "POLICY drill should finalize into agent_run"

        filtered, total_filtered = audit_store.list_agent_runs(conn, exclude_drills=True, limit=200)
        assert all(not r["run_id"].startswith("DRILL-") for r in filtered)
        assert all(r["run_id"] != run_id for r in filtered)

        unfiltered, _ = audit_store.list_agent_runs(conn, exclude_drills=False, limit=500)
        assert any(r["run_id"] == run_id for r in unfiltered)
    finally:
        conn.close()
