---
description: Two-Key verification and receipt check before declaring completion
---

Before completing any task:
1. Ensure receipt exists in `receipts/`:
```bash
python3 scripts/verify.py --chain
```
2. Confirm rollback is tested: `rollback.tested=true`.
3. Confirm `sim_evidence` is green for code/config changes.
4. Pass all unit tests:
```bash
python3 -m unittest discover -s tests
```
