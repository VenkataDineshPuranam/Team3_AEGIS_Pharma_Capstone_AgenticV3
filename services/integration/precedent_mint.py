"""mint_rejection() -- turns one HITL rejection into a citable EvidenceItem (ADR-010).

Called from services/api/graph.py's hitl_interrupt node, AFTER write_human_override has
already committed. That ordering is the whole safety property here: a Neo4j failure while
minting a precedent must never undo or block the human decision that was already recorded.
This module therefore catches its own errors and logs them -- it never raises into the
graph.

Mints only for action == "rejected". Never for "approved" or "timed_out" -- the specific
"QP approved a similar case" authority leak memory_design.md §2.3 and ADR-010 both name.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

from packages.domain.kg.client import session
from packages.domain.payloads import BatchPayload

_MERGE_PRECEDENT = """
MERGE (e:EvidenceItem {evidence_id: $evidence_id})
SET e.source_file = $source_file,
    e.authority = 'human_precedent',
    e.status = 'draft',
    e.trust = 'draft',
    e.jurisdiction = 'EU',
    e.effective_date = date($effective_date),
    e.finding_hash = $finding_hash,
    e.finding_categories = $finding_categories,
    e.source_run_id = $source_run_id,
    e.source_workflow = 'batch_review',
    e.action = 'rejected',
    e.justification_excerpt = $justification_excerpt,
    e._provenance_source_dataset = 'human_override_recorded',
    e._provenance_ingested_at = $ingested_at,
    e._provenance_ingestion_run_id = $source_run_id
"""

_EXCERPT_MAX_CHARS = 500


def finding_hash(findings) -> str:
    """SHA-256 of the sorted (category, status) pairs for findings that are gap or
    conflict -- excludes 'complete' findings and batch_id, so two runs with the same
    unresolved-finding shape hash identically regardless of subject."""
    pairs = sorted(
        (f.category, f.status) for f in findings if f.status in ("gap", "conflict")
    )
    raw = "|".join(f"{c}:{s}" for c, s in pairs)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def mint_rejection(
    run_id: str,
    workflow: str,
    domain_payload: BatchPayload | None,
    justification: str,
) -> None:
    """Best-effort. Skips silently (not an error) if this isn't a batch_review rejection
    with at least one gap/conflict finding -- an empty finding_hash would match every
    other run's precedent_retrieve.retrieve() call, exactly the "dump everything into
    every run" outcome ADR-010 rejects."""
    if workflow != "batch_review":
        return
    if domain_payload is None or not isinstance(domain_payload, BatchPayload):
        return

    gaps = [f for f in domain_payload.findings if f.status in ("gap", "conflict")]
    if not gaps:
        return

    try:
        with session() as s:
            s.run(
                _MERGE_PRECEDENT,
                evidence_id=f"HP-{run_id}",
                source_file=f"human_precedent/{run_id}.md",
                effective_date=datetime.now(UTC).date().isoformat(),
                finding_hash=finding_hash(domain_payload.findings),
                finding_categories=sorted({f.category for f in gaps}),
                source_run_id=run_id,
                justification_excerpt=justification[:_EXCERPT_MAX_CHARS],
                ingested_at=datetime.now(UTC).isoformat(),
            )
    except Exception:  # noqa: BLE001 -- best-effort; a human decision was already recorded
        logger.exception("precedent_mint.mint_rejection failed for run_id=%s (non-fatal)", run_id)
