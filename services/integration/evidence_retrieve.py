"""evidence.retrieve -- implements packages/contracts/tool_contracts/evidence_retrieve.schema.json
exactly, backed by Neo4j (packages/domain/kg).

Server-side enforcement, not caller-trusted (ADR-003, BC-2):
  - untrusted/superseded items are filtered in the Cypher query itself -- there is no code
    path that returns them and lets a caller decide whether to use them.
  - the single scope-preserving broadening (G3) is enforced by a per-run counter this
    module owns, not by the caller's own bookkeeping.

One server binding per bounded context (hooks.md "one MCP server per bounded context").
This module is the `batch_review` binding only -- 20a's scope.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

from packages.domain.evidence import EvidenceItem
from packages.domain.kg.client import session

# G3: failure_and_loop_guards.md -- 1 initial call + at most 1 scope-preserving broadening.
_PER_RUN_BROADENING_CEILING = 1

_CITABLE_STATUSES = ("approved", "draft")  # ADR-003 -- local_approved counts as approved-family
# for the local jurisdiction it's scoped to; 20a's single-jurisdiction fixtures don't yet
# exercise that distinction (PV/Supply-only concern per conflict_authority_rules.md), so the
# citable set here is exactly the two-value enum evidence_retrieve.schema.json's output declares.


class ToolError(Exception):
    """Carries one of the schema's declared error codes."""

    def __init__(self, code: str, meaning: str):
        self.code = code
        self.meaning = meaning
        super().__init__(f"{code}: {meaning}")


@dataclass
class _RunBroadeningTracker:
    """Per-process, per-run_id counter. A real deployment would key this on the graph
    checkpoint; for 20a (single-process, single-run-at-a-time tests) an in-memory dict is
    the honest minimal implementation -- not a shortcut around G3, just not yet
    checkpoint-backed."""

    counts: dict[str, int] = field(default_factory=dict)

    def check_and_increment(self, run_id: str, broadening: bool) -> None:
        if not broadening:
            return
        used = self.counts.get(run_id, 0)
        if used >= _PER_RUN_BROADENING_CEILING:
            raise ToolError(
                "BROADENING_LIMIT_EXCEEDED",
                "A second broadening call was attempted for the same run_id.",
            )
        self.counts[run_id] = used + 1


_broadening_tracker = _RunBroadeningTracker()

# Per-run registry of evidence_ids actually returned by THIS run's retrieval calls.
# batch_reconcile's EVIDENCE_ID_NOT_IN_RUN check (its schema's own error code) reads this --
# a run cannot reconcile against an evidence_id it never retrieved (schema.json:
# "The tool rejects any id it cannot trace to this run's retrieval").
_run_evidence_registry: dict[str, set[str]] = {}


def get_run_evidence_ids(run_id: str) -> set[str]:
    return _run_evidence_registry.get(run_id, set())


_QUERY = """
MATCH (e:EvidenceItem)
WHERE e.status IN $citable_statuses
  AND ($jurisdiction IS NULL OR e.jurisdiction = $jurisdiction OR e.jurisdiction = 'Global')
  AND any(term IN $terms WHERE toLower(e.source_file) CONTAINS toLower(term)
          OR toLower(e.authority) CONTAINS toLower(term))
RETURN e
"""

_COUNT_FILTERED = """
MATCH (e:EvidenceItem)
WHERE NOT e.status IN $citable_statuses
  AND any(term IN $terms WHERE toLower(e.source_file) CONTAINS toLower(term)
          OR toLower(e.authority) CONTAINS toLower(term))
RETURN e.status AS status, count(*) AS n
"""


def retrieve(
    run_id: str,
    terms: list[str],
    policy_contract_version: str,
    jurisdiction: str | None = None,
    broadening: bool = False,
) -> dict:
    """Matches evidence_retrieve.schema.json's input/output shape exactly."""
    if not run_id or not terms or not policy_contract_version:
        raise ToolError("POLICY_VERSION_MISMATCH", "Missing required input fields.")

    _broadening_tracker.check_and_increment(run_id, broadening)

    start = time.monotonic()
    try:
        with session() as s:
            records = list(
                s.run(_QUERY, terms=terms, jurisdiction=jurisdiction, citable_statuses=list(_CITABLE_STATUSES))
            )
            filtered_counts = {
                r["status"]: r["n"]
                for r in s.run(_COUNT_FILTERED, terms=terms, citable_statuses=list(_CITABLE_STATUSES))
            }
    except Exception as exc:  # noqa: BLE001 -- connection/driver errors all map to STORE_UNAVAILABLE
        # graph.py's retrieve node catches ToolError and turns it into a bare
        # "dependency_unavailable" abstention with no detail -- by design, a caller must
        # never see internal error text (BC-2). But that means this log line is the ONLY
        # place the real cause survives; every workflow shares this one function, so this
        # is also the only place that needs it.
        logger.exception("evidence_retrieve.retrieve failed for run_id=%s", run_id)
        raise ToolError("STORE_UNAVAILABLE", str(exc)) from exc

    latency_ms = int((time.monotonic() - start) * 1000)

    items = []
    for record in records:
        node = record["e"]
        items.append(
            EvidenceItem(
                evidence_id=node["evidence_id"],
                source=node["source_file"],
                status=node["status"],
                effective_date=node["effective_date"].to_native() if hasattr(node["effective_date"], "to_native") else node["effective_date"],
                jurisdiction=node.get("jurisdiction"),
                supersedes=None,  # populated via a separate supersedes-edge query if needed by a caller
                content_excerpt="",
            )
        )

    _run_evidence_registry.setdefault(run_id, set()).update(item.evidence_id for item in items)

    return {
        "items": [item.model_dump(mode="json") for item in items],
        "sufficient": len(items) > 0,
        "evidence_snapshot_version": f"snap-{uuid.uuid4().hex[:8]}",
        "tool_accounting": {
            "latency_ms": latency_ms,
            "items_scanned": len(items) + sum(filtered_counts.values()),
            "items_filtered_untrusted": filtered_counts.get("untrusted", 0),
            "items_filtered_superseded": filtered_counts.get("superseded", 0),
        },
    }
