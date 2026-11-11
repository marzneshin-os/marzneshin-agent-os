---
name: fsp-closeout
description: "Executes Stage 7 of ONBOARDING.md (Mandatory Session End Protocol) using the 20% reserved token budget: emits cryptographic receipts via scripts/lib/receipts.py, verifies chain and task_complete hook, compacts STATE.json, rewrites HANDOFF.md, updates CONTEXT-PACK.md, and releases the FSP lease."
---

# Mandatory Session Closeout Skill (`/fsp-closeout`)

Trigger this skill immediately upon completing one green increment OR when reaching 80% of the session token budget (switch to `Low` effort for fast mechanical execution):

1. **Confirm Green Point:**
   Ensure `python3 scripts/health.py` returns Exit `0` (or revert incomplete edits to the last green state / mark explicit safe WIP).

2. **Emit Cryptographic Receipt & Verify Chain (`I3`, `I15`):**
   - Create and persist the append-only task receipt into `receipts/<year>/<month>/T-XXXX.json` and update `receipts/_chain` using `scripts/lib/receipts.py` (`Receipt`, `Change`, `Verification`, `Rollback`, `SimEvidence`, `Idempotency`, `receipts.write(...)`).
   - Verify receipt, hash chain, and task completion hook:
     ```bash
     python3 scripts/verify.py --chain
     python3 scripts/verify.py --all
     echo '{}' | MARZ_TASK_ID=T-XXXX python3 hooks/task_complete.py
     ```

3. **Regenerate Derived State from Event Log (`I1`):**
   ```bash
   python3 scripts/compact.py
   ```

4. **Rewrite `state/HANDOFF.md` Completely:**
   Document:
   - Completed increment + new Receipt ID (`T-XXXX`).
   - Current green counts (`tests` / `verify` / `sim` from `health.py --json`).
   - **"Next session — start here"**: Exact next actionable item.
   - Any misleading non-regressions observed.
   - Open Owner blockers (`Oxx`).

5. **Refresh `CONTEXT-PACK.md` & Architecture Decision Records:**
   ```bash
   python3 scripts/context_pack.py
   ```
   - If an architectural decision was made during the session, add a new ADR file in `decisions/ADR/`.

6. **Release Fencing-Token Lease (`I17`):**
   ```bash
   python3 scripts/fsp.py release <WORKSTREAM> --agent antigravity-agent
   ```

