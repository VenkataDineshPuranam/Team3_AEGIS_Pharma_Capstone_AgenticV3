"""precedent.retrieve -- implements
packages/contracts/tool_contracts/precedent_retrieve.schema.json exactly (ADR-010),
backed by Neo4j (packages/domain/kg).

The batch_review binding only -- there is no PV or Supply binding for this tool
(ADR-010's non-negotiable: those graphs must not import or call it, and there is
structurally no shared code path here for them to reach).

Server-side enforcement, not caller-trusted, same posture as evidence_retrieve.py:
untrusted/superseded items are filtered in the Cypher query itself. Unlike
evidence_retrieve, matching is by finding-category overlap or exact finding_hash, not
free-text term containment -- a precedent lookup has no scope-preserving broadening
concept, so there is no per-run counter here.
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

from packages.domain.evidence import EvidenceItem
from packages.domain.kg.client import session

_CITABLE_STATUSES = ("approved", "draft")


class ToolError(Exception):
    """Carries one of the schema's declared error codes."""

    def __init__(self, code: str, meaning: str):
        self.code = code
        self.meaning = meaning
        super().__init__(f"{code}: {meaning}")


_QUERY = """
MATCH (e:EvidenceItem)
WHERE e.authority = 'human_precedent'
  AND e.source_workflow = 'batch_review'
  AND e.status IN $citable_statuses
  AND (
    e.finding_hash = $finding_hash
    OR any(cat IN e.finding_categories WHERE cat IN $finding_categories)
  )
RETURN e
ORDER BY e.effective_date DESC
"""


def retrieve(
    run_id: str,
    finding_categories: list[str],
    finding_hash: str,
    policy_contract_version: str,
) -> dict:
    """Matches precedent_retrieve.schema.json's input/output shape exactly. An empty
    `items` list is a valid result -- 'no similar refusals exist yet' is not an error."""
    if not run_id or not policy_contract_version:
        raise ToolError("STORE_UNAVAILABLE", "Missing required input fields.")

    if not finding_categories and not finding_hash:
        return {"items": []}

    start = time.monotonic()
    try:
        with session() as s:
            records = list(
                s.run(
                    _QUERY,
                    finding_hash=finding_hash,
                    finding_categories=finding_categories,
                    citable_statuses=list(_CITABLE_STATUSES),
                )
            )
    except Exception as exc:  # noqa: BLE001 -- connection/driver errors map to STORE_UNAVAILABLE
        # graph.py's precedent_retrieve node catches ToolError and leaves evidence
        # unchanged -- the run continues rather than treating an unreachable store as
        # proof no precedent exists. This log line is the only place the real cause
        # survives (BC-2: a caller must never see internal error text).
        logger.exception("precedent_retrieve.retrieve failed for run_id=%s", run_id)
        raise ToolError("STORE_UNAVAILABLE", str(exc)) from exc

    latency_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "precedent_retrieve: run_id=%s matched=%d latency_ms=%d", run_id, len(records), latency_ms
    )

    items = []
    for record in records:
        node = record["e"]
        items.append(
            EvidenceItem(
                evidence_id=node["evidence_id"],
                source=node["source_file"],
                status=node["status"],
                effective_date=node["effective_date"].to_native()
                if hasattr(node["effective_date"], "to_native")
                else node["effective_date"],
                jurisdiction=node.get("jurisdiction"),
                supersedes=None,
                content_excerpt=node.get("justification_excerpt", ""),
            )
        )

    return {"items": [item.model_dump(mode="json") for item in items]}
