"""HTTP wire-format models -- deliberately distinct from packages/domain/'s domain models
(GovernedState, DecisionSupportOutput, etc.). This is the API's own contract, not a
re-export of the domain layer, so the two can evolve independently."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Workflow = Literal[
    "batch_review", "pv_intake", "supply_planning",
    "research_review", "clinical_integrity", "regulatory_completeness",
]

# Minimum characters for an approval/rejection/veto justification. Not a governance
# threshold invented here -- escalation_override_log_design.md SS3 already requires a
# non-empty justification and audit_store.write_human_override already rejects a blank
# one. This is the API refusing to accept a single space as a considered rationale before
# it reaches the graph, so the failure is a clean 422 rather than a mid-graph exception.
MIN_JUSTIFICATION_CHARS = 12


class LoginRequest(BaseModel):
    user_id: str
    password: str


class SessionInfo(BaseModel):
    token: str
    user_id: str
    display_name: str
    role: str
    expires_at: str


class SubmitRunRequest(BaseModel):
    workflow: Workflow
    subject_id: str  # batch_id / case_id / product_id
    requester_role: str


class DecideRequest(BaseModel):
    """A human's decision at an HITL interrupt.

    `justification` is REQUIRED for every action a human takes. It is persisted to the
    real audit record (human_override_recorded.justification) by the graph's own
    hitl_interrupt node -- not held in the API, and not held in React state.

    Identity now comes from the authenticated session (services/api/auth.py's
    `require_user`, resolved from the request's Authorization header) -- NOT from this
    body. `claimed_identity` remains here only so `hitl_decision.decode`'s dict shape
    stays backward-compatible with the tests that resume graphs directly; the HTTP layer
    always overwrites it with the authenticated user's display name before it reaches the
    graph, in `main.decide_run`.
    """

    workflow: Workflow
    action: Literal["approved", "rejected", "veto", "timed_out"]
    justification: str = Field(min_length=MIN_JUSTIFICATION_CHARS, max_length=4000)
    claimed_identity: str | None = Field(default=None, max_length=200)
    leg: Literal["planning", "quality"] | None = None  # supply_planning only


class EvidenceRef(BaseModel):
    """One evidence item as it reached a run's GovernedState. Everything here passed the
    ADR-003 citable filter server-side before it existed as an EvidenceItem at all, which
    is why `status` is only ever approved/draft on this model -- see EvidenceCatalogItem
    for the wider view that CAN show untrusted/superseded."""

    evidence_id: str
    source: str
    status: str
    effective_date: str
    jurisdiction: str | None = None
    supersedes: str | None = None
    content_excerpt: str = ""


class EvidenceCatalogItem(BaseModel):
    """A knowledge-graph evidence node as it actually is, INCLUDING non-citable ones.

    The Evidence Explorer must be able to show an untrusted or superseded document and
    label it as unusable -- that is the point of the page. Showing it here does not make
    it citable: `citable` is computed from the same two-status rule the retrieval tool
    enforces in its own Cypher, and no run can pick an item up from this endpoint. This
    is a read-only catalog view, not an input to any graph.
    """

    evidence_id: str
    source: str
    status: str
    citable: bool
    authority: str | None = None
    jurisdiction: str | None = None
    effective_date: str | None = None
    supersedes: str | None = None
    superseded_by: str | None = None
    content_excerpt: str = ""


class RunResult(BaseModel):
    run_id: str
    workflow: Workflow
    status: Literal["pending_approval", "completed", "abstained", "blocked", "refused"]
    terminal_state: str | None = None
    abstention_reason: str | None = None
    llm_calls: int | None = None
    draft_summary: str | None = None
    draft_claims: list[dict[str, Any]] = []
    approver_roles: list[str] = []
    required_legs: list[str] | None = None
    approved_legs: list[str] = []
    veto_recorded: bool = False


class HitlTimerInfo(BaseModel):
    """services/integration/hitl_timer.py's severity/timer computation -- display only,
    recomputed fresh on every request. Does not affect who is authorized to decide."""

    tier: str
    label: str
    severity: int  # 1 (lowest) .. 4 (highest / red)
    hours_elapsed: float
    hours_to_next_tier: float | None


class QueueEntry(BaseModel):
    run_id: str
    workflow: Workflow
    subject_id: str
    requester_role: str
    approver_roles: list[str]
    required_legs: list[str] | None
    approved_legs: list[str]
    draft_summary: str | None
    draft_claims: list[dict[str, Any]]
    created_at: str
    # Stage 21 -- what the queue previously could not show: which evidence the findings
    # stand on, and the workflow's own structured findings (batch reconciliation
    # categories / PV duplicate candidates / supply planning options).
    evidence: list[EvidenceRef] = []
    domain_payload: dict[str, Any] | None = None
    evidence_accounting: dict[str, Any] | None = None
    hitl_timer: HitlTimerInfo


class AuditEvent(BaseModel):
    at: str
    event_type: str
    actor: str | None = None
    role: str | None = None
    action: str
    metadata: dict[str, Any] = {}


class AuditedRun(BaseModel):
    """One row of the append-only agent_run table. Fields added in Stage 21 read None for
    runs recorded before that migration -- the UI renders those as "not recorded", never
    as a zero or an empty list."""

    run_id: str
    workflow: str
    terminal_state: str
    abstention_reason: str | None = None
    trace_id: str | None = None
    policy_contract_version: str | None = None
    recorded_at: str
    llm_calls: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    subject_id: str | None = None
    requester_role: str | None = None
    approver_roles: list[str] | None = None
    hitl_status: str | None = None
    evidence_ids: list[str] | None = None


class RunHistoryPage(BaseModel):
    items: list[AuditedRun]
    total: int
    limit: int
    offset: int


class RunDetail(BaseModel):
    """Everything the system can truthfully say about one run.

    `pending` is populated only while the run is still parked at its interrupt in THIS API
    process (services/api/pending_queue.py is in-memory by design). `audit` is populated
    once finalize has written the record. A run can legitimately have one, the other, or
    both -- and `decision_support_available` states plainly which, so the UI never has to
    infer that an empty field means "nothing happened".
    """

    run_id: str
    pending: QueueEntry | None = None
    audit: AuditedRun | None = None
    timeline: list[AuditEvent] = []
    human_actions: list[dict[str, Any]] = []
    decision_support_available: bool = False
    decision_support_unavailable_reason: str | None = None


class GovernanceSnapshot(BaseModel):
    policy_contract_version: str
    prohibited_actions: dict[str, Any]
    hitl_rules: dict[str, Any]
    approver_roles: dict[str, Any]
    evidence_authority: dict[str, Any]
    authentication: dict[str, Any]


class DependencyHealth(BaseModel):
    name: str
    status: Literal["ok", "degraded", "unavailable", "not_configured"]
    detail: str | None = None
    latency_ms: int | None = None


class HealthDetail(BaseModel):
    api: DependencyHealth
    dependencies: list[DependencyHealth]
    audit_store: dict[str, Any]
    checked_at: str


class DashboardResponse(BaseModel):
    workflow: str | None
    cost: dict[str, Any]
    guardrail_trip: dict[str, Any]
    terminal_states: dict[str, Any]
    cache: dict[str, Any]


class EvalScorecard(BaseModel):
    """services/api/eval_dashboard.py:eval_scorecard() -- executed live on every request
    (~25ms, pure grading logic, no LLM/network calls). Not a cached snapshot."""

    total_scenarios: int
    passed: int
    failed: int
    accepted_non_pass: int
    category_count: int
    categories: list[dict[str, Any]]
    source: str


class InjectCoverage(BaseModel):
    """The curated 84-inject V1-to-V2 coverage mapping -- read from a reviewed file, not
    computed per-request. See services/api/eval_dashboard.py's module docstring."""

    methodology: str
    source_dataset: str
    reviewed_at: str
    total_injects: int
    by_status: dict[str, int]
    dimensions: list[dict[str, Any]]
    injects: list[dict[str, Any]]


# --- Record Assistant (Stage 23) ---------------------------------------------


class RecordChatRequest(BaseModel):
    """`question` may be empty: an empty question means "just describe this record",
    which is the panel's initial load. It is capped because a very long question is
    almost always either a paste accident or an injection payload padded to push the
    operator instructions out of the model's attention -- and a legitimate question about
    one record does not need this much room."""

    question: str = Field(default="", max_length=1000)


class RecordChatGuard(BaseModel):
    """What services/integration/prompt_guard.py saw. Returned to the caller rather than
    logged only, so an operator can tell the difference between "the assistant had nothing
    to say" and "the assistant's answer was withheld" -- and so a red-team exercise can
    assert on the guard from outside the process."""

    prompt_guard_version: str
    input_verdict: Literal["clear", "flagged", "blocked"]
    output_verdict: Literal["clear", "flagged", "blocked"]
    input_hits: list[dict[str, str]] = []
    record_hits: list[dict[str, str]] = []
    output_hits: list[dict[str, str]] = []
    refused: bool = False


class RecordChatResponse(BaseModel):
    """`record` and `next_steps` are computed deterministically from the run; `summary`,
    `answer` and `next_steps_explanation` are model-written prose over those same facts.
    The split is load-bearing -- see services/api/record_chat.py's module docstring -- so
    the two are kept in separate fields rather than merged into one blob of text a client
    could not tell apart."""

    run_id: str
    record: dict[str, Any]
    next_steps: list[dict[str, Any]]
    summary: str
    answer: str
    next_steps_explanation: str
    cites: list[str] = []
    llm_available: bool
    llm_unavailable_reason: str | None = None
    guard: RecordChatGuard


# --- Notifications (Stage 23) -------------------------------------------------


class NotificationItem(BaseModel):
    """One HITL escalation event, from services/integration/hitl_escalation_watch.py.
    `subject_id` and `approver_roles` are best-effort: they come from the in-memory
    pending queue at READ time (services/api/pending_queue.py), which is disposable UI
    state, not the audit record itself -- if the run has since been decided or the API
    process restarted, they are `null` rather than guessed. `tier`/`workflow`/`run_id`/
    `evaluated_at` always come from the append-only audit store and are never null."""

    run_id: str
    workflow: str
    tier: str
    severity: int
    evaluated_at: str
    subject_id: str | None = None
    approver_roles: list[str] | None = None


# --- Chaos drills (ADR-007 lab injectors) ------------------------------------


class ChaosDrillAssertion(BaseModel):
    name: str
    passed: bool
    detail: str


class ChaosDrillLastResult(BaseModel):
    drill_id: str
    passed: bool
    overall_verdict: str
    run_at: str
    duration_ms: int
    outcome_summary: str = ""
    observed: dict[str, Any] = {}


class ChaosDrillExperiment(BaseModel):
    id: str
    title: str
    adr_row: str
    ui_runnable: bool
    workflow: str
    runbook: str | None = None
    last_result: ChaosDrillLastResult | None = None


class ChaosDrillCapabilities(BaseModel):
    can_run: bool


class ChaosDrillCatalog(BaseModel):
    capabilities: ChaosDrillCapabilities
    experiments: list[ChaosDrillExperiment]


class ChaosDrillResult(BaseModel):
    drill_id: str
    experiment_id: str
    passed: bool
    overall_verdict: str
    assertions: list[ChaosDrillAssertion]
    observed: dict[str, Any]
    outcome_summary: str = ""
    duration_ms: int
    run_at: str
    run_by_user_id: str
    run_by_display_name: str
    run_by_role: str


class ChaosDrillSummary(BaseModel):
    drill_id: str
    experiment_id: str
    run_at: str
    run_by_display_name: str
    run_by_role: str
    passed: bool
    overall_verdict: str
    duration_ms: int
    outcome_summary: str = ""
    observed: dict[str, Any] = {}
