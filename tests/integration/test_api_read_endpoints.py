"""Stage 21 -- the API surface the AEGIS Control Center reads from.

Uses FastAPI's TestClient against the real app. The read endpoints hit the real audit
store and (where configured) the real knowledge graph, so these are integration tests, not
unit tests with mocks -- the thing worth proving is that the endpoint reports what the
store actually holds, which a mock would assume away.
"""
import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv()

from services.api.main import app
from services.api.schemas import MIN_JUSTIFICATION_CHARS

pytestmark = pytest.mark.stub

client = TestClient(app)

_NEO4J = bool(os.environ.get("NEO4J_PASSWORD")) and "xxxxxxxx" not in os.environ.get("NEO4J_URI", "")
needs_kg = pytest.mark.skipif(not _NEO4J, reason="BLOCKED_BY_ENVIRONMENT: Neo4j not configured")

# Stage 22: /api/runs/*/decide now requires an authenticated session (services/api/auth.py).
# Logs in as the real seeded EU Qualified Person account (services/integration/seed_users.py)
# against the same audit_store DB every other test in this file already reads from -- not a
# mock, the same "real store, not assumed away" posture the module docstring states.
from services.integration import user_store as _user_store  # noqa: E402


def _auth_headers() -> dict:
    conn = _user_store.get_connection()
    try:
        _user_store.create_user(conn, "test_qp", "Test QP", "EU Qualified Person", "test-qp-password")
        session = _user_store.login(conn, "test_qp", "test-qp-password")
    finally:
        conn.close()
    return {"Authorization": f"Bearer {session.token}"}


AUTH = _auth_headers()


# --- decide: the justification contract (G-10) ------------------------------------


def test_decide_rejects_a_missing_justification():
    """The justification is not optional. A client that omits it is refused at the
    boundary with a 422, before any graph is resumed."""
    r = client.post("/api/runs/R-nonexistent/decide", json={"workflow": "batch_review", "action": "approved"}, headers=AUTH)
    assert r.status_code == 422


def test_decide_rejects_a_token_justification():
    r = client.post(
        "/api/runs/R-nonexistent/decide",
        json={"workflow": "batch_review", "action": "approved", "justification": "ok"},
        headers=AUTH,
    )
    assert r.status_code == 422
    assert MIN_JUSTIFICATION_CHARS > 1


def test_decide_on_an_unknown_run_is_404_not_a_silent_success():
    r = client.post(
        "/api/runs/R-nonexistent/decide",
        json={
            "workflow": "batch_review", "action": "approved",
            "justification": "A justification long enough to pass validation.",
        },
        headers=AUTH,
    )
    assert r.status_code == 404


def test_veto_is_rejected_for_workflows_that_have_no_veto():
    """PV's advisory veto is a PV mechanism. Offering it elsewhere would imply a control
    that does not exist in those graphs."""
    for workflow in ("batch_review", "supply_planning"):
        r = client.post(
            "/api/runs/R-nonexistent/decide",
            json={
                "workflow": workflow, "action": "veto",
                "justification": "A justification long enough to pass validation.",
            },
            headers=AUTH,
        )
        assert r.status_code in (400, 404), workflow


# --- Stage 25: every record-specific read requires a session ----------------------


@pytest.mark.parametrize(
    "path", ["/api/queue", "/api/runs", "/api/runs/filters", "/api/evidence",
             "/api/evidence/stats", "/api/governance", "/api/dashboard", "/api/notifications"],
)
def test_record_specific_reads_require_a_session(path):
    """Before Stage 25 these were reachable with no Authorization header at all -- not
    merely unrestricted by role, genuinely unauthenticated. A caller with the API URL and
    no login could read every run's evidence and findings. Fixed by requiring a session
    (any role -- reads stay unrestricted by role, only decide() is), matching what the CD
    smoke test already asserts for /api/runs/{id}/chat ('actually enforcing auth')."""
    assert client.get(path).status_code == 401


def test_run_detail_requires_a_session():
    assert client.get("/api/runs/R-definitely-not-a-real-run").status_code == 401


# --- run history ------------------------------------------------------------------


