# chaos

Lab-safe ADR-007 failure-injection drills for AEGIS.

## What this is

Operators (CISO / DPO) run **named injectors** from the Control Center page `/chaos-drill`.
Each UI-runnable experiment builds a **fresh** `batch_review` graph with injectable
dependencies, asserts fail-closed behaviour, and persists a row in `chaos_drill_run`.

This is **not** Netflix-style production chaos. The UI never stops Neo4j, Redis, or the API.

## UI-runnable experiments

| ID | Injection | Expected |
|---|---|---|
| `CHAOS-LLM-01` | LLM raises | `degraded_mode` abstain |
| `CHAOS-REDIS-01` | Cache get/set bypass wrappers | Bypass observed; zero Redis I/O |
| `CHAOS-NEO4J-01` | retrieve `STORE_UNAVAILABLE` | `dependency_unavailable` |
| `CHAOS-HITL-01` | `Command(resume="timed_out")` | `hitl_timeout` |
| `CHAOS-POLICY-01` | Policy engine unavailable | `fail_closed` refuse |

Catalog JSON: `ops/chaos/experiments/`.

## DRILL- run ids

Graph runs use `DRILL-<experiment>-<uuid8>`. `GET /api/runs` defaults to
`exclude_drills=True` so Run History does not mix drills with governed decisions.
Drill evidence lives in `chaos_drill_run` (same SQLite file, separate table).

## Ops-only (no UI Run)

See `ops/chaos/runbooks/`: `CHAOS-LLM-02`, `CHAOS-HITL-02`, `CHAOS-CKPT-01`.

## Not covered here

- **LangSmith** — design-only in this build; no first-party client to inject against.
- **Remote MCP** — tools are in-process Python; store outage is covered by `CHAOS-NEO4J-01`.

## Proof surfaces

- UI: `/chaos-drill` (login `ciso_dpo_1`)
- Tests: `tests/resilience/test_chaos_harness.py`, `tests/integration/test_chaos_drill_endpoint.py`
- ADR: `docs/adr/ADR-007-degraded-mode-safe-not-offline-capable.md`
