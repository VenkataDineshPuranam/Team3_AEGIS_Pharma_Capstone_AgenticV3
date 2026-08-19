# Tool Inventory — Stage 11 (MCP)

**Executes:** `prompts/15_mcp.md` §1
**Builds on:** `docs/architecture/agentic/agent_roster.md` §2, `docs/architecture/c4/c4_components.md`,
ADR-003/004/008
**Artifact status:** `stable` for the `batch_review` tools (interim slice, 20a);
`provisional` for the PV Intake and Supply Planning tools (same reason as their graphs —
`agent_roster.md` §0, RR-2)

---

## 1. Design decision: one server per bounded context, not one server with a scope parameter

**Every tool in this system is read-only** (C4 `c4_components.md` — confirmed unchanged here,
not re-derived). The design question this stage actually has to answer is not read/write, it's
**how retrieval scope is enforced.**

The obvious design is one `evidence.retrieve` tool with a `scope` argument the agent supplies.
**Rejected.** That makes cross-context retrieval a matter of the agent supplying the right
string — a convention, not a control, and exactly the pattern ADR-004 rejects for prohibited
actions ("do not rely on the caller passing the right value; make the wrong value
unrepresentable"). Applying the same principle to tools:

**Decision: three separate MCP server registrations for evidence retrieval — one per bounded
context — each with `scope` fixed at server-binding time, not agent input time.** The
`evidence.retrieve` input schema has **no `scope` field at all.** An agent cannot retrieve
outside its own context because its own context's server registration is the only one it has
credentials for — the other two servers do not exist in its runtime configuration. This is a
second, independent enforcement layer on top of `langgraph_design.md`'s graph-level guarantee
(no edge, condition, or state field reaches another context's evidence) — intentional
redundancy, the same pattern `boundary_and_degraded_mode.md` uses for the write boundary.

## 2. Servers and tools

| # | Server (owning dir under `services/integration/`) | Tool | Bounded context | Read/write | Callable by |
|---|---|---|---|---|---|
| 1 | `evidence-retrieval-batch/` | `evidence.retrieve` | Batch Review | Read-only | Batch-Review Agent only |
| 2 | `evidence-retrieval-pv/` | `evidence.retrieve` | PV Intake | Read-only | PV-Intake Agent only |
| 3 | `evidence-retrieval-supply/` | `evidence.retrieve` | Supply Planning | Read-only | Supply-Planning Agent only |
| 4 | `batch-review-tools/` | `batch.reconcile` | Batch Review | Read-only | Batch-Review Agent only |
| 5 | `pv-intake-tools/` | `pv.duplicate_check` | PV Intake | Read-only | PV-Intake Agent only |
| 6 | `pv-intake-tools/` | `pv.normalize_terminology` | PV Intake | Read-only, suggestion-only output | PV-Intake Agent only |
| 7 | `supply-planning-tools/` | `supply.generate_options` | Supply Planning | Read-only, **no allocation/reservation method exists in this contract** | Supply-Planning Agent only |
| 8 | `batch-review-tools/` (`precedent_retrieve.py`) | `precedent.retrieve` | Batch Review | Read-only. Deterministic; not agent memory (ADR-010) | Batch-Review Agent only — no PV/Supply binding exists for this tool |

**Six server processes, eight tool operations.** Servers 1–3 share one JSON Schema
(`evidence_retrieve.schema.json`) with three independent bindings; servers 5–6 are combined
into one process (`pv-intake-tools/`) because they operate on the same `PVCase` aggregate and
splitting them into separate processes would add an Integration-waste hop with no
scope-enforcement benefit — unlike evidence retrieval, PV's two tools don't cross a bounded
context, so the ADR-004-style argument for separation does not apply.

**The Critic/Verifier Agent calls no tool.** It reads the `DecisionSupportOutput` already in
graph state (`agent_roster.md` §2) — giving it retrieval access would be a second, unnecessary
path into evidence, and unnecessary paths are exactly what this design avoids.

## 3. Interim (20a) vs. final (20b) scope

Matches `interim_state.md` exactly — verified, not re-derived: *"Two [tools] — Evidence
Retrieval (scoped) + Reconciliation... Duplicate-Check, Option-Generation (final)."*

| Tool | 20a (interim) | 20b (final) |
|---|---|---|
| `evidence.retrieve` (batch scope) | **Built** | — |
| `batch.reconcile` | **Built** | — |
| `evidence.retrieve` (pv scope) | Designed only | Built |
| `pv.duplicate_check` | Designed only | Built |
| `pv.normalize_terminology` | Designed only | Built |
| `evidence.retrieve` (supply scope) | Designed only | Built |
| `supply.generate_options` | Designed only | Built |

## 4. Cross-cutting contract requirements (apply to every tool)

From `langgraph_design.md` §"Handoff to Stage 11," carried forward as binding:

1. The `untrusted`/`superseded` filter runs **inside** `evidence.retrieve`, before the response
   is returned — never as a post-filter the graph applies (BC-2, ADR-003).
2. Every tool is read-only; `supply.generate_options` has no write method **in its contract**,
   not merely an unused one (ADR-004 layer 2).
3. No tool retrieves across bounded contexts (§1).
4. Every call increments the caller's `tool_calls` counter and reports token/latency
   accounting in its response envelope (BC-7).
5. Every schema is versioned (`contract_version`, semver); tests live in `tests/contract/`
   from the first tool (BC-10).

## 5. Rate limits and idempotency — ceilings now, budgets later

Same pattern as `failure_and_loop_guards.md` §1: a **ceiling** (derived from the graph's own
shape, defensible without measurement) now; a **budget** (from measured traffic) at Stage 15.

| Tool | Per-run ceiling | Idempotency key | Rationale |
|---|---|---|---|
| `evidence.retrieve` (any scope) | ≤ 2 calls/run (`failure_and_loop_guards.md` G3: 1 initial + 1 scope-preserving broadening) | `hash(query, evidence_snapshot_version, policy_contract_version)` | Same query against the same evidence snapshot must return the same result — required for safe retry after a timeout |
| `batch.reconcile` | ≤ 1 call/run | `hash(evidence_ids[], policy_contract_version)` | Deterministic given the same evidence set |
| `pv.duplicate_check` | ≤ 1 call/run | `hash(case_id, comparison_window_version)` | Must complete before `SignalTriaged` (DDD §7 hard ordering) |
| `pv.normalize_terminology` | ≤ 1 call/run | `hash(source_text, terminology_table_version)` | Pure function of input + a versioned table |
| `supply.generate_options` | ≤ 1 call/run | `hash(constraint_set, inventory_snapshot_version)` | Must be re-run, not replayed, if the inventory snapshot has moved — see §6 |
| `precedent.retrieve` | ≤ 1 call/run — no broadening concept, unlike `evidence.retrieve` | `hash(finding_hash, policy_contract_version)` | Deterministic given the same finding shape; called once, after `batch.reconcile`, before `synthesize` |

Global request-rate ceilings (circuit-breaker level, not a tuned quota): **60 calls/min per
server**, matching `failure_and_loop_guards.md` C4's blunt denial-of-wallet posture. Replaced
by measured per-tenant quotas at Stage 15 (parallel to BC-13/BC-14).

## 6. Caching — which of these tools even *can* be cached safely

Feeds Stage 18 (eval-ai-cache) directly, per the prompt's Lean lens question. **No cache exists
in 20a** (interim state excludes it entirely). This table is the input Stage 15 needs, not a
decision made here.

| Tool | Cache candidate? | Condition |
|---|---|---|
| `evidence.retrieve` | Yes, **if** the key includes evidence status and version | The exact ADR-003 guardrail (register row D5): a cache keyed only on the query, not on document status, can serve a since-superseded answer. Cache key must be `hash(query, evidence_snapshot_version)`, and a supersession event must invalidate every key built on the superseded version |
| `batch.reconcile` | Yes, same condition | Deterministic given the evidence set; the risk is identical to retrieval's |
| `pv.duplicate_check` | **Conditional — higher risk.** A case that was not a duplicate at time T can become one as new cases arrive | Cacheable only with a short TTL tied to case-ingestion rate, or invalidated on every new `PVCaseIntakeReceived` event in the same product family. Default: **do not cache** until Stage 15 designs the invalidation trigger |
| `pv.normalize_terminology` | Yes | Pure function of input text against a versioned terminology table; safe by construction |
| `supply.generate_options` | **No — do not cache by default.** | Inventory and quality status are the most volatile data in the system. A cached option set can recommend an option against inventory that no longer exists. This is a new instance of the same waste as D5/I1, worse here because the staleness is operational, not just evidentiary. If Stage 15 wants this cached, it needs a freshness bound tied to the inventory snapshot version, checked at serve time, not just at write time |

## 7. Exit criteria

- [x] Every tool an agent can call (per `agent_roster.md` §2) has a contract —
      `tool_contracts/*.schema.json`.
- [x] Every tool is read-only; the one write-adjacent tool
      (`supply.generate_options`) has its refusal mechanism detailed in
      `prohibited_write_enforcement.md`, not left as documentation alone.
- [x] `.claude/mcp.json` addressed — see that file's updated comment and §8 below for why it
      is **not** populated with live server entries this stage.

## 8. Why `.claude/mcp.json` stays an empty registry this stage

The prompt's §4 asks for "the actual server registration entries." Two things argue against
writing them as live entries right now:

1. **Nothing here is implemented.** `services/integration/` has no server code — Stage 20 is
   deliberately last. A live entry pointing at a command that does not exist would make this
   repo's own Claude Code environment attempt to launch six non-existent processes on every
   session start in this directory, which is a self-inflicted operational defect, not a design
   artifact.
2. **User instruction, this stage:** *"For MCP, if we need we use the available MCPs"* — read
   as: don't fabricate speculative server registrations; only register what is real and
   needed. That is consistent with the repo's own status-honesty rule ("designed" is never
   reported as "measured/running").

`.claude/mcp.json` is updated to point at this inventory as the design source of truth, with
`mcpServers` left `{}` until Stage 20 has actual server code to register. This table is what
Stage 20 registers, verbatim, when that code exists.