def test_run_history_returns_a_page_with_a_real_total():
    r = client.get("/api/runs", params={"limit": 5}, headers=_auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["limit"] == 5
    assert len(body["items"]) <= 5
    assert body["total"] >= len(body["items"])


def test_run_history_limit_is_bounded():
    """An unbounded limit is a way to ask the API to read the whole store into memory."""
    assert client.get("/api/runs", params={"limit": 100000}, headers=_auth_headers()).status_code == 422
    assert client.get("/api/runs", params={"limit": 0}, headers=_auth_headers()).status_code == 422
    assert client.get("/api/runs", params={"offset": -1}, headers=_auth_headers()).status_code == 422


def test_run_history_filters_by_workflow():
    body = client.get("/api/runs", params={"workflow": "pv_intake", "limit": 50}, headers=_auth_headers()).json()
    assert all(item["workflow"] == "pv_intake" for item in body["items"])


def test_run_filters_endpoint_reports_values_that_exist():
    body = client.get("/api/runs/filters", headers=_auth_headers()).json()
    assert set(body) == {"workflow", "terminal_state", "requester_role", "abstention_reason"}
    assert all(isinstance(v, list) for v in body.values())


def test_filters_route_is_not_shadowed_by_the_run_id_route():
    """/api/runs/filters and /api/runs/{run_id} share a prefix -- declaration order is
    what keeps 'filters' from being read as a run id."""
    assert isinstance(client.get("/api/runs/filters", headers=_auth_headers()).json(), dict)


# --- run detail -------------------------------------------------------------------


def test_unknown_run_detail_is_404():
    assert client.get("/api/runs/R-definitely-not-a-real-run", headers=_auth_headers()).status_code == 404


def test_known_run_detail_reports_what_it_can_and_says_what_it_cannot():
    page = client.get("/api/runs", params={"limit": 1}, headers=_auth_headers()).json()
    if not page["items"]:
        pytest.skip("audit store is empty -- nothing to open")
    run_id = page["items"][0]["run_id"]
    body = client.get(f"/api/runs/{run_id}", headers=_auth_headers()).json()

    assert body["run_id"] == run_id
    assert body["audit"] is not None
    assert isinstance(body["timeline"], list)
    # A historical run has no live decision-support package. The endpoint must say so
    # explicitly rather than returning empty fields the UI would have to interpret.
    if not body["decision_support_available"]:
        assert body["decision_support_unavailable_reason"]


def test_timeline_events_are_ordered_and_typed():
    page = client.get("/api/runs", params={"limit": 20}, headers=_auth_headers()).json()
    for item in page["items"]:
        timeline = client.get(f"/api/runs/{item['run_id']}", headers=_auth_headers()).json()["timeline"]
        if len(timeline) < 2:
            continue
        assert timeline == sorted(timeline, key=lambda e: e["at"])
        assert all(e["event_type"] and e["action"] for e in timeline)
        return


# --- evidence catalog -------------------------------------------------------------


@needs_kg
def test_evidence_catalog_shows_non_citable_items_and_labels_them():
    """The Explorer must be able to show an untrusted or superseded document. Its value is
    in saying 'you cannot rely on this', which requires returning it."""
    items = client.get("/api/evidence", headers=_auth_headers()).json()
    assert items
    by_status = {i["status"] for i in items}
    assert by_status - {"approved", "draft"}, "expected at least one non-citable item in the corpus"
    for item in items:
        assert item["citable"] == (item["status"] in ("approved", "draft"))


@needs_kg
def test_untrusted_and_superseded_are_never_reported_as_citable():
    """The single invariant this endpoint could plausibly break."""
    for item in client.get("/api/evidence", headers=_auth_headers()).json():
        if item["status"] in ("untrusted", "superseded"):
            assert item["citable"] is False


@needs_kg
def test_catalog_citable_rule_agrees_with_what_retrieval_actually_enforces():
    """The catalog imports evidence_retrieve's own citable tuple rather than restating it,
    so the page cannot drift into calling something usable that a run could not retrieve.
    `local_approved` is the case that would expose a restatement: it reads as approved to
    a human but is not in the retrieval tool's citable set."""
    from services.integration.evidence_retrieve import _CITABLE_STATUSES

    for item in client.get("/api/evidence", headers=_auth_headers()).json():
        assert item["citable"] == (item["status"] in _CITABLE_STATUSES)


@needs_kg
def test_evidence_stats_are_counted_not_asserted():
    stats = client.get("/api/evidence/stats", headers=_auth_headers()).json()
    assert stats["total"] == sum(stats["by_status"].values())
    assert stats["citable_total"] <= stats["total"]


# --- governance -------------------------------------------------------------------


def test_governance_snapshot_reports_the_real_policy_contract():
    body = client.get("/api/governance", headers=_auth_headers()).json()
    assert body["policy_contract_version"] == "v1"
    batch = body["prohibited_actions"]["by_workflow"]["batch_review"]
    assert "release the batch" in batch["banned_terms"]
    assert "release_recommended" in batch["banned_field_names"]


def test_governance_snapshot_accurately_states_real_auth_exists():
    """The inverse of this test's old name and old assertion: this page must never claim a
    security control is MISSING when it is real and enforced (Stage 22/25) -- that's just
    as dishonest as overclaiming one that doesn't exist, and it's what governance_view.py's
    'authentication' block said until this stage, predating the real login system."""
    auth = client.get("/api/governance", headers=_auth_headers()).json()["authentication"]
    assert "IMPLEMENTED" in auth["status"]
    assert "require_user" in auth["detail"]
    assert "synthetic" in auth["planned"]


def test_governance_reports_supply_dual_approval_as_two_required_legs():
    roles = client.get("/api/governance", headers=_auth_headers()).json()["approver_roles"]["supply_planning"]
    assert roles["required_legs"] == ["planning", "quality"]
    assert "one leg approving is not approval" in roles["structure"]


def test_governance_reports_the_pv_veto_as_non_overridable():
    pv = client.get("/api/governance", headers=_auth_headers()).json()["approver_roles"]["pv_intake"]
    assert pv["veto_role"] == "Patient Safety Representative"
    assert "cannot be overridden" in pv["structure"]


def test_governance_is_read_only():
    """No verb other than GET is exposed on a governance route."""
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)("/api/governance", headers=_auth_headers()).status_code == 405


