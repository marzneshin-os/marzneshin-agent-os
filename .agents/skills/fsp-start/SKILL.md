---
name: fsp-start
description: "Executes Stages 1 to 5 of ONBOARDING.md with ADR-030 Static-First KV-Cache ordering: SSoT sequential read, FSP status sync, killswitch reconciliation, workstream fencing-token lease claim, baseline health gate check, and 5-line Owner briefing."
---

# FSP Cold-Start & Baseline Verification Skill (`/fsp-start`)

Execute these exact steps at the start of every session (recommended on `Low` effort budget for 3-5x faster startup; see also `/fsp-warm-start`):

1. **Mandatory SSoT Read (Static-First per ADR-030, No Chunked Slicing):**
   - **Static Governance Prefix First (Tiers 0–2):** `CLAUDE.md` -> `BUILD-SPEC.md` (`§0`, `§16`, `§17` only) -> `decisions/TRADEOFF-REGISTER.md` -> `RECOVERY.md` -> newest `decisions/ADR/` -> newest `decisions/GAP-REPORT-*.md` -> static top section of `CONTEXT-PACK.md`.
   - **Dynamic State Tail Last (Tier 3):** `state/STATE.json` -> `state/HANDOFF.md` (focus on "Next session — start here" and open `Oxx` blockers) -> bottom section of `CONTEXT-PACK.md`.

2. **FSP Sync, Kill Switch Reconcile & Workstream Lease Claim (`BUILD-SPEC §0`, `I17`):**
   ```bash
   python3 scripts/fsp.py status
   python3 scripts/killswitch.py reconcile --skip-auto --by antigravity-agent
   python3 scripts/fsp.py claim <WORKSTREAM> --agent antigravity-agent
   ```
   *(Default workstream is `agentic-core` from `state/STATE.json`. Stale heartbeats `>900s` after a prior handoff are normal; `reconcile` resolves them. If an expired lease blocks `claim`, run `scripts/reaper.py` first).*

3. **Single-Command Baseline Gate (Stage 4):**
   ```bash
   python3 scripts/health.py
   ```
   - Exit `0`: Baseline is GREEN.
   - Exit `1` or `[REGRESSION]`: Fixing the regression against `state/HEALTH-BASELINE.json` becomes Priority #1 before any new feature work.
   - Exit `2`: Gate could not run (fail-closed). Check Python runtime / `.venv` (`pyyaml`, `jsonschema`).
   *(Note: Only run `python3 scripts/health.py --coldrestore` for `§11.2` drills AFTER claiming the lease and ONLY when explicitly requested in `HANDOFF.md`, as it emits prod events and regenerates `STATE.json`).*

4. **Select Work & Output 5-Line Owner Summary (Stage 5):**
   Pick work strictly in this priority order: (1) Stage 4 regression -> (2) `HANDOFF.md` "Next session — start here" -> (3) open DoD items in `BUILD-SPEC.md §17` -> (4) unimplemented `§16` scenarios (compare with `scripts/sim.py`) -> (5) newest `GAP-REPORT`.
   Output a concise 5-line summary before writing code:
   - Line 1: Active Phase & Slice (`VS-x`) + Fencing Lease Status
   - Line 2: Last Verified Receipt ID (`T-XXXX`)
   - Line 3: Current Health Numbers (`tests` / `verify` / `sim` vs baseline)
   - Line 4: Exact Single Increment Selected for This Session
   - Line 5: Open Owner Blockers (`Oxx`)

