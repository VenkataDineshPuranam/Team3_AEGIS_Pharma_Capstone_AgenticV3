"""ADR-010 / Shadow QP end-to-end: a rejected batch_review run mints a precedent that a
later run with a matching finding shape retrieves as evidence -- and never lets that
precedent short-circuit HITL. Requires a live Neo4j (precedent.retrieve and precedent.mint
both hit the real store) -- skipped otherwise, same convention as
test_batch_review_graph.py.
"""
import os
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv
from langgraph.types import Command

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

from packages.domain.state import new_state
from services.api.graph import build_graph

pytestmark = [
    pytest.mark.stub,
    pytest.mark.skipif(
        not os.environ.get("NEO4J_PASSWORD") or "xxxxxxxx" in os.environ.get("NEO4J_URI", ""),
        reason="BLOCKED_BY_ENVIRONMENT: Neo4j not configured",
    ),
]

# B-002 is the fixture batch_reconcile.py's real dataset reports as having at least one
# gap/conflict finding (test_batch_review_graph.py's own
# test_gap_batch_still_reaches_hitl_since_stub_always_cites relies on the same fact).
GAP_BATCH_ID = "B-002"


def _run_to_interrupt(batch_id: str):
    run_id = f"R-{uuid.uuid4().hex[:8]}"
    graph = build_graph(batch_id=batch_id)
    config = {"configurable": {"thread_id": run_id}}
    state = new_state(run_id=run_id, workflow="batch_review", requester_role="EU Qualified Person")
    result = graph.invoke(state, config=config)
    return graph, config, result, run_id


def test_rejection_mints_a_precedent_a_later_run_can_cite_without_skipping_hitl():
    # Run A: reject.
    graph_a, config_a, result_a, run_id_a = _run_to_interrupt(GAP_BATCH_ID)
    assert "__interrupt__" in result_a
    final_a = graph_a.invoke(Command(resume="rejected"), config=config_a)
    assert final_a["terminal_state"] == "completed"
    assert final_a["hitl_status"] == "rejected"

    # Run B: same finding shape. Its evidence should now include run A's precedent, and
    # it must STILL reach __interrupt__ -- a precedent is a citation, never a bypass.
    graph_b, config_b, result_b, run_id_b = _run_to_interrupt(GAP_BATCH_ID)
    assert "__interrupt__" in result_b, "a precedent citation must never let a run skip HITL"

    evidence_ids_b = [e.evidence_id for e in result_b["evidence"]]
    assert f"HP-{run_id_a}" in evidence_ids_b

    # Clean up: resolve run B so it doesn't leak a dangling interrupt into other tests.
    graph_b.invoke(Command(resume="approved"), config=config_b)


def test_an_approval_never_mints_a_precedent():
    """ADR-010's core non-negotiable: only action=rejected mints. An approval must never
    become retrievable as 'the QP approved a similar case'."""
    graph, config, result, run_id = _run_to_interrupt(GAP_BATCH_ID)
    assert "__interrupt__" in result
    graph.invoke(Command(resume="approved"), config=config)

    from services.integration.precedent_retrieve import retrieve

    lookup = retrieve(
        run_id="R-precedent-approval-check",
        finding_categories=["genealogy", "lab_results", "environmental_monitoring", "deviations", "capa", "change_control", "validation_state", "supplier_evidence", "release_packet_completeness", "process_analytical"],
        finding_hash="",
        policy_contract_version="v1",
    )
    ids = {item["evidence_id"] for item in lookup["items"]}
    assert f"HP-{run_id}" not in ids
