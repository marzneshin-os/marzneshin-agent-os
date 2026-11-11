---
name: sim-tdd
description: "Executes Stage 6 of ONBOARDING.md: Sim-First development loop (Invariant I11), In-Context RLVR binary reward verification via health.py and verify.py, and Agent-to-Agent adversarial self-review."
---

# Sim-First (I11) & In-Context RLVR Execution Skill (`/sim-tdd`)

Execute this micro-increment loop (switch to `High` effort for scenario/architecture design, and `Low`/`Medium` for mechanical gate runs):

1. **Step 6.1 — Failing Simulation / Test First (Red Gate):**
   - Identify or author the target chaos/scenario test in `sim/` (`scripts/sim.py` per `BUILD-SPEC.md §16`) and unit test in `tests/`.
   - Verify it fails first using a single seed or targeted test run:
     ```bash
     python3 scripts/health.py --seeds 11
     ```

2. **Step 6.2 — Minimal Surgical Implementation:**
   - Write the smallest possible stdlib-only code increment in `scripts/lib/` (keeping `scripts/`, `hooks/`, and `adapters/` thin and modular).
   - Use the fast feedback loop while iterating:
     ```bash
     python3 scripts/verify.py --lint-imports --lint-clock
     python3 scripts/health.py --skip-sim
     ```

3. **Step 6.3 — Full Deterministic RLVR Reward Gate (Green Gate):**
   - Before long runs (>15m into a session), renew the lease heartbeat (`python3 scripts/fsp.py heartbeat <WORKSTREAM> --agent antigravity-agent`) so `handoff_guardian` continuity checks do not flag an active lease as a stale zombie.
   - Run the complete gate suite and chain verifier:
     ```bash
     python3 scripts/health.py
     python3 scripts/verify.py --all
     ```
   - If Exit Code is `1`, inspect bounded failure details (max 8 items) via `python3 scripts/health.py --verbose`. Never swallow unbounded raw test logs.
   - If new tests/scenarios were added and ALL tracked baseline gates (including `--coldrestore` if tracked in `state/HEALTH-BASELINE.json`) were executed and passed, save the new green floor per `ADR-009`:
     ```bash
     python3 scripts/health.py --coldrestore --save-baseline
     ```

4. **Step 6.4 — Agent-to-Agent (A2A) Adversarial Self-Review:**
   - Invoke the `argon-critic` subagent (or inspect `git status` and `git diff`) to verify:
     - Zero raw secrets (`scripts/lib/redact.py` per `I6`).
     - Verified rollback metadata (`I7`: `rollback.tested=true`, `tested_at`, `tested_in`).
     - Valid Agent Cards (`agents/cards/`) and leased paths only (`I17`).
     - Zero hand-edits to derived state (`STATE.json`, `state/events/*`, `receipts/_chain`).
   - Output concise diffs only in chat; never reprint unchanged files.

