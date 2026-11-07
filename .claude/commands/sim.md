---
description: Run simulation harness to prove 72-hour behavior in 60 seconds
---

Run the Marzneshin Simulation suite:
```bash
python3 scripts/sim.py --suite full
```
Verify:
- Error budget compliance
- Connection Success Rate (CSR) stability
- Failsafe circuit breakers
