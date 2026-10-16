---
trigger: always_on
description: Superpowers agentic engineering methodology harmonized with Karpathy guidelines, AGENTS.md, and memory discipline
---

# Superpowers Engineering Methodology

This workspace has the complete **Superpowers** agentic skills framework enabled.

## 1. The Core Rule: Skills Before Action
Always invoke relevant Superpowers skills BEFORE taking action or writing code:
- **Starting a new feature or design:** Invoke `brainstorming` to explore requirements, tradeoffs, and architectural options.
- **Designing multi-step changes:** Invoke `writing-plans` to break work into bite-sized tasks with exact paths, complete code, and verification steps.
- **Writing code:** Enforce `test-driven-development` (RED-GREEN-REFACTOR cycle: write failing test, verify failure, write minimal code, verify pass, commit).
- **Investigating bugs or failures:** Enforce `systematic-debugging` (4-phase root cause analysis: investigate, isolate, fix, verify).
- **Finishing work:** Enforce `verification-before-completion` before declaring any task complete.

## 2. Antigravity Platform Adaptation
Skills speak in platform-agnostic actions. In this Antigravity environment, map them as follows:
- **Subagent Dispatch:** Use `invoke_subagent` with `TypeName: "self"` for full capability or `TypeName: "research"` for read-only codebase analysis.
- **Task Tracking & Checklists:** Antigravity has no standalone todo tool. Maintain a **task artifact** via `write_to_file` (`IsArtifact: true`, `ArtifactMetadata.ArtifactType: "task"`), updating checklist items with `replace_file_content` / `multi_replace_file_content` as steps complete.
- **Interactive Questions:** During planning mode, document open questions directly in the `implementation_plan.md` artifact. During conversational interaction, use `ask_question` or concise Markdown.
- **Code & Test Operations:** Use native tools (`run_command` for tests/builds, `grep_search` and `view_file` for reading, `replace_file_content` / `write_to_file` for editing).

## 3. Harmonization with Project Rules & Guidelines
You must ALWAYS adhere to the project's established standards:
1. **Karpathy Guidelines:**
   - *Think Before Coding:* Surface assumptions, state tradeoffs explicitly, never assume silently.
   - *Simplicity First:* Minimum code that solves the problem. No speculative abstractions or unnecessary complexity.
   - *Surgical Changes:* Touch only what you must. Don't refactor adjacent code or delete pre-existing code unless requested.
   - *Goal-Driven Execution:* Define verifiable success criteria for every step.
2. **Memory Discipline (`memory-discipline`):**
   - At task start: search memory for relevant context and settled decisions.
   - At decision points: record the settled decision, the reason, and file paths.
   - On corrections: save lessons learned.
3. **agentmemory Consistency Rules (`AGENTS.md`):**
   - TypeScript ESM only (`"type": "module"`).
   - No comments explaining WHAT code does — use clear naming.
   - Strictly follow consistency rules when touching MCP tools, REST endpoints, versions, or schemas.
   - All tests must pass before completing work.
