---
name: claude-code-hub
description: Claude Code Ecosystem Hub — provides native mappings and execution for Claude Code slash commands, Boris Cherny workflows, context compaction, doctor diagnostics, subagents, and worktrees in Antigravity IDE.
---

# Claude Code Hub for Antigravity IDE

This skill brings the complete workflow, slash command suite, and architectural principles of **Claude Code** (designed by Boris Cherny at Anthropic) directly into Antigravity IDE.

## 1. Boris Cherny's Core Tenets
1. **Explore & Plan First (`/plan`)**: Never write code on complex features without an approved plan. Invest in getting the architecture right.
2. **Context Window Hygiene**: Keep context clean. Run heavy exploration in isolated subagents (`invoke_subagent`).
3. **Living Memory (`CLAUDE.md` & `GEMINI.md`)**: When an agent makes a mistake, immediately update the living rules. Keep rules concise (<1,000 tokens).
4. **Deterministic Pre-Allowed Commands**: Pre-allow tests, formatters, and builds so iteration is frictionless.
5. **Parallel Worktrees**: Run independent workstreams in separate git worktrees (`python3 scripts/worktree_cli.py create <branch>`).
6. **Self-Correction & Test Verification**: Provide verification criteria with every mutation: "Make change, run tests, fix failures."

---

## 2. Slash Commands Quick Reference in Antigravity IDE

| Command | Action in Antigravity IDE | Underlying Execution |
|:---|:---|:---|
| `/plan` | Enter planning mode, analyze requirements, create implementation plan | `brainstorming` + `writing-plans` |
| `/context` | Inspect token consumption, cache hits, tool history | `python3 scripts/tokensaver.py status` + Codeburn MCP |
| `/compact` | Re-compact state and memory, clear bloated history | `python3 scripts/compact.py` + Headroom MCP |
| `/doctor` | Run full diagnostic matrix on credentials, MCPs, and repo state | `python3 scripts/antigravity_doctor_cli.py diagnose` |
| `/worktree` | Create, list, or remove isolated git worktrees | `python3 scripts/worktree_cli.py` |
| `/btw` | Ask quick side question without context contamination | Dispatch `invoke_subagent` with `TypeName: "research"` |
| `/diff` | Inspect active unstaged/staged git changes | `git status` + `git diff --stat` |
| `/review` | Run adversarial review on pending changes | `python3 scripts/review.py` |
| `/pr` | Verify test suite and generate verified PR description | `python3 scripts/pr.py` |
| `/caveman` | Force token-minimal brevity mode | Activate `caveman` skill |
| `/ponytail` | Execute 7-step YAGNI ladder before building new code | Activate `ponytail` skill |

---

## 3. Workflow Procedures

### Procedure A: Side-Channel Question (`/btw`)
When the user asks a quick question that does not relate to the main task:
1. Do not derail the main conversation context.
2. Delegate the exploration to a research subagent:
   `invoke_subagent(TypeName="research", Task="...")`
3. Return the succinct answer to the user and resume the primary task.

### Procedure B: Context Compaction (`/compact`)
When conversation history or state grows large:
1. Run `python3 scripts/compact.py` to rebuild `STATE.json` deterministically from event logs.
2. Sync key takeaways to `state/HANDOFF.md` or `agentmemory`.

### Procedure C: Parallel Branching (`/worktree`)
To run an independent feature branch without dirtying the current workspace:
```bash
python3 scripts/worktree_cli.py create feature-x
# Work within .worktrees/feature-x
python3 scripts/worktree_cli.py list
```
