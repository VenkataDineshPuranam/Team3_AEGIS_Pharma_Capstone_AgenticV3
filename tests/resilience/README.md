# resilience

Failure-injection, retry, and degradation tests.

- `test_ai_disabled_continuity.py` — K-002 StubLLM continuity (needs Neo4j)
- `test_vendor_exit_export.py` — vendor-exit export path
- `test_chaos_harness.py` — ADR-007 lab injectors via `chaos_harness` (offline, no Neo4j/Redis)
