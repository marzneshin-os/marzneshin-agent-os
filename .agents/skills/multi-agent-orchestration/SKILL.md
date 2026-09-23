---
name: multi-agent-orchestration
description: Use when you need to orchestrate multiple specialist agents in parallel to complete a complex project task. This is the CEO pattern — decompose, delegate, aggregate.
---

# Multi-Agent Orchestration

## Overview

You are the **CEO / Orchestrator**. You decompose complex project tasks into independent
work units, dispatch specialist agents in parallel, and aggregate their results. You never
implement directly — you coordinate.

This skill builds on `dispatching-parallel-agents` with structured specialist roles,
dependency-aware staging, and consistency gates specific to the agentmemory project.

## When to Use

- A task touches 3+ independent subsystems (functions, MCP tools, REST endpoints, hooks, tests)
- Work can be parallelized without shared-state conflicts
- The task would exceed ~100K tokens if done sequentially in one context
- You need structured quality gates (consistency audit, test suite)

## The Specialist Team

| Agent Role | Scope | Files | Model Tier |
|------------|-------|-------|------------|
| `@memory-architect` | Core functions, KV schema, types | `src/functions/`, `src/state/`, `src/types.ts` | Full capability |
| `@mcp-tool-builder` | MCP tool definitions + handlers | `src/mcp/tools-registry.ts`, `src/mcp/server.ts` | Full capability |
| `@api-endpoint-builder` | REST endpoints + auth | `src/triggers/api.ts`, `src/index.ts` | Full capability |
| `@hook-specialist` | Hook scripts + bridge | `src/hooks/` | Full capability |
| `@test-engineer` | Tests + coverage | `test/`, `vitest.config.ts` | Full capability |
| `@consistency-guardian` | Cross-file audit (read-only) | All files | Research |
| `@documentation-writer` | README, AGENTS.md, docs | `README.md`, `AGENTS.md`, `docs/` | Full capability |

## Execution Protocol

### Step 1: Analyze the Task

Read the task requirements. Identify which specialist agents are needed.
Not every task needs all 7 agents — use only what is needed.

### Step 2: Build the Dependency Graph

Map dependencies between agents:

```
Stage 1 (no deps):       @memory-architect
Stage 2 (needs Stage 1): @mcp-tool-builder, @api-endpoint-builder
Stage 3 (needs Stage 2): @hook-specialist
Stage 4 (needs all):     @test-engineer
Stage 5 (final gate):    @consistency-guardian -> @documentation-writer
```

### Step 3: Create Task Briefs

For each specialist, create a focused brief:

```markdown
## Task Brief for @mcp-tool-builder

### Objective
Add new MCP tool `memory_your_tool` for [specific purpose].

### Context
- Read AGENTS.md "When adding or removing MCP tools" checklist
- The underlying function `mem::your-function` is already registered

### Deliverables
1. Add tool definition to `src/mcp/tools-registry.ts` getAllTools()
2. Add handler case to `src/mcp/server.ts` switch statement
3. Run `npm test -- --grep "mcp"` to verify

### Constraints
- Do NOT modify files outside your scope
- Follow existing patterns in tools-registry.ts
- Validate all args with typeof checks
```

### Step 4: Dispatch in Parallel

Issue all independent agent dispatches in the **same response**:

```
Subagent (general-purpose): [Task brief for @memory-architect]
Subagent (general-purpose): [Task brief for @api-endpoint-builder]
# Both run concurrently because they are in the same response
```

Wait for results. Then dispatch the next stage.

### Step 5: Run Quality Gates

After all agents complete:

1. **Test Suite**: `npm test` — must have 0 failures
2. **Consistency Audit**: `npx tsx scripts/orchestrator/consistency-guardian.ts`
3. **Cross-check**: Verify agent outputs do not conflict

### Step 6: Aggregate and Report

Summarize what each agent accomplished:
- Files modified
- Tests added/modified
- Any issues encountered

## Agent System Prompts

When dispatching, prepend this context to the agent task:

```markdown
You are working on the agentmemory project (v0.9.29).

Architecture: iii-engine (Worker/Function/Trigger). Everything goes through
registerFunction/registerTrigger/sdk.trigger() — never bypass with standalone SQLite.

Key rules from AGENTS.md:
- TypeScript ESM only ("type": "module")
- No comments explaining WHAT code does
- Use fingerprintId() for content-addressable dedup
- Use recordAudit() for state-changing operations
- Timestamps: capture once with new Date().toISOString() and reuse

Your specific role: [ROLE NAME]
Your file scope: [FILE LIST]
```

## Safety Rules

1. **Never dispatch agents to edit the same file** — resolve file ownership first
2. **Test engineer always runs last** — needs all implementation changes first
3. **Consistency guardian is read-only** — it reports, never modifies
4. **Cap fix rounds at 5** — adjudicate after that (from subagent-driven-development)
5. **Run full test suite after merge** — individual agent tests are not sufficient

## Integration with Existing Skills

- Uses `dispatching-parallel-agents` for parallel dispatch mechanics
- Uses `subagent-driven-development` for implement -> review pipeline per agent
- Uses `verification-before-completion` before declaring orchestration complete
- Uses `writing-plans` if the task needs decomposition before dispatch

## Quick Reference

```
1. Analyze task -> identify needed specialists
2. Build dependency graph -> determine stages
3. Create task briefs -> focused, self-contained
4. Dispatch parallel agents -> same response = concurrent
5. Wait for results -> review each summary
6. Run quality gates -> tests + consistency audit
7. Aggregate -> report what changed
```
