# ADR-010 — Human rejection precedent is retrievable EvidenceItem, not agent memory

**Status:** `accepted`
**Evidence basis:** Reasoned extension of `docs/architecture/agentic/memory_design.md` §2
(the ADR that section's own "Revisit trigger" requires before reopening cross-run recall).
**Scope:** `batch_review` only (EU Qualified Person). PV Intake, Supply Planning, and the
three shared-shape workflows (research_review, clinical_integrity, regulatory_completeness)
are explicitly out of scope — ADR-008 / RR-2 does not extend to them.

## Context

`memory_design.md` §2 rules out long-term agent memory for three reasons: an uncitable
evidence path, a supersession hazard, and cross-run authority accumulation ("the QP
approved a similar case" sliding into inferred authority). That section names its own
revisit condition: reopening cross-run recall requires an ADR, not a code change.

Every HITL rejection is already recorded — `HumanOverrideRecorded` in the audit store
(`services/integration/audit_store.py::write_human_override`) — but agents cannot read the
audit store; it is write-only from the graph (`memory_design.md` §1's own table). Every
batch pack a QP reviews starts cold, including one that repeats a gap a QP rejected last
week for a structurally identical reason.

## Decision

A prior rejection becomes retrievable **only** as an `EvidenceItem`, through a hashed,
read-only tool call (`precedent.retrieve`), bound only to `batch_review`, invoked after
`reconcile` and before `synthesize` — the same evidence-authority path every other citable
fact in this system already travels. There is no other memory path: no free-text recall, no
embedding lookup, no field on `GovernedState` that persists across runs outside the
checkpointer.

This closes memory_design.md §2's three objections directly, not by exception:

1. **Uncitable evidence path** — closed. A precedent is an `EvidenceItem` with
   `evidence_id`, `status`, and `effective_date` like any other; a claim that cites one is
   citable and gate-checked exactly like citing `K-006`.
2. **Supersession hazard** — closed. Precedents are append-only nodes in the same
   `EvidenceItem` label ADR-003 already governs. A later admin/Quality path can set
   `status=superseded`, and `evidence.retrieve`'s existing citable-status filter drops it
   automatically — no second, unaudited cache with its own invalidation logic.
3. **Cross-run authority accumulation** — closed by construction, not by policy alone.
   Precedents are minted **only** on `action=rejected`, never on `approved` or
   `timed_out`. An approval never becomes citable evidence, so "the QP approved a similar
   case" cannot exist as a retrievable fact — only "a similar gap was previously not
   accepted" can. Synthesize/critic prompts are constrained to phrase a citation as that
   fact, never as "the QP would reject this" or any other disposition
   (`security/policies/policy_contract.v1.json`'s banned-terms list already covers the
   disposition vocabulary this would otherwise risk brushing against).

## Non-negotiables

- HITL interrupt remains mandatory; a precedent citation changes what a human reads, never
  whether a human decides (`services/api/graph.py`'s `hitl_interrupt` node is unchanged in
  shape).
- Mint precedents only for `action=rejected`. Never for `approved` or `timed_out`.
- No person name on the `EvidenceItem` — role + role-assignment pattern already used in
  the audit store, not a name.
- PV Intake / Supply Planning graphs must not import or call `precedent.retrieve` —
  structurally true already: `services/api/graph.py::build_graph` (batch_review) is a
  separate function from `build_pv_graph` / `build_supply_graph`, not a shared graph with a
  workflow switch, so there is no accidental shared code path to guard against.
- Precedent write is best-effort **after** the audit write. A Neo4j failure must not undo
  a human decision — `write_human_override` commits first; `precedent_mint` runs after and
  swallows its own errors (logged, never raised into the graph).
- Synthesize may cite a prior refusal of a similar gap; it must not say "reject the batch"
  — already banned in the policy contract.

## Data model

Reuses the existing `EvidenceItem` node type (`packages/domain/kg/ingest.py`'s MERGE
pattern), with additional scalar properties (Neo4j has no nested-map property type):
`authority=human_precedent`, `source_file=human_precedent/{source_run_id}.md` (synthetic,
never re-parsed), `status=draft`, `trust=draft`, `jurisdiction=EU` (v1: always EU, because
the only minting role is EU Qualified Person — no `app_user.jurisdiction` field is added in
this slice), `finding_hash` (SHA-256 of the rejected run's non-complete finding categories),
`finding_categories`, `source_run_id`, `source_workflow=batch_review`, `action=rejected`,
`justification_excerpt`, and the same `_provenance_*` fields ingestion already sets.
Idempotency: `MERGE (e:EvidenceItem {evidence_id: "HP-{source_run_id}"})` — re-deciding the
same run cannot mint a second node.

`packages/domain/evidence.py`'s `EvidenceItem` Python model is unchanged: `status` is still
exactly `approved | draft`, the enum `evidence_retrieve.schema.json` already declares.
`draft` already carries a citable-with-caveat treatment in the frontend
(`apps/web/lib/format.ts`) — no new status value is invented.

## Alternatives considered

- **Add `"precedent"` as a fourth `evidence.retrieve` term** — rejected. That tool matches
  `terms` against `source_file`/`authority` before reconcile even runs; similar-gap
  matching needs `BatchPayload.findings`, which only exists after reconcile. Widening the
  existing tool's term list would also dump every QP rejection into every run
  indiscriminately, with no category filter — the opposite of the scoped, hashed-contract
  discipline every other tool in this system follows.
- **Free-text agent memory keyed by embedding similarity** — rejected outright; this is
  exactly the memory tier §2 ruled out, and semantic/vector search is explicitly out of
  scope for this slice.

## Guardrails

Same fail-closed posture as every other retrieve tool: `STORE_UNAVAILABLE` or an empty
result leaves `state["evidence"]` unchanged and the run continues — a missing precedent is
never treated as "no similar rejection exists," only as "none was retrievable this run."

## Validation

Unit: mint-on-reject, no-op on approve/timeout/empty-findings, idempotent MERGE on
re-decide. Contract: `precedent_retrieve.schema.json` against `extra=forbid`/`read_only`.
Integration (skipped without a live Neo4j, same pattern as
`tests/resilience/test_ai_disabled_continuity.py`): a rejected run's finding shape is
retrievable by a second run with a matching shape, and that second run still reaches
`__interrupt__` — a precedent never short-circuits HITL.

## Revisit triggers

If a future workflow other than `batch_review` wants shadow-approver precedent, that is a
new ADR, not an extension of this one's scope note — the "EU Qualified Person only, v1
jurisdiction always EU" simplifications are load-bearing to this decision, not incidental.
