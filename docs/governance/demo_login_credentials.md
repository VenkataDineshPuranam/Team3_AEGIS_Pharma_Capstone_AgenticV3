# Demo login credentials — Stage 22

Ten synthetic accounts, seeded by `services/integration/seed_users.py` (idempotent —
safe to re-run) into the same SQLite store `services/integration/audit_store.py` already
uses (`evidence/audit_store.sqlite3`, `app_user`/`app_session` tables). No real people,
no real credentials — matches the project's synthetic-data-only posture applied to the
login layer added in this stage.

`user_id` follows the ordinary first-initial.lastname convention, matching a real
directory rather than a role-slug test fixture. Roles themselves (right column) are the
load-bearing strings -- unchanged, and matched verbatim by every authorization check.

| User ID | Password | Display name | Role |
|---|---|---|---|
| `e.moreau` | `Moreau#2026EU` | Elise Moreau | EU Qualified Person |
| `a.osei` | `Osei#2026Rx` | Dr. Amara Osei | Safety physician |
| `m.feldman` | `Feldman#2026Sc` | Marcus Feldman | Supply governance |
| `w.chen` | `Chen#2026Pre` | Dr. Wei Chen | Head of Preclinical Research |
| `s.alvarez` | `Alvarez#2026Cl` | Dr. Sofia Alvarez | Clinical Trial Medical Monitor |
| `p.nair` | `Nair#2026Reg` | Priya Nair | Head of Regulatory Affairs |
| `t.berg` | `Berg#2026QA` | Thomas Berg | Quality reviewer |
| `n.ilic` | `Ilic#2026Sec` | Naomi Ilic | CISO / DPO |
| `d.cho` | `Cho#2026Aud` | Daniel Cho | Auditor |
| `j.kessler` | `Kessler#2026Ub` | Dr. Julian Kessler | Unblinding authority |

## What each role can actually do

This is the enforcement table, not documentation of an intention — every row is checked
server-side by `services/integration/user_store.py`'s `ROLE_CATALOG`,
`approver_string_for()`, and `can_veto()`, called from `services/api/main.py::decide_run`
before a decide request ever reaches a graph. `GET /api/auth/roles` serves the
`product_use`/`must_never` half of this table to the frontend directly from the same
source, so the UI cannot drift from what the backend enforces.

| Role | May submit a run for | May approve/decide | May veto | Must never |
|---|---|---|---|---|
| EU Qualified Person | any workflow | `batch_review`; `supply_planning` (quality leg) | — | Release / certify |
| Safety physician | any workflow | `pv_intake` | `pv_intake` (as `Patient Safety Representative`) | Causality, reportability |
| Supply governance | any workflow | `supply_planning` (planning leg) | — | Allocate / ship |
| Head of Preclinical Research | any workflow | `research_review` | — | Qualify a model / approve intended use |
| Clinical Trial Medical Monitor | any workflow | `clinical_integrity` | — | Decide eligibility, unblind, disposition a deviation |
| Head of Regulatory Affairs | any workflow | `regulatory_completeness` | — | Classify a variation as reportable / mark submission-ready |
| Quality reviewer | any workflow | none — read/oversight only | — | Change quality status |
| CISO / DPO | any workflow | none — read/oversight only | — | Consent / residency decisions |
| Auditor | any workflow | none — read-only | — | Acknowledge anything |
| Unblinding authority | any workflow | none — reviews `clinical_integrity` findings only | — | Unblind; never sees allocation (excluded from `supply_planning` reads — `user_store.visible_workflows`) |

Submitting a run (`POST /api/runs`) requires only a live session, not a specific role —
any authenticated role may request any workflow, matching how a real requester (someone
who did not do the analysis themselves) commissions a review. **Deciding** a paused run
(`POST /api/runs/{run_id}/decide`) is the gate: a 403 there means the logged-in role was
never eligible for that workflow/leg, checked before the request reaches any graph.

## What this login layer deliberately is not

No SSO, no password reset flow, no account lockout policy, no MFA. Sessions are
server-side rows in SQLite with an 8-hour expiry (`user_store.SESSION_LIFETIME`),
resolved fresh on every request (`services/api/auth.py::require_user`) — never cached
client-side beyond the bearer token itself. Passwords are salted and PBKDF2-HMAC-SHA256
hashed (260,000 iterations, stdlib `hashlib` only, no plaintext ever stored or logged).

Microsoft Entra ID remains the planned production identity provider
(`docs/governance/hitl_control_model.md`); this is the synthetic, offline-capable
equivalent for the same reason every other credential and fixture in this repo is
synthetic — see the V1 predecessor's `CLAUDE.md`: "Synthetic data only; no real PHI/PII."
