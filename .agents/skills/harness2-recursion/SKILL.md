---
name: harness2-recursion
description: Google Research Harness² Two-Level Recursive Agent Optimization (Propose-Probe-Compose + Experience Ledger) for marzneshin-agent-os.
---
# Harness² Recursive Optimization Skill

## When to Activate
Activate automatically on `/goal`, `/boost`, `/teamwork-preview`, or whenever a task fails initial verification or touches >= 3 files.

## Level 1: Task-Level Recursion (Propose -> Probe -> Compose)
1. **Reference Trace:** Capture baseline behavior, failing test output, or architectural gap.
2. **Propose Dual Candidates:**
   - **Invariant Mutation (`C_inv`):** Check hook ordering (`antigravity-bridge.ts`), tool arguments, and 8/3/7-file Atomic Consistency Rules.
   - **Domain Mutation (`C_dom`):** Check `agentmemory` core logic, `iii-sdk` mocks, hybrid search scoring, and REST/MCP schemas.
3. **Probe Deterministically:** Execute `npm test` (`vitest`), `python3 scripts/harness2.py verify-sync`, and `@consistency-guardian` line-level verification.
4. **Contrastive Compose:** Merge only mutations proven to reduce test failures or invariant violations.

## Level 2: Harnessing-Level Recursion (Experience Persistence)
Before completing `HANDOFF` or `/ship`, record the lesson via `python3 scripts/harness2.py record-experience` (which updates `state/EXPERIENCE.md`, `state/LEDGER.json`, and `receipts/`) and call `memwal_remember`:
- **Cue:** [Task signature / error pattern]
- **Lesson:** [Generalizable harness or code rule]
- **Empirical Evidence:** [Test command, pass count, and receipt path]
