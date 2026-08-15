"""System-health probes -- Stage 21.

Every function here MEASURES something by actually touching the dependency. None of them
report a status derived from configuration alone: "REDIS_URL is set" and "Redis answers"
are different facts, and a health page that conflates them is worse than no health page.

The four statuses are distinct on purpose:
  ok             -- reachable, answered
  degraded       -- reachable but not fully usable
  unavailable    -- configured, but did not answer
  not_configured -- no credentials supplied; nothing was attempted

`not_configured` is deliberately not `unavailable`. The graphs treat an unconfigured
Redis as a bypass (ADR-007 degraded mode, runs proceed without a cache), whereas an
unconfigured Neo4j means evidence retrieval cannot function at all. Collapsing those into
one red light would misrepresent which one stops the system.
"""
from __future__ import annotations

import os
import time

from services.api.schemas import DependencyHealth


def _timed(fn) -> tuple[object, int]:
    start = time.monotonic()
    result = fn()
    return result, int((time.monotonic() - start) * 1000)


def probe_redis() -> DependencyHealth:
    if not os.environ.get("REDIS_URL"):
        return DependencyHealth(
            name="Redis (response cache)", status="not_configured",
            detail="REDIS_URL is unset. Runs proceed without caching -- this is the documented "
                   "ADR-007 bypass, not a failure.",
        )
    try:
        from packages.config.redis_client import get_client

        _, latency = _timed(lambda: get_client().ping())
        return DependencyHealth(name="Redis (response cache)", status="ok", latency_ms=latency)
    except Exception as exc:  # noqa: BLE001
        return DependencyHealth(
            name="Redis (response cache)", status="unavailable",
            detail=f"Configured but unreachable: {type(exc).__name__}. Runs continue uncached.",
        )


def probe_neo4j() -> DependencyHealth:
    uri = os.environ.get("NEO4J_URI", "")
    if not uri or "xxxxxxxx" in uri or not os.environ.get("NEO4J_PASSWORD"):
        return DependencyHealth(
            name="Neo4j (knowledge graph)", status="not_configured",
            detail="NEO4J_URI / NEO4J_PASSWORD unset. Evidence retrieval cannot run, so every "
                   "workflow will abstain on dependency_unavailable.",
        )
    try:
        from packages.domain.kg.client import session

        def _count():
            with session() as s:
                return s.run("MATCH (e:EvidenceItem) RETURN count(e) AS n").single()["n"]

        count, latency = _timed(_count)
        if count == 0:
            return DependencyHealth(
                name="Neo4j (knowledge graph)", status="degraded", latency_ms=latency,
                detail="Reachable, but holds no EvidenceItem nodes -- run "
                       "`python -m packages.domain.kg.ingest` to seed the evidence corpus.",
            )
        return DependencyHealth(
            name="Neo4j (knowledge graph)", status="ok", latency_ms=latency,
            detail=f"{count} evidence nodes.",
        )
    except Exception as exc:  # noqa: BLE001
        return DependencyHealth(
            name="Neo4j (knowledge graph)", status="unavailable",
            detail=f"Configured but unreachable: {type(exc).__name__}.",
        )


def probe_audit_store() -> DependencyHealth:
    try:
        from services.integration.audit_store import get_connection

        def _count():
            conn = get_connection()
            try:
                return conn.execute("SELECT COUNT(*) FROM agent_run").fetchone()[0]
            finally:
                conn.close()

        count, latency = _timed(_count)
        return DependencyHealth(
            name="Audit store (SQLite, append-only)", status="ok", latency_ms=latency,
            detail=f"{count} recorded runs.",
        )
    except Exception as exc:  # noqa: BLE001
        return DependencyHealth(
            name="Audit store (SQLite, append-only)", status="unavailable",
            detail=f"{type(exc).__name__}. A run that cannot write its audit record cannot finalize.",
        )


def probe_llm() -> DependencyHealth:
    """Reports the CONFIGURED provider without calling it.

    A live probe would spend real tokens on every page load, which the denial-of-wallet
    ceiling exists to prevent -- so this reports configuration and says so plainly rather
    than claiming reachability it has not verified. Whether the provider actually answers
    is visible in the dashboard's degraded_mode abstention count, which is measured from
    real runs.
    """
    provider = os.environ.get("LLM_PROVIDER", "").strip()
    if not provider:
        return DependencyHealth(
            name="LLM provider", status="not_configured",
            detail="LLM_PROVIDER unset -- graphs fall back to the deterministic StubLLM.",
        )
    key_var = {
        "anthropic": "ANTHROPIC_API_KEY",
        "groq": "GROQ_API_KEY",
        "azure_foundry": "AZURE_FOUNDRY_API_KEY",
    }.get(provider)
    if key_var and not os.environ.get(key_var):
        return DependencyHealth(
            name="LLM provider", status="not_configured",
            detail=f"LLM_PROVIDER={provider} but {key_var} is unset.",
        )
    return DependencyHealth(
        name="LLM provider", status="ok",
        detail=f"Configured: {provider}. Not called by this probe -- a health check must not "
               f"spend tokens. Real availability is visible as the degraded_mode abstention count.",
    )


def probe_policy_engine() -> DependencyHealth:
    try:
        from services.api.governance_view import POLICY_VERSION
        from services.integration.policy_engine import load_policy_contract

        _, latency = _timed(lambda: load_policy_contract(POLICY_VERSION))
        return DependencyHealth(
            name="Policy engine", status="ok", latency_ms=latency,
            detail=f"Contract {POLICY_VERSION} loaded.",
        )
    except Exception as exc:  # noqa: BLE001
        return DependencyHealth(
            name="Policy engine", status="unavailable",
            detail=f"{exc}. ADR-005/BC-3: every run refuses while this is unreadable.",
        )


def all_dependencies() -> list[DependencyHealth]:
    return [probe_policy_engine(), probe_audit_store(), probe_neo4j(), probe_redis(), probe_llm()]
