# High-level architecture

Open [`aegis_high_level.html`](aegis_high_level.html) in a browser. Icons are shared with the low-level diagram (`../low-level/icons/used/`).

C4 Level 1 (context) and Level 2 (containers) of the **running** system — people, one software system, the containers inside it, and the externals it talks to. It is the counterpart of the [low-level Azure-style drawing](../low-level/aegis_low_level.html) (subscription / VNet / subnet) and the [agents-and-flow diagram](../agentic/aegis_agents.html) (roster, shared spine, HITL).

| Layer | What it shows |
|---|---|
| People | Named HITL roles from `user_store.ROLE_CATALOG` |
| This system | AEGIS-PHARMA — advisory decision support, never a terminal GxP action |
| Control Center | Next.js (`apps/web`) |
| Orchestrator | One FastAPI process, six peer LangGraphs (ADR-008) |
| Governance | In-process policy, guard, denial-of-wallet, HITL — not a separate VM |
| Tools | In-process Python (`services/integration`). C4 called these MCP servers |
| Data | Neo4j evidence, Redis cache, SQLite audit |
| Brownfield | Read-only ingest. No write-back |
| Externals | Azure AI Foundry (default), Anthropic/Groq (dev), optional SMTP, LangSmith (must not block) |
| Azure that CD actually ships | Container Apps (API + web), ACR |
| Designed, not in cd.yml | Entra, Key Vault, Blob WORM, Monitor, Private Endpoint, `apps/admin`, `services/worker` |

Click a tile for the repo path. Toggle **Context**, **Local compose**, **Azure target**, and **Chaos injectors**.
