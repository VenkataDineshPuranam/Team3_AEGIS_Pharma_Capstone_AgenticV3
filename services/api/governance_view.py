"""Governance Center read model -- Stage 21.

Assembles, for display only, the controls that are already enforced elsewhere. Every value
here is READ from the artefact that actually enforces it:

  - prohibited actions      <- security/policies/policy_contract.v1.json, via the same
                               policy_engine the graphs load it with
  - approver roles / legs   <- the graph modules' own module-level constants
  - evidence authority      <- evidence_retrieve's own citable-status tuple
  - HITL rules              <- hitl_route's own tier durations

Nothing in this module is a second copy of a rule. If a value here ever disagreed with
enforcement, it would be because the import broke, not because someone updated one and
forgot the other -- which is the failure mode a hand-maintained governance page has.

This is a read model. It cannot change a policy: there is no writer in this module, and
the API exposes no endpoint that would call one.
"""
from __future__ import annotations

from services.api import pv_graph, supply_graph
from services.api.research_graph import RESEARCH_PRIMARY_APPROVER
from services.api.clinical_graph import CLINICAL_PRIMARY_APPROVER
from services.api.regulatory_graph import REGULATORY_PRIMARY_APPROVER
from services.integration import hitl_route
from services.integration.evidence_retrieve import _CITABLE_STATUSES, _PER_RUN_BROADENING_CEILING
from services.integration.policy_engine import PolicyEngineUnavailable, load_policy_contract

POLICY_VERSION = "v1"


def snapshot() -> dict:
    try:
        contract = load_policy_contract(POLICY_VERSION)
        policy_status = "loaded"
        prohibitions = contract["prohibition_contracts"]
    except PolicyEngineUnavailable as exc:
        # ADR-005/BC-3: an unreadable policy makes every graph refuse. The page must show
        # that as the alarming state it is, not as an empty section.
        policy_status = f"unavailable: {exc}"
        prohibitions = {}

    return {
        "policy_contract_version": POLICY_VERSION,
        "prohibited_actions": {
            "status": policy_status,
            "source": "security/policies/policy_contract.v1.json",
            "enforcement": [
                "Layer 1 -- schema absence: packages/domain/payloads.py models set extra='forbid', "
                "so a disposition field raises on construction rather than being dropped.",
                "Layer 2 -- tool capability absence: no tool contract in packages/contracts/ "
                "exposes an operation that could release, allocate, or determine causality.",
                "Layer 3 -- runtime guard: services/integration/prohibited_action_guard.py "
                "pattern-matches generated text, twice per run (before and after the Critic).",
            ],
            "by_workflow": prohibitions,
        },
        "hitl_rules": {
            "source": "docs/governance/hitl_control_model.md, "
            "docs/architecture/agentic/failure_and_loop_guards.md SS5",
            "escalation_ladder_hours": {
                "T1_reminder": hitl_route.T1_REMINDER_HOURS,
                "T2_escalation": hitl_route.T2_ESCALATION_HOURS,
                "T3_expiry": hitl_route.T3_EXPIRY_HOURS,
            },
            "invariants": [
                "Timeout means no action was taken -- never an implicit approval (BC-12).",
                "The ladder only widens who may approve; it never replaces the primary approver.",
                "An approval or rejection recorded after T3 expiry is structurally rejected, "
                "not merely discouraged (hitl_route.record_approval raises).",
                "Every approval, rejection and veto requires a justification, persisted to the "
                "append-only audit store before the run can finalize.",
            ],
            "clock_status": "NOT WIRED IN THIS BUILD -- the tier ladder is implemented and unit-"
            "tested as a pure function of elapsed time, but no scheduler advances a live run "
            "through T1/T2/T3. A timeout only occurs when one is explicitly submitted.",
        },
        "approver_roles": {
            "batch_review": {
                "primary": [hitl_route.PRIMARY_APPROVER],
                "escalation": hitl_route.ESCALATION_ROLE,
                "structure": "single approver",
            },
            "pv_intake": {
                "primary": [pv_graph.PV_PRIMARY_APPROVER],
                "veto_role": pv_graph.PV_VETO_ROLE,
                "structure": "single approver plus an advisory veto that cannot be overridden",
            },
            "supply_planning": {
                "primary": [supply_graph.SUPPLY_PLANNING_APPROVER, supply_graph.SUPPLY_QUALITY_APPROVER],
                "required_legs": [supply_graph.PLANNING_LEG, supply_graph.QUALITY_LEG],
                "structure": "dual approval -- both legs required; one leg approving is not approval",
            },
            "research_review": {
                "primary": [RESEARCH_PRIMARY_APPROVER],
                "structure": "single approver",
            },
            "clinical_integrity": {
                "primary": [CLINICAL_PRIMARY_APPROVER],
                "structure": "single approver",
            },
            "regulatory_completeness": {
                "primary": [REGULATORY_PRIMARY_APPROVER],
                "structure": "single approver",
            },
        },
        "evidence_authority": {
            "source": "ADR-003, BC-2; enforced in services/integration/evidence_retrieve.py",
            "citable_statuses": list(_CITABLE_STATUSES),
            "enforcement": "Non-citable items are excluded inside the Cypher query itself. There is "
            "no code path that returns an untrusted or superseded item and lets a caller decide "
            "whether to use it. packages/domain/evidence.py's EvidenceItem cannot even represent "
            "a non-citable status.",
            "broadening_ceiling_per_run": _PER_RUN_BROADENING_CEILING,
            "cache_rule": "A cached response is re-validated against each cited item's CURRENT "
            "status before it can be served; an entry whose evidence has since been superseded "
            "counts as a miss, never a hit.",
        },
        "authentication": {
            "status": "IMPLEMENTED (synthetic accounts, not production SSO)",
            "detail": "Every request that reads or writes a run requires a live, server-side "
            "session (services/integration/user_store.py): salted PBKDF2-HMAC-SHA256 password "
            "hashing, an 8-hour session expiry, and no client-cached authorization -- "
            "services/api/auth.py::require_user resolves the bearer token fresh on every request. "
            "The role attached to a session is not a claimed label: user_store.approver_string_for "
            "is checked against it before any decide() request reaches a graph, and every "
            "record-specific read endpoint (queue, run history, run detail, evidence, this "
            "governance snapshot, notifications, dashboard) requires a session, not just decide().",
            "planned": "Microsoft Entra ID (ADR-009 deployment target), to replace these eleven "
            "synthetic demo accounts (docs/governance/demo_login_credentials.md) with real "
            "organizational identity -- not to add a control that is currently missing.",
            "roles_referenced_by_the_domain": [
                "EU Qualified Person",
                "Global Head of Pharmacovigilance",
                "Patient Safety Representative",
                "Supply Chain VP",
                "Quality Co-Approver",
                "Compliance Reviewer",
                "Platform Operator",
            ],
        },
    }
