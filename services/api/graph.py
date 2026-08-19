"""batch_review LangGraph -- Stage 20a Phase 4. Direct transcription of
docs/architecture/agentic/langgraph_design.md SS1-2's mermaid diagram and edge table.
11 nodes, 2 of them LLM (pluggable via `llm`, defaults to StubLLM -- see nodes/llm_interface.py).

Read the graph for what it refuses to do: there is no edge from `synthesize` to `finalize`.
Generated text cannot reach a caller without passing the guard, the Critic, the guard again,
and a human (langgraph_design.md SS1).
"""
from __future__ import annotations

from datetime import UTC, datetime

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from packages.domain import hitl_decision
from packages.domain.payloads import BatchPayload, ReconciliationFinding
from packages.domain.evidence import EvidenceItem
from packages.domain.state import GovernedState, ReasonCode, RETRYABLE_REASON_CODES
from infra.policies.denial_of_wallet_guardrail import DenialOfWalletGuard
from services.integration import audit_store, evidence_gate, hitl_route, prohibited_action_guard, response_cache
from services.integration.batch_reconcile import ToolError as ReconcileError, reconcile as tool_reconcile
from services.integration.evidence_retrieve import ToolError as RetrieveError, retrieve as tool_retrieve
from services.integration.policy_engine import PolicyEngineUnavailable, get_prohibition_contract
from services.integration.precedent_mint import finding_hash as precedent_finding_hash, mint_rejection
from services.integration.precedent_retrieve import ToolError as PrecedentRetrieveError, retrieve as tool_precedent_retrieve
from services.api.nodes.llm_interface import LLMNodes, StubLLM

POLICY_VERSION = "v1"
MAX_LLM_CALLS = 6  # G1, failure_and_loop_guards.md SS2


