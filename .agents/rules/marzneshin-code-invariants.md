---
trigger: glob
description: "Enforces Marzneshin-Agent-OS iron laws, Python stdlib-only architecture, secret redaction, virtual clock discipline, and single-writer fencing leases across all code, hooks, adapters, schemas, and state directories."
globs: "scripts/**, hooks/**, sim/**, adapters/**, agents/**, analytics/**, state/**, receipts/**, tests/**"
---

# Marzneshin-Agent-OS Code, Hook & State Invariants Guard

1. **Strict Layering & Stdlib-Only Core:**
   - All shared logic MUST reside in `scripts/lib/` and use **Python standard library ONLY** (`pyyaml` and `jsonschema` are restricted to lazy schema/config validation boundaries).
   - CLI scripts in `scripts/` (`fsp.py`, `killswitch.py`, `health.py`, `verify.py`, `compact.py`, `sim.py`, `anomaly.py`, `context_pack.py`) and hooks in `hooks/` (`session_start.py`, `pre_tool.py`, `post_tool.py`, `pre_commit.py`, `stop.py`, `task_complete.py`) must remain thin wrappers calling `scripts/lib/`.
2. **Forbidden Hand-Edits (Append-Only & Event-Sourced Integrity):**
   - NEVER hand-edit `state/STATE.json`. Rebuild it exclusively via `python3 scripts/compact.py` (`I1`).
   - NEVER hand-edit `state/events/*`, `receipts/_chain`, or `_anomalies.json`. Register/close sequence anomalies strictly via `python3 scripts/anomaly.py`.
   - NEVER delete or alter historical receipts in `receipts/<year>/` (`I3`, `I15`).
3. **Mandatory Secret Redaction (`I6`) & Virtual Clock (`D6`):**
   - Route all event payloads, receipt artifacts, and hook outputs through `scripts/lib/redact.py`.
   - Never call `datetime.now()`, `time.time()`, `time.sleep()`, or `date.today()` outside `scripts/lib/clock.py` (`python3 scripts/verify.py --lint-clock`).
4. **Sim-First & Production Purity (`I11`):**
   - Never ship mocks, stubs, or synthetic chaos actors outside `sim/` and `tests/`. Never use a fake in production to bypass an Owner blocker (`Oxx`).
5. **Agent Cards, A2A Bus & Fencing Leases (`I12`, `I17`):**
   - Verify valid Agent Cards in `agents/cards/` and JSON schemas in `analytics/schemas/`.
   - Ensure A2A bus envelopes preserve scoped-TTL idempotency and fail-closed hysteresis when heartbeats are stale.
   - Never write to a workspace path without an active lease claimed via `python3 scripts/fsp.py claim <workstream> --agent <id>`.
6. **Raw Log Swallowing Prohibition:**
   - Never run unbounded `unittest discover` into context. Always use `python3 scripts/health.py` (or `--skip-sim` / `--verbose`).

