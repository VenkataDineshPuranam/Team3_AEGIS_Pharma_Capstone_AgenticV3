# Decision Index — Stage 04 (ADR)

| ADR | Title | Status | DDD context | C4 element | Evidence basis | Blocked on backlog? |
|---|---|---|---|---|---|---|
| [001](ADR-001-runtime-stack.md) | Runtime stack: LangGraph, LangSmith, Redis | `accepted` | Agent Orchestration (generic) | Orchestrator API, Redis Cache, LangSmith | Fact (sponsor directive) | No |
| [002](ADR-002-build-v2-separate-from-v1.md) | V2 built separately from V1 | `accepted` | All | Whole system | Fact (user decision) + verified V1 constraints | No |
| [003](ADR-003-evidence-authority-deterministic-gate.md) | Evidence authority is a deterministic gate; `untrusted` **and** `superseded` non-citable | `accepted` | Evidence & Provenance | Evidence Retrieval tool, Semantic Layer | **Fact — verified against V1 grader code** | No |
| [004](ADR-004-prohibited-actions-structurally-unrepresentable.md) | Prohibited actions structurally unrepresentable | `accepted` | All three core contexts + Governance | Aggregate schemas, MCP tools, Prohibited-Action Guard | Fact (V1 case pack) + derivation | No |
| [005](ADR-005-governance-as-separate-container.md) | Governance/Policy Engine as separate container | `accepted` | Governance & Oversight | Governance/Policy Engine container | Derivation | No |
| [006](ADR-006-audit-store-separate-from-langsmith.md) | Audit store separate from LangSmith | `accepted` | Governance & Oversight (audit) | Audit/Evidence Log Store | Derivation | No |
| [007](ADR-007-degraded-mode-safe-not-offline-capable.md) | Degraded-mode-safe, not offline-capable | `accepted` | Cross-cutting | All hosted dependencies | Fact (incl. sponsor decision on EAB-2) | No — closed |
| [008](ADR-008-one-graph-per-workflow-single-deployment.md) | One deployment, one graph per workflow | `accepted` | All three core contexts | Orchestrator API | Derivation | No |
| [009](ADR-009-azure-platform.md) | Azure is the target cloud platform | `accepted`, fully — LLM-hosting route confirmed **Route A** (Claude via Azure AI Foundry) | Cross-cutting | All hosted containers (Container Apps, Redis, Blob Storage, Key Vault, Entra ID) | Fact (sponsor directive; route confirmed by user ahead of Stage 20a) | No |
| [010](ADR-010-human-precedent-as-evidence.md) | A prior HITL rejection is retrievable only as a citable `EvidenceItem` (Shadow QP), never as agent memory | `accepted` | Batch Review only (EU Qualified Person) | `precedent.retrieve` tool, `graph.py`'s `hitl_interrupt`, Neo4j `EvidenceItem` | Reasoned extension of `memory_design.md` §2's own revisit trigger | No |

## Status summary

- **9 of 9 `accepted`**, no open sub-decisions. ADRs 005/006/008 were upgraded when
  **EAB-3 closed** (DDD reached `stable`); ADR-007 was upgraded when **EAB-2 closed** (sponsor
  confirmed cloud-connected operation); ADR-009's LLM-hosting route was confirmed **Route A**
  ahead of Stage 20a. No ADR rests on an unconfirmed assumption. Trigger **T-6**
  (`dmaic_plan.md`) remains live as a *revisit* condition — if the route ever changes to Route
  B, Stage 14's eval baselines must be re-run — but the route itself is no longer open.

## Blocked on evidence acquisition backlog

**None.** Both blockers are closed:
- ~~EAB-2 (air-gap requirement)~~ — **closed**; sponsor confirmed cloud-connected operation
  is acceptable. The air-gapped production variant is recorded as a known limitation in
  ADR-007 rather than silently dropped.
- ~~EAB-3 (real HITL/context owners)~~ — **closed**; roles taken verbatim from V1's
  `case/STAKEHOLDER_PACK.md`.

## Carried forward from `c4/adr_candidates.md` but not yet an ADR

| Candidate | Why deferred |
|---|---|
| MCP tool authentication/authorization mechanism | Needs Stage 11 (MCP) input before a decision is meaningful |
| Redis cache topology + semantic-cache embedding model | Needs Stage 15 measurement first; deciding now would be guessing |
| Verify rules-vs-AI boundary against V1 graders | **Done this stage** — became ADR-003, and corrected the DDD model |
