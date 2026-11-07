---
name: worktree-runner
description: Git Worktree Manager for Multi-Agent Parallelism — enables running parallel isolated agents on separate git branches without context bleed (Boris Cherny pattern).
---

# Worktree Runner Skill

This skill operationalizes Boris Cherny's multi-instance parallel agent workflow using Git Worktrees.

## When to Use
- Running 2 or more independent features or bugfixes concurrently.
- Isolating exploratory spikes without affecting the main working branch.
- Running long-running test suites or builds in an isolated folder.

## Core Operations

### 1. Create an Isolated Worktree
```bash
python3 scripts/worktree_cli.py create <branch-name> [--base <base-branch>]
```
- Sets up `.worktrees/<branch-name>`
- Copies over local `.env` and environment configurations safely.

### 2. List Active Worktrees
```bash
python3 scripts/worktree_cli.py list
```

### 3. Cleanup after Completion
Once work has been merged or validated:
```bash
python3 scripts/worktree_cli.py remove <branch-name>
```

## Best Practices
- Never share unstaged changes across worktrees.
- Each worktree can run its own Antigravity subagent or terminal session.
