"""user_store -- Stage 22 login. SQLite, mirrors audit_store.py's connection pattern.

This is a real, credential-backed login: passwords are salted + PBKDF2-HMAC hashed (stdlib
only, no plaintext ever stored or logged), sessions are server-side rows with an expiry, and
`services.api.auth.require_user` rejects any request whose bearer token doesn't resolve to a
live session. It replaces `OperatorContext`'s old "claimed identity" free-text field, which
`apps/web/components/layout/OperatorContext.tsx` documented plainly as unauthenticated.

What this deliberately still is NOT: a production identity provider. Ten synthetic accounts
(one per governed role, see ROLE_CATALOG below), no SSO, no password reset flow, no lockout
policy beyond what's noted in login(). That scope matches the project's "fully synthetic,
offline-capable" ethos (see V1 CLAUDE.md) applied to V2's own login layer, not a shortcut
taken silently -- see docs/governance/demo_login_credentials.md for the seeded accounts and
the reasoning for not going further.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = REPO_ROOT / "evidence" / "audit_store.sqlite3"  # same DB file as audit_store

SESSION_LIFETIME = timedelta(hours=8)
PBKDF2_ITERATIONS = 260_000

_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_user (
    user_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_session (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Role catalog -- one row per governed role. `approver_for` maps a login role to the
# exact approver-role STRING already baked into each graph's PRIMARY_APPROVER constant
# (services/api/{graph,pv_graph,supply_graph,research_graph,clinical_graph,regulatory_graph}.py,
# services/integration/hitl_route.py). This is the enforcement point: services.api.auth
# checks a decide() caller's role against this map before letting the request reach the
# graph at all, closing the gap the app previously documented as "no server-side
# authorization." Renaming or duplicating the graphs' own PRIMARY_APPROVER strings was
# deliberately avoided -- every existing graph test already asserts those exact strings,
# so this maps TO them instead of replacing them.
# ---------------------------------------------------------------------------

ROLE_CATALOG: dict[str, dict] = {
    "EU Qualified Person": {
        "product_use": "Batch pack",
        "must_never": "Release / certify",
        "approver_for": {
            ("batch_review", None): "EU Qualified Person",
            ("supply_planning", "quality"): "EU Qualified Person",
        },
    },
    "Safety physician": {
        "product_use": "PV pack",
        "must_never": "Causality, reportability",
        "approver_for": {("pv_intake", None): "Global Head of Pharmacovigilance"},
        # pv_graph.py's advisory veto (PV_VETO_ROLE = "Patient Safety Representative") is a
        # SEPARATE constant from the primary approver, registrable at any tier as an
        # independent check-and-balance. There is no distinct "Patient Safety
        # Representative" login role in this catalog, so that authority is granted here
        # instead of inventing an unused eleventh role -- see `can_veto`.
        "veto_for": {"pv_intake"},
    },
    "Supply governance": {
        "product_use": "Draft options",
        "must_never": "Allocate / ship",
        "approver_for": {("supply_planning", "planning"): "Supply Chain VP"},
    },
    "Head of Preclinical Research": {
        "product_use": "Research pack",
        "must_never": "Qualify a model / approve intended use",
        "approver_for": {("research_review", None): "Head of Preclinical Research"},
    },
    "Clinical Trial Medical Monitor": {
        "product_use": "Clinical pack",
        "must_never": "Decide eligibility, unblind, or disposition a deviation",
        "approver_for": {("clinical_integrity", None): "Clinical Trial Medical Monitor"},
    },
    "Head of Regulatory Affairs": {
        "product_use": "Regulatory pack",
        "must_never": "Classify a variation as reportable / mark submission-ready",
        "approver_for": {("regulatory_completeness", None): "Head of Regulatory Affairs"},
    },
    "Quality reviewer": {
        "product_use": "Contradictions and gaps",
        "must_never": "Change quality status",
        "approver_for": {},  # read/oversight only -- no decide() permission on any workflow
    },
    "CISO / DPO": {
        "product_use": "Gates and privacy",
        "must_never": "Consent / residency decisions",
        "approver_for": {},
    },
    "Auditor": {
        "product_use": "Read-only oversight",
        "must_never": "Acknowledge anything",
        "approver_for": {},
    },
    "Unblinding authority": {
        "product_use": "Unblinding findings",
        "must_never": "Unblind; never sees allocation",
        "approver_for": {},  # reviews clinical_integrity findings; never decides for it
        # Segregation of duties, enforced (not just documented): excluded from every
        # supply_planning read endpoint by services.api.auth.visible_workflows().
        "excluded_workflows": {"supply_planning"},
    },
    "Super Admin": {
        "product_use": "Everything -- full cross-workflow visibility for system oversight",
        "must_never": "Approve, reject, veto, or otherwise decide any workflow",
        # Deliberately empty, same as Auditor/CISO/Quality reviewer: this system's whole
        # governance model rests on no single role holding blanket decide authority (BC-12,
        # segregation of duties). "Sees everything" is answered by the ABSENCE of an
        # excluded_workflows entry below, not by adding approve/veto power here.
        "approver_for": {},
    },
}


def visible_workflows(role: str) -> set[str] | None:
    """None means "no restriction" -- every role except Unblinding authority."""
    excluded = ROLE_CATALOG.get(role, {}).get("excluded_workflows")
    if not excluded:
        return None
    all_workflows = {
        "batch_review", "pv_intake", "supply_planning",
        "research_review", "clinical_integrity", "regulatory_completeness",
    }
    return all_workflows - excluded


def approver_string_for(role: str, workflow: str, leg: str | None) -> str | None:
    """The approver-role string `role` is entitled to act as for (workflow, leg), or None
    if this role cannot decide that workflow/leg at all."""
    return ROLE_CATALOG.get(role, {}).get("approver_for", {}).get((workflow, leg))


def can_veto(role: str, workflow: str) -> bool:
    return workflow in ROLE_CATALOG.get(role, {}).get("veto_for", set())


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    # check_same_thread=False -- see audit_store.get_connection's identical fix. Same
    # module, same DB file, same risk if a caller ever holds this connection across a
    # thread-dispatched call the way graph.py's audit_conn does.
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # nolock=1: see audit_store.get_connection's identical fix -- same DB file, same Azure
    # Files (SMB) mount, where SQLite's locking calls aren't reliably honored. Safe here
    # because Container Apps runs at most one replica of this app (maxReplicas=1).
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?nolock=1", uri=True, check_same_thread=False)
    conn.executescript(_SCHEMA)
    return conn


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS).hex()


def create_user(conn: sqlite3.Connection, user_id: str, display_name: str, role: str, password: str) -> None:
    if role not in ROLE_CATALOG:
        raise ValueError(f"Unknown role {role!r} -- not in ROLE_CATALOG")
    salt = secrets.token_bytes(16)
    conn.execute(
        "INSERT OR REPLACE INTO app_user (user_id, display_name, role, password_hash, password_salt, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, display_name, role, _hash_password(password, salt), salt.hex(), datetime.now(UTC).isoformat()),
    )
    conn.commit()


@dataclass
class Session:
    token: str
    user_id: str
    display_name: str
    role: str
    expires_at: str


class InvalidCredentials(Exception):
    pass


def login(conn: sqlite3.Connection, user_id: str, password: str) -> Session:
    row = conn.execute(
        "SELECT user_id, display_name, role, password_hash, password_salt FROM app_user WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        # Deliberately the same error as a wrong password -- do not reveal whether the
        # user_id exists.
        raise InvalidCredentials("Invalid user_id or password.")
    _, display_name, role, password_hash, password_salt = row
    candidate = _hash_password(password, bytes.fromhex(password_salt))
    if not hmac.compare_digest(candidate, password_hash):
        raise InvalidCredentials("Invalid user_id or password.")

    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    expires_at = (now + SESSION_LIFETIME).isoformat()
    conn.execute(
        "INSERT INTO app_session (token, user_id, display_name, role, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
        (token, user_id, display_name, role, now.isoformat(), expires_at),
    )
    conn.commit()
    return Session(token=token, user_id=user_id, display_name=display_name, role=role, expires_at=expires_at)


def resolve_session(conn: sqlite3.Connection, token: str) -> Session | None:
    row = conn.execute(
        "SELECT token, user_id, display_name, role, expires_at FROM app_session WHERE token = ?", (token,)
    ).fetchone()
    if row is None:
        return None
    token, user_id, display_name, role, expires_at = row
    if datetime.fromisoformat(expires_at) < datetime.now(UTC):
        # Expired -- delete it so a stale row can never be mistaken for a live session
        # (the exact "cached authorization" pattern INJ-067 / test_no_cached_authorization
        # already proves the rest of this system never relies on).
        conn.execute("DELETE FROM app_session WHERE token = ?", (token,))
        conn.commit()
        return None
    return Session(token=token, user_id=user_id, display_name=display_name, role=role, expires_at=expires_at)


def logout(conn: sqlite3.Connection, token: str) -> None:
    conn.execute("DELETE FROM app_session WHERE token = ?", (token,))
    conn.commit()


def list_users(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT user_id, display_name, role FROM app_user ORDER BY role").fetchall()
    return [{"user_id": r[0], "display_name": r[1], "role": r[2]} for r in rows]
