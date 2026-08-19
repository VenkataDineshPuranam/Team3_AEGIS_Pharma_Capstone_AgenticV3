# Low-level architecture

Open [`aegis_low_level.html`](aegis_low_level.html) in a browser (needs the `icons/used/` files next to it). For C4 context + containers of the same system, see the [high-level diagram](../high-level/aegis_high_level.html). For the six agents and the shared graph spine, see [agents and flow](../agentic/aegis_agents.html).

Visio-style nested drawing (subscription → VNet → subnet) with **explicit arrows**:
- thick black = HTTPS / ingest / Internet
- grey double-headed = virtual network peering
- thin black = NIC → orchestrator traffic (Trust / Untrust / HITL / Management, same pattern as a hub VM)
- red = chaos inject and fail-closed branches
- purple = LLM egress

| Layer | What it shows |
|---|---|
| Named operators | HITL roles from `user_store.ROLE_CATALOG` |
| Control Center | Next.js pages in `apps/web` |
| Orchestrator hub | FastAPI + six LangGraphs + governance + chaos lab |
| Integration spoke | In-process tools (`services/integration`) |
| Data plane | Neo4j, Redis, SQLite audit |
| Azure platform | ADR-009 target bindings (Foundry, Entra, Key Vault, Blob WORM) |
| Brownfield | Read-only evidence sources — no write path |

Click a tile for the repo path and fail-closed behaviour. Toggle **Local compose**, **Azure target**, and **Chaos injectors**.
