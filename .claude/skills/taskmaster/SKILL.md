---
name: taskmaster
description: Structured task pipeline orchestration for Claude Code using Task Master AI principles (Khairallah Stack Tool #18). Use when breaking down PRDs, tracking multi-step work, or executing tasks sequentially with dependency resolution.
---

# Task Master AI Orchestration Skill

Task Master AI serves as the structured project manager for AI coding sessions, organizing chaotic tasks into dependency-aware DAG pipelines.

## CLI Commands
- `python3 scripts/taskmaster_cli.py init <spec.md>`: Parse markdown spec/PRD into `state/tasks.json`.
- `python3 scripts/taskmaster_cli.py list`: Display all tasks, status, and dependency graph.
- `python3 scripts/taskmaster_cli.py next`: Fetch next unblocked task with acceptance criteria.
- `python3 scripts/taskmaster_cli.py start <id>`: Mark task as `in_progress`.
- `python3 scripts/taskmaster_cli.py complete <id> [--receipt <id>]`: Mark task as `completed`.
- `python3 scripts/taskmaster_cli.py status`: Show completion rate and remaining workload.

## Workflow Rules
1. **Dependency Invariant**: Never begin a task until all predecessor tasks listed in `depends_on` are completed.
2. **Acceptance Criteria Verification**: Validate every criterion listed in the task before running `complete`.
3. **Receipt Linkage**: When working within a workstream, attach the verification receipt ID to the completed task.