def build_graph(
    llm: LLMNodes | None = None,
    batch_id: str = "B-001",
    checkpointer=None,
    *,
    retrieve_fn=None,
    reconcile_fn=None,
    policy_fn=None,
    cache_get=None,
    cache_set=None,
    precedent_retrieve_fn=None,
    precedent_mint_fn=None,
):
    """Compile the batch_review graph.

    Optional callables (chaos drills / tests only) default to the production imports.
    Production `_get_graph` passes none of them. Cache overrides must mimic
    `response_cache`: return None / no-op on outage — never raise into synthesize.
    """
    llm = llm or StubLLM()
    do_retrieve = retrieve_fn or tool_retrieve
    do_reconcile = reconcile_fn or tool_reconcile
    do_policy = policy_fn or get_prohibition_contract
    do_cache_get = cache_get or response_cache.get
    do_cache_set = cache_set or response_cache.set_cleared
    do_precedent_retrieve = precedent_retrieve_fn or tool_precedent_retrieve
    do_precedent_mint = precedent_mint_fn or mint_rejection
    audit_conn = audit_store.get_connection()
    dow_guard = DenialOfWalletGuard()

    def intake(state: GovernedState) -> dict:
        # Stage 18 finding: this hook was documented in hooks.md as wired but was never
        # actually called from graph code. Fixed here. Uses requester_role as the ceiling
        # key (GovernedState has no separate caller-identity field in 20a's scope) --
        # a real deployment keys on the actual caller identity, not the approver role.
        admission = dow_guard.check_and_admit(
            user_id=state["requester_role"], workflow=state["workflow"], as_of=datetime.now(UTC).date()
        )
        if not admission["admit"]:
            return {
                "authorization_checked_at": datetime.now(UTC),
                "trace_id": f"TR-{state['run_id']}",
                "terminal_state": "refused",
                "abstention_reason": admission["reason"],
            }
        return {
            "authorization_checked_at": datetime.now(UTC),
            "trace_id": f"TR-{state['run_id']}",
        }

    def policy_load(state: GovernedState) -> dict:
        try:
            contract = do_policy(POLICY_VERSION, state["workflow"])
        except PolicyEngineUnavailable:
            return {"policy_contract_version": None, "terminal_state": "refused", "abstention_reason": "fail_closed"}
        return {"policy_contract_version": POLICY_VERSION, "prohibition_contract": contract}

    def retrieve(state: GovernedState) -> dict:
        try:
            result = do_retrieve(
                run_id=state["run_id"],
                terms=["BATCH_RELEASE", "policy"],
                policy_contract_version=state["policy_contract_version"],
                broadening=state["broadenings_used"] > 0,
            )
        except RetrieveError:
            return {"terminal_state": "abstained", "abstention_reason": "dependency_unavailable"}
        items = [EvidenceItem(**item) for item in result["items"]]
        return {
            "evidence": state["evidence"] + items,
            "tool_calls": state["tool_calls"] + 1,
        }

    def evidence_gate_node(state: GovernedState) -> dict:
        result = evidence_gate.check(state["evidence"], state["broadenings_used"])
        if result.outcome == "broaden":
            return {"broadenings_used": state["broadenings_used"] + 1}
        if result.outcome == "abstain":
            return {"terminal_state": "abstained", "abstention_reason": result.reason}
        if result.outcome == "defect_halt":
            return {"terminal_state": "refused", "abstention_reason": "gate_defect"}
        return {"evidence_sufficient": True}

    def reconcile(state: GovernedState) -> dict:
        evidence_ids = [e.evidence_id for e in state["evidence"]]
        try:
            result = do_reconcile(
                run_id=state["run_id"], batch_id=batch_id,
                evidence_ids=evidence_ids, policy_contract_version=state["policy_contract_version"],
            )
        except ReconcileError:
            return {"terminal_state": "abstained", "abstention_reason": "dependency_unavailable"}
        findings = tuple(ReconciliationFinding(**f) for f in result["findings"])
        payload = BatchPayload(batch_id=batch_id, reconciliation_complete=result["reconciliation_complete"], findings=findings)
        return {"domain_payload": payload, "tool_calls": state["tool_calls"] + 1}

    def precedent_retrieve_node(state: GovernedState) -> dict:
        """ADR-010: retrieves prior HITL rejections of a similar finding shape as citable
        evidence. Never blocks the run -- STORE_UNAVAILABLE or an empty result leaves
        `evidence` unchanged (a missing precedent is not proof none exists)."""
        payload = state["domain_payload"]
        gaps = [f for f in payload.findings if f.status in ("gap", "conflict")]
        if not gaps:
            return {}
        finding_hash = precedent_finding_hash(payload.findings)
        try:
            result = do_precedent_retrieve(
                run_id=state["run_id"],
                finding_categories=sorted({f.category for f in gaps}),
                finding_hash=finding_hash,
                policy_contract_version=state["policy_contract_version"],
            )
        except PrecedentRetrieveError:
            return {}
        items = [EvidenceItem(**item) for item in result["items"]]
        if not items:
            return {}
        return {"evidence": state["evidence"] + items, "tool_calls": state["tool_calls"] + 1}

    def synthesize(state: GovernedState) -> dict:
        # Cache lookup, per redis_tuning.md SS2's pipeline placement: only a prior
        # guard-and-Critic-cleared response can be a hit (set_cleared is only ever called
        # from guard2's "clear" path below). Stale-evidence check happens inside
        # response_cache.get itself (the ADR-003 correctness scenario), not here.
        evidence_ids = [e.evidence_id for e in state["evidence"]]
        cached = do_cache_get(state["workflow"], batch_id, evidence_ids)
        if cached is not None:
            return {"draft_output": cached}  # zero llm_calls/tokens -- the whole point of a hit
        try:
            draft, tin, tout = llm.synthesize(state)
        except Exception:  # noqa: BLE001 -- ADR-007: LLM provider unreachable -> abstain,
            # never guess. The deterministic partial result (domain_payload, already
            # computed by `reconcile`) is attached via `domain_payload` staying in state --
            # failure_and_loop_guards.md SS6 "the rules-only path still produces auditable
            # findings" is satisfied by that field surviving into the AgentRun record.
            return {"terminal_state": "abstained", "abstention_reason": "degraded_mode"}
        return {
            "draft_output": draft,
            "llm_calls": state["llm_calls"] + 1,
            "tokens_in": state["tokens_in"] + tin,
            "tokens_out": state["tokens_out"] + tout,
        }

    def guard(state: GovernedState) -> dict:
        result = prohibited_action_guard.check(state["draft_output"], state["prohibition_contract"])
        if result.verdict == "blocked":
            # ProhibitedActionBlocked recorded via agent_run's terminal_state="blocked" --
            # written ONCE, by finalize (below), not here too. A second write_agent_run
            # call here previously crashed with IntegrityError (agent_run.run_id is a
            # PRIMARY KEY) the first time this path was ever actually exercised by a real
            # guard block, this session (Stage 20b) -- every guard-block test before now
            # had used a model that happened not to trigger it, or a cache hit that
            # bypassed synthesize entirely.
            return {"guard_verdict": "blocked", "terminal_state": "blocked", "abstention_reason": "prohibited_action"}
        return {"guard_verdict": "clear"}

    def guard2_with_cache_write(state: GovernedState) -> dict:
        """guard2 is the ONLY point that writes to the cache -- redis_tuning.md SS2's
        pipeline: '...Security/guardrail check -> Successful response -> CACHE'. guard1
        runs on a freshly-generated draft (never cached); guard2 runs on whatever the
        Critic approved, whether it came from a real LLM call or a cache hit -- writing
        here, not in guard1, means a cache hit is re-validated by the guard exactly once
        more before being written back, same as any other draft."""
        result = guard(state)
        if result.get("guard_verdict") == "clear":
            evidence_ids = [e.evidence_id for e in state["evidence"]]
            do_cache_set(state["workflow"], batch_id, evidence_ids, state["draft_output"])
        return result

    def critic_verify(state: GovernedState) -> dict:
        try:
            verdict, reason_code, tin, tout = llm.critic(state)
        except Exception:  # noqa: BLE001 -- same ADR-007 rule as synthesize
            return {"terminal_state": "abstained", "abstention_reason": "degraded_mode"}
        updates: dict = {
            "critic_verdict": verdict,
            "llm_calls": state["llm_calls"] + 1,
            "tokens_in": state["tokens_in"] + tin,
            "tokens_out": state["tokens_out"] + tout,
        }
        if reason_code is not None:
            updates["critic_reason_codes"] = state["critic_reason_codes"] + [reason_code]
        return updates

    def hitl_route_node(state: GovernedState) -> dict:
        return {
            "hitl_required": True,
            "approver_roles": [hitl_route.PRIMARY_APPROVER],
            "hitl_status": "pending",
            "hitl_tier": "T0",
        }

    def hitl_interrupt(state: GovernedState) -> dict:
        decision = hitl_decision.decode(interrupt(
            {"approver_roles": state["approver_roles"], "run_id": state["run_id"], "batch_id": batch_id}
        ))
        # BC-12: timeout => no action, EVER. Set explicitly here, not left to finalize's
        # fallback -- that fallback is exactly what silently mislabeled a timeout as
        # "completed" before this fix (interim assumption 3's own failure mode).
        if decision.action == "timed_out":
            audit_store.write_hitl_expired(
                audit_conn, state["run_id"], state["workflow"],
                eligible_roles_at_expiry=state["approver_roles"], recorded_at=datetime.now(UTC).isoformat(),
            )
            return {"hitl_status": "timed_out", "terminal_state": "abstained", "abstention_reason": "hitl_timeout"}
        # Stage 19 finding, fixed: this write was previously never made -- HumanOverrideRecorded
        # existed as a schema and unit tests (escalation_override_log_design.md), but the
        # running graph only ever set hitl_status in state, never wrote the audit record.
        # Stage 21: `justification` is now what the approver actually typed (see
        # packages/domain/hitl_decision.py) rather than the 20a placeholder constant. The
        # role written is still the governance layer's own eligible approver, NOT anything
        # the caller claimed -- a caller-supplied identity cannot rewrite who the record
        # says was accountable.
        audit_store.write_human_override(
            audit_conn, state["run_id"], role=state["approver_roles"][0], tier_at_action=state.get("hitl_tier") or "T0",
            action=decision.action, justification=decision.justification,
            recorded_at=datetime.now(UTC).isoformat(),
        )
        # ADR-010: best-effort, AFTER the audit write above -- a Neo4j failure here must
        # never undo or block the human decision that was just committed.
        if decision.action == "rejected":
            do_precedent_mint(
                state["run_id"], state["workflow"], state.get("domain_payload"), decision.justification,
            )
        return {"hitl_status": decision.action, "terminal_state": "completed"}

    def mark_blocked_prohibition_adjacent(state: GovernedState) -> dict:
        """critic_verify's PROHIBITION_ADJACENT route bypasses guard2 entirely (never
        retried, failure_and_loop_guards.md SS4) -- this node is what actually sets
        terminal_state on that path, since route_after_critic is a pure router and
        cannot mutate state itself."""
        return {"guard_verdict": "blocked", "terminal_state": "blocked", "abstention_reason": "prohibition_adjacent"}

    def mark_abstained_cap_exceeded(state: GovernedState) -> dict:
        """G1 (max 6 LLM calls) hit -- failure_and_loop_guards.md SS6:
        abstained/cap_exceeded, alerted as an engineering defect (SEV-3, alerting.md)."""
        return {"terminal_state": "abstained", "abstention_reason": "cap_exceeded"}

    def finalize(state: GovernedState) -> dict:
        terminal = state.get("terminal_state") or "completed"
        # Real token usage feeds the ceiling forward -- also never wired before this stage.
        if terminal != "refused":  # a refused-at-intake run consumed no tokens
            dow_guard.record_run(
                user_id=state["requester_role"], workflow=state["workflow"],
                as_of=datetime.now(UTC).date(), actual_tokens=state["tokens_in"] + state["tokens_out"],
            )
        audit_record_id = f"AR-{state['run_id']}"
        audit_store.write_agent_run(
            audit_conn, state["run_id"], state["workflow"], terminal,
            datetime.now(UTC).isoformat(), abstention_reason=state.get("abstention_reason"),
            trace_id=state["trace_id"], policy_contract_version=state.get("policy_contract_version"),
            llm_calls=state["llm_calls"], tokens_in=state["tokens_in"], tokens_out=state["tokens_out"],
            # Stage 21 -- run context, so a decided run stays investigable from the audit
            # store alone. Every value is read from state, never re-derived or defaulted.
            subject_id=batch_id, requester_role=state["requester_role"],
            approver_roles=state.get("approver_roles") or [], hitl_status=state.get("hitl_status"),
            evidence_ids=[e.evidence_id for e in state["evidence"]],
        )
        return {"terminal_state": terminal, "audit_record_id": audit_record_id}

    graph = StateGraph(GovernedState)
    graph.add_node("intake", intake)
    graph.add_node("policy_load", policy_load)
    graph.add_node("retrieve", retrieve)
    graph.add_node("evidence_gate", evidence_gate_node)
    graph.add_node("reconcile", reconcile)
    graph.add_node("precedent_retrieve", precedent_retrieve_node)
    graph.add_node("synthesize", synthesize)
    graph.add_node("guard1", guard)
    graph.add_node("guard2", guard2_with_cache_write)
    graph.add_node("critic_verify", critic_verify)
    graph.add_node("hitl_route", hitl_route_node)
    graph.add_node("hitl_interrupt", hitl_interrupt)
    graph.add_node("blocked_terminal", mark_blocked_prohibition_adjacent)
    graph.add_node("abstain_cap", mark_abstained_cap_exceeded)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("intake")
    graph.add_conditional_edges(
        "intake",
        lambda s: "refuse" if s.get("terminal_state") == "refused" else "policy_load",
        {"refuse": "finalize", "policy_load": "policy_load"},
    )

    graph.add_conditional_edges(
        "policy_load",
        lambda s: "refuse" if s.get("terminal_state") == "refused" else "retrieve",
        {"refuse": "finalize", "retrieve": "retrieve"},
    )
    graph.add_conditional_edges(
        "retrieve",
        lambda s: "abstain" if s.get("terminal_state") == "abstained" else "gate",
        {"abstain": "finalize", "gate": "evidence_gate"},
    )

    def route_after_gate(s: GovernedState) -> str:
        if s.get("terminal_state") in ("abstained", "refused"):
            return "terminal"
        if s.get("evidence_sufficient"):
            return "reconcile"
        return "retrieve"  # broadening

    graph.add_conditional_edges("evidence_gate", route_after_gate, {"terminal": "finalize", "reconcile": "reconcile", "retrieve": "retrieve"})
    graph.add_conditional_edges(
        "reconcile",
        lambda s: "abstain" if s.get("terminal_state") == "abstained" else "precedent",
        {"abstain": "finalize", "precedent": "precedent_retrieve"},
    )
    graph.add_edge("precedent_retrieve", "synthesize")
    graph.add_conditional_edges(
        "synthesize",
        lambda s: "degraded" if s.get("terminal_state") == "abstained" else "guard1",
        {"degraded": "finalize", "guard1": "guard1"},
    )
    graph.add_conditional_edges(
        "guard1", lambda s: "blocked" if s["guard_verdict"] == "blocked" else "critic",
        {"blocked": "finalize", "critic": "critic_verify"},
    )

    def route_after_critic(s: GovernedState) -> str:
        if s.get("terminal_state") == "abstained":  # degraded_mode -- llm.critic() raised
            return "degraded"
        if s["critic_verdict"] == "approve_for_human":
            return "guard2"
        codes = s["critic_reason_codes"]
        if not codes:
            # Defense-in-depth: a reject verdict with no reason code should never reach
            # here (packages/config/llm_client.py's parser now rejects that shape), but
            # this router must not crash if it ever does -- escalate to a human rather
            # than trust an assumption a second time (found live under Groq, this session).
            return "hitl_escalate"
        latest = codes[-1]
        # PROHIBITION_ADJACENT checked first, unconditionally -- never retried (the
        # earlier-session bug fix this graph must not reintroduce).
        if latest == ReasonCode.PROHIBITION_ADJACENT:
            return "blocked"
        if s["llm_calls"] >= MAX_LLM_CALLS:
            return "abstain"
        if codes.count(latest) > 1:
            return "hitl_escalate"  # repeated code -- escalate, don't retry
        if latest in RETRYABLE_REASON_CODES:
            return "synthesize"
        return "hitl_escalate"

    graph.add_conditional_edges(
        "critic_verify", route_after_critic,
        {
            "guard2": "guard2", "blocked": "blocked_terminal", "abstain": "abstain_cap",
            "hitl_escalate": "hitl_route", "synthesize": "synthesize", "degraded": "finalize",
        },
    )
    graph.add_edge("blocked_terminal", "finalize")
    graph.add_edge("abstain_cap", "finalize")
    graph.add_conditional_edges(
        "guard2", lambda s: "blocked" if s["guard_verdict"] == "blocked" else "hitl",
        {"blocked": "finalize", "hitl": "hitl_route"},
    )
    graph.add_edge("hitl_route", "hitl_interrupt")

    def route_after_hitl(s: GovernedState) -> str:
        status = s.get("hitl_status")
        if status == "timed_out":
            return "no_action"
        return "finalize"

    graph.add_conditional_edges("hitl_interrupt", route_after_hitl, {"no_action": "finalize", "finalize": "finalize"})
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=checkpointer or MemorySaver())
