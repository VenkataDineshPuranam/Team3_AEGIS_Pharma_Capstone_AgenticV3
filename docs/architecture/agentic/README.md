# agentic

Stage 10 — the multi-agent design: which agents exist, the graph they run in, what persists,
and what stops a runaway loop.

| Document | Answers |
|---|---|
| [agent_roster.md](agent_roster.md) | Which agents exist, their authority limits, why there is **no planner agent**, and what is shared across the three workflows |
| [**aegis_agents.html**](aegis_agents.html) | Interactive diagram: orchestrator dispatch (FastAPI `_get_graph`), roster, six peer graphs, shared 14-node spine, and HITL map. This page matches the six `*_graph.py` modules (14 `add_node` calls). The markdown below still says 3 graphs / 11 nodes — trust the HTML + code. |
| [langgraph_design.md](langgraph_design.md) | Nodes, edges, the shared state schema (including what it deliberately cannot express), checkpointing, and every HITL interrupt |
| [memory_design.md](memory_design.md) | What persists across turns — and why there is **no long-term agent memory** |
| [failure_and_loop_guards.md](failure_and_loop_guards.md) | Numeric caps, ceilings, the no-blind-retry rule, the four-tier HITL escalation ladder, and the failure taxonomy |
| [dmaic_lens.md](dmaic_lens.md) | What this design removes vs. what it costs (thin lens) |

**Status:** `stable` for the `batch_review` graph — the interim slice (20a). **`provisional`**
for `pv_intake` and `supply_planning`, which are designed by analogy and must be re-checked
rather than assumed to transfer (RR-2 / trigger T-10).

**Two LLM nodes out of eleven.** Every control in this design is deterministic — a schema, a
status lookup, a pattern match, or an edge condition. No control is implemented by a model.
