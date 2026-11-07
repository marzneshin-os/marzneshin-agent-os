---
description: Audit and manage 5-path Kill Switch (K1-K5)
---

Check kill switch verdict:
```bash
python3 scripts/killswitch.py status
```
Reconcile external signals:
```bash
python3 scripts/killswitch.py reconcile
```
To test all 5 kill paths:
```bash
python3 scripts/killswitch.py verify
```
