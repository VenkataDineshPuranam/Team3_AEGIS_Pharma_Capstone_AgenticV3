# CHAOS-CKPT-01 — MemorySaver loss on API restart (ops)

**UI-runnable:** no

## Purpose

Document the known limitation: graphs use in-process `MemorySaver`. Restarting the
Orchestrator API mid-HITL loses pause state. There is no RedisSaver in this build.

## Steps

1. Submit a run that pauses at HITL.
2. Confirm it appears in the Decision Queue.
3. Restart the API process.
4. Expect the pending in-memory entry to be gone; no durable checkpoint to resume.

## Evidence

Queue empty for that run_id after restart. Treat as known topology limit (ADR-008 / MemorySaver),
not a regression of durable checkpointer failover (not implemented).
