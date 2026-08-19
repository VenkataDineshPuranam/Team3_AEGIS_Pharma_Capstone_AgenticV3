"""LLM node interface -- Stage 20a Phase 4/5.

Two methods, `synthesize` and `critic`, implemented by:
  - StubLLM (this file): deterministic fake responses, no network call. Used by Phase 4's
    graph-shape tests so routing/caps/guards can be exercised with zero API key.
  - packages/config/llm_client.py's real clients (Phase 5): Grok (dev-only, provisional
    results) and Anthropic (Route A, ADR-009 -- the only provider whose output counts
    toward Stage 20a's interim-assumption exit criteria).

Swapping which one `services/api/graph.py` uses is a constructor argument, never a graph
change -- this is the interface ADR-009's "one client interface" guardrail exists for.
"""
from __future__ import annotations

from typing import Protocol

from packages.domain.evidence import Claim
from packages.domain.payloads import (
    BatchPayload,
    ClinicalPayload,
    PVPayload,
    RegulatoryPayload,
    ResearchPayload,
    SupplyPayload,
)
from packages.domain.state import DecisionSupportOutput, GovernedState, ReasonCode

# Stage 21 -- research_review/clinical_integrity/regulatory_completeness all share
# BatchPayload's exact shape (reconciliation_complete + findings[category/status/
# gap_description]), so StubLLM's batch branch logic applies unchanged -- only the
# subject-id field name differs per payload type.
_FINDINGS_PAYLOAD_SUBJECT_FIELD = {
    ResearchPayload: "research_id",
    ClinicalPayload: "protocol_id",
    RegulatoryPayload: "submission_id",
}


class LLMNodes(Protocol):
    def synthesize(self, state: GovernedState) -> tuple[DecisionSupportOutput, int, int]:
        """Returns (draft_output, tokens_in, tokens_out)."""
        ...

    def critic(self, state: GovernedState) -> tuple[str, ReasonCode | None, int, int]:
        """Returns (verdict, reason_code, tokens_in, tokens_out).
        verdict: 'approve_for_human' | 'reject'."""
        ...


def _append_precedent_claim(claims: tuple, evidence: tuple) -> tuple:
    """ADR-010: if precedent.retrieve added any human_precedent evidence to this run
    (source_file always starts with "human_precedent/" -- see precedent_mint.py), add
    one claim citing it, phrased as a fact about a prior rejection -- never as a
    disposition ("the QP would reject this") and never as approval-shaped authority,
    since only rejections are ever minted. Lets batch_review tests exercise a
    precedent citation without a live model."""
    precedent_ids = tuple(e.evidence_id for e in evidence if e.source.startswith("human_precedent/"))
    if not precedent_ids:
        return claims
    return claims + (
        Claim(
            text="A similar finding shape was previously not accepted by the EU Qualified Person.",
            cites=precedent_ids,
        ),
    )


class StubLLM:
    """No network call. Reads domain_payload's findings and produces a deterministic
    draft that cites real evidence_ids -- enough for guard/critic/HITL routing to be
    exercised meaningfully without a model."""

    def synthesize(self, state: GovernedState) -> tuple[DecisionSupportOutput, int, int]:
        payload = state["domain_payload"]
        evidence_ids = tuple(e.evidence_id for e in state["evidence"])

        if isinstance(payload, BatchPayload):
            gaps = [f for f in payload.findings if f.status != "complete"]
            if gaps:
                summary = f"Batch {payload.batch_id}: {len(gaps)} category/categories not complete."
                claims = tuple(
                    Claim(text=f"{g.category}: {g.status} -- {g.gap_description or 'no description'}", cites=evidence_ids)
                    for g in gaps
                )
            else:
                summary = f"Batch {payload.batch_id}: all reconciliation categories complete."
                claims = (Claim(text="All categories complete per retrieved evidence.", cites=evidence_ids),)
            claims = _append_precedent_claim(claims, state["evidence"])
        elif isinstance(payload, PVPayload):
            if payload.duplicate_suspected:
                candidate_ids = ", ".join(c.candidate_case_id for c in payload.candidates)
                summary = f"Case {payload.case_id}: duplicate suspected against {candidate_ids}."
                claims = (Claim(text=f"Case {payload.case_id} structurally matches prior case(s) {candidate_ids}.", cites=evidence_ids),)
            else:
                summary = f"Case {payload.case_id}: no duplicate suspected."
                claims = (Claim(text="No structural match found against the comparison window.", cites=evidence_ids),)
        elif isinstance(payload, SupplyPayload):
            if payload.options:
                summary = f"Product {payload.product_id}: {len(payload.options)} candidate option(s) within constraints."
                claims = tuple(
                    Claim(text=f"Option {o.option_id}: {o.description}", cites=evidence_ids) for o in payload.options
                )
            else:
                summary = f"Product {payload.product_id}: no candidate options satisfy the constraint set."
                claims = (Claim(text="Constraint-filtered candidate set is empty.", cites=evidence_ids),)
        elif type(payload) in _FINDINGS_PAYLOAD_SUBJECT_FIELD:
            subject_id = getattr(payload, _FINDINGS_PAYLOAD_SUBJECT_FIELD[type(payload)])
            gaps = [f for f in payload.findings if f.status != "complete"]
            if gaps:
                summary = f"{subject_id}: {len(gaps)} category/categories not complete."
                claims = tuple(
                    Claim(text=f"{g.category}: {g.status} -- {g.gap_description or 'no description'}", cites=evidence_ids)
                    for g in gaps
                )
            else:
                summary = f"{subject_id}: all reconciliation categories complete."
                claims = (Claim(text="All categories complete per retrieved evidence.", cites=evidence_ids),)
        else:
            raise TypeError(f"StubLLM.synthesize: unrecognized payload type {type(payload)!r}")

        draft = DecisionSupportOutput(summary=summary, claims=claims)
        return draft, 100, 50

    def critic(self, state: GovernedState) -> tuple[str, ReasonCode | None, int, int]:
        draft = state["draft_output"]
        for claim in draft.claims:
            if not claim.cites:
                return "reject", ReasonCode.MISSING_CITATION, 80, 20
        return "approve_for_human", None, 80, 20
