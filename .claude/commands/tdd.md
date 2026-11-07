---
description: Superpowers Phase 3 — Test-Driven Development (RED-GREEN-REFACTOR with unittest)
---

**SUPERPOWERS PHASE 3: TEST-DRIVEN DEVELOPMENT**

Enforce the ironclad TDD cycle:
1. **RED**: Write a failing unit test in `tests/test_<feature>.py`.
   - Run: `python3 -m unittest tests.test_<feature>`
   - Verify it fails for the expected reason (not import or syntax error).
2. **GREEN**: Write the minimal code necessary to make the test pass.
   - Avoid speculative code or gold-plating.
   - Run: `python3 -m unittest tests.test_<feature>`
   - Verify it passes.
3. **REFACTOR**: Clean up, adhere to stdlib-only and `lib/clock.py` rules.
4. **GATE**: Ensure local CI gate is green: `python3 scripts/verify.py --all`.