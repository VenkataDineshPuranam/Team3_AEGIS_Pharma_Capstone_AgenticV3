"""One-time (idempotent) seed of the ten synthetic demo accounts, one per ROLE_CATALOG
entry in user_store.py. Run directly: `python3 -m services.integration.seed_users`.

Passwords are synthetic and intentionally documented in
docs/governance/demo_login_credentials.md -- this is a capstone/demo environment with no
real PHI/PII and no real people behind these accounts, the same posture the project
already takes with every other fixture (see V1 CLAUDE.md's "Synthetic data only").

user_id follows the ordinary enterprise first-initial.lastname convention rather than a
role-slug -- so a login screen showing these accounts reads like a real org directory, not
a list of test fixtures. Role strings themselves are UNCHANGED and load-bearing (matched
verbatim by services/integration/user_store.py's ROLE_CATALOG and every approver_roles
check downstream) -- only the person attached to each role changed.
"""
from __future__ import annotations

from services.integration import user_store

# (user_id, display_name, role, password)
SEED_ACCOUNTS = [
    ("e.moreau", "Elise Moreau", "EU Qualified Person", "Moreau#2026EU"),
    ("a.osei", "Dr. Amara Osei", "Safety physician", "Osei#2026Rx"),
    ("m.feldman", "Marcus Feldman", "Supply governance", "Feldman#2026Sc"),
    ("w.chen", "Dr. Wei Chen", "Head of Preclinical Research", "Chen#2026Pre"),
    ("s.alvarez", "Dr. Sofia Alvarez", "Clinical Trial Medical Monitor", "Alvarez#2026Cl"),
    ("p.nair", "Priya Nair", "Head of Regulatory Affairs", "Nair#2026Reg"),
    ("t.berg", "Thomas Berg", "Quality reviewer", "Berg#2026QA"),
    ("n.ilic", "Naomi Ilic", "CISO / DPO", "Ilic#2026Sec"),
    ("d.cho", "Daniel Cho", "Auditor", "Cho#2026Aud"),
    ("j.kessler", "Dr. Julian Kessler", "Unblinding authority", "Kessler#2026Ub"),
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
