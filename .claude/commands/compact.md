---
description: Perform safe context compaction while preserving active leases, tasks, and state
---

**Safe Context Compaction (with Marzneshin State Preservation)**
1. Ensure in-flight edits are saved.
2. The `PreCompact` hook automatically checkpoints active leases and tasks to `state/checkpoints/`.
3. Invoke Claude Code compaction:
```text
/compact
```
4. Upon return, the `SessionStart` hook re-injects the live slice, fencing tokens, and invariant reminders.
