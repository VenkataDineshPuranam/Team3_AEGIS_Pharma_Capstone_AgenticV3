# Project AEGIS-PHARMA — V2: Agentic AI

V2 evolves the [V1 capstone](./Project_AEGIS_Pharma_AI_FDE_Capstone_Workshop_Ready_v2_claude/)
from a document-driven FDE exercise into a governed, observable, multi-agent AI system —
the **AEGIS Control Center** — covering six pharma workflows (GxP batch review,
pharmacovigilance intake, supply-shortage planning, preclinical research review, clinical
trial integrity, regulatory submission completeness), built with **LangGraph**
(orchestration), Redis caching, real login/authorization, and explicit governance,
security, and compliance layers enforced server-side, not just documented.

Process discovery, SCQA, DDD, C4, and ADR came first, then the app (Stage 20), then a
real login layer and full gap closure across all 84 V1 tabletop-exercise scenarios
(Stage 21–22). See:
- [`SPEC_DRIVEN_DEVELOPMENT.md`](./SPEC_DRIVEN_DEVELOPMENT.md) — the method, full stage list, and git workflow
- [`STAGES.md`](./STAGES.md) — live status tracker for every stage/branch
- [`STRUCTURE_MANIFEST.json`](./STRUCTURE_MANIFEST.json) — machine-readable folder tree
- [`PROJECT_SUMMARY.md`](./PROJECT_SUMMARY.md) — detailed per-stage summary of everything built

## The application

A real FastAPI orchestrator (`services/api/`) wrapping six governed LangGraph workflows,
and a Next.js operator UI (`apps/web/`, the **AEGIS Control Center**).

