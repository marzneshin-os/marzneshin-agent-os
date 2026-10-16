---
name: boost
description: Deep reasoning, red-teaming, and recursive verification loop. Use when user invokes /boost, asks for deep analysis, or needs rigorous architecture adjudication.
metadata:
  short-description: Deep reasoning & multi-perspective adjudication loop
---

# 🚀 Boost Reasoning Engine

Activate this skill when the user types `/boost` or requests deep analysis, stress-testing, or adversarial validation.

## When to Use
- When facing complex architectural decisions or high-risk refactoring.
- When debugging subtle race conditions, state corruption, or memory leaks.
- When validating changes against the project's Consistency Constitution.

## The 5-Phase Boost Protocol

### Phase 1: Explore & Challenge Assumptions (Red Teaming)
- Surface unstated assumptions and edge cases.
- Attack proposed solutions from multiple failure angles (network partition, schema drift, race conditions).
- Check against Karpathy guidelines: Is this minimal? Are we overcomplicating?

### Phase 2: Architectural Invariants & Consistency
- Map affected boundaries:
  - If touching MCP Tools: enforce 8-file atomic update.
  - If touching REST API: enforce 3-file atomic update.
  - If bumping version: enforce 7-file atomic update.
- Ensure TypeScript ESM compliance (`"type": "module"`).

### Phase 3: Tradeoff Analysis
- Contrast at least two competing architectural designs.
- Evaluate blast radius, maintainability, and token/performance overhead.

### Phase 4: Proof of Correctness & TDD Specification
- Formulate exact Vitest assertions before writing implementation code.
- Enforce the RED -> GREEN -> REFACTOR cycle.

### Phase 5: Synthesis & Decision Recording
- Record settled decisions, rationale, and file paths using `memwal_remember`.
- Document lessons learned and update `state/HANDOFF.md`.
