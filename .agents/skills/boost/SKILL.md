---
name: boost
description: "Activate on-demand multi-agent deep reasoning loops (/boost) in Google Antigravity to solve complex coding tasks, concurrency bugs, race conditions, intricate refactoring, and algorithmic challenges via decoupled investigation and implementation tiers."
---

# Boost Deep Reasoning (/boost)

Use this skill when tackling high-difficulty engineering tasks during interactive coding sessions where single-turn assistance falls short. Boost initiates an on-demand three-phase multi-agent reasoning pipeline that decouples strategy formulation from isolated execution and verification.

## When to Use

- **Concurrency & Race Conditions**: Multithreaded timing issues, deadlocks, cache synchronization bugs requiring trace reproduction and thread-safe design.
- **Algorithmic Problem Solving**: High-performance algorithms, custom data structures, graph traversals, or mathematical routines with rigorous boundary testing.
- **Non-Trivial Refactoring**: Refactoring tightly coupled modules, modernizing legacy interfaces, or converting synchronous APIs to asynchronous patterns across multiple files.
- **Deep Root-Cause Investigation**: Tracing execution paths across large codebases to isolate failure mechanisms without modifying production code.

## Three-Phase Reasoning Pipeline

```
[User / Session Prompt]
          │  /boost
          ▼
[Phase 1: Primary Orchestrator]
    Goal & Strategy Formulation ──► Decomposes challenge into verifiable subtasks
          │
          ▼
[Phase 2: Parallel Workstreams & Local Verification]
    ├─► [Deep Investigator] (Read-only call graphs, trace analysis, root cause)
    └─► [Deep Coder]        (Thread-safe code, algorithmic fixes, local tests)
          │
          ▼
[Phase 3: Synthesis & Delivery]
    Primary Orchestrator Runs Regression Checks
          │
      ┌───┴───────────────────────────────┐
      │ Tests Pass?                       │
      ├─────────────────┬─────────────────┤
      ▼ No              ▼ Yes
  [Auto-Correction]  [Delivery Summary]
  Feeds diagnostics  Verified changes presented
  back to iteration  to User
```

## Workstream Discipline

1. **Investigation Workstreams (`deep-investigator`)**:
   - Strictly read-only. Operates without modifying production code.
   - Traces call graphs using Graphify and AST tools.
   - Isolates minimal conditions to reproduce failures.
   - Delivers structured root-cause diagnostic reports to the orchestrator.

2. **Implementation Workstreams (`deep-coder`)**:
   - Constructs candidate code solutions with surgical precision.
   - Implements atomic primitives, concurrency guards, and optimized logic.
   - Enforces **Local Verification**: Builds targets and runs test suites locally prior to reporting completion.

3. **Automated Feedback Correction Loop**:
   - The Primary Orchestrator verifies combined results against complete test suites.
   - If any assertion fails or a regression is detected, the full diagnostic stack trace is automatically routed back into the next iteration loop for surgical repair.
