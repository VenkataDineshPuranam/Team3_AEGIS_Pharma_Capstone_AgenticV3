"""One-time (idempotent) seed of the eleven synthetic demo accounts, one per ROLE_CATALOG
entry in user_store.py. Run directly: `python3 -m services.integration.seed_users`.

Passwords are synthetic and intentionally documented in
docs/governance/demo_login_credentials.md -- this is a capstone/demo environment with no
real PHI/PII and no real people behind these accounts, the same posture the project
already takes with every other fixture (see V1 CLAUDE.md's "Synthetic data only").

user_id is the person's own firstname.lastname -- so a login screen showing these accounts
reads like a real org directory, not a list of test fixtures. Role strings themselves are
UNCHANGED and load-bearing (matched verbatim by services/integration/user_store.py's
ROLE_CATALOG and every approver_roles check downstream) -- only the person attached to
each role changed. Super Admin is new: full cross-workflow read visibility, no decide
authority on anything -- see the ROLE_CATALOG entry for why that boundary is deliberate.
"""
from __future__ import annotations

from services.integration import user_store

# (user_id, display_name, role, password)
SEED_ACCOUNTS = [
    ("james.whitfield", "James Whitfield", "EU Qualified Person", "Whitfield#2026EU"),
    ("rachel.coleman", "Dr. Rachel Coleman", "Safety physician", "Coleman#2026Rx"),
    ("michael.turner", "Michael Turner", "Supply governance", "Turner#2026Sc"),
    ("david.bennett", "Dr. David Bennett", "Head of Preclinical Research", "Bennett#2026Pre"),
    ("laura.simmons", "Dr. Laura Simmons", "Clinical Trial Medical Monitor", "Simmons#2026Cl"),
    ("jennifer.hayes", "Jennifer Hayes", "Head of Regulatory Affairs", "Hayes#2026Reg"),
    ("robert.doyle", "Robert Doyle", "Quality reviewer", "Doyle#2026QA"),
    ("karen.mitchell", "Karen Mitchell", "CISO / DPO", "Mitchell#2026Sec"),
    ("brian.foster", "Brian Foster", "Auditor", "Foster#2026Aud"),
    ("steven.parker", "Dr. Steven Parker", "Unblinding authority", "Parker#2026Ub"),
    ("patricia.grant", "Patricia Grant", "Super Admin", "Grant#2026Admin"),
]


def seed() -> None:
    conn = user_store.get_connection()
    try:
        for user_id, display_name, role, password in SEED_ACCOUNTS:
            user_store.create_user(conn, user_id, display_name, role, password)
    finally:
        conn.close()
    print(f"Seeded {len(SEED_ACCOUNTS)} accounts into {user_store.DEFAULT_DB_PATH}")


if __name__ == "__main__":
    seed()
