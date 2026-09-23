---
description: Run on-demand multi-agent deep reasoning loops for tricky concurrency bugs, race conditions, algorithmic challenges, and non-trivial refactoring.
argument-hint: "[complex bug / optimization task / refactoring goal]"
---

# Boost Deep Reasoning (/boost)

This workflow activates Google Antigravity's on-demand multi-agent deep reasoning pipeline.

## Workflow Execution Steps

1. **Phase 1: Goal & Strategy Formulation**:
   - Primary Orchestrator receives task and inspects workspace context.
   - Decomposes problem into discrete, verifiable subtasks.
   - Identifies required investigation and implementation workstreams.

2. **Phase 2: Parallel Execution & Local Verification**:
   - Dispatches `deep-investigator` for non-mutating call graph analysis and root-cause tracing.
   - Dispatches `deep-coder` for thread-safe fixes, algorithmic logic, and local test passes.

3. **Phase 3: Synthesis & Automated Feedback Correction**:
   - Primary Orchestrator runs full regression test suites.
   - If any assertion fails, error diagnostics are fed directly into the next iteration for autonomous repair.
   - Delivers concise, verified summary with passing test evidence.
