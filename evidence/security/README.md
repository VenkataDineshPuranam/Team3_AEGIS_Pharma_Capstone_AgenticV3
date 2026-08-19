# security

Security review and threat-model sign-off evidence.

## Chaos drill history

Executable ADR-007 degraded-mode drill results are stored in
`evidence/audit_store.sqlite3`, table `chaos_drill_run` (separate from ADR-006
`agent_run` compliance rows).

- List via Control Center `/chaos-drill` or `GET /api/chaos-drill/history`
- Run (CISO / DPO only): `POST /api/chaos-drill/experiments/{id}/run`
- Catalog: `ops/chaos/experiments/`
- See `ops/chaos/README.md`
