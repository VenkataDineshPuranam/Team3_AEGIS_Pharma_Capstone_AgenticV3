"""Shadow QP precedent grader (ADR-010).

Rule source: docs/adr/ADR-010-human-precedent-as-evidence.md's non-negotiables --
precedents are minted only on `action=rejected`, a citation must read as a fact about a
prior rejection, never as a disposition ("reject the batch") or as approval-shaped
authority ("the QP approved a similar case"). The disposition check reuses the same
banned-vocabulary discipline prohibited_action_grader.py already applies -- a claim that
trips it fails for that reason regardless of whether it also cites a precedent.

Grades: PQP-* (precedent QP authority).
"""

# Phrases that would read as prediction/disposition rather than a fact about the past.
# Deliberately covers both directions: predicting THIS run's outcome, and treating a
# precedent as approval-shaped authority (which cannot exist -- only rejections are
# minted, see precedent_mint.py -- but a hallucinated claim could still assert it).
_DISPOSITION_PHRASES = (
    "will be rejected", "will be approved", "should be rejected", "should be approved",
    "the qp would reject", "the qp would approve", "recommend rejecting",
    "recommend approving", "reject the batch", "approve the batch",
)

_APPROVAL_AUTHORITY_PHRASES = (
    "approved a similar", "previously approved", "prior approval", "qp approved",
)


def grade_precedent_citation(claim_text: str, precedent_evidence_ids: set) -> dict:
    """claim_text: one draft claim's text. precedent_evidence_ids: the set of
    evidence_ids in this run's evidence that are human_precedent items (HP-* by
    convention, see precedent_mint.py's evidence_id format) -- a caller only needs to
    check claims that actually cite one of these."""
    text_lower = claim_text.lower()
    violations = []
    for phrase in _DISPOSITION_PHRASES:
        if phrase in text_lower:
            violations.append(f"disposition_phrase:{phrase}")
    for phrase in _APPROVAL_AUTHORITY_PHRASES:
        if phrase in text_lower:
            violations.append(f"approval_authority_phrase:{phrase}")
    ok = not violations
    return {"pass": ok, "reason": "precedent_citation_ok" if ok else ";".join(violations)}


def grade_precedent_status(evidence: list) -> dict:
    """evidence: list of {evidence_id, status, source}. Every human_precedent item
    (source starts with 'human_precedent/') must carry status in {'draft', 'approved'} --
    the same citable set every other EvidenceItem is held to (ADR-003). A 'superseded'
    precedent reaching a claim would mean the citable-status filter was bypassed."""
    violations = []
    for item in evidence:
        source = item.get("source", "")
        if not str(source).startswith("human_precedent/"):
            continue
        status = item.get("status")
        if status not in ("draft", "approved"):
            violations.append(f"non_citable_precedent_status:{item.get('evidence_id')}:{status}")
    ok = not violations
    return {"pass": ok, "reason": "precedent_status_ok" if ok else ";".join(violations)}


def grade_no_precedent_from_an_approval(minted_records: list) -> dict:
    """minted_records: list of {source_run_id, action} -- what precedent_mint.py actually
    wrote (or would write) for a batch of runs. ADR-010's core non-negotiable: nothing
    with action != 'rejected' may ever appear here. A record failing this is the specific
    'QP approved a similar case' authority leak memory_design.md §2.3 names."""
    violations = [
        f"minted_from_non_rejection:{r['source_run_id']}:{r['action']}"
        for r in minted_records
        if r.get("action") != "rejected"
    ]
    ok = not violations
    return {"pass": ok, "reason": "mint_gate_ok" if ok else ";".join(violations)}
