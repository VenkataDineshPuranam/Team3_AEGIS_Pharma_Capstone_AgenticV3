# Memory Design — Stage 10

**Executes:** `prompts/14_agentic_architecture.md` §4
**Artifact status:** `stable` for 20a

The prompt asks what persists across turns and what must never persist. The short version:
**within a run, the graph state is the only memory; across runs, the agents have none.**

---

## 1. The four memory tiers, and which ones exist

| Tier | Exists? | Lifetime | Agent-readable? |
|---|---|---|---|
| **Working memory** — `GovernedState` | **Yes** | One run | Yes — it is the only thing a node reads (BC-9) |
| **Run-resumable memory** — checkpointer | **Yes** | Until the run reaches a terminal state, plus retention | Indirectly, on resume |
| **Long-term agent memory** — cross-run recall | **No — deliberately absent.** See §2 | — | — |
| **Institutional memory** — audit store, semantic layer/KG | **Yes**, but it is **not agent memory** | Retention policy (Stage 19) | Audit: no, write-only from the graph. Semantic layer: only through `evidence.retrieve`, as evidence |

## 2. Why there is no long-term agent memory

This is the one substantive memory decision, so it gets a reason rather than an assertion.

An agent that remembers a conclusion from a previous run would create three failures the
programme has already ruled out:

1. **An uncitable evidence path.** Every claim must trace to an `EvidenceItem` with a source
   and an authority status. "I concluded this last week" has no status, no effective date, and
   no supersession pointer — it is an assertion the provenance model cannot represent.
2. **A supersession hazard.** Remembered conclusions do not get superseded when their
   underlying documents do. This is the ADR-003 guardrail arriving through a side door: the
   register's stale-inventory row (D5/I1) is about the cache, and agent memory would be a
   second, unaudited cache with no key and no invalidation.
3. **Cross-run authority accumulation.** Memory of "the QP approved a similar case" is one
   short step from treating that as precedent — a system inferring its own authority from past
   human approvals. Nothing in ADR-004 blocks that, because it never had to.

**Cost of the choice, stated:** every run starts cold, so identical requests re-retrieve and
re-reason. That is Token waste, and it is the specific waste the Redis cache is meant to
address at 20b — as a **keyed, status-aware, invalidatable** cache rather than as agent recall.
Caching a *response* under a key that includes evidence status is auditable; an agent
remembering something is not.

**Revisit trigger:** if Stage 15 shows repeat-request cost is material, the answer is cache
tuning (ADR-003 guardrail applies), **not** introducing agent memory. Reopening this would
require an ADR.

**Reopened, narrowly:** [`ADR-010`](../../adr/ADR-010-human-precedent-as-evidence.md)
(Shadow QP) does exactly what this section's revisit trigger asked for — an ADR, not a
code change reached first. It does not contradict the three failures above; it closes each
one by construction rather than accepting them: a prior rejection becomes retrievable only
as an `EvidenceItem` (closes #1, uncitable path), append-only in the same supersession
model ADR-003 already governs (closes #2), and minted **only** on `action=rejected` — an
approval can never become "the QP approved a similar case" because it is never written
(closes #3, cross-run authority accumulation). Scope: `batch_review` / EU Qualified Person
only.

## 3. What persists, precisely

| Item | Tier | Persisted | Note |
|---|---|---|---|
| `evidence[]` with statuses as retrieved | working + checkpoint | Yes | Reproducibility of the citation trail |
| Budget counters | working + checkpoint | Yes | Otherwise a restart resets the caps |
| `policy_contract_version` | working + checkpoint | Yes | The run is judged against the policy in force at start |
| `draft_output` (guard-clear) | working + checkpoint | Yes | Needed to resume a pending approval |
| `critic_reason_codes[]` | working + checkpoint | Yes, append-only | Drives no-progress detection |
| `AgentRun` record | audit store | **Yes, immutable** | WORM in deployment. The compliance artifact |
| `HumanOverrideRecorded` | audit store | Yes | Every HITL decision, approve **or** reject |
| `ProhibitedActionBlocked` | audit store | Yes | Includes a classification and a hash of the blocked draft — not the draft |
| Traces | LangSmith + audit store | Yes, **after redaction** | BC-8: redaction rules exist before the first trace |

## 4. What must never persist

| Never persisted | Where it would otherwise leak | Handling |
|---|---|---|
| **The text of a draft the guard blocked** | Checkpoint, trace, audit record | Quarantine: record the reason code, the matched prohibition class, and a SHA-256 of the draft. **The prohibited text itself is discarded.** A stored draft batch-release recommendation is a document that should not exist in a GxP system, and its existence in a trace would be discoverable as though the system had made the recommendation |
| Unredacted PII/PHI | Traces (hosted), audit store | Redaction before write, both sinks (`boundary_and_degraded_mode.md`). Stage 17 owns the rules; this design guarantees there is exactly one write path per sink to apply them at |
| Approver personal identity | Audit record, notifications | **Role + role-assignment ID only.** Accountability attaches to the role (`hitl_control_model.md` §1) |
| Credentials, tokens, connection strings | Anywhere in state | Key Vault in deployment; env-injected locally. Never a state field — there is no field for them |
| Raw prompt/response bodies | Checkpoint | Traces only, redacted. Keeps resumable state small and keeps one redaction path, not two |
| Cross-workflow evidence | State, cache | Structurally impossible: retrieval is context-scoped and there is no cross-graph path (ADR-008) |

## 5. Retention — deferred, with the boundary named

Retention **durations** are a Stage 19 decision and genuinely contested: the DPO's
minimization interest and the Chief Quality Officer's GxP-preservation interest point opposite
ways, and `hitl_control_model.md` §5 says explicitly that this must be agreed by both rather
than "chosen by engineering default." This design therefore fixes the *structure* and leaves
the *durations* open:

- Audit records: immutable, WORM, retention ≥ the GxP requirement — **duration open**.
- Traces: redacted, retention set independently of audit — **duration open**, and shorter is
  the expected answer.
- Checkpoints: deleted after terminal state + a short resumption window — **window open**.

Recording it this way means Stage 19 inherits a decision to make, not a default to discover.
