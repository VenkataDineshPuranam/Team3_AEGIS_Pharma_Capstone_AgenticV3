"""Orchestrator API -- the C4 container this belongs to (c4_containers.md: "Orchestrator
API... owns the shared state schema and HITL interrupt mechanism" -> services/api).

Wraps the three existing, already-tested graphs (graph.py, pv_graph.py, supply_graph.py)
over HTTP. No changes to any graph's internal logic -- this is purely an HTTP boundary
around code that already works, so every guarantee those graphs' own test suites already
proved (guard behavior, HITL routing, veto, dual-approval, degraded mode, fail-closed
policy engine) holds here unchanged.

Stage 21 adds READ endpoints (run history, run detail, audit timeline, evidence catalog,
governance snapshot, health detail) so the AEGIS Control Center can show what the system
actually did. They are additive: no existing endpoint's request or response shape changed
except `DecideRequest`, which now requires the justification the audit store was always
supposed to receive.

The one rule this file must never break: the API is a boundary, not a control. Every
governance decision below is made by the graph or the policy engine and reported here.
Nothing in this module decides whether an action is permitted.

Run: uvicorn services.api.main:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from langgraph.types import Command

from packages.config.llm_client import get_llm
from packages.domain.state import new_state
from services.api import (
    compliance_view,
    eval_dashboard,
    governance_view,
    health_probe,
    pending_queue,
    record_chat,
)
from services.api.auth import require_user
from services.api.graph import build_graph
from services.api.pv_graph import build_pv_graph
from services.api.research_graph import build_research_graph
from services.api.clinical_graph import build_clinical_graph
from services.api.regulatory_graph import build_regulatory_graph
from services.api.schemas import (
    AuditedRun,
    AuditEvent,
    DashboardResponse,
    DecideRequest,
    EvalScorecard,
    EvidenceCatalogItem,
    GovernanceSnapshot,
    HealthDetail,
    HitlTimerInfo,
    InjectCoverage,
    LoginRequest,
    NotificationItem,
    QueueEntry,
    RecordChatRequest,
    RecordChatResponse,
    RunDetail,
    RunHistoryPage,
    RunResult,
    SessionInfo,
    SubmitRunRequest,
)
from services.api.supply_graph import build_supply_graph
from services.integration import audit_store, evidence_catalog, hitl_escalation_watch, hitl_timer, user_store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Background scheduler (Stage 23) -- the live poller hitl_timer.py's own docstring said
# did not exist ("no scheduler advances it"). Notification only: it writes an audit
# record and sends a best-effort email when a pending run crosses severity 3 or 4
# (services/integration/hitl_escalation_watch.py has the full scope statement). It never
# decides, approves, or widens who may approve a run -- BC-12 ("timeout => no action,
# ever") is unaffected.
# ---------------------------------------------------------------------------

HITL_NOTIFIER_POLL_SECONDS = float(os.environ.get("HITL_NOTIFIER_POLL_SECONDS", "60"))


async def _hitl_escalation_loop() -> None:
    """Runs for the API process's lifetime. `scan_once` is synchronous sqlite work, run in
    a thread so it never blocks the event loop other requests share. One bad scan must not
    end all future ones, so the whole iteration is guarded -- the loop itself is what stays
    alive; only its current attempt can fail."""
    while True:
        try:
            await asyncio.to_thread(hitl_escalation_watch.scan_once)
        except Exception:  # noqa: BLE001 -- ADR-007: a scan failure must not end future scans
            logger.exception("hitl_escalation_watch.scan_once failed")
        await asyncio.sleep(HITL_NOTIFIER_POLL_SECONDS)


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    task = asyncio.create_task(_hitl_escalation_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="AEGIS Pharma AI -- Orchestrator API", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("WEB_ORIGIN", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
)

_WORKFLOWS = (
    "batch_review", "pv_intake", "supply_planning",
    "research_review", "clinical_integrity", "regulatory_completeness",
)
_llm = get_llm()

# Subject-id-parametrized graphs: batch_id/case_id/product_id is baked into the graph
# closure at build time (matches every existing graph module's own design -- it's a
# constructor argument, not a per-run field). To let a single running API serve
# different subject ids without rebuilding a graph per request, build one graph per
# (workflow, subject_id) pair the first time it's requested, and cache it -- each cached
# graph's own MemorySaver is what lets a paused run's state survive between the initial
# submit and the later decide() resume call, same assumption every existing test relies on.
_GRAPH_CACHE: dict[tuple[str, str], object] = {}


def _get_graph(workflow: str, subject_id: str):
    key = (workflow, subject_id)
    if key in _GRAPH_CACHE:
        return _GRAPH_CACHE[key]
    if workflow == "batch_review":
        graph = build_graph(llm=_llm, batch_id=subject_id)
    elif workflow == "pv_intake":
        graph = build_pv_graph(llm=_llm, case_id=subject_id)
    elif workflow == "supply_planning":
        graph = build_supply_graph(llm=_llm, product_id=subject_id)
    elif workflow == "research_review":
        graph = build_research_graph(llm=_llm, research_id=subject_id)
    elif workflow == "clinical_integrity":
        graph = build_clinical_graph(llm=_llm, protocol_id=subject_id)
    elif workflow == "regulatory_completeness":
        graph = build_regulatory_graph(llm=_llm, submission_id=subject_id)
    else:
        raise HTTPException(400, f"Unknown workflow {workflow!r}")
    _GRAPH_CACHE[key] = graph
    return graph


def _evidence_dicts(state: dict) -> list[dict]:
    """EvidenceItems from a run's state, as JSON. These are already ADR-003-filtered by
    construction -- an item could not be in state otherwise."""
    return [e.model_dump(mode="json") for e in (state.get("evidence") or [])]


def _payload_dict(state: dict) -> dict | None:
    payload = state.get("domain_payload")
    return payload.model_dump(mode="json") if payload is not None else None


def _result_from_state(run_id: str, workflow: str, state: dict) -> RunResult:
    draft = state.get("draft_output")
    return RunResult(
        run_id=run_id,
        workflow=workflow,
        status="pending_approval" if "__interrupt__" in state else _status_for(state),
        terminal_state=state.get("terminal_state"),
        abstention_reason=state.get("abstention_reason"),
        llm_calls=state.get("llm_calls"),
        draft_summary=draft.summary if draft else None,
        draft_claims=[c.model_dump() for c in draft.claims] if draft else [],
        approver_roles=state.get("approver_roles") or [],
        required_legs=state.get("hitl_required_legs"),
        approved_legs=state.get("hitl_approved_legs") or [],
        veto_recorded=bool(state.get("veto_recorded")),
    )


def _status_for(state: dict) -> str:
    terminal = state.get("terminal_state")
    if terminal in ("completed", "abstained", "blocked", "refused"):
        return terminal
    return "abstained"  # defensive fallback -- should be unreachable given graph invariants


def _queue_entry(e: pending_queue.PendingEntry) -> QueueEntry:
    timer = hitl_timer.compute(e.created_at, e.workflow)
    return QueueEntry(
        run_id=e.run_id, workflow=e.workflow, subject_id=e.subject_id,
        requester_role=e.requester_role, approver_roles=e.approver_roles,
        required_legs=e.required_legs, approved_legs=e.approved_legs,
        draft_summary=e.draft_summary, draft_claims=e.draft_claims, created_at=e.created_at,
        evidence=e.evidence, domain_payload=e.domain_payload,
        hitl_timer=HitlTimerInfo(
            tier=timer.tier, label=timer.label, severity=timer.severity,
            hours_elapsed=timer.hours_elapsed, hours_to_next_tier=timer.hours_to_next_tier,
        ),
    )


# ---------------------------------------------------------------------------
# Auth (Stage 22)
# ---------------------------------------------------------------------------


@app.get("/api/auth/demo-accounts")
def demo_accounts():
    """Populates the login page's account picker. Returns user_id/display_name/role only
    -- never a password, even though this is a documented synthetic demo environment
    (docs/governance/demo_login_credentials.md), because a picker that types a password
    into the DOM for you is a bad habit to demo even in a synthetic system."""
    conn = user_store.get_connection()
    try:
        return user_store.list_users(conn)
    finally:
        conn.close()


@app.post("/api/auth/login", response_model=SessionInfo)
def login(req: LoginRequest):
    conn = user_store.get_connection()
    try:
        session = user_store.login(conn, req.user_id, req.password)
    except user_store.InvalidCredentials as exc:
        raise HTTPException(401, str(exc)) from exc
    finally:
        conn.close()
    return SessionInfo(
        token=session.token, user_id=session.user_id, display_name=session.display_name,
        role=session.role, expires_at=session.expires_at,
    )


@app.post("/api/auth/logout")
def logout(session: user_store.Session = Depends(require_user)):
    conn = user_store.get_connection()
    try:
        user_store.logout(conn, session.token)
    finally:
        conn.close()
    return {"status": "logged_out"}


@app.get("/api/auth/me", response_model=SessionInfo)
def me(session: user_store.Session = Depends(require_user)):
    return SessionInfo(
        token=session.token, user_id=session.user_id, display_name=session.display_name,
        role=session.role, expires_at=session.expires_at,
    )


@app.get("/api/auth/roles")
def role_catalog():
    """The role/boundary table itself -- what each role uses the product for and must
    never do -- so the frontend can render it without hardcoding a second copy."""
    return {
        role: {"product_use": info["product_use"], "must_never": info["must_never"]}
        for role, info in user_store.ROLE_CATALOG.items()
    }


def _require_super_admin(session: user_store.Session = Depends(require_user)) -> user_store.Session:
    """Evaluation results, red-team inject coverage, and compliance evidence describe how
    well-defended (or not) the system is -- exposing that to every logged-in role hands a
    map of untested edges to anyone with a login, not just the person accountable for
    system-wide oversight. Super Admin is the only role with no decide authority anywhere
    (user_store.ROLE_CATALOG), so it's the natural place for a read-only,
    everything-visible surface like this one."""
    if session.role != "Super Admin":
        raise HTTPException(403, "Only Super Admin may view this data.")
    return session


@app.get("/api/compliance")
def compliance(session: user_store.Session = Depends(_require_super_admin)):
    """EU AI Act risk classification + ISO 42001 control mapping + open gap register,
    parsed live from docs/governance/compliance/*.md. Super Admin only -- see
    _require_super_admin's docstring."""
    try:
        return compliance_view.snapshot()
    except compliance_view.ComplianceDocsUnavailable as exc:
        raise HTTPException(503, f"Compliance documentation unavailable: {exc}") from exc


@app.post("/api/runs", response_model=RunResult)
def submit_run(req: SubmitRunRequest, session: user_store.Session = Depends(require_user)):
    graph = _get_graph(req.workflow, req.subject_id)
    run_id = f"R-web-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": run_id}}
    state = new_state(run_id=run_id, workflow=req.workflow, requester_role=req.requester_role)
    result = graph.invoke(state, config=config)

    if "__interrupt__" in result:
        draft = result.get("draft_output")
        pending_queue.add(
            pending_queue.PendingEntry(
                run_id=run_id, workflow=req.workflow, subject_id=req.subject_id,
                requester_role=req.requester_role,
                approver_roles=result.get("approver_roles") or [],
                required_legs=result.get("hitl_required_legs"),
                approved_legs=result.get("hitl_approved_legs") or [],
                draft_summary=draft.summary if draft else None,
                draft_claims=[c.model_dump() for c in draft.claims] if draft else [],
                evidence=_evidence_dicts(result),
                domain_payload=_payload_dict(result),
            )
        )

    return _result_from_state(run_id, req.workflow, result)


@app.get("/api/queue", response_model=list[QueueEntry])
def get_queue(workflow: str | None = None, session: user_store.Session = Depends(require_user)):
    return [_queue_entry(e) for e in pending_queue.list_all(workflow)]


@app.post("/api/runs/{run_id}/decide", response_model=RunResult)
def decide_run(run_id: str, req: DecideRequest, session: user_store.Session = Depends(require_user)):
    """Resume a paused run with a human's decision.

    This endpoint is never retried automatically by any client, and must not be: it
    records an irreversible human action in an append-only store. The API layer enforces
    shape (a justification of real length, a leg where the workflow needs one) AND, as of
    Stage 22, authorization: `require_user` establishes who is calling, and
    `user_store.approver_string_for` checks whether THIS role may decide THIS
    (workflow, leg) at all before the request reaches the graph -- a 403 here means the
    logged-in role was never eligible, not a governance verdict the graph itself renders.
    Every governance consequence beyond that -- whether a veto stands, whether one leg is
    enough, what a timeout means -- is still decided inside the graph, unchanged.
    """
    entry = pending_queue.get(run_id)
    if entry is None:
        raise HTTPException(404, f"No pending run {run_id!r} -- already decided, or never existed.")

    if req.workflow != entry.workflow:
        # The client sends the workflow it believes it is deciding. If that disagrees with
        # the paused run, something is out of sync -- resolving it by trusting either side
        # would resume the wrong graph, so refuse instead.
        raise HTTPException(409, "Workflow does not match the pending run.")

    if req.action == "veto":
        if not user_store.can_veto(session.role, req.workflow):
            raise HTTPException(403, f"Role {session.role!r} may not register a veto for {req.workflow!r}.")
    elif req.action != "timed_out":
        required_role = user_store.approver_string_for(session.role, req.workflow, req.leg)
        if required_role is None:
            raise HTTPException(
                403,
                f"Role {session.role!r} is not an eligible approver for "
                f"{req.workflow!r}" + (f" ({req.leg} leg)" if req.leg else "") + ".",
            )

    graph = _get_graph(req.workflow, entry.subject_id)
    config = {"configurable": {"thread_id": run_id}}

    if req.workflow == "supply_planning":
        if req.action == "veto":
            raise HTTPException(400, "Veto applies to pv_intake only.")
        if req.action != "timed_out" and req.leg is None:
            raise HTTPException(400, "supply_planning decisions require a leg ('planning' or 'quality').")
        if req.leg is not None and req.leg in entry.approved_legs:
            raise HTTPException(409, f"The {req.leg} leg has already been approved for this run.")
    elif req.action == "veto" and req.workflow != "pv_intake":
        raise HTTPException(400, "Veto applies to pv_intake only.")

    resume_value = {
        "action": req.action,
        "justification": req.justification,
        "claimed_identity": f"{session.display_name} ({session.role})",
        "leg": req.leg,
    }
    if req.action == "timed_out":
        # A timeout is not a human action and carries no justification -- it is the
        # ABSENCE of one. Sent as the bare legacy string so every graph takes exactly the
        # timeout path its own tests already cover.
        resume_value = "timed_out"

    result = graph.invoke(Command(resume=resume_value), config=config)

    if "__interrupt__" in result:
        # supply_planning: one leg approved, still pending the other. NOTE: result's own
        # hitl_approved_legs is NOT yet updated here -- supply_graph.py's hitl_interrupt
        # loops on multiple interrupt() calls inside ONE node execution, and LangGraph
        # only persists a node's state changes once the node function fully returns.
        # Mid-loop (after exactly one leg), the graph's own state snapshot still shows the
        # pre-this-call value, not what we just submitted -- found live, via this exact
        # endpoint. Tracked here instead, from what the API itself just sent, which it
        # knows unambiguously regardless of when the graph's checkpoint catches up.
        approved_legs = list(entry.approved_legs)
        if req.workflow == "supply_planning" and req.action == "approved" and req.leg not in approved_legs:
            approved_legs.append(req.leg)
        pending_queue.update_approved_legs(run_id, approved_legs)
    else:
        pending_queue.remove(run_id)

    response = _result_from_state(run_id, req.workflow, result)
    if "__interrupt__" in result:
        # Same reason as above -- report what the API just tracked, not the graph's
        # not-yet-caught-up snapshot, so the UI shows the real approval progress.
        response.approved_legs = pending_queue.get(run_id).approved_legs
    return response


# ---------------------------------------------------------------------------
# Read endpoints (Stage 21)
# ---------------------------------------------------------------------------


@app.get("/api/runs", response_model=RunHistoryPage)
def list_runs(
    workflow: str | None = None,
    terminal_state: str | None = None,
    subject_id: str | None = None,
    search: str | None = None,
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: user_store.Session = Depends(require_user),
):
    """Historical runs, from the append-only audit store. Newest first."""
    conn = audit_store.get_connection()
    try:
        rows, total = audit_store.list_agent_runs(
            conn, workflow=workflow, terminal_state=terminal_state,
            subject_id=subject_id, search=search, limit=limit, offset=offset,
        )
    finally:
        conn.close()
    return RunHistoryPage(
        items=[AuditedRun(**r) for r in rows], total=total, limit=limit, offset=offset
    )


@app.get("/api/runs/filters")
def run_filters(session: user_store.Session = Depends(require_user)):
    """Distinct values actually present in the audit store, so the History page's filters
    offer what exists rather than a hardcoded list that may not match the data."""
    conn = audit_store.get_connection()
    try:
        return {
            column: audit_store.distinct_values(conn, column)
            for column in ("workflow", "terminal_state", "requester_role", "abstention_reason")
        }
    finally:
        conn.close()


@app.get("/api/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str, session: user_store.Session = Depends(require_user)):
    """One run, from both sources that can know about it: the in-memory pending registry
    (only while it is still paused in THIS process) and the audit store (once finalized).

    Neither being present is a real 404. One being present without the other is normal and
    is reported as-is -- a paused run has no audit record yet, and a run decided before
    this process started has no pending entry, which is why `decision_support_available`
    exists rather than leaving the UI to guess what an empty field means.
    """
    pending = pending_queue.get(run_id)
    conn = audit_store.get_connection()
    try:
        audited = audit_store.get_agent_run(conn, run_id)
        timeline = audit_store.run_timeline(conn, run_id)
        overrides = audit_store.human_overrides(conn, run_id)
    finally:
        conn.close()

    if pending is None and audited is None:
        raise HTTPException(404, f"No run {run_id!r} is pending or recorded.")

    reason = None
    if pending is None:
        reason = (
            "The decision-support package (draft summary, claims, evidence and structured "
            "findings) is held in the run's own graph state while it is paused for approval. "
            "It is not copied into the append-only audit store, so it is unavailable for a run "
            "that has already been decided, or that was decided before this API process started. "
            "The audit record and timeline below are complete and authoritative."
        )

    return RunDetail(
        run_id=run_id,
        pending=_queue_entry(pending) if pending else None,
        audit=AuditedRun(**audited) if audited else None,
        timeline=[AuditEvent(**e) for e in timeline],
        human_actions=overrides,
        decision_support_available=pending is not None,
        decision_support_unavailable_reason=reason,
    )


@app.post("/api/runs/{run_id}/chat", response_model=RecordChatResponse)
def chat_about_run(
    run_id: str, req: RecordChatRequest, session: user_store.Session = Depends(require_user)
):
    """Record Assistant -- a grounded, guarded reading aid for one run.

    Read-only in every sense that matters: it writes nothing, decides nothing, and cannot
    resume a paused run. The one thing it must not become is a side channel around
    `decide` -- so it is authenticated like every other endpoint, it enforces the same
    segregation-of-duties rule the workflow lists enforce (a role segregated from a
    workflow cannot read its records here either), and its prose is checked against the
    same ProhibitionContract the graph's own guard uses before it is returned.

    Guard outcomes are results, not errors: a refused question and a withheld answer both
    come back 200 with `guard` populated, because the record facts and next steps are
    still valid and still useful. Only "no such run" and "not your workflow" are HTTP
    failures.
    """
    try:
        return RecordChatResponse(
            **record_chat.answer(run_id, req.question, role=session.role, llm=_llm)
        )
    except record_chat.RecordNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except record_chat.RecordNotVisible as exc:
        raise HTTPException(403, str(exc)) from exc


@app.get("/api/notifications", response_model=list[NotificationItem])
def list_notifications(
    limit: int = Query(default=20, ge=1, le=100), session: user_store.Session = Depends(require_user)
):
    """Recent HITL escalation events -- the web app's notification bell. Read-only: this
    endpoint cannot fire an escalation, only report ones hitl_escalation_watch.py's
    background loop already recorded. Requires a session, same as every other
    record-specific read here (`/api/queue`, `/api/runs`) -- the bell is only ever
    rendered inside RequireAuth's tree (apps/web/components/layout/AppShell.tsx), never on
    the login page, so there is no login-page-bell case to keep this one unauthenticated for.
    """
    conn = audit_store.get_connection()
    try:
        rows = audit_store.list_recent_hitl_escalations(conn, limit=limit)
    finally:
        conn.close()

    items = []
    for row in rows:
        entry = pending_queue.get(row["run_id"])
        items.append(NotificationItem(
            run_id=row["run_id"], workflow=row["workflow"], tier=row["tier"],
            severity=hitl_timer.TIER_SEVERITY.get(row["tier"], 0),
            evaluated_at=row["evaluated_at"],
            subject_id=entry.subject_id if entry else None,
            approver_roles=entry.approver_roles if entry else None,
        ))
    return items


@app.get("/api/evidence", response_model=list[EvidenceCatalogItem])
def list_evidence(session: user_store.Session = Depends(require_user)):
    """The evidence corpus, INCLUDING non-citable items, each labelled with whether it may
    be relied upon. See services/integration/evidence_catalog.py for why showing them here
    does not weaken the rule that a run can never retrieve them."""
    try:
        return [EvidenceCatalogItem(**item) for item in evidence_catalog.list_catalog()]
    except evidence_catalog.CatalogUnavailable as exc:
        raise HTTPException(503, f"Knowledge graph unavailable: {exc}") from exc


@app.get("/api/evidence/stats")
def evidence_stats(session: user_store.Session = Depends(require_user)):
    try:
        return evidence_catalog.catalog_stats()
    except evidence_catalog.CatalogUnavailable as exc:
        raise HTTPException(503, f"Knowledge graph unavailable: {exc}") from exc


@app.get("/api/governance", response_model=GovernanceSnapshot)
def governance(session: user_store.Session = Depends(require_user)):
    return GovernanceSnapshot(**governance_view.snapshot())


@app.get("/api/evals/scorecard", response_model=EvalScorecard)
def evals_scorecard(session: user_store.Session = Depends(_require_super_admin)):
    """Runs the real eval-ai-cache harness in-process, live, on every request -- see
    eval_dashboard.py's module docstring for why this one is safe to compute per-request
    (pure grading logic against synthetic fixtures, ~25ms, no LLM/network calls) while
    inject coverage below is not."""
    return EvalScorecard(**eval_dashboard.eval_scorecard())


@app.get("/api/coverage/injects", response_model=InjectCoverage)
def inject_coverage(session: user_store.Session = Depends(_require_super_admin)):
    """The curated V1-inject-to-V2-reality coverage mapping. Read-only; there is no
    endpoint that can write to this file."""
    try:
        return InjectCoverage(**eval_dashboard.inject_coverage())
    except eval_dashboard.InjectCoverageUnavailable as exc:
        raise HTTPException(503, f"Inject coverage data unavailable: {exc}") from exc


@app.get("/api/dashboard", response_model=DashboardResponse)
def dashboard(workflow: str | None = None, session: user_store.Session = Depends(require_user)):
    from packages.observability.dashboard_data import (
        cache_hit_rate_panel,
        cost_panel,
        guardrail_trip_panel,
        terminal_state_panel,
    )

    return DashboardResponse(
        workflow=workflow,
        cost=cost_panel(workflow).__dict__,
        guardrail_trip=guardrail_trip_panel(workflow).__dict__,
        terminal_states=terminal_state_panel(workflow).__dict__,
        cache=cache_hit_rate_panel(),
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "workflows": list(_WORKFLOWS)}


@app.get("/api/health/detail", response_model=HealthDetail)
def health_detail():
    """Measured dependency health -- every entry is the result of actually touching the
    dependency, except the LLM provider, which reports configuration and says so."""
    conn = audit_store.get_connection()
    try:
        stats = audit_store.store_stats(conn)
    finally:
        conn.close()
    return HealthDetail(
        api=health_probe.DependencyHealth(
            name="Orchestrator API", status="ok",
            detail=f"Serving workflows: {', '.join(_WORKFLOWS)}. "
                   f"{len(pending_queue.list_all())} run(s) currently awaiting a decision.",
        ),
        dependencies=health_probe.all_dependencies(),
        audit_store=stats,
        checked_at=datetime.now(UTC).isoformat(),
    )


# ---------------------------------------------------------------------------
# Debug aid (Stage 22) -- NOT part of the governed product surface.
#
# Reaching HITL severity T2/T3 for real takes 16/24 real elapsed hours (hitl_timer.py).
# This lets a developer backdate an already-real pending run's created_at to see the
# severity badge render at every tier without waiting. It touches ONLY the timestamp the
# badge reads -- the run's findings, evidence, and audit trail are completely untouched,
# and this cannot be reached from any UI control. Off by default; only mounted if
# AEGIS_ENABLE_DEBUG_ENDPOINTS=1 is set, so it never accidentally ships live.
# ---------------------------------------------------------------------------

if os.environ.get("AEGIS_ENABLE_DEBUG_ENDPOINTS") == "1":

    @app.post("/api/debug/backdate/{run_id}")
    def debug_backdate(run_id: str, hours_ago: float = Query(..., ge=0, le=1000)):
        entry = pending_queue.debug_backdate(run_id, hours_ago)
        if entry is None:
            raise HTTPException(404, f"No pending run {run_id!r} to backdate.")
        return _queue_entry(entry)
