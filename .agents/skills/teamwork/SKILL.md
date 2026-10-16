---
name: teamwork
description: Multi-agent parallel coordination and teamwork preview. Use when user invokes /teamwork, /teamwork-preview, or needs to orchestrate specialist subagents across isolated workstreams.
metadata:
  short-description: Multi-agent parallel execution and teamwork orchestration
---

# 👥 Teamwork Multi-Agent Orchestrator

Activate this skill when the user types `/teamwork` or `/teamwork-preview`, or needs to dispatch specialist sub-agents across isolated workstreams.

## When to Use
- When facing 2+ independent, non-overlapping tasks that can be executed in parallel.
- When orchestrating specialized roles (architecture, API, tests, audit) for a major feature.
- When generating preview task graphs before parallel subagent dispatch.

## The Teamwork Execution Protocol

### 1. Task Graph Decomposition
- Decompose the objective into independent workstreams with clear ownership boundaries.
- Identify blocking dependencies and isolate concurrent execution lanes.

### 2. Specialist Model & Role Allocation
- **@memory-architect** (`Claude Opus 4.6 Thinking`): Core function logic, state engine, schema design.
- **@mcp-tool-builder** (`Gemini 3 Pro`): MCP tool definitions, handler dispatch, and 8-file sync.
- **@api-endpoint-builder** (`Gemini 3 Pro`): REST API endpoints, auth verification, and 3-file sync.
- **@test-engineer** (`Gemini Flash 3.8`): Vitest suites, test-driven development, and regression testing.
- **@consistency-guardian** (`Gemini Flash 3.8`): Cross-cutting verification, file counts, and audit logs.

### 3. Workspace Isolation & Leases
- Ensure subagents do not edit the same files concurrently.
- Respect leases in `state/leases/` and state tracking in `state/STATE.json`.

### 4. Two-Key Verification & Synthesis
- **Key 1 (QA):** Verify that all `npm test` assertions pass (1,596+ tests).
- **Key 2 (Adversarial Review):** Inspect the unified diff, confirm zero regressions, and update `state/HANDOFF.md`.
