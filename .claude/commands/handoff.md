---
description: Update state/HANDOFF.md and release workstream lease
---

**Rule 3: No session ends without a HANDOFF.**
1. Summarize accomplishments, open risks, and next steps in `state/HANDOFF.md`.
2. Release held leases:
```bash
python3 scripts/fsp.py release <workstream> --agent <agent_id>
```
3. Run `python3 scripts/compact.py` if events need reconciliation.
