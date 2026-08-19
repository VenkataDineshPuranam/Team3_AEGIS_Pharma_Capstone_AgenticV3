# CHAOS-LLM-02 — real LLM provider outage (ops)

**UI-runnable:** no

## Purpose

Confirm live `degraded_mode` abstention when the configured provider is actually unreachable
(API key revoked, network block, or provider outage) — same ADR-007 row as `CHAOS-LLM-01`,
different cause.

## Steps

1. Note current `LLM_PROVIDER` / API key in `.env`.
2. Break reachability (invalid key or firewall) for a **lab** environment only.
3. Submit a real `batch_review` run via the Control Center.
4. Expect `abstained` / `degraded_mode`; deterministic findings still present.
5. Restore credentials.

## Evidence

Audit `agent_run` row with `abstention_reason=degraded_mode`. Do not use production.
