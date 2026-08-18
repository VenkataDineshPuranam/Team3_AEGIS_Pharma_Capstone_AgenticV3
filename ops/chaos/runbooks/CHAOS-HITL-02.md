# CHAOS-HITL-02 — HITL backdate debug (ops)

**UI-runnable:** no

## Purpose

Exercise HITL severity ladder display (T2/T3) without waiting 16–24 hours.

## Steps

1. Set `AEGIS_ENABLE_DEBUG_ENDPOINTS=1` and restart the API (lab only).
2. Create a pending HITL run.
3. `POST /api/debug/backdate/{run_id}?hours_ago=25`.
4. Confirm severity badge advances; decide with `timed_out` or approve as appropriate.
5. Unset the debug flag before any shared demo.

## Notes

Backdate touches only `created_at` used by the badge — not findings or audit content.
