"""audit_store -- Stage 20a Phase 3. SQLite, append-only. Emulates the WORM property
locally (ADR-009's real Blob WORM immutability is a Stage 20 deploy concern) by exposing
no UPDATE/DELETE at the data-access layer -- there is no function in this module that can
modify or remove an existing row, which is the actual enforcement, not a comment promising
one.

Record shapes from escalation_override_log_design.md SS2-5: AgentRun, HumanOverrideRecorded,
HitlEscalation, HitlExpired. `finalize` (langgraph_design.md node #11) writes AgentRun before
any response reaches the caller -- ADR-006.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# AEGIS_DB_PATH lets deployment mount persistent storage (e.g. Azure Files) at a dedicated
# path instead of "evidence/" -- mounting a volume there would shadow the static files
# already baked into that directory in the image (evidence/quality-gates/*, read by
# eval_dashboard.py), replacing the whole directory with whatever's on the share. Local/CI
# runs are unaffected: no env var set, same path as always.
DEFAULT_DB_PATH = Path(os.environ.get("AEGIS_DB_PATH", str(REPO_ROOT / "evidence" / "audit_store.sqlite3")))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_run (
    run_id TEXT PRIMARY KEY,
    workflow TEXT NOT NULL,
    terminal_state TEXT NOT NULL,
    abstention_reason TEXT,
    trace_id TEXT,
    policy_contract_version TEXT,
    recorded_at TEXT NOT NULL,
    llm_calls INTEGER,
    tokens_in INTEGER,
    tokens_out INTEGER,
    subject_id TEXT,
    requester_role TEXT,
    approver_roles TEXT,
    hitl_status TEXT,
    evidence_ids TEXT
);

CREATE TABLE IF NOT EXISTS human_override_recorded (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    role TEXT NOT NULL,
    role_assignment_id TEXT,
    tier_at_action TEXT NOT NULL,
    action TEXT NOT NULL,
    justification TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hitl_escalation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    workflow TEXT NOT NULL,
    tier TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    conditions TEXT NOT NULL,
    outcome TEXT NOT NULL,
    skip_reason TEXT,
    escalation_role TEXT,
    policy_contract_version TEXT
);

CREATE TABLE IF NOT EXISTS hitl_expired (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    workflow TEXT NOT NULL,
    eligible_roles_at_expiry TEXT NOT NULL,
    abstention_reason TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prohibited_action_blocked (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    matched_terms TEXT NOT NULL,
    draft_sha256 TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
"""


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    # check_same_thread=False: graph.py builds one connection per request and closes over
    # it from every node function (intake through finalize). LangGraph's runner can
    # dispatch those node calls onto different worker threads within the same request,
    # which trips Python's default same-thread guard even though access here is always
    # sequential -- one node at a time, never concurrent -- which is exactly the case
    # SQLite's own thread safety (serialized mode, the default build) already covers.
    # Surfaced only under a real multi-threaded deployment (Stage 23); local/CI runs never
    # exercised this path before.
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # nolock=1: the DB file lives on an Azure Files (SMB) mount for persistence across
    # scale-to-zero cycles (Stage 24). SQLite's POSIX advisory-locking calls are not
    # reliably honored over SMB/CIFS -- per SQLite's own docs, network filesystems are
    # unsupported for locking -- so even a single writer opening a fresh file gets
    # "database is locked" immediately; busy_timeout doesn't help because the failure
    # isn't a timed-out retry, the underlying lock call itself fails. nolock=1 disables
    # SQLite's locking layer entirely, which is safe here because Container Apps runs at
    # most one replica of this app (maxReplicas=1), so there is never a second process to
    # race against.
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?nolock=1", uri=True, check_same_thread=False)
    conn.executescript(_SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Stage 20b Phase 6: agent_run predates llm_calls/tokens_in/tokens_out (added to
    make the Stage 17 dashboards panels computable from real data). CREATE TABLE IF NOT
    EXISTS doesn't add columns to an already-existing table -- this does, idempotently.

    Stage 21 adds a second, same-shaped group: subject_id / requester_role /
    approver_roles / hitl_status / evidence_ids. Every one of these is already in
    GovernedState at the moment `finalize` runs -- they were simply never persisted, which
    is why a decided run could not afterwards be answered for ("which batch was this?",
    "which evidence did it stand on?", "who was it waiting for?"). Recording them makes the
    audit trail answer its own questions; it is additive (existing rows read NULL, and the
    UI says so rather than guessing) and changes no governance decision.
    """
    existing = {row[1] for row in conn.execute("PRAGMA table_info(agent_run)")}
    for column in ("llm_calls", "tokens_in", "tokens_out"):
        if column not in existing:
            conn.execute(f"ALTER TABLE agent_run ADD COLUMN {column} INTEGER")
    for column in ("subject_id", "requester_role", "approver_roles", "hitl_status", "evidence_ids"):
        if column not in existing:
            conn.execute(f"ALTER TABLE agent_run ADD COLUMN {column} TEXT")
    conn.commit()


def write_agent_run(
    conn: sqlite3.Connection,
    run_id: str,
    workflow: str,
    terminal_state: str,
    recorded_at: str,
    abstention_reason: str | None = None,
    trace_id: str | None = None,
    policy_contract_version: str | None = None,
    llm_calls: int | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    subject_id: str | None = None,
    requester_role: str | None = None,
    approver_roles: list[str] | None = None,
    hitl_status: str | None = None,
    evidence_ids: list[str] | None = None,
) -> None:
    """finalize's mandatory write -- a response reaching the caller with no audit write
    is not a valid terminal state (hooks.md). llm_calls/tokens_in/tokens_out (Stage 20b)
    are what makes dashboards.md's Cost panel computable from real data; subject_id /
    requester_role / approver_roles / hitl_status / evidence_ids (Stage 21) are what make a
    decided run investigable afterwards without re-running it. All are optional -- an
    older caller that omits them still writes a valid record."""
    conn.execute(
        "INSERT INTO agent_run (run_id, workflow, terminal_state, abstention_reason, trace_id, policy_contract_version, recorded_at, llm_calls, tokens_in, tokens_out, subject_id, requester_role, approver_roles, hitl_status, evidence_ids) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id, workflow, terminal_state, abstention_reason, trace_id, policy_contract_version,
            recorded_at, llm_calls, tokens_in, tokens_out, subject_id, requester_role,
            json.dumps(approver_roles) if approver_roles is not None else None,
            hitl_status,
            json.dumps(evidence_ids) if evidence_ids is not None else None,
        ),
    )
    conn.commit()


def write_human_override(
    conn: sqlite3.Connection,
    run_id: str,
    role: str,
    tier_at_action: str,
    action: str,
    justification: str,
    recorded_at: str,
    role_assignment_id: str | None = None,
) -> None:
    if not justification.strip():
        raise ValueError("justification is required and cannot be empty -- escalation_override_log_design.md SS3.")
    if action == "approved" and has_veto(conn, run_id):
        raise ValueError(
            "A veto_registered record already exists for this run_id -- escalation_override_log_design.md SS4: "
            "a veto cannot be superseded by a later approval."
        )
    conn.execute(
        "INSERT INTO human_override_recorded (run_id, role, role_assignment_id, tier_at_action, action, justification, recorded_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (run_id, role, role_assignment_id, tier_at_action, action, justification, recorded_at),
    )
    conn.commit()


def has_veto(conn: sqlite3.Connection, run_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM human_override_recorded WHERE run_id = ? AND action = 'veto_registered' LIMIT 1",
        (run_id,),
    ).fetchone()
    return row is not None


def has_recorded_action(conn: sqlite3.Connection, run_id: str, role: str, action: str) -> bool:
    """Stage 21 gap-closure (INJ-080: checkpoint corruption / duplicate writes on
    resume). Same pattern as has_veto -- a persistent-store check, not an in-memory
    flag, because LangGraph re-executes a node's Python code from the top on every
    resume and REPLAYS each already-consumed interrupt()'s return value. Side-effecting
    code between two interrupt() calls in the same node therefore runs again on every
    later resume within that node execution; an in-memory list built up during that same
    re-execution (e.g. a local `approved_legs`) is reset by the replay too, so it cannot
    detect "I already wrote this." Only a check against what was actually persisted
    last time is replay-safe -- this is that check, for supply_planning's dual-approval
    writes specifically."""
    row = conn.execute(
        "SELECT 1 FROM human_override_recorded WHERE run_id = ? AND role = ? AND action = ? LIMIT 1",
        (run_id, role, action),
    ).fetchone()
    return row is not None


def write_hitl_escalation(
    conn: sqlite3.Connection,
    run_id: str,
    workflow: str,
    evaluated_at: str,
    conditions: dict[str, bool],
    outcome: str,
    tier: str = "T2",
    skip_reason: str | None = None,
    escalation_role: str | None = None,
    policy_contract_version: str | None = None,
) -> None:
    """Stage 23 -- `tier` was hardcoded to 'T2' here because nothing called this function
    (hitl_timer.py's own docstring: "wired into nothing -- no scheduler advances it").
    services/integration/hitl_escalation_watch.py is that scheduler now, and it fires at
    both T2 (severity 3, "escalation due") and T3 (severity 4, "expired"/red) -- a fixed
    literal would have silently mislabeled every T3 event as T2. Existing behavior for any
    caller that omits the argument is unchanged."""
    conn.execute(
        "INSERT INTO hitl_escalation (run_id, workflow, tier, evaluated_at, conditions, outcome, skip_reason, escalation_role, policy_contract_version) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, workflow, tier, evaluated_at, json.dumps(conditions), outcome, skip_reason, escalation_role, policy_contract_version),
    )
    conn.commit()


def has_hitl_escalation(conn: sqlite3.Connection, run_id: str, tier: str) -> bool:
    """Whether an escalation at this exact tier has already been recorded for this run --
    the idempotency check hitl_escalation_watch.py uses so a run sitting at T2 across many
    poll cycles fires exactly one notification, not one every cycle. Keyed on the
    append-only audit store itself rather than an in-memory set, so it survives an API
    process restart the same way every other "did this already happen" check in this
    module does (has_recorded_action, has_veto)."""
    row = conn.execute(
        "SELECT 1 FROM hitl_escalation WHERE run_id = ? AND tier = ? LIMIT 1", (run_id, tier)
    ).fetchone()
    return row is not None


def list_recent_hitl_escalations(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    """Escalation events, newest first -- the Notification Bell's read source. Deliberately
    the same table `run_timeline` already reads for a single run, exposed here across all
    runs: one audit record, two read shapes, never two places that could disagree about
    which escalations actually happened."""
    rows = conn.execute(
        "SELECT run_id, workflow, tier, evaluated_at, escalation_role "
        "FROM hitl_escalation ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [
        {"run_id": r[0], "workflow": r[1], "tier": r[2], "evaluated_at": r[3], "escalation_role": r[4]}
        for r in rows
    ]


def write_hitl_expired(
    conn: sqlite3.Connection,
    run_id: str,
    workflow: str,
    eligible_roles_at_expiry: list[str],
    recorded_at: str,
) -> None:
    conn.execute(
        "INSERT INTO hitl_expired (run_id, workflow, eligible_roles_at_expiry, abstention_reason, recorded_at) "
        "VALUES (?, ?, ?, 'hitl_timeout', ?)",
        (run_id, workflow, json.dumps(eligible_roles_at_expiry), recorded_at),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Read side (Stage 21). SELECT only.
#
# The module docstring's WORM claim is that no function here can modify or remove an
# existing row -- "which is the actual enforcement, not a comment promising one". Every
# function below is a SELECT, so that property is unchanged: adding readers cannot make an
# append-only store less append-only. These exist because an audit trail nothing can read
# is not an audit trail; until Stage 21 the only reader was dashboard_data.py's aggregate
# counts, which can tell you ten runs were blocked but not which ten.
# ---------------------------------------------------------------------------

_RUN_COLUMNS = (
    "run_id, workflow, terminal_state, abstention_reason, trace_id, policy_contract_version, "
    "recorded_at, llm_calls, tokens_in, tokens_out, subject_id, requester_role, approver_roles, "
    "hitl_status, evidence_ids"
)


def _json_or_none(raw: str | None) -> list | None:
    """A NULL column means 'this run predates the column' -- reported to the caller as
    None so the UI can say "not recorded" rather than render a misleading empty list."""
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _run_row_to_dict(row: sqlite3.Row | tuple) -> dict:
    keys = [c.strip() for c in _RUN_COLUMNS.split(",")]
    record = dict(zip(keys, row))
    record["approver_roles"] = _json_or_none(record["approver_roles"])
    record["evidence_ids"] = _json_or_none(record["evidence_ids"])
    return record


def list_agent_runs(
    conn: sqlite3.Connection,
    workflow: str | None = None,
    terminal_state: str | None = None,
    subject_id: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    exclude_drills: bool = True,
) -> tuple[list[dict], int]:
    """Newest-first page of agent_run rows plus the total matching count (for pagination).

    `search` is a case-insensitive substring match over run_id and subject_id only --
    deliberately not a free-text search over every column, so a caller cannot use it to
    probe fields (trace_id, policy versions) it was not given a filter for.

    `exclude_drills` (default True) omits chaos-drill graph runs whose run_id starts with
    `DRILL-`. Those rows remain in the store and are listed from /api/chaos-drill/history;
    Run History must not mix them with governed decisions.
    """
    clauses: list[str] = []
    params: list = []
    if exclude_drills:
        clauses.append("run_id NOT LIKE 'DRILL-%'")
    if workflow:
        clauses.append("workflow = ?")
        params.append(workflow)
    if terminal_state:
        clauses.append("terminal_state = ?")
        params.append(terminal_state)
    if subject_id:
        clauses.append("subject_id = ?")
        params.append(subject_id)
    if search:
        clauses.append("(LOWER(run_id) LIKE ? OR LOWER(IFNULL(subject_id, '')) LIKE ?)")
        params.extend([f"%{search.lower()}%"] * 2)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    total = conn.execute(f"SELECT COUNT(*) FROM agent_run {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT {_RUN_COLUMNS} FROM agent_run {where} ORDER BY recorded_at DESC, rowid DESC LIMIT ? OFFSET ?",
        (*params, max(1, min(limit, 200)), max(0, offset)),
    ).fetchall()
    return [_run_row_to_dict(r) for r in rows], total


def get_agent_run(conn: sqlite3.Connection, run_id: str) -> dict | None:
    row = conn.execute(f"SELECT {_RUN_COLUMNS} FROM agent_run WHERE run_id = ?", (run_id,)).fetchone()
    return _run_row_to_dict(row) if row else None


def distinct_values(conn: sqlite3.Connection, column: str) -> list[str]:
    """Filter-option source for the UI. `column` is checked against an allowlist rather
    than interpolated as given -- these values reach SQL, and a caller-supplied column
    name is the shape of an injection, whether or not today's only caller is trusted."""
    allowed = {"workflow", "terminal_state", "subject_id", "requester_role", "abstention_reason"}
    if column not in allowed:
        raise ValueError(f"{column!r} is not a filterable column.")
    rows = conn.execute(
        f"SELECT DISTINCT {column} FROM agent_run WHERE {column} IS NOT NULL ORDER BY {column}"
    ).fetchall()
    return [r[0] for r in rows]


def run_timeline(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    """Every audit record this store actually holds for one run, merged and ordered.

    Real events only. This function invents nothing: if the graph never wrote an
    escalation record, no escalation event appears, and the UI shows a shorter timeline
    rather than a plausible-looking one. Node-level trace events (evidence retrieved,
    guard evaluated, critic verified) live in LangSmith, not here -- they are absent from
    this list because they are absent from this store, and the caller is told so rather
    than shown a reconstruction.
    """
    events: list[dict] = []

    for row in conn.execute(
        "SELECT recorded_at, terminal_state, abstention_reason, policy_contract_version, workflow "
        "FROM agent_run WHERE run_id = ?", (run_id,)
    ):
        events.append({
            "at": row[0], "event_type": "AgentRun", "actor": "system", "role": None,
            "action": f"Run finalized: {row[1]}",
            "metadata": {
                "terminal_state": row[1], "abstention_reason": row[2],
                "policy_contract_version": row[3], "workflow": row[4],
            },
        })

    for row in conn.execute(
        "SELECT recorded_at, role, role_assignment_id, tier_at_action, action, justification "
        "FROM human_override_recorded WHERE run_id = ? ORDER BY id", (run_id,)
    ):
        events.append({
            "at": row[0], "event_type": "HumanOverrideRecorded", "actor": row[1], "role": row[1],
            "action": row[4],
            "metadata": {
                "role_assignment_id": row[2], "tier_at_action": row[3], "justification": row[5],
            },
        })

    for row in conn.execute(
        "SELECT evaluated_at, tier, conditions, outcome, skip_reason, escalation_role, policy_contract_version "
        "FROM hitl_escalation WHERE run_id = ? ORDER BY id", (run_id,)
    ):
        events.append({
            "at": row[0], "event_type": "HitlEscalation", "actor": "system", "role": row[5],
            "action": f"Escalation {row[3]}",
            "metadata": {
                "tier": row[1], "conditions": _json_or_none(row[2]), "outcome": row[3],
                "skip_reason": row[4], "escalation_role": row[5], "policy_contract_version": row[6],
            },
        })

    for row in conn.execute(
        "SELECT recorded_at, eligible_roles_at_expiry, abstention_reason FROM hitl_expired WHERE run_id = ? ORDER BY id",
        (run_id,)
    ):
        events.append({
            "at": row[0], "event_type": "HitlExpired", "actor": "system", "role": None,
            "action": "Approval window expired -- no action was taken",
            "metadata": {"eligible_roles_at_expiry": _json_or_none(row[1]), "abstention_reason": row[2]},
        })

    for row in conn.execute(
        "SELECT recorded_at, matched_terms, draft_sha256 FROM prohibited_action_blocked WHERE run_id = ? ORDER BY id",
        (run_id,)
    ):
        events.append({
            "at": row[0], "event_type": "ProhibitedActionBlocked", "actor": "system", "role": None,
            "action": "Prohibited action blocked",
            "metadata": {"matched_terms": _json_or_none(row[1]), "draft_sha256": row[2]},
        })

    return sorted(events, key=lambda e: e["at"])


def human_overrides(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    """The human actions recorded for one run, in order -- what the Supply dual-approval
    panel reads to show which leg actually landed, from the audit trail rather than from
    the UI's own memory of what it just submitted."""
    rows = conn.execute(
        "SELECT role, tier_at_action, action, justification, recorded_at "
        "FROM human_override_recorded WHERE run_id = ? ORDER BY id", (run_id,)
    ).fetchall()
    return [
        {"role": r[0], "tier_at_action": r[1], "action": r[2], "justification": r[3], "recorded_at": r[4]}
        for r in rows
    ]


def export_all_runs(conn: sqlite3.Connection, exclude_drills: bool = True) -> list[dict]:
    """Every finalized run, newest-first, with its human decision(s) folded in -- the
    audit-report export (Stage 26) for Super Admin / Auditor / Unblinding authority.
    Unlike list_agent_runs, there is no limit clamp: an audit export must be complete, not
    a page of it."""
    where = "WHERE run_id NOT LIKE 'DRILL-%'" if exclude_drills else ""
    rows = conn.execute(
        f"SELECT {_RUN_COLUMNS} FROM agent_run {where} ORDER BY recorded_at DESC, rowid DESC"
    ).fetchall()
    runs = [_run_row_to_dict(r) for r in rows]

    overrides = conn.execute(
        "SELECT run_id, role, action, justification, recorded_at "
        "FROM human_override_recorded ORDER BY id"
    ).fetchall()
    by_run: dict[str, list[dict]] = {}
    for run_id, role, action, justification, recorded_at in overrides:
        by_run.setdefault(run_id, []).append(
            {"role": role, "action": action, "justification": justification, "recorded_at": recorded_at}
        )

    for run in runs:
        decisions = by_run.get(run["run_id"], [])
        run["human_decisions"] = decisions
        run["decided_by"] = "; ".join(f"{d['role']} ({d['action']})" for d in decisions) or None
        run["decided_at"] = decisions[-1]["recorded_at"] if decisions else None
    return runs


def store_stats(conn: sqlite3.Connection) -> dict:
    """Row counts per table -- the System Health page's "audit store" section, measured
    rather than asserted."""
    tables = (
        "agent_run", "human_override_recorded", "hitl_escalation", "hitl_expired",
        "prohibited_action_blocked",
    )
    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    latest = conn.execute("SELECT MAX(recorded_at) FROM agent_run").fetchone()[0]
    return {"row_counts": counts, "latest_run_recorded_at": latest, "db_path": str(DEFAULT_DB_PATH)}
