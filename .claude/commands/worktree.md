---
description: Manage Git Worktrees for Boris Cherny multi-agent parallel execution
---

Manage isolated worktrees:
```bash
# List all active worktrees
python3 scripts/worktree_cli.py list

# Create a new isolated workstream
python3 scripts/worktree_cli.py create <branch-name>

# Cleanup finished worktree
python3 scripts/worktree_cli.py remove <branch-name>
```
Run 3-5 Claude Code terminal instances in parallel across separate worktrees without file conflicts.