**Fastest path — one command:**
```sh
./scripts/bootstrap.sh
```
Creates a venv, installs backend + frontend deps, copies `.env.example` → `.env`, and (once
you've filled in `NEO4J_URI`/`NEO4J_PASSWORD`/`AZURE_FOUNDRY_*`) seeds demo users and the
starter knowledge graph. Re-run anytime; every step is idempotent.

**Run it locally, manually:**
```sh
# Backend — from the repo root
pip install -r requirements-dev.txt          # runtime deps + pytest/ruff
python3 -m services.integration.seed_users   # one-time: seeds the 10 demo accounts
uvicorn services.api.main:app --port 8000

# Frontend — from apps/web/
npm install
npm run build && npm start   # or `npm run dev` for hot reload
```

**Or the whole stack in containers**, Neo4j and Redis included:
```sh
cp .env.example .env   # fill in AZURE_FOUNDRY_ENDPOINT/API_KEY/DEPLOYMENT at minimum
docker compose up --build
docker compose --profile seed run --rm seed   # first run only: demo users + starter KG
```
`docker-compose.yml` runs local Neo4j/Redis containers as dev substitutes for the cloud
services ADR-009 targets — nothing in application code branches on which one is live.

**Or build the deploy images directly** (the same images CI builds and CD deploys):
```sh
docker build -f deploy/containers/Dockerfile.api -t aegis-api .
docker build -f deploy/containers/Dockerfile.web \
  --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000 -t aegis-web .
```
`NEXT_PUBLIC_API_URL` is a **build** argument: Next.js inlines `NEXT_PUBLIC_*` into the
client bundle during `next build`, so setting it at runtime does nothing.
Open `http://localhost:3000` — every page except `/login` requires a signed-in session.
Demo credentials for all ten roles are in
[`docs/governance/demo_login_credentials.md`](./docs/governance/demo_login_credentials.md)
(synthetic accounts only, no real people).

**Login and authorization** (Stage 22): `services/integration/user_store.py` is a real,
credential-backed login — salted PBKDF2-hashed passwords, server-side sessions with an
8-hour expiry, no client-supplied identity ever trusted. Every workflow decision
(`POST /api/runs/{run_id}/decide`) is authorized server-side against the signed-in role
before it reaches any graph — a role not eligible to approve a given workflow gets a 403,
not a UI-only restriction. See the credentials doc above for the full role/permission table.

**HITL severity/timer** (Stage 22): every pending decision shows a live 1–4 severity
badge (grey → amber → purple → red) in the Decision Queue and on the Decision Detail
page header, computed fresh on every poll from `services/integration/hitl_timer.py`
against the per-workflow ladder durations `docs/governance/hitl_control_model.md` §7
specifies (Batch Review/Supply Planning 8h/16h/24h, PV Intake's deliberately shorter
4h/8h/24h). **Display only** — reaching severity 4 does not widen who can approve a run;
see §8 of that document for exactly what this does and does not close. A dev-only
endpoint for exercising all four tiers without waiting real hours is documented there
too, off by default.

**Live HITL escalation notifications** (Stage 23):
[`services/integration/hitl_escalation_watch.py`](./services/integration/hitl_escalation_watch.py)
is the background poller §8 above used to say didn't exist — running inside the API
process (`services/api/main.py`'s lifespan), it checks every pending run and, the first
time one crosses severity 3 (T2) or severity 4 (T3), records the event once
(`hitl_escalation`, idempotent — never fires twice for the same run at the same tier) and
sends one best-effort email via Gmail SMTP
([`services/integration/notifier.py`](./services/integration/notifier.py)). The audit
record alone powers the web app's notification bell (`GET /api/notifications`, no
configuration required); email needs `SMTP_*` / `NOTIFY_EMAIL_TO` filled in under `.env`
(see `.env.example` — Gmail requires an
[App Password](https://myaccount.google.com/apppasswords), not your account password) and
degrades to bell-only if absent. **Visibility only, same as the timer it reads** —
crossing a threshold authorizes no new approver and does not decide the run;
`notifier.py`'s docstring also explains why this is plain SMTP rather than an MCP tool
call (an MCP tool is reachable from an interactive Claude Code session, not from a running
server process making its own decisions between requests).

**Record Assistant** (Stage 23): an **Ask about a record** button sits on every signed-in
page. It explains a record in plain language — what it is, what it found, and what happens
next — so a Quality reviewer or an auditor does not have to read four tabs and an audit
timeline to answer "what is this?". On a run detail page it opens straight onto that run;
anywhere else it offers a short picker (pending runs first, since those still hold their
decision-support package). Opening it costs zero typing; a free-text box handles
follow-ups. The same panel is also an **Assistant** tab on the run detail page, for when
you are already reading a run.

The design rule it is built around: **the model writes prose, it does not compute facts
and it does not choose actions.** The record card and the "what happens next" list are
computed deterministically from the run's own governance state by
[`services/api/record_chat.py`](./services/api/record_chat.py), from a closed catalog of
procedural steps — so the assistant can say *"this run is waiting on the EU Qualified
Person, and you are eligible to decide it"*, and structurally cannot say *"release it"*.
The model's entire job is to summarize, answer the question, and paraphrase the steps.
The UI keeps the two halves visually distinct, because a reader has to be able to tell
which half can be wrong. If the model is unreachable the assistant degrades to the
deterministic facts (ADR-007) rather than failing the request.

**PI/PG — prompt-injection defence** (Stage 23):
[`services/integration/prompt_guard.py`](./services/integration/prompt_guard.py) brackets
ADR-004's three structural layers with two more — an input scan before any text reaches a
prompt, and an output scan before any generated text reaches a human. It catches
instruction override, role hijack, system-prompt exfiltration, control-token smuggling,
fabricated citations and claimed decision authority; a `high`-severity match is refused
outright, a `medium` one is neutralized and recorded. Layers 1–3 make a bad *outcome*
impossible; this makes a bad *attempt* visible — a `clear` verdict is explicitly not a
safety guarantee. See
[`docs/security/prompt_injection_defense.md`](./docs/security/prompt_injection_defense.md)
for the severity model, the false-positive argument, and the stated limits.

**AI-BOM** (Stage 23): [`security/sbom/ai_sbom.json`](./security/sbom/ai_sbom.json) is a
CycloneDX 1.6 ML-BOM recording the models, every system prompt, the PI/PG ruleset and the
governance files that constrain runtime behaviour — each by SHA-256, all computed from the
live repository by [`generate_ai_sbom.py`](./security/sbom/generate_ai_sbom.py). It exists
because the things that determine how this AI system behaves have no version number, so
`pip freeze` can stay byte-identical while every governance property changes. The
practical effect: **an edit that weakens a governance instruction in a system prompt fails
CI**, and `tests/security/test_ai_sbom_verification.py` proves that by making such an edit.
Model identifiers are recorded as *mutable aliases* and flagged as such — see
[`security/sbom/README.md`](./security/sbom/README.md) for what this artifact deliberately
does not claim.

**CI/CD:** [`.github/workflows/ci.yml`](./.github/workflows/ci.yml) runs the governance
gates first (both SBOMs, tool-manifest integrity, committed-secret check), then API lint
and tests, web typecheck/lint/tests/build, and both container builds.
[`cd.yml`](./.github/workflows/cd.yml) deploys to **Azure Container Apps** per ADR-009,
with signed SLSA build provenance on both images and a post-deploy smoke test that
verifies the deployed API both answers and enforces authentication. It stops in a
`preflight` job with a readable message when the required repository secrets are absent,
and states in the run summary which parts of ADR-009 it does *not* implement (Key Vault,
Entra ID, Blob WORM audit storage). [`nightly-redteam.yml`](./.github/workflows/nightly-redteam.yml)
runs the live prompt-injection suite against a real model each night.

**Explore the architecture:** [`docs/architecture/graphical/architecture_explorer.html`](./docs/architecture/graphical/architecture_explorer.html)
is a self-contained, interactive diagram of the actual implemented system — every
frontend page, API endpoint, the six workflow graphs' shared spine, the tool layer, and
the stores — with a Flows panel that highlights real end-to-end paths (login, submitting
a run, approving a decision, a prohibited-action guard blocking a draft, dual-approval,
and more). The same data is available as machine-readable JSON at
[`architecture_graph.json`](./docs/architecture/graphical/architecture_graph.json).

A second, independently generated repo graph — same source-grounded approach, different
visual layout (grouped by layer: client → API → orchestration → governed tools → domain
packages → stores/providers) — is at
[`docs/architecture/repo-graph/architecture.html`](./docs/architecture/repo-graph/architecture.html)
(86 components, 129 relationships, 14 flows), with its own JSON at
[`architecture.json`](./docs/architecture/repo-graph/architecture.json).

**Coverage:** every one of the V1 predecessor's 84 tabletop-exercise "inject" scenarios
is mapped to a real, citable V2 artifact (test, fixture, structural guard, or governance
document) — see the in-app Evaluation & Security dashboard (`/coverage`) or
`evidence/quality-gates/inject_coverage_v1_to_v2.json`.

## Repository Pattern

This repo follows a `.claude`-based "AI-Assisted SDLC Repository" scaffold: Claude-native,
platform-neutral, offline-compatible, workshop-deployable.

| Section | Purpose |
|---|---|
| `.claude/` | rules, agents, skills, hooks, `mcp.json`, `settings.json` |
| `docs/` | product (SCQA, current/interim/final state), architecture (DDD, C4, agentic design, ontology, graphical), adr, engineering, quality (DMAIC/Lean, evals, performance), security, operations, governance (incl. compliance) |
| `plans/` | active / completed / superseded stage specs |
| `apps/` | web, admin — participant/operator UI |
| `services/` | api (LangGraph orchestrator), worker (agent workers), integration (MCP servers) |
| `packages/` | domain (DDD + ontology bindings), contracts (API/tool/MCP schemas), config, observability (LangSmith/OTel), test-support |
| `tests/` | unit, integration, contract, e2e, performance, security, resilience, fixtures/synthetic |
| `quality/` | gates, coverage, mutation, static-analysis |
| `security/` | policies, threat-models, abuse-cases, exceptions, sbom, secrets |
| `infra/` | modules, environments (local/dev/staging/production), policies |
| `deploy/` | containers, manifests, migrations, rollback |
| `ops/` | dashboards, alerts, runbooks, slo, incident, chaos |
| `evidence/` | requirements, architecture, tests, security, quality-gates, releases, deployments, operations, incidents, ai-assisted-changes |
| `templates/` | change-plan, requirement, adr, test-plan, threat-model, privacy-review, runbook, release-readiness, incident-record, ai-change-record |
| `workshop/` | scenarios, labs, checkpoints, assessments, participant-output |
| `.github/workflows/` | CI (governance gates, tests, container builds), CD (Azure Container Apps), nightly live red-team |

**Carried forward / extended from V1:** `prompts/` (numbered lifecycle prompts),
`knowledge/` (domain knowledge base), `evaluation/` (public fixtures/contracts),
`runbooks/` (participant runbooks), `eval-ai-cache/` (seeded brownfield evals +
Redis + OpenTelemetry runbook library — the direct source material for Stage 14/15).

## Non-negotiables (inherited from V1)
- Synthetic data only; no real PHI/PII.
- No agent makes a terminal safety/release/allocation decision — decision **support** only.
- Every claim traceable to evidence (provenance required).
- GxP, privacy, and security boundaries are enforced by the governance layer
  (`docs/governance/`, `security/`, `.claude/hooks/`), not by agent prompting alone.
