# PROJECT SUMMARY — Context Handoff

> **Purpose:** paste/reference this file at the start of a new chat to restore full context
> without re-reading the repo. Kept current as stages complete.
> **Last updated:** after building the FastAPI + Next.js app on top of Stage 20b (§6m).
> Stages 16–19, Stage 20 (interim and full), and this app were all completed in the same
> session that also fixed a stale-doc gap here — this file had not been updated since Stage 15
> despite three more stages landing on top of it before this session started. §6k (Compliance)
> and §6l (Stage 20b) were also missing their narrative sections until this pass — only the
> status table had been kept current for those two.

---

## 1. What this project is

**Project AEGIS-PHARMA V2** — an agentic AI evolution of the V1 pharma FDE capstone.
V1 delivered governed pharma decision-support as a **single-shot** app (one request in, one
JSON-contracted response out, graded by a deterministic harness). V2 re-architects the same
three governed workflows as a **governed, observable, multi-agent system**.

**Repo:** `/Users/puranamdinesh/Documents/FDE/Project_AEGIS_Pharma_AI_FDE_Capstone_Workshop_Ready_v3_claude_Agentic`
**V1 (read-only reference, gitignored):** `./Project_AEGIS_Pharma_AI_FDE_Capstone_Workshop_Ready_v2_claude/`

### The three governed workflows (unchanged from V1, verbatim prohibitions)

| Workflow | Does | **Must NEVER do** |
|---|---|---|
| **A — GxP Batch Review** | Reconcile batch genealogy, lab results, deviations, CAPA, validation state, release-packet completeness | Release, reject, reprocess, relabel, or recall a batch |
| **B — PV Intake & Signal Support** | Intake, duplicate detection, terminology normalization, reporting-clock reconstruction, listedness | Make final seriousness / causality / expectedness / reportability / signal-confirmation decisions |
| **C — Supply-Shortage & Cold-Chain Planning** | Generate traceable, non-executing options | Change inventory status, reserve, allocate, ship, or initiate recall |

### Non-negotiables (inherited)
Synthetic data only · decision **support** only, never terminal decisions · full evidence
provenance · GxP/privacy boundaries enforced by the governance layer, **not by prompting**.

---

## 2. Method & repo structure

**Spec-Driven Development**, 21 stages, **one git branch per stage**, app built **last**
(Stage 20). Lean + DMAIC block at every stage. SDD reference material:
`/Users/puranamdinesh/Documents/FDE-training/Day-27/1785208772944-Deck/`
(layered specs, each doc answers exactly one question, "nothing written twice").

Repo follows a `.claude`-based AI-Assisted SDLC scaffold: `.claude/ docs/ plans/ apps/
services/ packages/ tests/ quality/ security/ infra/ deploy/ ops/ evidence/ templates/
workshop/` + V1 carry-overs (`prompts/ knowledge/ evaluation/ runbooks/ eval-ai-cache/`).

- **`SPEC_DRIVEN_DEVELOPMENT.md`** — method + full stage table (each stage's driving prompt)
- **`STAGES.md`** — live status tracker
- **`plans/active/EXECUTION_PLAN.md`** — delivery plan for stages 10–21: four waves, the
  **20a/20b split around Gate M** (measurement only exists once code runs), the 5 decisions
  that need a human, and local-first environment guidance
- **`prompts/`** — 23 prompts: 01–13 adapted from V1, 14–23 new for V2-only concerns.
  `ADAPTATION_NOTES.md` records what changed and why.

### Git conventions (important)
- Work happens on the stage branch; downstream branches are **fast-forwarded** after each commit.
- **`main` is deliberately NOT kept in sync** (standing user instruction) — it sits at `57d0b92`.
- Sync command used: `for b in $(git branch --format='%(refname:short)' | grep '^stage-' | grep -vE '^stage-0[1-N]-'); do git branch -f "$b" <current-branch>; done`
- Outputs are written to `docs/...` **and mirrored** to `workshop/participant-output/NN-name/`.

---

## 3. Status: 19 of 21 stages complete, plus Stage 20 (full implementation, all 3 workflows)
built and running, plus a real app (FastAPI + Next.js) on top of it — not itself a numbered
stage, but the first interface a human can actually use

| # | Stage | Branch | Status |
|---|---|---|---|
| 01 | Discovery + SCQA | `stage-01-discovery-scqa` | stable |
| 02 | **DDD** | `stage-02-ddd` | stable |
| 03 | **C4** | `stage-03-c4` | stable |
| 04 | **ADR** | `stage-04-adr` | stable — 9 ADRs, all accepted; review = **pass** |
| 05 | Current state | `stage-05-current-state` | stable |
| 06 | Interim state | `stage-06-interim-state` | stable |
| 07 | Final state | `stage-07-final-state` | stable |
| 08 | Graphical views | `stage-08-graphical` | stable |
| 09 | **DMAIC/Lean workbook** | `stage-09-dmaic-lean` | stable — 9 lenses reconciled; gate `cleared` |
| 10 | **Agentic arch (LangGraph)** | `stage-10-agentic-architecture` | stable for `batch_review`; provisional for PV/Supply |
| 11 | **MCP tool contracts** | `stage-11-mcp` | stable for batch tools; provisional for PV/Supply tools |
| 12 | **Skills & Hooks** | `stage-12-skills-hooks` | stable for `batch_review` bindings; provisional for PV/Supply |
| 13 | **Ontology-KG** | `stage-13-ontology-kg` | stable for Batch/Evidence classes; provisional for PV/Supply |
| 14 | **Eval-AI-Cache** | `stage-14-eval-ai-cache` | stable — 63 scenarios, 0 FAIL/ERROR |
| 15 | **Performance tuning** | `stage-15-performance-tuning` | stable — cost/latency models awaiting U1/U2; denial-of-wallet ceiling enforced (7/7 tests) |
| 16 | **Governance & Control** | `stage-16-governance-control` | stable — 13 policies (P-01…P-13) registered, all traced to an existing ADR/BC/hook; 3 (HITL timeout/escalation/veto) flagged with no executable eval yet |
| 17 | **Observability** | `stage-17-observability` | stable — 11-node tracing design, RBAC model (new — no prior RBAC coverage existed), severity taxonomy (SEV-1…4), redaction ruleset. **Gap:** never actually cites `eval-ai-cache/`'s OpenTelemetry Brownfield Runbook (NAB-4 not fully closed for this stage) |
| 18 | **AI Security** | `stage-18-ai-security` | stable — full DMAIC pass, 12 threats catalogued, **3 actually attempted against the live 20a system** (T-01 indirect injection, T-06 evidence-authority bypass, T-11 denial-of-wallet). Found and fixed a real gap: the denial-of-wallet guard was never wired into `services/api/graph.py` despite `hooks.md` calling it "implemented and tested" |
| 19 | **Compliance** | `stage-19-compliance` | stable — EU AI Act classification (reasoned, not legal), ISO 42001 mapping (16 clauses), 10 gaps (G-1…G-10) each with a named owner. **Found and fixed a second real audit-write gap** (same pattern as Stage 18): `HumanOverrideRecorded` had a schema + unit tests but was never written by the running graph — fixed, verified against a real run |
| **20a** | **Implementation — interim slice** (`batch_review` only) | `stage-20-repo-implementation` | **built and running** — real code for the first time since Stage 14. 6/7 interim assumptions pass (1 correctly `NOT_OBSERVABLE`); results are **provisional** (run on Groq, dev-only substitute; Route A/Claude re-run still owed per ADR-009). 3 real routing bugs found and fixed. See `docs/product/state/interim/interim_state_results.md` |
| **20b** | **Implementation — full build** (+PV Intake, +Supply Planning, +Redis cache, +dashboard data) | `stage-20-repo-implementation` | **built and running.** PV veto (forces rejected, never overridden) and Supply's real dual-approval (both legs required, one leg ≠ approval) both implemented and tested against the live graph. Redis response cache wired end-to-end — the exact ADR-003 target scenario (a cache hit on since-superseded evidence must be caught, not served) is a real passing test against live Redis + live Neo4j. **2 more real bugs found and fixed**, both on paths no prior test had ever completed: a guard-block double-write crashed with `IntegrityError` the first time any guard block ever finished end-to-end (any workflow, whole programme); a live model returning `reject` with no reason code crashed the router with `IndexError`. Interim assumptions re-checked independently per RR-2/T-10 for both new workflows — all PASS |
| 21 | Documentation | `stage-21-documentation` | not started |

**Note:** stages were resequenced early on — DDD/C4/ADR moved *before* current/interim/final
state, per the user's explicit ordering (discovery → SCQA → DDD → C4 → ADR → … → app last).

---

## 4. Architecture decisions (all 9 accepted)

| ADR | Decision |
|---|---|
| **001** | Runtime stack: LangGraph (orchestration) + LangSmith (traces/evals) + Redis (cache) |
| **002** | **V2 built fully separately from V1** — V1 is read-only evidence only, no code reuse |
| **003** | Evidence authority is a **deterministic status gate**; **`untrusted` AND `superseded` are both non-citable**. Content never self-declares authority (prompt-injection catch) |
| **004** | Prohibited actions are **structurally unrepresentable** — 3 layers: aggregate schema has no such field, tool has no such method, runtime guard. Not a prompt instruction |
| **005** | Governance/Policy Engine = **separate container**, **fails closed** |
| **006** | Audit store **separate from LangSmith** (compliance retention ≠ vendor SLA) |
| **007** | **"Degraded-mode-safe", not "offline-capable"** — every hosted dep has a safe fallback. Air-gapped GxP-network variant recorded as a known limitation |
| **008** | **One deployment, one graph per workflow, NO cross-graph agent calls** |
| **009** | **Azure** is the target platform (see §7) |

### ADR-003 origin — worth remembering
Verifying V1's actual grader code (`submission/evaluation/graders/authority_grader.py`,
66 lines) **found an error in our own DDD model**: it had claimed `superseded` docs could be
cited with a flag; V1 defines `_MUST_NOT_CITE = {"untrusted", "superseded"}`. Corrected.
**Standing rule since:** never claim V1 behavior from a filename inference — verify against
V1 code/data.

