---
description: Run Marzneshin OS 6-check verification gate (Two-Key rule)
---

Execute local verification gate to ensure zero regressions:
```bash
python3 scripts/verify.py --all
```

Check the 6 gates:
1. Receipt chain continuity
2. Event append-only integrity
3. Schema validation (110+ artifacts)
4. Agent cards alignment
5. Circular imports lint
6. Clock virtualization lint
