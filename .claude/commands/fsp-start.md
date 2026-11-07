---
description: Start an FSP session (SYNC -> GAP SCAN -> CLAIM workstream)
---

Follow the 9-stage FSP protocol (§0):
1. Check current system status:
```bash
python3 scripts/fsp.py status
cat state/HANDOFF.md
```
2. Scan for open gaps and claim workstream:
```bash
python3 scripts/fsp.py claim <workstream> --agent <agent_id>
```
3. Verify fencing token and proceed with Plan mode.
