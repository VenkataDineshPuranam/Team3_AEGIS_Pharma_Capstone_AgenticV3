"""Regression test for a real bug found in Stage 20b Phase 6: the guard's 'blocked' path
wrote an agent_run record immediately, and finalize wrote a SECOND one for the same
run_id -- agent_run.run_id is a PRIMARY KEY, so this crashed with IntegrityError the first
time a real guard block was ever actually exercised end-to-end (every prior test either
used a model that didn't trigger it, or hit a cache hit that bypassed synthesize).

This is the single highest-stakes path in the whole system (ADR-004's runtime guard) --
a crash here is worse than a clean block, since a caller could plausibly retry into an
unclear state. Guarding against regression explicitly.

Requires a live, ingested Neo4j and Redis (the probe_retrieve call and cache clear below)
-- skipped otherwise, consistent with the BLOCKED_BY_ENVIRONMENT convention from Stage 14
(see e.g. tests/contract/test_evidence_retrieve_contract.py).
"""
import os
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

pytestmark = pytest.mark.skipif(
    not os.environ.get("NEO4J_PASSWORD") or "xxxxxxxx" in os.environ.get("NEO4J_URI", ""),
    reason="BLOCKED_BY_ENVIRONMENT: Neo4j not configured",
)

from packages.domain.evidence import Claim
from packages.domain.state import DecisionSupportOutput, new_state
from services.api.graph import build_graph
from services.api.nodes.llm_interface import StubLLM


class GuaranteedBlockLLM(StubLLM):
    """Always produces text that trips prohibited_action_guard -- no reliance on a real
    model's behavior, unlike the Stage 18 red-team test (which used a real, sometimes-
    resistant model). This test isolates the graph's OWN handling of a block, not whether
    a model complies with an injection."""

    def synthesize(self, state):
        draft = DecisionSupportOutput(
            summary="recommend release of this batch",
            claims=(Claim(text="recommend release per all evidence", cites=("K-006",)),),
        )
        return draft, 10, 10


def test_guard_block_reaches_a_clean_terminal_state_not_a_crash():
    # Clear any pre-existing cache entry for this fixture's real evidence set -- a warm
    # cache hit would skip synthesize entirely and never exercise the block this test
    # exists to check (response_cache only ever caches CLEAR drafts, so a cache hit here
    # would silently make this test pass for the wrong reason).
    from packages.config.redis_client import get_client
    from services.integration.evidence_retrieve import retrieve as probe_retrieve
    from services.integration.response_cache import cache_key

    probe = probe_retrieve(run_id=f"R-probe-{uuid.uuid4().hex[:8]}", terms=["BATCH_RELEASE", "policy"], policy_contract_version="v1")
    real_evidence_ids = [item["evidence_id"] for item in probe["items"]]
    get_client().delete(cache_key("batch_review", "B-001", real_evidence_ids))

    run_id = f"R-guardblock-{uuid.uuid4().hex[:8]}"
    graph = build_graph(llm=GuaranteedBlockLLM(), batch_id="B-001")
    state = new_state(run_id=run_id, workflow="batch_review", requester_role="EU Qualified Person")
    # No try/except -- a crash here IS the failure this test guards against.
    result = graph.invoke(state, config={"configurable": {"thread_id": run_id}})
    assert result["terminal_state"] == "blocked"
    assert result["abstention_reason"] == "prohibited_action"
    assert result["audit_record_id"] is not None
