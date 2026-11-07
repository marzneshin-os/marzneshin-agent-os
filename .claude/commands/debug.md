---
description: Superpowers Phase 4 — Systematic 4-Phase Root Cause Analysis
---

**SUPERPOWERS PHASE 4: SYSTEMATIC DEBUGGING**

Do not guess or try random edits. Follow the 4 phases:
1. **Investigate**: Reproduce the bug with an isolated test case or command. Capture exact error outputs and logs.
2. **Isolate**: Trace the exact code path, state condition, or input that triggers the divergence. Check recent events in `state/events/`.
3. **Fix**: Apply a surgical fix addressing the root cause. Clean up only your own changes.
4. **Verify**: Run the reproduction test to prove the bug is gone, then run `python3 scripts/verify.py --all` to prove no regressions.