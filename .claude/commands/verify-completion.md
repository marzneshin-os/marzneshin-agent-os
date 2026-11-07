---
description: Superpowers Phase 5 — Verification Before Completion (Evidence Before Assertions)
---

**SUPERPOWERS PHASE 5: VERIFICATION BEFORE COMPLETION**

**NEVER CLAIM WORK IS DONE WITHOUT FRESH COMMAND EVIDENCE.**
1. Run local CI verification:
   ```bash
   python3 scripts/verify.py --all
   ```
2. Run targeted test suite:
   ```bash
   python3 -m unittest discover -s tests
   ```
3. Inspect Git status for untracked artifacts or unwanted diffs:
   ```bash
   git status --short
   ```
4. Confirm budget compliance:
   ```bash
   python3 scripts/cost_tracker.py status
   ```
5. Emit Two-Key verification receipt or update `state/HANDOFF.md`.