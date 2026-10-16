---
name: graph-loop-engineering
description: Graph & Loop Engineering for Marzneshin Autonomous OS. Implements the 4-layer taxonomy (Prompts -> Agents -> Loops -> Graphs), 4 node types (Splitter, Worker, CodeNode, Gate), 3-lane blast radius policy, and dual return paths (unit-level correction edge & learning edge).
---

# 🕸️ Graph & Loop Engineering (4-Layer Multi-Agent Runtime)

## 📌 Architectural Overview

Graph & Loop Engineering replaces monolithic prompt stuffing with a structured 4-layer taxonomy:
$$\text{Prompts} \longrightarrow \text{Agents} \longrightarrow \text{Loops} \longrightarrow \text{Graphs}$$

- **Prompts**: Bounded single-task instructions.
- **Agents**: Model + local toolset in an isolated context window.
- **Loops** (Inside Nodes): Deterministic verification loop (`produce -> check -> correct -> repeat until green`).
- **Graphs** (Between Nodes): Defines what runs in parallel, dependencies, deterministic code transforms, gating, and return paths.

---

## 🧩 The Four Node Types

| Node Type | Responsibility | Execution Mechanism | LLM Cost |
|---|---|---|---|
| **Splitter** | Slices objectives along blast-radius dimensions, injects learned constraints, and sets strict file scopes. | `splitter_node` | 1 bounded call or deterministic fallback |
| **Worker (Coder / Reviewer)** | Operates in an isolated ephemeral session, executing internal loop until test green or capped. | `coder_node` / `reviewer_node` | Bounded |
| **Code Node** | Pure deterministic operations (deduplication, ranking, schema check, diff bounds, result merging). | `code_node` (`agents/code_nodes.py`) | **0 Tokens (Zero Variance)** |
| **Gate** | Evaluates unit results against blast radius and reversibility. Rejects units (never batches) and records learnings. | `gate_node` (`agents/gate_nodes.py`) | **0 Tokens (Deterministic Checks First)** |

---

## 🛡️ Three-Lane Blast Radius Gating Policy

Do **NOT** gate on model confidence scores. Gate strictly on blast radius:

1. **Lane 1: Contained & Reversible** (`contained`):
   - Scope: Isolated tests, helper functions with unit test coverage, documentation.
   - Requirement: Test exit code 0 + zero scope creep outside target files.
   - Outcome: Autonomous **GREEN**.

2. **Lane 2: Wide & Reversible** (`wide`):
   - Scope: Shared utility modules, core schemas, cross-cutting configs.
   - Requirement: Deterministic test pass + clean trajectory (no regressions in sibling slices).
   - Outcome: Autonomous **GREEN**.

3. **Lane 3: Irreversible & Critical** (`irreversible`):
   - Scope: Production database migrations, state resets, secret updates, financial operations.
   - Requirement: Explicit Two-Key verification or human authorization.
   - Outcome: **BLOCKED by default (Fail-Closed §4)** until approved.

---

## 🔁 The Two Return Paths

### 1. Correction Edge (Short Return Path)
> **IRON RULE: Return the unit, NOT the batch!**
When 1 unit out of 4 fails, returning the entire batch forces 3 correct units to be rewritten, causing non-deterministic divergence.
- The Gate emits **only** the failing unit.
- Payload includes:
  - `task_id`
  - `verdict: "RED"`
  - `reason`
  - `verdict_evidence` (exact failed assertion / line)
  - `scope_constraint` (strict boundary)
  - `attempts` (incremented, capped at 3)

### 2. Learning Edge (Long Return Path)
- Verified green results produce a permanent derived constraint.
- Constraint is appended to `state["learned_constraints"]` and persisted.
- Future Splitter nodes automatically inject these constraints into the briefs of upcoming runs, preventing recurrent mistakes.

---

## 🛠️ Cross-Agentic Tool Usage

### MCP Tools (Antigravity, Claude Code, OpenCode)
- `start_graph_pipeline`: Dispatches full Graph & Loop cycle.
- `evaluate_unit_gate`: Programmatic gate evaluation.
- `query_learning_constraints`: Inspects active learned rules.

### CLI Usage
```bash
# Run a pipeline
python3 scripts/graph_engine.py run --objective "Fix redirect in gateway/auth.py"

# Evaluate a unit gate
python3 scripts/graph_engine.py gate --task-id "T-1" --blast-radius "contained" --tests-passed

# Query permanent constraints
python3 scripts/graph_engine.py constraints
```