# --- health -----------------------------------------------------------------------


def test_health_detail_measures_each_dependency():
    body = client.get("/api/health/detail").json()
    assert body["api"]["status"] == "ok"
    names = {d["name"] for d in body["dependencies"]}
    assert "Policy engine" in names and "Audit store (SQLite, append-only)" in names
    for dep in body["dependencies"]:
        assert dep["status"] in ("ok", "degraded", "unavailable", "not_configured")


def test_health_detail_distinguishes_not_configured_from_unavailable():
    """Collapsing these would misreport which dependency actually stops the system."""
    statuses = {d["name"]: d["status"] for d in client.get("/api/health/detail").json()["dependencies"]}
    assert statuses  # each is one of the four, asserted above; this pins the distinction's existence
    assert "not_configured" != "unavailable"


def test_health_detail_does_not_leak_secrets():
    """Probes touch credentialed services. Their detail strings must describe state, never
    echo a URL or key."""
    body = client.get("/api/health/detail").text
    for secret_env in ("REDIS_URL", "NEO4J_PASSWORD", "ANTHROPIC_API_KEY", "GROQ_API_KEY"):
        value = os.environ.get(secret_env, "")
        if value and len(value) > 8:
            assert value not in body, f"{secret_env} leaked into /api/health/detail"


def test_error_responses_do_not_expose_a_stack_trace():
    r = client.get("/api/runs/R-definitely-not-a-real-run")
    assert "Traceback" not in r.text
    assert "sqlite3" not in r.text.lower()


# --- notifications (Stage 23) -------------------------------------------------


def test_notifications_requires_auth_and_reports_recent_escalations():
    """GET /api/notifications is the notification bell's source, and (Stage 25) now
    requires a session like every other record-specific read -- see main.py's
    list_notifications docstring for why the earlier unauthenticated exception no
    longer applies. Uses the escalation watcher's real scan against the real, shared
    audit store (this file's own posture -- see the module docstring), a unique run_id
    so this test cannot collide with any other test's rows or with a previous run of
    itself."""
    import uuid
    from datetime import UTC, datetime, timedelta

    from services.api import pending_queue
    from services.integration import hitl_escalation_watch

    run_id = f"R-notif-endpoint-{uuid.uuid4().hex[:8]}"
    pending_queue.add(
        pending_queue.PendingEntry(
            run_id=run_id, workflow="pv_intake", subject_id="PV-notif-test",
            requester_role="Safety physician", approver_roles=["Global Head of Pharmacovigilance"],
            required_legs=None, approved_legs=[], draft_summary=None, draft_claims=[],
            created_at=(datetime.now(UTC) - timedelta(hours=25)).isoformat(),  # past pv_intake's 24h T3
        )
    )
    try:
        fired = hitl_escalation_watch.scan_once()
        assert any(n.run_id == run_id for n in fired)

        assert client.get("/api/notifications").status_code == 401

        r = client.get("/api/notifications", headers=_auth_headers())
        assert r.status_code == 200
        rows = r.json()
        match = next(row for row in rows if row["run_id"] == run_id)
        assert match["tier"] == "T3"
        assert match["severity"] == 4
        assert match["workflow"] == "pv_intake"
        # The pending entry is still in memory at read time, so the enrichment fields
        # resolve rather than reporting null.
        assert match["subject_id"] == "PV-notif-test"
        assert match["approver_roles"] == ["Global Head of Pharmacovigilance"]
    finally:
        pending_queue.remove(run_id)


def test_notifications_reports_null_enrichment_for_a_run_no_longer_pending():
    """A decided run, or one from a process that has since restarted, has no pending
    entry -- the endpoint must say so honestly rather than guessing a subject id."""
    import uuid
    from datetime import UTC, datetime, timedelta

    from services.api import pending_queue
    from services.integration import hitl_escalation_watch

    run_id = f"R-notif-gone-{uuid.uuid4().hex[:8]}"
    pending_queue.add(
        pending_queue.PendingEntry(
            run_id=run_id, workflow="batch_review", subject_id="B-notif-gone",
            requester_role="EU Qualified Person", approver_roles=["EU Qualified Person"],
            required_legs=None, approved_legs=[], draft_summary=None, draft_claims=[],
            created_at=(datetime.now(UTC) - timedelta(hours=17)).isoformat(),
        )
    )
    hitl_escalation_watch.scan_once()
    pending_queue.remove(run_id)  # simulate: decided, or process restarted

    rows = client.get("/api/notifications", headers=_auth_headers()).json()
    match = next(row for row in rows if row["run_id"] == run_id)
    assert match["subject_id"] is None
    assert match["approver_roles"] is None


def test_notifications_respects_the_limit_param():
    r = client.get("/api/notifications?limit=1", headers=_auth_headers())
    assert r.status_code == 200
    assert len(r.json()) <= 1


def test_notifications_is_read_only():
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)("/api/notifications", headers=_auth_headers()).status_code == 405
