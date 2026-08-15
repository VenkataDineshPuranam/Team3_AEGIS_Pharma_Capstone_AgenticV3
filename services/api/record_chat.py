"""Record Assistant -- Stage 23. A grounded, guarded chat surface over ONE run record.

WHY THIS EXISTS
---------------
Everything the Control Center knows about a run is already on screen somewhere -- across
four tabs, an audit timeline, an evidence list and a governance panel. That is correct for
an approver working a decision, and slow for everyone else: a Quality reviewer, an
auditor, or an on-call operator who just needs to know *what this record is* and *what
happens next*. This module answers those two questions in one call.

THE DESIGN RULE THAT SHAPES EVERYTHING BELOW
--------------------------------------------
The LLM writes PROSE. It does not compute FACTS and it does not choose ACTIONS.

  - `build_record_card()` assembles every fact deterministically from the same two
    sources /api/runs/{run_id} reads (pending_queue + audit_store). No model is involved,
    so a fact shown here cannot be a hallucination -- it is the same data the run detail
    page renders, in a different shape.
  - `derive_next_steps()` computes "what to do next" deterministically from the record's
    own state and the governance model. The catalog of possible steps is a closed set in
    this file. The model cannot invent a step, cannot omit one, and cannot reorder them
    into a recommendation, because it is never asked to produce them -- it is handed the
    finished list and asked only to restate it in plain language.
  - The model's entire job is: summarize, answer the question, and paraphrase the steps.

That split is what makes "what to do next" safe to offer at all. A free-form model asked
"what should I do about this batch?" will eventually answer "release it" -- the V1/V2
non-negotiable that no agent makes a terminal safety decision cannot survive that question
being delegated. So it isn't. The steps are procedural facts about the governance state
("this run is waiting on the EU Qualified Person"), never dispositions.

DEFENCE IN DEPTH (PI/PG, services/integration/prompt_guard.py)
--------------------------------------------------------------
  in   -- the operator's question is scanned before it reaches the prompt; a high-severity
          injection is refused outright, and nothing is sent.
  in   -- the record's own free-text (findings, draft summary) is scanned and neutralized
          before being embedded. This is threat_catalogue.md T-01's exact attack path:
          B-EVIL's `gap_description` reaches the synthesize prompt, so it would reach this
          one too.
  out  -- every answer is scanned for prohibited disposition terms (against the SAME
          ProhibitionContract the graph's guard uses), fabricated evidence ids, and
          system-prompt leakage. A blocked answer is replaced, never shown-with-a-warning.

KNOWN LIMITS, STATED PLAINLY
----------------------------
  - A run decided before this API process started has no pending entry, so its findings
    and evidence are unavailable -- exactly the limitation /api/runs/{run_id} already
    reports via `decision_support_available`. The card says so rather than implying the
    run had no evidence.
  - This is stateless: each call sees one record and one question, with no conversation
    history. Follow-up questions must restate their subject. That is a deliberate
    simplification, not an oversight -- multi-turn history is a second injection surface
    (an attacker who gets one poisoned turn into history influences every later turn), and
    nothing in the "help me read this record" use case needs it.
  - Answers are NOT written to the append-only audit store. That store records agent runs
    and human overrides (audit_store.py's schema); a read-only reading aid is neither, and
    widening it would blur what an audit record means. Guard hits ARE returned to the
    caller and logged, so an attack attempt is not silent.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from services.api import pending_queue
from services.integration import audit_store, hitl_timer, policy_engine, prompt_guard, user_store

logger = logging.getLogger(__name__)

#: Policy contract version whose prohibition terms scan_output() checks answers against.
#: Same default the graphs compile with -- see services/api/graph.py.
POLICY_VERSION = "v1"

WORKFLOW_LABELS: dict[str, str] = {
    "batch_review": "GxP Batch Review",
    "pv_intake": "Pharmacovigilance Intake",
    "supply_planning": "Supply Shortage Planning",
    "research_review": "Preclinical Research Review",
    "clinical_integrity": "Clinical Trial Integrity",
    "regulatory_completeness": "Regulatory Submission Completeness",
}

#: What the accountable human is deciding, per workflow -- phrased as the QUESTION they
#: answer, never as an option to pick. Used to tell an operator who decides what, which is
#: the legitimate half of "what should I do?".
DECISION_OWNED_BY_HUMAN: dict[str, str] = {
    "batch_review": "the batch disposition (release, reject, reprocess, relabel, recall)",
    "pv_intake": "causality, seriousness, expectedness and reportability for this case",
    "supply_planning": "the allocation and shipment decision",
    "research_review": "model qualification and intended-use approval",
    "clinical_integrity": "eligibility, unblinding, and deviation disposition",
    "regulatory_completeness": "variation classification and submission readiness",
}


class RecordNotFound(Exception):
    """No run with this id is pending or recorded."""


class RecordNotVisible(Exception):
    """The signed-in role is segregated from this run's workflow (user_store.
    visible_workflows -- Unblinding authority vs supply_planning)."""


@dataclass(frozen=True)
class NextStep:
    """One procedural step. `owner` is who does it, `blocking` marks the step the run is
    actually stuck on. Never a disposition -- see the module docstring."""

    step: str
    owner: str
    blocking: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"step": self.step, "owner": self.owner, "blocking": self.blocking}


# ---------------------------------------------------------------------------
# 1. Facts -- deterministic, no model involved
# ---------------------------------------------------------------------------


def build_record_card(run_id: str, *, role: str) -> dict[str, Any]:
    """Every fact the system can truthfully state about one run, in one flat structure.

    Reads the same two sources as /api/runs/{run_id} and reports the same
    availability caveat, so the assistant and the run detail page can never disagree
    about what is known.
    """
    visible = user_store.visible_workflows(role)

    pending = pending_queue.get(run_id)
    conn = audit_store.get_connection()
    try:
        audited = audit_store.get_agent_run(conn, run_id)
        timeline = audit_store.run_timeline(conn, run_id)
        overrides = audit_store.human_overrides(conn, run_id)
    finally:
        conn.close()

    if pending is None and audited is None:
        raise RecordNotFound(f"No run {run_id!r} is pending or recorded.")

    workflow = pending.workflow if pending else audited.get("workflow")
    if visible is not None and workflow not in visible:
        # Segregation of duties is enforced here, not just rendered: an Unblinding
        # authority cannot read a supply_planning record through the assistant any more
        # than through the workflow list. A new read surface that skipped this check
        # would quietly reopen a closed control.
        raise RecordNotVisible(
            f"Role {role!r} is segregated from {workflow!r} records and cannot read this run."
        )

    subject_id = pending.subject_id if pending else audited.get("subject_id")
    evidence = list(pending.evidence) if pending else []
    evidence_ids = [e.get("evidence_id") for e in evidence if e.get("evidence_id")]
    if not evidence_ids and audited and audited.get("evidence_ids"):
        # A finalized run kept its evidence IDS (Stage 21 migration) even though the full
        # items are gone with the pending entry. Ids alone still let the answer cite.
        evidence_ids = list(audited["evidence_ids"])

    timer = None
    if pending is not None:
        computed = hitl_timer.compute(pending.created_at, pending.workflow)
        timer = {
            "tier": computed.tier, "label": computed.label, "severity": computed.severity,
            "hours_elapsed": computed.hours_elapsed, "hours_to_next_tier": computed.hours_to_next_tier,
        }

    return {
        "run_id": run_id,
        "workflow": workflow,
        "workflow_label": WORKFLOW_LABELS.get(workflow, workflow),
        "subject_id": subject_id,
        "status": "awaiting_human_decision" if pending else "decided",
        "requester_role": pending.requester_role if pending else (audited or {}).get("requester_role"),
        "approver_roles": pending.approver_roles if pending else ((audited or {}).get("approver_roles") or []),
        "required_legs": pending.required_legs if pending else None,
        "approved_legs": pending.approved_legs if pending else [],
        "hitl_timer": timer,
        "decision_belongs_to_human": DECISION_OWNED_BY_HUMAN.get(workflow, "the accountable human reviewer"),
        "draft_summary": pending.draft_summary if pending else None,
        "draft_claims": pending.draft_claims if pending else [],
        "domain_payload": pending.domain_payload if pending else None,
        "evidence": evidence,
        "evidence_ids": evidence_ids,
        "terminal_state": (audited or {}).get("terminal_state"),
        "abstention_reason": (audited or {}).get("abstention_reason"),
        "hitl_status": (audited or {}).get("hitl_status"),
        "policy_contract_version": (audited or {}).get("policy_contract_version"),
        "recorded_at": (audited or {}).get("recorded_at"),
        "human_actions": overrides,
        "timeline_event_count": len(timeline),
        "decision_support_available": pending is not None,
        "decision_support_unavailable_reason": None if pending else (
            "This run has already been decided, or was decided before the current API process "
            "started. Its draft summary, structured findings and evidence live in the paused "
            "run's graph state and are not copied into the audit store, so they cannot be shown. "
            "The audit record and human actions below are complete and authoritative."
        ),
    }


# ---------------------------------------------------------------------------
# 2. Next steps -- deterministic, closed catalog
# ---------------------------------------------------------------------------


def derive_next_steps(card: dict[str, Any], *, role: str) -> list[NextStep]:
    """What happens next with this run, computed from its state and the governance model.

    Every branch below returns PROCESS facts. Read the returned strings as a set: none of
    them tells anyone what to decide, and none of them can, because no branch has a
    disposition to return. That is the property this function is written to hold, and
    tests/security/test_record_chat_governance.py asserts it against the banned-term list.
    """
    workflow = card["workflow"]
    steps: list[NextStep] = []

    if card["status"] == "decided":
        terminal = card.get("terminal_state")
        if terminal == "blocked":
            steps.append(NextStep(
                step=(
                    "This run was blocked by the prohibited-action guard before reaching a human. "
                    "Nothing is waiting on you. If the block was unexpected, review the audit "
                    "timeline and re-submit the workflow once the underlying data is corrected."
                ),
                owner="Requester",
            ))
        elif terminal == "abstained":
            steps.append(NextStep(
                step=(
                    f"This run abstained ({card.get('abstention_reason') or 'reason not recorded'}) "
                    "rather than producing decision support. Re-submitting will not change the "
                    "outcome until the condition that caused the abstention is resolved."
                ),
                owner="Requester",
            ))
        else:
            steps.append(NextStep(
                step=(
                    f"This run is closed (terminal state: {terminal or 'not recorded'}"
                    + (f", human decision: {card['hitl_status']}" if card.get("hitl_status") else "")
                    + "). It cannot be reopened or re-decided; a new run is required to reassess."
                ),
                owner="No action required",
            ))
        steps.append(NextStep(
            step="The audit record for this run is append-only and remains available for inspection.",
            owner="Auditor / Quality reviewer",
        ))
        return steps

    # --- still awaiting a human -------------------------------------------------
    approvers = card.get("approver_roles") or []
    required_legs = card.get("required_legs")
    approved_legs = card.get("approved_legs") or []

    if required_legs:
        outstanding = [leg for leg in required_legs if leg not in approved_legs]
        steps.append(NextStep(
            step=(
                f"This workflow requires dual approval ({', '.join(required_legs)}). "
                + (
                    f"Still outstanding: {', '.join(outstanding)}."
                    if outstanding else "Both legs are recorded."
                )
                + " Neither leg can be recorded by the same person twice, and the run stays "
                "paused until every leg is present."
            ),
            owner=", ".join(approvers) if approvers else "Named approvers",
            blocking=bool(outstanding),
        ))
    else:
        steps.append(NextStep(
            step=(
                "This run is paused awaiting a human decision. It cannot proceed on its own, "
                "and no part of the system will decide it by timing out."
            ),
            owner=", ".join(approvers) if approvers else "Named approver",
            blocking=True,
        ))

    can_decide = any(user_store.approver_string_for(role, workflow, leg) for leg in (required_legs or [None]))
    if can_decide:
        steps.append(NextStep(
            step=(
                "You are eligible to record a decision on this run. Review the decision-support "
                "package and cited evidence first; a written justification is required and is "
                f"stored permanently. You decide {card['decision_belongs_to_human']} -- the system "
                "does not and will not."
            ),
            owner=f"You ({role})",
            blocking=True,
        ))
    else:
        steps.append(NextStep(
            step=(
                f"Your role ({role}) cannot record a decision on this run. You can read the "
                "record, the evidence and the audit trail. A decision attempt would be refused "
                "by the API, not merely hidden in the UI."
            ),
            owner=f"You ({role})",
        ))

    if user_store.can_veto(role, workflow):
        steps.append(NextStep(
            step=(
                "You hold a patient-safety veto on this workflow. A veto can be registered at "
                "any tier and cannot be overridden by a later approval."
            ),
            owner=f"You ({role})",
        ))

    timer = card.get("hitl_timer") or {}
    if timer.get("severity", 0) >= 3:
        steps.append(NextStep(
            step=(
                f"This decision has been pending long enough to reach severity {timer['severity']} "
                f"({timer.get('label')}). Escalation severity is a visibility signal only -- it does "
                "not widen who may approve, and it will not auto-resolve."
            ),
            owner=", ".join(approvers) if approvers else "Named approvers",
        ))

    if not card.get("evidence_ids"):
        steps.append(NextStep(
            step=(
                "No citable evidence is recorded against this run. Any claim in the decision-support "
                "package should be treated as unsupported until that is explained."
            ),
            owner="Quality reviewer",
        ))

    return steps


# ---------------------------------------------------------------------------
# 3. Prose -- the model's only job
# ---------------------------------------------------------------------------


def _scrub_record_for_prompt(card: dict[str, Any]) -> tuple[dict[str, Any], list[prompt_guard.PatternHit]]:
    """Neutralize injection payloads in the record's free-text before it is embedded.

    Only the fields that actually carry free text are scanned -- findings, the draft
    summary and claim text. `EvidenceItem.content_excerpt` is not among them for the same
    reason test_prompt_injection_red_team.py asserts it is never transmitted: the evidence
    embedded here is id/status/source only. Scanning a field that is never sent would be
    theatre.
    """
    hits: list[prompt_guard.PatternHit] = []

    def clean(value: Any, source: str) -> Any:
        if isinstance(value, str):
            scan = prompt_guard.scan_input(value, source=source)
            hits.extend(scan.hits)
            return scan.neutralized
        if isinstance(value, list):
            return [clean(v, source) for v in value]
        if isinstance(value, dict):
            return {k: clean(v, f"{source}.{k}") for k, v in value.items()}
        return value

    scrubbed = dict(card)
    scrubbed["draft_summary"] = clean(card.get("draft_summary"), "draft_summary")
    scrubbed["draft_claims"] = clean(card.get("draft_claims") or [], "draft_claims")
    scrubbed["domain_payload"] = clean(card.get("domain_payload"), "domain_payload")
    scrubbed["evidence"] = [
        {"evidence_id": e.get("evidence_id"), "status": e.get("status"), "source": e.get("source")}
        for e in (card.get("evidence") or [])
    ]
    scrubbed.pop("human_actions", None)  # justifications are human-authored; summarized separately
    return scrubbed, hits


def _build_user_prompt(scrubbed: dict[str, Any], question: str, steps: list[NextStep]) -> str:
    """Takes the ALREADY-scrubbed record. Scrubbing is done once by the caller and passed
    in, rather than repeated here -- both because scanning a large payload twice is waste,
    and because two independent scrubs could in principle disagree, and the one the
    operator is shown must be the one the model was given."""
    return json.dumps(
        {
            "RECORD": scrubbed,
            "NEXT_STEPS": [s.as_dict() for s in steps],
            "QUESTION": question,
        },
        default=str,
    )


def _fallback_summary(card: dict[str, Any]) -> str:
    """Deterministic summary used when the model is unavailable or its answer is blocked.

    ADR-007's degraded mode, applied here: the assistant loses its prose, not its facts.
    An operator in this state still gets a correct, if blunt, description of the record.
    """
    if card["status"] == "awaiting_human_decision":
        approvers = ", ".join(card.get("approver_roles") or []) or "a named approver"
        return (
            f"{card['workflow_label']} run {card['run_id']} for {card['subject_id']} is paused, "
            f"awaiting a decision by {approvers}. "
            f"{len(card.get('evidence_ids') or [])} evidence item(s) are cited. "
            f"{card['decision_belongs_to_human'].capitalize()} is decided by that human, not by this system."
        )
    return (
        f"{card['workflow_label']} run {card['run_id']} for {card['subject_id']} is closed "
        f"(terminal state: {card.get('terminal_state') or 'not recorded'}"
        + (f", human decision: {card['hitl_status']}" if card.get("hitl_status") else "")
        + f"). {len(card.get('human_actions') or [])} human action(s) are recorded against it."
    )


#: What the operator sees instead of a blocked answer. Deliberately says what happened --
#: an operator who is told "the assistant declined" and not why will simply ask again, or
#: worse, assume the system is broken and work around it.
_BLOCKED_ANSWER = (
    "The assistant's answer was withheld by the output guard because it contained language "
    "reserved for the accountable human decision-maker, a citation that does not exist in "
    "this record, or a copy of the assistant's own instructions. The record facts and next "
    "steps shown here are computed directly from the run and are unaffected."
)

_REFUSED_QUESTION = (
    "That question was not sent to the assistant: it contains text matching a known "
    "prompt-injection pattern (an attempt to replace the assistant's instructions or to "
    "extract them). Rephrase it as a plain question about this record. The record facts "
    "and next steps below are unaffected."
)


def answer(
    run_id: str,
    question: str,
    *,
    role: str,
    llm: Any,
    policy_version: str = POLICY_VERSION,
) -> dict[str, Any]:
    """The whole flow: facts -> steps -> guarded prose. Never raises for a guard outcome;
    a refusal is a normal, reported result."""
    card = build_record_card(run_id, role=role)
    steps = derive_next_steps(card, role=role)

    result: dict[str, Any] = {
        "run_id": run_id,
        "record": card,
        "next_steps": [s.as_dict() for s in steps],
        "summary": _fallback_summary(card),
        "answer": "",
        "next_steps_explanation": "",
        "cites": [],
        "llm_available": False,
        # Present on every path, not only the degraded one. RecordChatResponse defaults it
        # to None, which meant a caller reading the dict directly (a test, another service)
        # got a KeyError on the paths that succeed -- the schema default was hiding an
        # incomplete shape.
        "llm_unavailable_reason": None,
        "guard": {
            "prompt_guard_version": prompt_guard.PROMPT_GUARD_VERSION,
            "input_verdict": "clear",
            "output_verdict": "clear",
            "input_hits": [],
            "record_hits": [],
            "output_hits": [],
            "refused": False,
        },
    }

    question = (question or "").strip()
    question_scan = prompt_guard.scan_input(question, source="operator_question")
    result["guard"]["input_verdict"] = question_scan.verdict
    result["guard"]["input_hits"] = prompt_guard.hits_as_dicts(question_scan.hits)

    if question_scan.blocked:
        logger.warning(
            "prompt_guard blocked a Record Assistant question: run_id=%s role=%s sha256=%s patterns=%s",
            run_id, role, question_scan.input_sha256, [h.pattern_id for h in question_scan.hits],
        )
        result["guard"]["refused"] = True
        result["answer"] = _REFUSED_QUESTION
        return result

    scrubbed, record_hits = _scrub_record_for_prompt(card)
    result["guard"]["record_hits"] = prompt_guard.hits_as_dicts(tuple(record_hits))
    if record_hits:
        logger.warning(
            "prompt_guard neutralized injection-shaped text inside record %s: patterns=%s",
            run_id, [h.pattern_id for h in record_hits],
        )

    try:
        parsed, _tin, _tout = llm.record_chat(
            _build_user_prompt(scrubbed, question_scan.neutralized, steps)
        )
    except Exception as exc:  # noqa: BLE001 -- degraded mode is a state, not a crash
        # noqa rationale: provider SDKs raise their own exception hierarchies (auth, rate
        # limit, timeout) and _parse_record_chat_response raises on malformed JSON. Every
        # one means the same thing to an operator: no prose this time.
        # ADR-007: the assistant degrades to deterministic facts rather than failing the
        # request. Broad on purpose -- provider SDKs raise their own exception hierarchies
        # (auth, rate limit, timeout, malformed JSON), and every one of them means the same
        # thing to an operator: no prose this time.
        logger.warning("Record Assistant LLM unavailable for run %s: %s", run_id, exc)
        result["llm_unavailable_reason"] = (
            "The language model could not be reached, so this answer is the deterministic "
            "record summary. Every fact shown is read directly from the run."
        )
        return result

    # The model answered. Recorded here, BEFORE the output guard runs, because
    # `llm_available` reports whether the model responded -- not whether its answer
    # survived. Setting it only on the clear path (as this originally did) made a blocked
    # answer indistinguishable from an unreachable provider, and the UI said "record only"
    # for a model that had in fact replied. Those are different failures and an operator
    # needs to tell them apart; `guard.output_verdict` is what reports the block.
    result["llm_available"] = True

    contract = None
    try:
        contract = policy_engine.get_prohibition_contract(policy_version, card["workflow"])
    except policy_engine.PolicyEngineUnavailable as exc:
        # ADR-005 fails closed: no contract means no way to check the answer against the
        # prohibition list, so the prose is dropped rather than shown unchecked.
        logger.error("Policy contract unavailable for output guard on run %s: %s", run_id, exc)
        result["guard"]["output_verdict"] = "blocked"
        result["answer"] = _BLOCKED_ANSWER
        return result

    combined = " ".join(
        [parsed["summary"], parsed["answer"], parsed["next_steps_explanation"]]
    )
    output_scan = prompt_guard.scan_output(
        combined,
        allowed_evidence_ids=frozenset(card.get("evidence_ids") or []),
        # The record's own identifiers. An answer that names the batch/case/product it is
        # describing is not fabricating a citation -- see scan_output's docstring for the
        # live false positive this closes.
        known_identifiers=frozenset(
            str(v) for v in (card.get("subject_id"), card.get("run_id")) if v
        ),
        contract=contract,
    )
    result["guard"]["output_verdict"] = output_scan.verdict
    result["guard"]["output_hits"] = prompt_guard.hits_as_dicts(output_scan.hits)

    if output_scan.blocked:
        logger.warning(
            "prompt_guard blocked a Record Assistant answer: run_id=%s patterns=%s fabricated=%s banned=%s",
            run_id, [h.pattern_id for h in output_scan.hits],
            output_scan.fabricated_citations, output_scan.matched_banned_terms,
        )
        result["answer"] = _BLOCKED_ANSWER
        return result

    result["summary"] = parsed["summary"] or result["summary"]
    result["answer"] = parsed["answer"]
    result["next_steps_explanation"] = parsed["next_steps_explanation"]
    # Only ids that exist survive -- scan_output already blocked on fabrication, so this
    # is belt-and-braces against a citation the guard's id pattern did not recognize.
    allowed = set(card.get("evidence_ids") or [])
    result["cites"] = [c for c in parsed["cites"] if c in allowed]
    return result