---

## 5. Domain model (Stage 02, stable)

**Bounded contexts:** 3 core (Batch Review, PV Intake, Supply Planning) — **peers, no direct
coupling**; 2 supporting (Evidence & Provenance = shared kernel; Governance & Oversight =
**open-host service**, deliberately not a shared kernel so policy can't be locally weakened);
1 generic (Agent Orchestration).

**Domain agents:** Batch-Review, PV-Intake, Supply-Planning, + **Critic/Verifier** per graph.
A single generalist agent was explicitly **rejected** — it would have to hold all three
distinct prohibition sets at once.

**Key invariants:** `Batch` has no release/reject field · `ShortageOption` has no
`allocated_quantity` field · PV output has no causality/seriousness/reportability field ·
Supply tool has no allocation write method · zero write integrations to any brownfield system.

### Named HITL approvers (EAB-3, closed — taken verbatim from V1's `case/STAKEHOLDER_PACK.md`)

| Workflow | Approver | Their stated authority |
|---|---|---|
| A | **EU Qualified Person** (esc: Chief Quality Officer) | "Final certification remains human-only" |
| B | **Global Head of Pharmacovigilance** (esc: CMO; Patient Safety Rep has advisory veto) | "Final safety decisions remain human-only" |
| C | **Supply Chain VP** **+ Quality co-approver** where quality status is implicated | "Planning; regulated execution needs approvals" |

- **Manufacturing VP is explicitly NOT a batch approver** — "operations, never independent batch release".
- Accountability attaches to **roles, not individuals** (survives turnover; ISO 42001 expectation).
- HITL timeout ⇒ **no action**, never auto-proceed.

---

## 6. Transition plan

- **Current state:** design complete through Stage 08; **zero implementation**; 249 tracked files.
- **Interim state:** **ONE workflow (Batch Review) end-to-end.** Cache **deliberately excluded**
  (don't introduce stale-authority risk alongside agent-correctness risk). Prohibited-Action
  Guard present **day one** (can't be retrofitted). Must prove **7 assumptions**, incl.
  assumption 6 = **first real token/cost measurement** (Unknown since Stage 01) and
  assumptions 1–2 = **stop-the-line** (prohibited-action + evidence-authority enforcement).
- **Final state:** 3 workflows, 4 MCP tools, cache, dashboards/SLOs, threat model executed,
  compliance evidence from real runs. **3 of 7 completion gates still open** — all require
  the system to actually run.

---

## 6b. Lean/DMAIC consolidation (Stage 09, `docs/quality/dmaic-lean/`)

Nine prior `dmaic_lens.md` files + five register pairs reconciled into **one governing set**
(`lens_rollup.md`, `dmaic_plan.md`, two registers, `build_constraints_from_lean.md`,
`structural_reopen.md`). **24 distinct wastes merged; 11 still open.**

- **Mode = Measure-first.** Framing is `decision-ready`, but *every* baseline that matters is
  Unknown — nothing has ever been measured on a running system. Instrumentation outranks
  feature scale-out; no waste is described as "fixed," only as "decided, proof scheduled."
- **Three findings no single prior lens contained:**
  1. **C3 / RR-1** — Stage 01 said quantify token cost *before* locking topology. It wasn't:
     ADR-008 was accepted with cost still Unknown. Now an explicit accepted debt with revisit
     trigger **T-3** (bad interim cost number ⇒ reopen ADR-008 before building 3×).
  2. **G3** — "blind retry" (Model waste) lost its owner in the stage resequencing; assigned
     to Stage 10 (BC-5).
  3. **C1** — ontology-vs-agent ordering was resolved in practice but never written: Stage 10
     designs against an ontology **contract**, Stage 13 fills it in (BC-4).
- **12 must-fix-before-build constraints (BC-1…BC-12)** are binding input to Stage 10, with a
  recommended task order: guard + state schema + graph isolation first, then contract-first
  retrieval / retry rules / Critic scope, then instrumentation before any node is "done."
- **10 revisit triggers T-1…T-10** are now programme-level, incl. two stop-the-line ones
  (interim assumptions 1 and 2).
- **Structural gate: `cleared`** — no Improve action reopens C4, an ADR, or a contract.
  Two *documentation* defects recorded instead: **ADR-009 is missing from `decision_index.md`
  and `architecture_review.md`** (both still say "8 ADRs"), and NAB-2.

**Execution plan** (`plans/active/EXECUTION_PLAN.md`, not a stage spec): Stage 20 splits into
**20a (Batch Review interim slice, no cache) → Gate M → 20b (full build)**, because every
Unknown baseline becomes measurable only once code runs. Governance (16) and eval/observability
*design* passes (14/17) are sequenced **before** 20a; their *measured* passes come after.
5 human decisions named, the binding one being the **LLM route** (ADR-009) before 20a runs.

## 6c. Agentic architecture + MCP (Stages 10–11, `docs/architecture/agentic/`, `services/integration/`)

**Stage 10 — LangGraph design.** 11 nodes, **2 of them LLM nodes** (domain-agent synthesis +
Critic/Verifier); every control is deterministic (schema, status lookup, pattern match, edge
condition). Two decisions made and justified, not defaulted into: **no planner agent** (the
sequence is a constant; a planner would be a new authority surface and pure token waste) and
**no long-term agent memory** (a remembered conclusion has no citable source/status — it would
be a second, unaudited cache). DMAIC lens states plainly that **the multi-agent split is a net
token/context/transportation cost to buy one defect control** (the Critic doubles happy-path
LLM calls, 1→2) — most of the actual safety benefit comes from the deterministic nodes and the
absent schema fields, not from having multiple agents.

**HITL timeout = a four-tier escalation ladder** (T0 interrupt → T1 reminder → T2 conditional
escalation → T3 expiry/no-action), not a single deadline. Escalation only **widens** who may
approve (adds a role, never replaces or auto-approves) and only proceeds if, checked at that
moment: an escalation role is named for the workflow, that role has a **live** authorization
right now, the draft is still guard-clear, the policy version is still current, and the role's
own authority covers the decision. Any failed condition ⇒ audit-logged skip, run stays with the
primary on schedule. **Supply's planning leg has no escalation role at all** (V1's stakeholder
pack names none above the Supply Chain VP — not invented here) and its dual approval survives
escalation intact (both legs still required). PV's advisory veto (Patient Safety Rep) sits
outside the ladder — registrable at any tier, never overridden.

**Status split:** `batch_review` graph = `stable` (20a slice). `pv_intake`/`supply_planning` =
`provisional`, designed by analogy — RR-2/T-10 require re-checking, not assuming transfer.
Open gap flagged, not papered over: PV's reporting-clock reconstruction fits neither a tool
node nor a synthesis node yet (20b).

**Stage 11 — MCP tool contracts.** 7 tool operations across 6 server registrations. **Every
tool is read-only** — the real design question was retrieval-scope enforcement, not
read/write. Decision: **one server per bounded context for `evidence.retrieve`, with `scope`
absent from the input schema entirely** (fixed at server-binding time, not agent-supplied) —
applying ADR-004's "don't rely on the caller passing the right value" one layer down, to tools.
`prohibited_write_enforcement.md` walks the three-layer argument (schema/tool-method/runtime
guard) through a worked example on `supply.generate_options`, the contract closest to a write.

**Caching finding for Stage 15:** "read-only ⇒ cacheable" is wrong for two tools —
`pv.duplicate_check` (a case can become a duplicate as new cases arrive) and
`supply.generate_options` (inventory/quality status are the most volatile data in the system;
a stale cached option set can recommend against inventory that no longer exists). Both marked
do-not-cache-by-default pending an invalidation design.

`.claude/mcp.json` deliberately left with `mcpServers: {}` — registering commands for
unimplemented servers would make this repo's own Claude Code session try to launch nonexistent
processes. Per standing instruction: **register only real, needed MCP servers**, not
speculative ones; Stage 20 populates it for real when server code exists.

**Stage 12 — Skills & Hooks** (`.claude/skills/skills.md`, `.claude/hooks/hooks.md`,
`.claude/skill_vs_hook_boundary.md`). Catalogued Stage 10's 9 deterministic nodes as hook
bindings (session-start, pre-tool-call, post-tool-call, pre-output, on-interrupt, post-run) and
named 4 runtime domain-agent skills + 4 build-process skills for the 2 LLM nodes. **The rule
this stage adds, not just relabels:** no skill's output is ever the last check on itself —
every skill (e.g. the Critic's judgement) has a downstream hook checking its output's *shape*,
never trusting the skill's own reasoning. Worked counterexample in
`skill_vs_hook_boundary.md` §4 shows why folding the prohibited-action check into the Critic's
prompt (skip the separate guard hook) would fail: it makes the highest-severity control in the
system depend on a model correctly resisting a jailbreak exactly once, with no independent
check — precisely the H5 risk from Stage 01.

Same operational-safety call as Stage 11's `mcp.json`: **`.claude/hooks.json` stays
`hooks: {}`.** These bindings govern the *deployed* V2 runtime (Stage 20), not this coding
session — populating real PreToolUse/PostToolUse commands now, before the scripts exist, would
make this repo's own Claude Code session try to run nonexistent hooks on every tool call.

**Correction applied same session:** cross-verifying `failure_and_loop_guards.md` against
`langgraph_design.md`'s actual edge table found a real contradiction — a first-occurrence
`PROHIBITION_ADJACENT` Critic verdict was routable back to `synthesize` for a retry, when the
rule required it go straight to `blocked`, never retried. Dangerous specifically because that
code only fires when the cheaper `guard1` pattern-match has already missed a draft — retrying
would ask the model to rephrase a near-miss on the system's highest-severity control. Fixed:
`critic_verify` now has an unconditional `PROHIBITION_ADJACENT ⇒ blocked` edge, checked first.

## 6d. Ontology / Knowledge Graph (Stage 13, `docs/architecture/ontology/`)

**NAB-3 half-resolved.** V1's `knowledge/` (32 policy docs) + `knowledge_catalog.csv` (the
provenance/status/trust/supersession index) copied into this repo's own `knowledge/` and
SHA-256-verified against the catalog's own hashes. V1's `data/`/`evaluation/` fixture half
stays cross-repo, left for Stage 14 on the Overproduction argument (copying unused fixtures now
would be waste). Reasoning: a gitignored, 983MB sibling directory isn't reproducible for anyone
cloning only this repo, and this stage is the first that needs a stable source to build a KG
schema against. Not a reopening of ADR-002 ("no code reuse") — this is domain reference data,
not application code.

**17 classes, 14 edge types, grounded against V1's actual CSV schemas** (`batches.csv`,
`icsr_cases.csv`, `knowledge_catalog.csv`, etc.), not derived from DDD prose alone. Two findings
surfaced only by checking real data:

1. **`SensitiveSegment`** (`pregnancy`/`minor` case segments with restricted `access_group`s) —
   a governance boundary DDD's original entity table never named. Flows *backward* as a gap in
   Stage 02, recorded honestly rather than silently patched. Consequence: the PV-Intake Agent's
   evidence scope needs an access-group check in addition to bounded-context scope — currently
   unmodeled in `langgraph_design.md` or the MCP contracts; assigned to Stage 16/20.
2. **`Deviation` has no `batch_id` foreign key anywhere in V1's own relationship model.** The
   deviation-to-batch link that `batch.reconcile` needs isn't a guaranteed structured join —
   Stage 20 will need a defined matching heuristic (site/date/product overlap), not a lookup.

**Semantic layer fills BC-4** (Stage 10 designed agents against an ontology contract that
didn't exist yet) and specifies exactly what Stage 11's `evidence.retrieve` query terms resolve
against: KG concept/relationship/text match, single-hop bounded by context, `PortfolioProduct`
as a hop-terminator (it's the one cross-workflow hub node, so a naive second hop would leak
across workflows — blocked by both the hop rule and by each context having its own server
process, `tool_inventory.md` §1).

**Conflict/authority rules — every one traced to an existing decision, none invented:** the
ADR-003 citability rule re-confirmed independently against real catalog data (not just Stage
04's grader-code reading); `local_approved` documents are fully citable within their
jurisdiction, never subordinate to a `Global` document by jurisdiction alone — only an explicit
`supersedes` edge establishes precedence; `supersedes` is populated only from the catalog's own
column (which stores a filename, not a key — normalized once at ingestion), never re-derived
from a document's prose claiming to supersede something.

## 6e. Eval-AI-Cache (Stage 14, `eval-ai-cache/`, `quality/gates/`, `tests/unit/graders/`)

**Full DMAIC stage** (sets Measure/Control for the whole agentic system). Consumes
`eval-ai-cache/AI_FDE_Brownfield_Evals_Cursor_Runbook/` rather than re-deriving it (NAB-4/T-7)
— gate-state vocabulary (`PASS`/`FAIL`/`REVIEW`/`NOT_APPLICABLE`/`NOT_OBSERVABLE`/
`THRESHOLD_NOT_DEFINED`/`BLOCKED_BY_ENVIRONMENT`) and hard/threshold/operational gate taxonomy
both taken from it directly. Grader **patterns** (not code — ADR-002) verified against V1's
actual `submission/evaluation/graders/*.py` and `tool_gateway.py` first.

**63 real scenarios, 15 categories (12 required + 3 agent-specific), executed this session —
0 FAIL, 0 ERROR.** Honestly scoped: this is a design-pass run against synthetic fixtures shaped
like our own contracts, since no `apps/`/`services/` code exists yet (Stage 20 last) — not a
live-system run. 2 `NOT_APPLICABLE` (business outcome, human-rubric, matches V1's own
un-automated category), 1 `THRESHOLD_NOT_DEFINED` (cost-per-task cap — U1 still Unknown,
refused to guess), 1 `BLOCKED_BY_ENVIRONMENT` (model-substitution check pending ADR-009's route
decision). Verify with `python3 eval-ai-cache/graders/run_eval_dataset.py` or
`pytest tests/unit/graders/ -q`.

**The harness found 7 real defects in itself before it was trusted** (`scorecard.md` §2) —
a schema-path doubling, a replay-counter that incorrectly incremented on plain replays
(contradicting V1's own verified `tool_gateway.py` behavior), an adversarial fixture whose
"bad" branch the grader had no way to actually produce, and 3 more. All fixed; recorded rather
than hidden behind the final green run, since a scorecard showing only the clean pass
overstates first-try correctness.

**Agent-specific category 13 (`agent_wrong_handoff`) is the regression suite for the real
`PROHIBITION_ADJACENT` routing bug** found and fixed at Stage 10 — `AWH-01` asserts the fix
holds: a first-occurrence `PROHIBITION_ADJACENT` verdict must route straight to `blocked`,
never to a retry.

**Cache design (`cache_design.md`) — not built,** per `interim_state.md`'s deliberate exclusion.
Cache key = `hash(query, evidence_snapshot_version)`, never a plain wall-clock TTL (a TTL can't
distinguish "still correct" from "coincidentally not yet expired"); do-not-cache list
(`pv.duplicate_check`, `supply.generate_options`, both from Stage 11) enforced via an executable
grader, not just documentation. **Cache-correctness evals: 8 checks, all executed and correct**
(`cache_correctness_evals.md`) — including the exact scenario the prompt names: a cache hit on
`K-007` (the real `BATCH_RELEASE_POLICY_OLD.md` supersession pair) after it transitions to
`superseded` is caught, not served.

**Release gates independently re-derived from our own ADRs**, not copied from V1's 10 gates
(ADR-002) — traceability table maps every gate to its owning ADR/DDD invariant and grader.

## 6f. Performance Tuning (Stage 15, `docs/quality/performance/`, `infra/policies/`)

Same honesty split as every measurement-dependent stage: cost/latency **targets** need U1/U2
(Unknown since Stage 01, first measurable at 20a); what's real is stated as real, what isn't is
left explicitly open rather than guessed.

**Token economics — real, verified pricing, no invented usage numbers.** Loaded the `claude-api`
skill (standing trigger for any Claude/Anthropic pricing discussion) rather than recalling
stale figures: Opus 5 $5/$25 per MTok, Sonnet 5 $3/$15, and confirmed Azure AI Foundry
(ADR-009 Route A) bills at the same first-party rates — closing one small piece of ADR-009's
open question. Recommended (not decided) starting model for 20a: Sonnet 5. Cost model is exact
(2 LLM nodes only, per `langgraph_design.md`); actual token volume per run is still Unknown.

**Redis tuning — consumed the pre-seeded runbook in full** (NAB-4/T-7, previously unread).
Key finding: the runbook's own engineering-plane/data-plane split means the deployed app must
use a **native Redis client, never MCP**, at runtime — a new rule, distinct from Stage 11's
unrelated domain-agent MCP tool servers. Also found and fixed a real gap in Stage 14's cache
design: it never specified *where in the pipeline* caching happens relative to the
Prohibited-Action Guard/Critic — now fixed (never cache a draft, only a guard-and-Critic-cleared
response). Cluster-failure *alerting* (as opposed to correctness-on-failure, already specified)
was also missing and is now specified. No cache is built — unchanged from Stage 14.

**Denial-of-wallet guardrail — the one Stage 15 deliverable that's actually built and tested,
not just designed.** A worst-case ceiling needs no measurement, only already-ratified inputs:
`DAILY_RUN_CEILING=20` (reuses C4) × `MAX_TOKENS_PER_RUN=150,000` (=C1) × verified Sonnet 5
output price = **$45.00/user/workflow/day**. Fail-safe direction matches ADR-005. **7/7 tests
passing** (`tests/unit/policies/test_denial_of_wallet_guardrail.py`), proving per-user/
per-workflow isolation, daily reset, and that the ceiling actually trips. Wired into
`.claude/hooks/hooks.md` as a tenth hook row (pre-tool-call, at `intake`) — the only row in that
table backed by a real executable + test rather than only a design reference.

## 6g. Governance & Control (Stage 16, `docs/governance/`, `security/policies/`)

**13 governed boundaries (P-01…P-13) consolidated, none invented** — every entry traces to an
existing ADR (004/005/006/008), a Build Constraint (BC-1/3/5/8/12/17), or a `hooks.md` binding
that already existed. The exercise itself surfaced a real gap the individual documents hadn't
made visible: P-07/P-08/P-09 (HITL timeout, escalation, PV advisory veto) are `stable` in
design but have **no executable eval** yet — they need a running interrupt/clock, which
Stage 14's fixture-based harness can't simulate. Recorded honestly, not hidden behind the
9-of-13-covered figure.

`hitl_control_model.md` was **extended, not overwritten** (per its own instruction) with a new
§7 confirming the Stage 10 timeout-ladder durations against the named roles — "confirmed" here
means checked for internal consistency, not signed off by an actual person (no operating org
exists yet). New revisit trigger **T-11**: re-confirm every role/duration against a live Entra
assignment at first real deployment.

`escalation_override_log_design.md` designs three distinct audit record shapes
(`HitlEscalation`, `HumanOverrideRecorded`, `HitlExpired`) — deliberately kept separate so "the
system widened who may approve" is never conflated with "a human actually decided," which BC-12
depends on staying distinguishable.

## 6h. Observability (Stage 17, `packages/observability/`, `ops/`)

**Tracing design binds one span per node/hook that already existed** in `langgraph_design.md`/
`hooks.md` — no new control invented, only made explainable. Actor identity
(`actor_plane`/`actor_role`/`actor_id`) added to every span, closing a gap that existed between
the RBAC model and the trace schema.

**Two additions beyond the stage's original prompt scope**, added at explicit user request
after a gap review mid-session:
- **`rbac_model.md`** — zero RBAC coverage existed anywhere in the repo before this. Names both
  a human plane (extends `hitl_control_model.md` with system-access roles it never covered —
  Compliance Reviewer, Platform Operator) and a service plane (one managed identity per
  container, mapped 1:1 onto ADR-008's "zero cross-graph calls" as Azure RBAC role scoping),
  both on Entra ID (ADR-009).
- **Severity taxonomy** (`alerting.md` §1) — SEV-1 (stop the line) through SEV-4 (dashboard-only),
  replacing severity language that was previously asserted ad hoc and inconsistently across
  `failure_and_loop_guards.md`.

**Known gap, not silently closed:** this stage's own prompt says it should draw on
`eval-ai-cache/`'s OpenTelemetry Brownfield Runbook — none of `packages/observability/`'s docs
actually cite it. Flagged in §8 below.

## 6i. Implementation — Interim Slice (Stage 20a, `packages/`, `services/`, `tests/`)

**First stage to produce and run real application code**, not design documents, since
Stage 14's eval harness. Scope exactly matches `EXECUTION_PLAN.md` Wave 3: `batch_review` only,
no Redis, no PV/Supply.

- **`packages/domain/`** — `GovernedState`, `EvidenceItem`, `BatchPayload`,
  `DecisionSupportOutput`. ADR-004 layer 1 enforced with pydantic `extra="forbid"`: a
  disposition field (`release_recommended`, etc.) cannot be constructed, not just disallowed by
  convention — proven by a red-team-style test that tries and fails at construction time.
- **`packages/domain/kg/`** — the Stage 13 semantic layer, actually built on **Neo4j** (a
  technology no prior ADR had selected — added at user request this session), ingesting the
  real 32-doc `knowledge/` corpus with SHA-256 provenance. K-006 supersedes K-007 (a real pair
  in the catalog) verified live: querying for K-007 after ingestion never returns it.
- **`services/integration/`** — `evidence_retrieve.py`/`batch_reconcile.py` contract-validated
  against the real Stage 11 JSON schemas; `policy_engine.py` (fails closed, ADR-005),
  `prohibited_action_guard.py` (ADR-004 layer 3), `evidence_gate.py` (ADR-003 second check),
  `hitl_route.py` (four-tier ladder), `audit_store.py` (append-only SQLite, veto cannot be
  superseded — enforced at the write layer, not by convention).
- **`services/api/graph.py`** — the full 11-node `batch_review` LangGraph. LLM provider is
  swappable via one interface (`packages/config/llm_client.py`) — Anthropic (Route A, the only
  provider whose results count) or Groq (dev-only, provisional, used this session per user
  instruction while the Anthropic key was being corrupted in transit twice).

**Results: 6 of 7 interim assumptions (`interim_state.md` §3) PASS**, one correctly
`NOT_OBSERVABLE` (hop count needs Stage 20's real deployed topology, not this in-process
build). Full writeup: `docs/product/state/interim/interim_state_results.md`.

**Three real routing bugs found and fixed**, all only because a live model (even an unreliable
one) exercised paths the deterministic stub test never did:
1. Cap-exceeded and `PROHIBITION_ADJACENT`-blocked routes reached `finalize` without setting
   `terminal_state`, silently mislabeling both as `"completed"`.
2. Approval detection used an empty `critic_reason_codes` list as its signal, but that list
   accumulates across the whole run — a genuine approval after a prior rejection was misrouted
   using a stale reason code.
3. **The HITL timeout path never set `terminal_state`** — the highest-stakes of the three,
   since it directly affects BC-12 ("timeout ⇒ no action, never auto-proceed"). A timeout was
   silently finalizing as `"completed"`. Fixed directly in the `hitl_interrupt` node.

**Finding beyond pass/fail:** Groq's small model (`llama-3.1-8b-instant`) repeatedly
false-rejected a correctly-cited draft, hitting the G1 retry cap (6 LLM calls) rather than
approving quickly. Not a code defect — the loop guards worked exactly as designed — but direct
evidence for ADR-009's own rationale (keep the model variable fixed while the platform moves):
a weaker model changes the *shape* of a run, not just its prose quality.

## 6j. AI Security (Stage 18, `security/threat-models/`, `security/abuse-cases/`, `tests/security/`)

**12 threats catalogued (T-01…T-12) against the real Stage 20a code**, not the design docs —
plus 3 more (T-13…T-15) named as not-yet-buildable until PV/Supply exist. Full DMAIC, per the
stage's own prompt (security is designated full-DMAIC alongside Discovery/DDD/C4/ADR, not a
thin lens).

**Three threats actually attempted, not just modeled:**
- **T-01 (indirect prompt injection).** Confirmed by code inspection first: `EvidenceItem.
  content_excerpt` is never sent to the LLM, but `batch_reconcile`'s `findings[].
  gap_description` *is*. Built a real adversarial fixture (`B-EVIL.json`) with an injection
  payload in that field, ran it against a live model (Groq). The model didn't comply this run;
  the test asserts the structural guard (`prohibited_action_guard.py`) would catch compliance
  regardless — the actual claim ADR-004 makes, now backed by a real attempt rather than only
  the design argument.
- **T-06 (evidence authority bypass).** Re-confirmed K-998/K-999 (real `untrusted` fixtures)
  never leak through `evidence.retrieve`, server-side filter verified via
  `tool_accounting.items_filtered_untrusted`.
- **T-11 (denial of wallet) — found a real, unfixed gap.** `DenialOfWalletGuard` (Stage 15,
  7/7 tests passing at the module level) was **never actually called** from
  `services/api/graph.py` — `intake` never called `check_and_admit`, `finalize` never called
  `record_run`. `hooks.md`'s "stable — implemented and tested" claim was true of the standalone
  module, not the graph integration, and nothing had exercised the real graph with an LLM
  before this session to catch the gap. **Fixed**: both calls wired in; confirmed against the
  full 107+ test regression suite.

**Residual risks recorded honestly**, not hidden behind the "3 real attacks, all handled"
headline: paraphrase evasion of the guard's literal-string match (**Medium**) — a model
complying without using any literal banned term wouldn't be caught; the denial-of-wallet
ceiling is in-process only, doesn't survive restart/scale-out (**Medium**); **zero dependency
supply-chain control exists in this repo at all** — no lockfile, no pinned versions, no SBOM
(**Open**); two threats (T-08 stale-policy replay, T-09 PII redaction) are genuinely untestable
today, not neglected — T-08 needs a second policy version, T-09 needs PV Intake's PHI fields,
neither of which exist yet.

**Own-suite bug found and fixed too:** `test_assumption_3` (Stage 20a's interim tests) asserted
HITL was always reached before timeout — but a live model can legitimately exhaust the G1
retry cap first (Groq did, under a full-suite run). The actual safety invariant (never silently
`"completed"`) held either way; the test was over-asserting *which path* got there, not the
property. Also moved `test_interim_assumptions.py` under the `live` pytest marker — it had been
making real API calls even during `-m "not live"` filtered runs.

## 6k. Compliance (Stage 19, `docs/governance/compliance/`)

**EU AI Act classification is reasoned, explicitly not a legal determination** — matches V1's
own `REGULATORY_BOUNDARY_PACK.md` framing ("research anchors, not legal conclusions"), read this
stage per the standing ADR-002 rule rather than inventing classification criteria. Points toward
decision-support (not an Annex III-listed high-risk category), but whether it's a "safety
component" under Article 6(1) is a determination this project cannot make with legal authority —
recorded as **Gap G-1**, not silently treated as resolved.

**ISO 42001 mapping across 16 clauses**, most backed by real operating evidence (99+ real
`AgentRun` records, live Neo4j, Stage 18's real red-team results) rather than documents alone.
Several clauses (internal audit, management review) are named as **structurally premature** —
they need an operating organization that doesn't exist yet, not more code.

**Found and fixed a second real audit-write gap**, same pattern as Stage 18: `HumanOverrideRecorded`
had a schema and passing unit tests (`escalation_override_log_design.md`) but the running graph
never actually wrote one — 0 rows despite 99+ real `AgentRun` records. Fixed: `hitl_interrupt`
now calls `write_human_override`/`write_hitl_expired`, verified against a real live run producing
a real row. Justification field is a stated placeholder (no approver-input UI existed at the
time). **Still open**: the app built in 6m has a real approve/reject/veto UI now, but its
`DecisionButtons` component doesn't collect a justification string either — Gap G-10 (no
structured justification input) is not closed, just not made any worse.

**10 gaps (G-1…G-10)**, each with a named owner — including a real, previously-unflagged one:
zero dependency supply-chain control anywhere in this repo (no lockfile, no SBOM), re-flagged
from Stage 18 as an ISO 42001 clause gap in its own right, not just a security nice-to-have.

## 6l. Implementation — Full Build (Stage 20b, `services/api/pv_graph.py`, `supply_graph.py`, `packages/config/redis_client.py`)

**PV Intake and Supply Planning built and proven independently** (RR-2/T-10 — nothing assumed
from Batch Review): PV's Patient Safety Representative veto (forces `rejected`, never
overridden — enforced at the audit-store write layer, not by convention) and Supply's **real**
dual-approval (Supply Chain VP + Quality legs, both required — proven via LangGraph's
multi-interrupt-per-node pattern across separate `invoke()` calls that one leg approving alone
never completes the run).

**Redis response cache wired end-to-end** — the exact ADR-003 target scenario (a cache hit on
evidence that's since transitioned to `superseded` must be caught, not served) is a real passing
test against live Redis + live Neo4j, not a design citation. Real hit/miss counters (not a
proxy), feeding a new `dashboard_data.py` module that makes the Stage 17 dashboard panels
computable from real data across all three workflows for the first time (155/46/38 real runs
respectively, as of this stage).

**Two more real bugs found and fixed**, both on paths no prior test had ever completed end to
end: `guard()`'s "blocked" branch wrote its own `agent_run` record, and `finalize` wrote a
*second* one for the same `run_id` — a PRIMARY KEY, so this crashed with `IntegrityError` the
**first time any guard block, in any workflow, across the whole programme, ever actually
finished**. And a live model returning `verdict: "reject"` with no `reason_code` crashed the
router with `IndexError` — fixed at both the parse layer (now a proper `CONTRACT_VIOLATION`) and
the router (defense in depth: an empty reason-code list escalates to a human instead of
crashing).

## 6m. The App — FastAPI Orchestrator API + Next.js Approver Dashboard (`services/api/main.py`, `apps/web/`)

**Not a numbered stage** — built at explicit request, after Stage 20 proved the engine worked
but nothing let an actual human interact with it (every run through Stage 20b had been driven by
a script). `services/api/main.py` (FastAPI) wraps the three existing graphs over HTTP with
**zero changes to their internal logic**; `apps/web` (Next.js 16, TypeScript, Tailwind) is the
Approver Dashboard — queue of pending decisions, expand to see the draft + citations,
approve/reject/veto or dual-leg-approve.

**Found a third serious bug, this time via the real HTTP flow specifically** — the kind of bug
none of the prior in-process test scripts could have caught: `response_cache`'s cache key hashed
only `evidence_ids`, but every batch/case/product in a workflow retrieves the *same* evidence set
(query terms are workflow-scoped, not subject-scoped) — so **the cache served one batch's
reconciliation findings for a completely different batch's request.** Worse than the ADR-003
staleness scenario already tested: factually wrong content, not merely stale content. Fixed:
`cache_key()` now includes `subject_id`; new regression test
(`test_cache_is_isolated_per_subject_id`) proves two subjects sharing evidence never share a
cache entry. A fourth, smaller bug (Supply Planning's dual-approval progress not visible
mid-flow, due to LangGraph only persisting a node's state once it fully returns) was also found
and fixed, tracked in the API layer instead of read back from the graph's not-yet-caught-up
snapshot.

**Stated honestly as basic, not polished**: functionally real (live LLM calls, live HITL, live
audit trail, verified via curl against real Neo4j/Redis/Groq) but minimal — default Tailwind
styling only, no auth (Entra ID is the real ADR-009 target, not built here), polling instead of
push updates, no run-history view. `services/api/pending_queue.py` is explicitly in-memory/
single-process, same disclosed-simplification pattern as `denial_of_wallet_guardrail.py`'s own
docstring — the audit trail itself is unaffected and remains the real record regardless.

## 6n. Record Assistant, PI/PG and the AI-BOM (Stage 23, `services/api/record_chat.py`, `services/integration/prompt_guard.py`, `security/sbom/`)

Three moonshot items, built together because each depends on the one before it.

### Record Assistant — a chatbot that structurally cannot recommend

`POST /api/runs/{run_id}/chat` answers "what is this record, and what happens next?" for
one run.

Reachable from **every signed-in page** via an "Ask about a record" launcher mounted in
`AppShell` (`components/assistant/AssistantLauncher.tsx`), and additionally as an
**Assistant** tab on the run detail page. Both render the same `RecordAssistant`
component rather than duplicating it. The launcher opens straight onto the run when the
route already identifies one (`/decisions/<id>`, `/runs/<id>`) and otherwise shows a
picker, pending runs first — a pending run still holds its decision-support package in
memory, so it yields the richer answer.

**This placement was a correction, not the original design.** The assistant shipped as a
run-detail tab only, which made it undiscoverable from the overview, the queue, and every
other screen an operator actually starts from — defeating the point of building it. Found
by running the app, not by any test.

The design rule the whole feature is built around: **the model writes prose; it does not
compute facts and it does not choose actions.**

| Half | Source | Can it be wrong? |
|---|---|---|
| Record card (subject, approvers, evidence ids, HITL timer, terminal state, human actions) | `build_record_card()` — same two sources `/api/runs/{run_id}` reads | No — same data, different shape |
| "What happens next" | `derive_next_steps()` — a **closed catalog** of procedural branches | No — no branch has a disposition to return |
| Summary, answer, step paraphrase | The model | Yes — and the UI labels it as such |

That split is what makes "what to do next" safe to offer. A free-form model asked "what
should I do about this batch?" will eventually answer "release it"; the non-negotiable
that no agent makes a terminal safety decision cannot survive that question being
delegated — so it isn't. `test_next_steps_never_contain_a_disposition_for_any_role`
asserts the generated steps against **every** banned term in the policy contract, for four
different roles.

Governance carried through, not re-derived: authentication via the same `require_user`
dependency; segregation of duties enforced (`Unblinding authority` gets a 403 on a
`supply_planning` record, not an empty answer); ADR-007 degraded mode (no model → the
deterministic facts survive, `llm_available: false`); ADR-005 fail-closed (no policy
contract → the prose is dropped rather than shown unchecked). Stateless by design — no
conversation history, because history is a second injection surface and nothing in this
use case needs it.

**Not done:** chat interactions are not written to the append-only audit store. That store
records agent runs and human overrides; a read-only reading aid is neither, and widening
it would blur what an audit record means. Guard hits are logged and returned to the caller.

### PI/PG — prompt-injection detection and prompt guarding

`services/integration/prompt_guard.py` adds **layer 0** (input, before any prompt) and
**layer 4** (output, before any human) around ADR-004's three structural layers. 13 input
patterns and 3 output patterns plus system-prompt-marker and citation-fabrication checks.

The framing matters and is stated in the module's own docstring: *layers 1–3 make a bad
outcome impossible; layers 0 and 4 make a bad attempt visible.* A pattern matcher can
always be paraphrased around, so a `clear` verdict is not a safety guarantee.

- `high` → refused, nothing sent. `medium` → neutralized and recorded, request proceeds.
- Neutralization names the *pattern*, never echoes the matched text — an earlier version
  wrote `[NEUTRALIZED:<matched text>]`, which left the instruction in the prompt verbatim.
  Caught during the build; `test_the_neutralized_text_never_echoes_the_payload_back` is the
  regression guard.
- False positives are treated as a real cost, not a safe default: a corpus of ordinary
  pharmaceutical record text is asserted to scan `clear`, because a control that mangles
  legitimate findings is a control that gets switched off.
- `scan_output()` takes the **same** `ProhibitionContract` the graph guard uses, so the
  assistant and the graph cannot disagree about what is prohibited.

Full write-up, including the stated limits: `docs/security/prompt_injection_defense.md`.

### AI-BOM — the supply chain that has no version numbers

`security/sbom/ai_sbom.json` (CycloneDX 1.6 ML-BOM). The argument for a *second* SBOM:
every component in `sbom.json` has a version an installer can check, which is what makes
`verify_sbom.py` trustworthy. The things that actually determine this system's behaviour —
the model endpoint, the system prompts, the prohibition contract, the guard's pattern set —
have no version number at all. Change any of them and every governance property can change
while `pip freeze` stays byte-identical.

Everything recorded is **computed from the live repository**: prompts hashed from the
actual module attributes, the guard ruleset hashed from the compiled patterns (including
severities — a `high`→`medium` downgrade turns a refusal into a pass-through without
touching a regex), policy contract and tool manifest hashed from disk.
`verify_ai_sbom.py` recomputes all of it and exits non-zero on drift.

**The practical effect: an edit that weakens a governance instruction in a system prompt
fails CI.** `test_weakening_a_governance_prompt_fails_verification` proves it by making
exactly that edit.

Stated honestly: model identifiers are recorded as **mutable aliases** and flagged
`aegis:identifier_is_mutable_alias: true`. A matching id proves nothing about the weights
serving the request, so an id change is *reported* rather than failed (`--strict` opts
into the stricter reading). ADR-009's revisit trigger applies and this file cannot detect it.

**Gap closed along the way:** `openai` — the SDK `GroqLLM` actually imports — was absent
from `sbom.json` while `groq` was recorded. An SDK on the live LLM call path was
unrecorded, which is precisely INJ-070's blind spot. Both are now listed, with a note
explaining which one the code imports.

### CI/CD

`.github/workflows/ci.yml` — governance gates first (both SBOMs, tool-manifest integrity,
committed-secret check), then API lint/tests, web typecheck/lint/tests/build, and both
container image builds. A single `ci-passed` job is the branch-protection target.

`cd.yml` — build, push, and deploy to **Azure Container Apps** (ADR-009), with signed SLSA
build provenance attached to both images, both SBOMs published as run artifacts, and a
post-deploy smoke test that checks the deployed API both answers *and* returns 401 to an
unauthenticated caller. A `preflight` job stops with a readable message when secrets are
missing, and writes to the run summary which parts of ADR-009 this pipeline does **not**
implement: secrets are GitHub Actions secrets rather than Key Vault, login is this repo's
credential store rather than Entra ID, and the audit store is container-local rather than
Blob WORM. Recording those gaps in the pipeline that ships the system is deliberate — a
deploy workflow that implies its ADR is fully realized is how a documented control becomes
an assumed one.

`nightly-redteam.yml` — the live prompt-injection suite against a real model, nightly,
opening an issue on failure with the two distinct causes spelled out (structural
regression vs guard-coverage gap).

**Supporting artifacts added:** `requirements.txt` / `requirements-dev.txt` (pinned, must
agree with `sbom.json`), `deploy/containers/Dockerfile.api` and `.web`, `.dockerignore`,
`ruff.toml`, and `pytest.ini` — the last because a bare `pytest` collected the gitignored
V2 reference tree locally and failed, while CI (where that tree is absent) passed on the
same commit.

**Not verified here:** the container images have not been built — Docker was unavailable in
the environment this stage was built in. CI's `containers` job is the first thing that will
exercise them.

### Live HITL escalation notifications (`services/integration/hitl_escalation_watch.py`, `services/integration/notifier.py`)

Closes a gap `hitl_timer.py` and `docs/governance/hitl_control_model.md` §8 had stated
plainly since Stage 22: severity was computed and displayed, but "only visible to someone
who opens the app and looks" — no scheduler, no notification channel.

**What was requested and what was actually possible.** The ask was "wire this to Gmail
MCP." No Gmail MCP was reachable in this session (empty `mcp.json` at both project and
user level, no matching tool via `ToolSearch`) — but the harder constraint surfaced first
and would have applied even with one configured: an MCP tool is part of Claude's own
tool-calling loop, reachable from an interactive session, **not** from a running FastAPI
process making its own decisions between requests. "Live" ruled the approach out before
"which mail API" was even a question. Surfaced to the user directly rather than building
around it silently; the chosen alternative (real SMTP) was their explicit choice among
three options offered.

**Design.**
- `services/integration/hitl_escalation_watch.py::scan_once()` — one pass over the
  pending queue. For each entry, computes `hitl_timer.compute()` (unchanged, still
  display-only) and, the first time a run crosses severity 3 (T2) or 4 (T3), writes an
  audit record and attempts an email. Idempotency is keyed against the audit store itself
  (`audit_store.has_hitl_escalation`, a new read helper) rather than an in-memory set, so
  a run already notified at T2 stays notified across an API process restart — the same
  posture `has_recorded_action`/`has_veto` already take toward "did this already happen."
- **The audit write happens before the email attempt, and never depends on it
  succeeding.** ADR-007's posture (`response_cache.py`'s Redis-absent handling) applied
  to a new dependency: a run reaching severity 4 must be recorded and shown in the app
  whether or not SMTP is configured or reachable right now.
- `services/integration/notifier.py::send_email()` — one interface, same pattern as
  `redis_client.py`/`llm_client.py`: raises `EmailNotConfigured` (never silently
  swallowed) so the caller decides what "not configured yet" means for it. Gmail SMTP via
  App Password (`SMTP_HOST=smtp.gmail.com:587`, STARTTLS; port 465/SMTP_SSL also
  supported) — a regular account password does not work once 2-Step Verification is on,
  a Google account-security requirement, not a choice made here.
- **A real scheduler, added for the first time.** `services/api/main.py` gained a
  `lifespan` context manager (this repo's first) running an `asyncio` background task on
  a `HITL_NOTIFIER_POLL_SECONDS`-second interval (default 60), synchronous sqlite work
  offloaded via `asyncio.to_thread` so it never blocks request handling. Confirmed a bare
  `TestClient(app)` (the pattern every existing test file already uses) does **not**
  trigger FastAPI lifespan in the installed Starlette version — verified empirically
  before relying on it — so adding this touches zero existing tests.
- `GET /api/notifications` — the bell's read source. `subject_id`/`approver_roles` are
  best-effort, resolved from the in-memory pending queue at read time; `null` rather than
  guessed for a run that has since been decided or that predates the current process,
  same honesty pattern `RunDetail.decision_support_unavailable_reason` already uses.
- **Web:** `NotificationBell` in `AppShell` (both the desktop sidebar and the mobile
  header) — polls every 20s, badge count is "escalations newer than this browser last
  opened the bell." Stated as an explicit, accepted simplification: there is no per-user
  server-side read state (ten shared demo accounts, no user-scoped notification table),
  so "unread" is necessarily browser-local (localStorage), the same category of
  simplification `pending_queue.py`'s own docstring already accepts for its state.

**What this does NOT close, restated the same way §8 states its own boundary:**
`hitl_route.resolve_tier`'s approver-widening state machine is still unwired; crossing a
notified threshold authorizes no one new. This module only makes an already-true fact
(a run has been waiting a long time) visible to a human who was not already looking at
the screen.

**Verified live**, not only in tests: a real pending entry backdated past each
workflow's ladder, scanned, confirmed to fire exactly once and never again on repeat
scans, `GET /api/notifications` read back over HTTP with correct enrichment (and correct
`null` enrichment once the pending entry was removed, simulating a decided run). 13 new
backend tests for the watcher, 9 for the notifier (fake SMTP transport, no real network
dependency), 4 for the endpoint, 9 for the bell (including a from-scratch jsdom
`localStorage` polyfill, since this project's jsdom has none configured — discovered via
a failing test, not assumed).

## 6o. Chaos Drill — ADR-007 lab injectors (`/chaos-drill`)

Hybrid moonshot: CISO/DPO runs named fail-closed injectors from the Control Center
(LLM outage, Redis bypass, Neo4j unavailable, HITL timeout, policy fail-closed) without
taking down shared infra. Graph DI on `build_graph` only; `DRILL-` run ids excluded from
Run History; results in `chaos_drill_run`. See `docs/chaos/moonshot_plan.md` and
`ops/chaos/README.md`.

## 7. Tech stack (ADR-001 + ADR-009 Azure)

| Concern | Choice |
|---|---|
| Orchestration | **LangGraph** on **Azure Container Apps** (AKS if scale demands) |
| LLM inference | **CONFIRMED — Route A: Claude via Azure AI Foundry.** Dev/20a calls the Anthropic API directly (one client interface, `packages/config/llm_client.py`); Foundry is the deployment-time binding behind the same interface. **20a's actual runs used Groq (dev-only, provisional) at user's direction while the Anthropic key was being sorted** — Route A itself is unchanged and still the only provider whose results count toward the real exit criteria. Verify region availability at implementation time |
| Cache | **Azure Cache for Redis** |
| Observability | **LangSmith** + **Azure Monitor/App Insights**; **OpenTelemetry** as the instrumentation layer so the backend stays swappable |
| Audit/evidence store | **Azure Blob Storage with immutability (WORM)** + optional Azure SQL for queryable metadata |
| Secrets | **Azure Key Vault** |
| Identity / approver authorization | **Microsoft Entra ID** — approver roles become Entra groups, making "current authorization at execution time" enforceable infra; Supply's dual approval = membership in two groups |
| Orchestrator API | **FastAPI** (`services/api/main.py`) — the C4 "Orchestrator API" container, filled in for real (6m). Wraps the LangGraph engine over HTTP, not itself a design change |
| Approver UI | **Next.js 16 (App Router, TypeScript) + Tailwind** (`apps/web`) — no charting library; observability renders as real stat cards/tables, not synthetic visuals |
| Knowledge graph | **Neo4j** (AuraDB this session) — added at user request during Stage 20a; **no ADR selected this**, Stage 13 specifies the ontology, not a storage engine. Known risk, see §9 |

**Guardrail:** no Azure-specific API may leak into domain or agent logic — platform bindings
live in `packages/config` and `infra/`.

### Azure is the DEPLOYMENT target, not a DEVELOPMENT requirement
**Only LLM inference needs cloud.** LangGraph is a library; Redis runs in Docker; audit store
can be local Postgres/SQLite; OTel can point at a local collector; Entra ID/Key Vault are
stubbable. **Develop locally (Docker Compose + one API key), deploy to Azure.** The whole
interim state — including all 7 assumption tests — runs on a laptop, with no Azure spend
until deployment. Stage 20 must not treat Azure as a prerequisite for writing/testing code.

---

## 8. Open items

| ID | Item | Blocks |
|---|---|---|
| NAB-2 | `plans/active/` empty while method doc says specs go there. Recommended fix: **correct the method doc** (prompts already are the spec; duplicating violates "nothing written twice") | Doc accuracy only |
| NAB-3 | Copy V1's `knowledge/` (32 docs) + `evaluation/` fixtures locally, or keep as cross-repo reference? — **half-resolved**: `knowledge/` copied and SHA-256 verified (Stage 13), now also live-ingested into Neo4j (Stage 20a). `data/`/`evaluation/` fixtures still cross-repo | Stage 20b |
| **NAB-4 (partial)** | `eval-ai-cache/`'s OpenTelemetry Brownfield Runbook (`eval-ai-cache/*OpenTelemetry Brownfield Implementation Runbook.docx`) was **never actually cited or consumed** by Stage 17's `packages/observability/` docs, despite the stage's own prompt saying it should draw on it. Stages 14/15 did consume their respective parts of `eval-ai-cache/`; Stage 17 did not | Should be revisited before Stage 20b's real dashboards/alerting are built |
| **P-07/P-09 closed, P-08 still open** | HITL timeout (P-07) and PV veto (P-09) now both have real evidence against a live graph (`test_assumption_3`, `test_veto_forces_rejected_and_is_never_overridden`, Stage 20b). Escalation (P-08, E1–E5 conditions) is still untested — never actually triggered, since no real HITL clock is wired for any workflow (durations are config values the graph doesn't yet enforce against wall-clock time) | Needs real clock wiring, not scoped to any stage yet |
| **20a/20b results provisional** | Interim-assumption results (`interim_state_results.md`) and everything run through the app (6m) were run under Groq (dev-only), not Claude. Token-economics numbers are real but not the Route A numbers | Must re-run under `LLM_PROVIDER=anthropic` before Gate M can evaluate real evidence |
| Stale checkpointer warning | LangGraph's `MemorySaver` deserializes our custom pydantic types (`EvidenceItem`, `BatchPayload`, etc.) via an unregistered-type fallback that "will be blocked in a future version" | Register `allowed_msgpack_modules` or add custom serializers before upgrading LangGraph |
| **No dependency supply-chain control** | Zero lockfile/version pinning/SBOM for any Python package, **now also true of `apps/web`'s npm dependencies** (a real `package-lock.json` exists there, but nothing enforces it's checked/audited) | Should close before any real deployment |
| **Guard evadable by paraphrase** | `prohibited_action_guard.py` matches literal banned terms/phrases — a model complying with an injection without using any listed term wouldn't be caught (Stage 18, T-01 residual risk) | Needs a design decision (semantic check vs. expanded phrase list) before it's closed, not a quick patch |
| **No approver-justification capture (G-10)** | Neither the 20a/20b placeholder nor the app's (6m) `DecisionButtons` UI collects a real justification string for an approve/reject/veto — `HumanOverrideRecorded.justification` is still a hardcoded placeholder | A real approver-input form field, not built yet |
| **App has no auth** | `apps/web` has no login — requester role is a free-text field. Entra ID is the real ADR-009 target | Before any real deployment, not a demo-scope concern |

**Closed:** EAB-2 (air-gap → cloud-connected confirmed), EAB-3 (approvers named), NAB-1,
**ADR-009's LLM route** (confirmed Route A), **S09-D1** (ADR-009 now listed in both
`decision_index.md` and `architecture_review.md`, "9 ADRs" not "8").

---

## 9. Known risks carried forward

1. **Single-workflow generalization** — Batch Review's shape may not transfer to PV's
   duplicate/clock semantics or Supply's option ranking. Each interim conclusion must be
   **re-checked per workflow**, not assumed to transfer (Stage 20 acceptance condition).
2. **Shared blast radius** — one deployment serves all three graphs (ADR-008, accepted).
3. **Vendor concentration** — now Microsoft *and* the model provider. V1's own source-system
   pack flags "bundled vendor, weak cost controls" as a known org failure pattern.
4. **Cache staleness under supersession** — a cache hit must never serve an answer built on
   since-superseded evidence (ADR-003 guardrail; Stage 14 cache-correctness evals).
5. **Neo4j added without an ADR.** Stage 20a's semantic-layer implementation uses Neo4j
   (AuraDB) at user request — no prior ADR selected a graph database technology; Stage 13's
   `kg_schema.md` specifies the ontology, not a storage engine. Widens the vendor-concentration
   risk in item 3 by one more provider. Should get a real ADR before Stage 20b if the choice is
   meant to persist past this interim slice.
6. **Provisional-provider results in the repo.** `interim_state_results.md`'s numbers were
   measured under Groq, not Claude — a reader skimming only the pass/fail table without the
   provisional caveat could mistake them for Route A evidence.

---

## 10. Working style established in this project

- Ground claims in **evidence with file paths**; classify fact / derivation / assumption / question.
- Mark artifact status honestly (`provisional` vs `stable`) rather than overclaiming.
- **Flag disagreements and errors openly** — the ADR-003 correction is the precedent.
- Record known limitations rather than papering over them (e.g. ADR-007's air-gap note).
- Don't add scope without a stated requirement (V1 workflows D/E were explicitly rejected).
