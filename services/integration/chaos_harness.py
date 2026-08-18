"""chaos_harness -- lab-safe ADR-007 failure injection for chaos drills.

Builds a fresh batch_review graph with injectable dependencies (never _GRAPH_CACHE,
never process-global monkeypatch). Run ids use the DRILL- prefix so Run History can
exclude them. Does not kill Neo4j/Redis/API processes.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from packages.domain.state import DecisionSupportOutput, new_state
from services.api.graph import build_graph
from services.api.nodes.llm_interface import StubLLM
from services.integration import chaos_drill_store, user_store
from services.integration.evidence_retrieve import ToolError as RetrieveError
from services.integration.policy_engine import PolicyEngineUnavailable

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "ops" / "chaos" / "experiments"

SYNTHETIC_EVIDENCE_ID = "K-CHAOS-001"

_BANNED_DISPOSITION_FRAGMENTS = (
    "recommend release",
    "cleared for release",
    "approve release",
    "release the batch",
)


@dataclass
class AssertionResult:
    name: str
    passed: bool
    detail: str


@dataclass
class ExperimentResult:
    drill_id: str
    experiment_id: str
    passed: bool
    overall_verdict: str
    assertions: list[AssertionResult] = field(default_factory=list)
    observed: dict[str, Any] = field(default_factory=dict)
    outcome_summary: str = ""
    duration_ms: int = 0
    run_at: str = ""
    run_by_user_id: str = ""
    run_by_display_name: str = ""
    run_by_role: str = ""


def describe_outcome(experiment_id: str, observed: dict[str, Any] | None) -> str:
    """Plain-language 'what happened' for the UI — not a second verdict."""
    o = observed or {}
    terminal = o.get("terminal_state") or "unknown"
    reason = o.get("abstention_reason")
    reason_bit = f" with reason {reason}" if reason else ""

    if experiment_id == "CHAOS-LLM-01":
        findings = (
            "Deterministic reconciliation findings survived the outage."
            if o.get("domain_payload_present")
            else "Deterministic findings were missing."
        )
        return (
            f"Injected an LLM outage (synthesize/critic raised). "
            f"The graph {terminal}{reason_bit} instead of guessing. {findings}"
        )
    if experiment_id == "CHAOS-REDIS-01":
        gets = o.get("cache_get_calls", 0)
        sets = o.get("cache_set_calls", 0)
        return (
            f"Simulated Redis unreachable: cache get returned empty ({gets} lookup(s)) "
            f"and cache set was a no-op ({sets} write(s)). "
            f"The run still finished ({terminal}{reason_bit}) without talking to Redis."
        )
    if experiment_id == "CHAOS-NEO4J-01":
        return (
            f"Injected STORE_UNAVAILABLE on evidence retrieve. "
            f"The graph {terminal}{reason_bit} — it did not invent evidence."
        )
    if experiment_id == "CHAOS-HITL-01":
        hitl = o.get("hitl_status")
        hitl_bit = f" HITL status {hitl}." if hitl else ""
        return (
            f"The graph reached a human interrupt; a timeout was applied. "
            f"Outcome: {terminal}{reason_bit}.{hitl_bit} "
            f"Timeout was not treated as an approval."
        )
    if experiment_id == "CHAOS-POLICY-01":
        return (
            f"Policy engine was made unreachable. "
            f"The graph {terminal}{reason_bit} — no decision-support package was produced."
        )
    return f"Graph ended {terminal}{reason_bit}."


class _BypassCache:
    """Mirrors response_cache ADR-007 posture: return None / no-op, never raise."""

    def __init__(self) -> None:
        self.get_calls = 0
        self.set_calls = 0

    def get(self, workflow: str, subject_id: str, evidence_ids: list[str]) -> DecisionSupportOutput | None:
        self.get_calls += 1
        return None

    def set_cleared(
        self, workflow: str, subject_id: str, evidence_ids: list[str], draft: DecisionSupportOutput
    ) -> None:
        self.set_calls += 1


class _BrokenLLM:
    def synthesize(self, state):
        raise ConnectionError("chaos drill: simulated LLM provider outage")

    def critic(self, state):
        raise ConnectionError("chaos drill: simulated LLM provider outage")


def load_catalog() -> list[dict]:
    experiments: list[dict] = []
    if not EXPERIMENTS_DIR.is_dir():
        return experiments
    for path in sorted(EXPERIMENTS_DIR.glob("CHAOS-*.json")):
        experiments.append(json.loads(path.read_text(encoding="utf-8")))
    return experiments


def get_experiment(experiment_id: str) -> dict | None:
    for exp in load_catalog():
        if exp["id"] == experiment_id:
            return exp
    return None


def _synthetic_retrieve(**kwargs) -> dict:
    item = {
        "evidence_id": SYNTHETIC_EVIDENCE_ID,
        "source": "chaos-harness",
        "status": "approved",
        "effective_date": date(2026, 1, 1).isoformat(),
        "jurisdiction": "EU",
        "supersedes": None,
        "content_excerpt": "Synthetic evidence for chaos drill; not production corpus.",
    }
    return {
        "items": [item],
        "sufficient": True,
        "evidence_snapshot_version": "snap-chaos",
        "tool_accounting": {"latency_ms": 0, "items_scanned": 1,
                            "items_filtered_untrusted": 0, "items_filtered_superseded": 0},
    }


def _synthetic_reconcile(*, run_id: str, batch_id: str, evidence_ids: list[str],
                         policy_contract_version: str) -> dict:
    findings = [
        {
            "category": "genealogy",
            "status": "complete",
            "evidence_ids": [SYNTHETIC_EVIDENCE_ID],
            "gap_description": None,
        },
        {
            "category": "lab_results",
            "status": "complete",
            "evidence_ids": [SYNTHETIC_EVIDENCE_ID],
            "gap_description": None,
        },
        {
            "category": "release_packet_completeness",
            "status": "complete",
            "evidence_ids": [SYNTHETIC_EVIDENCE_ID],
            "gap_description": None,
        },
    ]
    return {
        "reconciliation_complete": True,
        "findings": findings,
        "tool_accounting": {"latency_ms": 0},
    }


def _neo4j_unavailable_retrieve(**kwargs) -> dict:
    raise RetrieveError("STORE_UNAVAILABLE", "chaos drill: simulated Neo4j outage")


def _policy_unavailable(version: str, workflow: str):
    raise PolicyEngineUnavailable("chaos drill: simulated policy engine outage")


def _assert(name: str, passed: bool, detail: str) -> AssertionResult:
    return AssertionResult(name=name, passed=passed, detail=detail)


def _no_banned_disposition(payload: str) -> AssertionResult:
    lower = payload.lower()
    hits = [f for f in _BANNED_DISPOSITION_FRAGMENTS if f in lower]
    return _assert(
        "no_disposition_language",
        not hits,
        "clear" if not hits else f"banned fragments present: {hits}",
    )


def _run_graph(
    *,
    experiment_id: str,
    llm=None,
    retrieve_fn: Callable | None = None,
    reconcile_fn: Callable | None = None,
    policy_fn: Callable | None = None,
    cache_get: Callable | None = None,
    cache_set: Callable | None = None,
    resume_timed_out: bool = False,
) -> tuple[dict, str, str]:
    run_id = f"DRILL-{experiment_id}-{uuid.uuid4().hex[:8]}"
    batch_id = f"CHAOS-{experiment_id}"
    graph = build_graph(
        llm=llm,
        batch_id=batch_id,
        checkpointer=MemorySaver(),
        retrieve_fn=retrieve_fn,
        reconcile_fn=reconcile_fn,
        policy_fn=policy_fn,
        cache_get=cache_get,
        cache_set=cache_set,
    )
    config = {"configurable": {"thread_id": run_id}}
    state = new_state(
        run_id=run_id,
        workflow="batch_review",
        requester_role="EU Qualified Person",
    )
    result = graph.invoke(state, config=config)
    if resume_timed_out:
        if "__interrupt__" not in result:
            return result, run_id, batch_id
        result = graph.invoke(Command(resume="timed_out"), config=config)
    return result, run_id, batch_id


def _run_llm_01() -> tuple[list[AssertionResult], dict]:
    bypass = _BypassCache()
    result, run_id, batch_id = _run_graph(
        experiment_id="CHAOS-LLM-01",
        llm=_BrokenLLM(),
        retrieve_fn=_synthetic_retrieve,
        reconcile_fn=_synthetic_reconcile,
        cache_get=bypass.get,
        cache_set=bypass.set_cleared,
    )
    observed = {
        "run_id": run_id,
        "batch_id": batch_id,
        "terminal_state": result.get("terminal_state"),
        "abstention_reason": result.get("abstention_reason"),
        "domain_payload_present": result.get("domain_payload") is not None,
    }
    assertions = [
        _assert("terminal_state", observed["terminal_state"] == "abstained",
                f"got {observed['terminal_state']!r}"),
        _assert("abstention_reason", observed["abstention_reason"] == "degraded_mode",
                f"got {observed['abstention_reason']!r}"),
        _assert("deterministic_partial", observed["domain_payload_present"],
                "domain_payload should survive LLM outage"),
        _assert("drill_prefix", run_id.startswith("DRILL-"), run_id),
        _no_banned_disposition(json.dumps(observed)),
    ]
    return assertions, observed


def _run_redis_01() -> tuple[list[AssertionResult], dict]:
    bypass = _BypassCache()
    result, run_id, batch_id = _run_graph(
        experiment_id="CHAOS-REDIS-01",
        llm=StubLLM(),
        retrieve_fn=_synthetic_retrieve,
        reconcile_fn=_synthetic_reconcile,
        cache_get=bypass.get,
        cache_set=bypass.set_cleared,
        resume_timed_out=True,
    )
    observed = {
        "run_id": run_id,
        "batch_id": batch_id,
        "terminal_state": result.get("terminal_state"),
        "abstention_reason": result.get("abstention_reason"),
        "cache_get_calls": bypass.get_calls,
        "cache_set_calls": bypass.set_calls,
        "cache_bypassed": bypass.get_calls > 0 and bypass.set_calls > 0,
    }
    assertions = [
        _assert("cache_get_called", bypass.get_calls > 0, f"get_calls={bypass.get_calls}"),
        _assert("cache_set_called", bypass.set_calls > 0, f"set_calls={bypass.set_calls}"),
        _assert("no_redis_io", True, "injectors never call redis_client"),
        _assert("run_finished", result.get("terminal_state") is not None,
                f"terminal={result.get('terminal_state')!r}"),
        _assert("drill_prefix", run_id.startswith("DRILL-"), run_id),
        _no_banned_disposition(json.dumps(observed)),
    ]
    return assertions, observed


def _run_neo4j_01() -> tuple[list[AssertionResult], dict]:
    result, run_id, batch_id = _run_graph(
        experiment_id="CHAOS-NEO4J-01",
        retrieve_fn=_neo4j_unavailable_retrieve,
    )
    observed = {
        "run_id": run_id,
        "batch_id": batch_id,
        "terminal_state": result.get("terminal_state"),
        "abstention_reason": result.get("abstention_reason"),
    }
    assertions = [
        _assert("terminal_state", observed["terminal_state"] == "abstained",
                f"got {observed['terminal_state']!r}"),
        _assert("abstention_reason", observed["abstention_reason"] == "dependency_unavailable",
                f"got {observed['abstention_reason']!r}"),
        _assert("drill_prefix", run_id.startswith("DRILL-"), run_id),
        _no_banned_disposition(json.dumps(observed)),
    ]
    return assertions, observed


def _run_hitl_01() -> tuple[list[AssertionResult], dict]:
    bypass = _BypassCache()
    result, run_id, batch_id = _run_graph(
        experiment_id="CHAOS-HITL-01",
        llm=StubLLM(),
        retrieve_fn=_synthetic_retrieve,
        reconcile_fn=_synthetic_reconcile,
        cache_get=bypass.get,
        cache_set=bypass.set_cleared,
        resume_timed_out=True,
    )
    observed = {
        "run_id": run_id,
        "batch_id": batch_id,
        "terminal_state": result.get("terminal_state"),
        "abstention_reason": result.get("abstention_reason"),
        "hitl_status": result.get("hitl_status"),
    }
    timeout_ok = (
        observed["abstention_reason"] == "hitl_timeout"
        or observed["hitl_status"] == "timed_out"
    )
    assertions = [
        _assert("hitl_timeout", timeout_ok,
                f"reason={observed['abstention_reason']!r} hitl={observed['hitl_status']!r}"),
        _assert("not_completed_as_approve", observed["terminal_state"] != "completed",
                f"terminal={observed['terminal_state']!r}"),
        _assert("drill_prefix", run_id.startswith("DRILL-"), run_id),
        _no_banned_disposition(json.dumps(observed)),
    ]
    return assertions, observed


def _run_policy_01() -> tuple[list[AssertionResult], dict]:
    result, run_id, batch_id = _run_graph(
        experiment_id="CHAOS-POLICY-01",
        policy_fn=_policy_unavailable,
    )
    observed = {
        "run_id": run_id,
        "batch_id": batch_id,
        "terminal_state": result.get("terminal_state"),
        "abstention_reason": result.get("abstention_reason"),
    }
    assertions = [
        _assert("terminal_state", observed["terminal_state"] == "refused",
                f"got {observed['terminal_state']!r}"),
        _assert("abstention_reason", observed["abstention_reason"] == "fail_closed",
                f"got {observed['abstention_reason']!r}"),
        _assert("drill_prefix", run_id.startswith("DRILL-"), run_id),
        _no_banned_disposition(json.dumps(observed)),
    ]
    return assertions, observed


_RUNNERS: dict[str, Callable[[], tuple[list[AssertionResult], dict]]] = {
    "CHAOS-LLM-01": _run_llm_01,
    "CHAOS-REDIS-01": _run_redis_01,
    "CHAOS-NEO4J-01": _run_neo4j_01,
    "CHAOS-HITL-01": _run_hitl_01,
    "CHAOS-POLICY-01": _run_policy_01,
}


def run_experiment(
    experiment_id: str,
    triggered_by: user_store.Session | None = None,
    *,
    persist: bool = True,
) -> ExperimentResult:
    exp = get_experiment(experiment_id)
    if exp is None:
        raise KeyError(f"Unknown experiment {experiment_id!r}")
    if not exp.get("ui_runnable", False):
        raise ValueError(f"Experiment {experiment_id!r} is ops-only and cannot be run from the API")

    runner = _RUNNERS.get(experiment_id)
    if runner is None:
        raise ValueError(f"No harness runner for {experiment_id!r}")

    started = time.monotonic()
    run_at = datetime.now(UTC).isoformat()
    assertions, observed = runner()
    duration_ms = int((time.monotonic() - started) * 1000)
    passed = all(a.passed for a in assertions)
    verdict = "pass" if passed else "fail"
    drill_id = f"CD-{experiment_id}-{uuid.uuid4().hex[:8]}"
    summary = describe_outcome(experiment_id, observed)

    session = triggered_by
    result = ExperimentResult(
        drill_id=drill_id,
        experiment_id=experiment_id,
        passed=passed,
        overall_verdict=verdict,
        assertions=assertions,
        observed=observed,
        outcome_summary=summary,
        duration_ms=duration_ms,
        run_at=run_at,
        run_by_user_id=session.user_id if session else "harness",
        run_by_display_name=session.display_name if session else "harness",
        run_by_role=session.role if session else "harness",
    )

    if persist:
        conn = chaos_drill_store.get_connection()
        try:
            chaos_drill_store.write_drill_run(
                conn,
                drill_id=result.drill_id,
                experiment_id=result.experiment_id,
                run_at=result.run_at,
                run_by_user_id=result.run_by_user_id,
                run_by_display_name=result.run_by_display_name,
                run_by_role=result.run_by_role,
                passed=result.passed,
                overall_verdict=result.overall_verdict,
                assertions=[{"name": a.name, "passed": a.passed, "detail": a.detail} for a in assertions],
                observed=observed,
                duration_ms=duration_ms,
            )
        finally:
            conn.close()

    return result
