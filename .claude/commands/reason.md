---
description: Reason Network P2P Mesh - check peer agents, send messages, and check network health (1R-030)
---

**Reason Network P2P Mesh Command**

Run Reason Network operations across your peer mesh:

1. **Check active peers and sessions:**
```bash
reason-network who
```

2. **Check daemon and connectivity health:**
```bash
reason-network doctor
```

3. **Send a secure message to a peer agent (auto-redacted):**
```bash
python3 scripts/reason_cli.py send <peer-session> "<message>"
```

ç. **Show team invite link to onboard a new machine or teammate:**
```bash
reason-network invite
```
