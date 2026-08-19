"""API auth for chaos-drill endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from services.api.main import app
from services.integration import user_store

pytestmark = pytest.mark.stub

client = TestClient(app)


def _auth_headers(user_id: str, display_name: str, role: str, password: str) -> dict:
    conn = user_store.get_connection()
    try:
        user_store.create_user(conn, user_id, display_name, role, password)
        session = user_store.login(conn, user_id, password)
    finally:
        conn.close()
    return {"Authorization": f"Bearer {session.token}"}


@pytest.fixture(scope="module")
def auth_ciso():
    return _auth_headers("chaos_ciso", "Chaos CISO", "CISO / DPO", "chaos-ciso-pass")


@pytest.fixture(scope="module")
def auth_qp():
    return _auth_headers("chaos_qp", "Chaos QP", "EU Qualified Person", "chaos-qp-pass")


@pytest.fixture(scope="module")
def auth_super_admin():
    return _auth_headers("chaos_admin", "Chaos Admin", "Super Admin", "chaos-admin-pass")


def test_unauthenticated_catalog_401():
    assert client.get("/api/chaos-drill/experiments").status_code == 401


def test_qp_cannot_view_catalog(auth_qp):
    """Chaos drill is restricted to Super Admin / CISO-DPO -- not just run, view too."""
    r = client.get("/api/chaos-drill/experiments", headers=auth_qp)
    assert r.status_code == 403


def test_qp_cannot_run_drill(auth_qp):
    r = client.post("/api/chaos-drill/experiments/CHAOS-POLICY-01/run", headers=auth_qp, json={})
    assert r.status_code == 403


def test_ciso_can_run_drill(auth_ciso):
    r = client.post("/api/chaos-drill/experiments/CHAOS-POLICY-01/run", headers=auth_ciso, json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["experiment_id"] == "CHAOS-POLICY-01"
    assert body["overall_verdict"] in ("pass", "fail")
    assert body["passed"] is True
    assert "fail_closed" in body["outcome_summary"]
    assert body["observed"]["terminal_state"] == "refused"


def test_super_admin_can_run_drill(auth_super_admin):
    r = client.post(
        "/api/chaos-drill/experiments/CHAOS-POLICY-01/run", headers=auth_super_admin, json={}
    )
    assert r.status_code == 200, r.text


def test_super_admin_can_list_catalog(auth_super_admin):
    r = client.get("/api/chaos-drill/experiments", headers=auth_super_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["capabilities"]["can_run"] is True
    ids = {e["id"] for e in body["experiments"]}
    assert "CHAOS-LLM-01" in ids
    assert "CHAOS-CKPT-01" in ids


def test_ops_only_run_returns_400(auth_ciso):
    r = client.post("/api/chaos-drill/experiments/CHAOS-CKPT-01/run", headers=auth_ciso, json={})
    assert r.status_code == 400


def test_history_visible_to_super_admin(auth_super_admin, auth_ciso):
    client.post("/api/chaos-drill/experiments/CHAOS-NEO4J-01/run", headers=auth_ciso, json={})
    r = client.get("/api/chaos-drill/history", headers=auth_super_admin)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_history_hidden_from_qp(auth_qp):
    r = client.get("/api/chaos-drill/history", headers=auth_qp)
    assert r.status_code == 403
