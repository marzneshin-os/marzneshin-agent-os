---
trigger: model_decision
description: "Apply this deep reasoning protocol whenever performing complex architectural design, root-cause debugging, designing chaos simulation scenarios in sim/, extending A2A bus/adapters (vs4-vs11), writing ADRs, or resolving ambiguous tasks."
---

# Argon & Anthropic-Grade Deep Reasoning Protocol (Harness 2.0)

When tackling complex engineering, state-machine, or architectural tasks in `marzneshin-agent-os`, you MUST override default one-shot generation and execute this 5-phase structured reasoning protocol before modifying any file:

## Phase 1: Anti-Excursion & Holistic Context Acquisition
1. **Zero Side Quests:** Bound your investigation strictly to the active slice (`VS-x`) in `state/STATE.json` and `state/HANDOFF.md`. Do NOT run exploratory Git history commands unless investigating a specific `[REGRESSION]`.
2. **Holistic File Reading (No Chunked Slicing):** Never call `view_file` repeatedly on small line fragments of the same file. Locate symbols via `grep` first, then read the entire target module in `scripts/lib/`, `adapters/`, or `analytics/schemas/` in a single pass.

## Phase 2: First-Principles & Invariant Matrix Verification
Explicitly map the problem against Governing Specifications:
- Which invariants in `CLAUDE.md` (`I1`–`I17`) govern this change?
- Is any observed behavior recorded as intentional technical debt in `decisions/TRADEOFF-REGISTER.md`? (If yes, DO NOT touch or "fix" it).
- Does the change interact with untrusted input? (If yes, enforce `I16`: maximum autonomy cap = `L1`).
- Does the target agent have a valid Agent Card in `agents/cards/` with explicit path ownership (`I17`)?
- How does the component remain strictly fail-closed (`I12`) if a fencing lease expires, an A2A peer heartbeat goes stale (`>900s`), or any path of the 5-path kill switch (`K1 state/KILL`, `K2 env KILL_SWITCH`, `K3 Moxt`, `K4 scripts/killswitch.py`, `K5 auto`) activates?

## Phase 3: Best-of-3 Tree-of-Thoughts (In-Context RLVR Sampling)
Formulate 3 distinct candidate architectures internally:
- **Candidate A (Minimal Surgical Patch):** Smallest stdlib-only delta inside `scripts/lib/`.
- **Candidate B (Schema/Adapter Contract):** Updating `analytics/schemas/` or `adapters/` with idempotent A2A hysteresis fallback.
- **Candidate C (Event-Sourced Projection):** Emitting new redacted events and updating `scripts/compact.py`.

Score all 3 candidates against `BUILD-SPEC.md` (`§16` mandatory scenarios & `§17` DoD) and select the candidate with the smallest blast radius, zero external dependencies, and verified rollback (`I7`: `rollback.tested=true`, `tested_at`, `tested_in`).

## Phase 4: Adversarial Pre-Mortem Audit
Assume your chosen implementation just caused a `[REGRESSION]` or exit code `1`/`2` in `python3 scripts/health.py`. Audit:
1. Could a concurrent writer violate fencing-token leases (`I17`)?
2. Could any exception path leak an unredacted token/secret bypassing `scripts/lib/redact.py` (`I6`)?
3. Could `health.py --save-baseline` reject the run under `ADR-009` because a tracked gate (e.g., `coldrestore`) was omitted?

## Phase 5: Sim-First Execution Loop (I11)
Write or execute the failing simulation scenario in `sim/` (`scripts/sim.py`) FIRST, observe the expected failure, implement the minimal surgical code in `scripts/lib/`, and drive `python3 scripts/health.py` to Exit Code `0` (Reward = 1).

