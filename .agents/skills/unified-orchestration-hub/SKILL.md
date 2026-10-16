---
name: unified-orchestration-hub
description: "Unified Multi-Agent Orchestration Hub -- bridges Antigravity IDE built-in capabilities, Superpowers framework, Marzneshin custom orchestration, and MCP ecosystem into a single activation point. Use when orchestrating any multi-agent task."
---

# Unified Orchestration Hub

Single activation point for all 4 orchestration layers in Marzneshin Autonomous OS + Antigravity IDE.

## When to Use

- Any task that requires more than one agent
- When you need to decide WHICH orchestration layer to use
- When combining project-specific and IDE-built-in capabilities

## Step 0 -- Size Classification (Mandatory)

Before dispatching ANY agents, classify the task:

| Tier | Signal | Orchestration Layer | Activation |
|------|--------|---------------------|------------|
| Trivial | 1 file, few lines | Direct execution | Just do it |
| Small | 1 file, 1 function | Superpowers Cycle | brainstorm, plan, TDD, verify |
| Standard | 2-5 files | Marzneshin Orchestrator | 9-step protocol with Tier-0 specialists |
| Large | 5+ files, cross-cutting | Marzneshin + Parallel Dispatch | Full CEO pattern + Two-Key |
| Epic | Multi-day project | Antigravity /teamwork-preview | Sentinel, Orchestrator, Workers, Gates |

## Step 1 -- Pre-Flight (Always Run)

1. State Sync: Read state/STATE.json -- verify kill_switch.verdict == running
2. Handoff Check: Read state/HANDOFF.md -- understand current context
3. Memory Recall: Query memwal for relevant past decisions
4. Knowledge Graph: Query graphify for codebase relationships

## Step 2 -- Superpowers Cycle (Always Active)

Regardless of tier, every task MUST follow:
brainstorming -> writing-plans -> test-driven-development -> systematic-debugging -> verification-before-completion

## Step 3 -- Layer Activation by Tier

### Tier Small -- Superpowers Only
1. Invoke brainstorming
2. Invoke writing-plans
3. Execute with TDD
4. Invoke verification-before-completion

### Tier Standard -- Marzneshin 9-Step
1. SYNC: state/STATE.json + killswitch
2. GAP SCAN: distance to DoD
3. CLAIM: lease in state/leases/
4. PLAN: max 7 steps with verifiable artifacts
5. SIM: test in sim/ first
6. EXECUTE: dispatch Tier-0 specialists via subagents
7. VERIFY: python3 scripts/verify.py
8. EMIT: receipt to receipts/
9. HANDOFF: rewrite state/HANDOFF.md

### Tier Large -- Full Parallel Dispatch
1. Follow 9-Step Protocol (Steps 1-5)
2. Build dependency graph between specialists
3. Dispatch independent specialists in PARALLEL (same response)
4. Wait for results then dispatch next stage
5. Run Two-Key Verification
6. Emit receipt with prev_receipt_hash
7. Rewrite HANDOFF.md

### Tier Epic -- Antigravity Native Teams
Recommend the user invoke /teamwork-preview or /goal for autonomous long-running execution.

## Step 4 -- MCP Enhancement Layer (Always Available)

| Server | Enhancement | When |
|--------|-------------|------|
| memwal | remember/recall decisions | Every session start/end |
| graphify | query codebase structure | Before planning |
| headroom | compress context | When context grows large |
| codeburn | track token costs | During parallel dispatch |
| kimi-moe | multi-model reasoning | Complex decisions |
| moxt | file operations | Cross-workspace tasks |

## Step 5 -- Post-Execution Gates

### Two-Key Verification (Standard+ tiers)
1. Key 1 (@qa-gate): python3 scripts/verify.py -- all 6 checks green
2. Key 2 (@adversarial-reviewer): Raw diff audit -- no metric gaming, no mock shortcuts

### Five Iron Rules (Always Enforced)
1. No changes without receipt (receipts/)
2. Every state change through canonical schemas
3. state/HANDOFF.md rewritten at every session end
4. Fail-closed kill switches (scripts/killswitch.py)
5. Sim harness verification before production

## Available Specialist Agents

### From marzneshin-orchestration (Tier-0)
- @config-engineer -- configs/**, canary rollouts (L2)
- @adversarial-reviewer -- cross-cutting review (L3 reject / L0 approve)
- @qa-gate -- qa/**, verification suites (L3)
- @security-compliance -- security/** (L1)
- @handoff-guardian -- state/HANDOFF.md, leases (L3)
- @infra-sre -- infra/** (L1)
- @analytics-engineer -- analytics/** (L2)

### From multi-agent-orchestration (Superpowers)
- @memory-architect -- src/functions/, src/state/, src/types.ts
- @mcp-tool-builder -- src/mcp/tools-registry.ts, src/mcp/server.ts
- @api-endpoint-builder -- src/triggers/api.ts, src/index.ts
- @hook-specialist -- src/hooks/
- @test-engineer -- test/, vitest.config.ts
- @consistency-guardian -- all files (read-only)
- @documentation-writer -- README.md, AGENTS.md, docs/

## Quick Reference

Task arrives -> Size classify -> Pre-flight -> Superpowers cycle ->
Layer activation -> MCP enhancement -> Post-execution gates -> Done

## Integration Points

This skill composes:
- marzneshin-orchestration -- project-specific CEO pattern
- multi-agent-orchestration -- Superpowers CEO pattern
- dispatching-parallel-agents -- parallel dispatch mechanics
- subagent-driven-development -- implement then review pipeline
- team-agent-orchestration -- Kanban-based team coordination
- plan-orchestrate -- ECC engine for plan-to-execution mapping
- orch-pipeline -- shared Research, Plan, TDD, Review, Commit engine
- council -- 4-voice decision-making under ambiguity
- teamwork -- Antigravity native multi-agent teams
- verification-before-completion -- final verification gate
