---
name: boris
description: Boris Cherny's official Claude Code philosophy, workflow patterns, and power-user guidelines (howborisusesclaudecode.com).
---

# How Boris Cherny Uses Claude Code

Compiled from Boris Cherny's official posts, threads on X (@bcherny), and the canonical guide at `howborisusesclaudecode.com`.

## 1. Core Philosophy: Surprisingly Vanilla
- Claude Code is designed to be exceptional out-of-the-box. Avoid fragile, bespoke wrappers when native capabilities suffice.
- Focus effort on **clear behavioral contracts (`CLAUDE.md`)**, **deterministic verification scripts**, and **clean permissions**.

## 2. Multi-Agent Parallel Execution
- Run **3 to 5 Claude Code sessions in parallel** in separate terminal windows.
- Always use **Git Worktrees** (`python3 scripts/worktree_cli.py`) so each session operates on an isolated checkout without stepping on other branches.
- Use `--teleport` to transfer active work between terminal CLI and web (`claude.ai/code`).

## 3. Plan Mode First
- For every non-trivial feature or refactor, start in **Plan Mode** (`/plan` or `Shift+Tab`).
- Explore the codebase, review existing tests, trace callers, and lay out an exact plan before touching a line of code.

## 4. Verification Loops as a Force Multiplier
- Never ask Claude to simply "make it work".
- Give Claude an automated, deterministic test loop (`python3 scripts/verify.py`, `pytest`, `ruff format`).
- When Claude has a concrete verifier, hallucinations plummet and multi-step accuracy compounds exponentially.

## 5. Ruthless CLAUDE.md Hygiene
- Keep `CLAUDE.md` concise (< 200-300 lines). Bloated rulebooks cause context dilution.
- State strict **negative constraints** ("NEVER edit state/ manually", "DO NOT bypass verify.py").
- Keep instructions actionable and trigger-action oriented.

## 6. Smart Permission Management
- Don't run `--dangerously-skip-permissions`.
- Instead, pre-approve inner-loop developer commands (`test`, `build`, `format`, `lint`) in `.claude/settings.json`.
