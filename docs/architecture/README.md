# architecture

C4 model, DDD bounded contexts, agentic architecture (LangGraph), ontology/semantic layer.

- [High-level C4 diagram](high-level/aegis_high_level.html) — people, one software system, containers (Control Center, Orchestrator + six graphs, in-process tools, data plane), brownfield (read-only), LLM / LangSmith, ADR-009 Azure targets. Open the HTML in a browser.
- [Agents and flow](agentic/aegis_agents.html) — orchestrator dispatch, roster (six domain agents + Critic), shared LangGraph spine, fail-closed branches, HITL map. Open the HTML in a browser.
- [Low-level Azure-style diagram](low-level/aegis_low_level.html) — nested subscription / VNet / subnet view of the same running repo. Open the HTML in a browser.
