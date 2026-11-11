---
name: scar-learn
description: "Implements Mitchell Hashimoto's Scar-Driven Harness Engineering and Self-Harness protocol. Converts any regression, anomaly, or agent mistake into a permanent deterministic sensor or rule."
---

# Scar-Driven Self-Harness Evolution Skill (`/scar-learn`)

Whenever an agent error, `[REGRESSION]`, or sequence anomaly occurs:

1. **Analyze Failure Trajectory:**
   - Determine whether the failure stemmed from a missing pre-action Guide (ambiguous convention) or a missing post-action Sensor (untested edge case).
   - If a sequence anomaly occurred in `state/events/`, manage it strictly via `python3 scripts/anomaly.py` (never hand-edit `_anomalies.json`).

2. **Engineer Permanent Prevention ("One Scar at a Time"):**
   - **Computational Sensor (Preferred):** Add a deterministic check to `scripts/verify.py`, a unit test to `tests/`, or a chaos regression scenario to `sim/`.
   - **Inferential Guide:** Add a concise 1-line constraint to `.agents/rules/marzneshin-code-invariants.md` or persist the architectural lesson in the `marzneshin-agentmemory` MCP server (`state/agentmemory/`).

3. **Validate Scar Effectiveness:**
   - Run `python3 scripts/health.py` (or targeted test + `python3 scripts/verify.py --all`) to confirm the new sensor passes and deterministically prevents recurrence.

