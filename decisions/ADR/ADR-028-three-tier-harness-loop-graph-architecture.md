# ADR-028: Three-Tier Harness-Loop-Graph Architecture & Graph-and-Loop Engineering Engine

**Date:** 2026-10-11  
**Status:** Accepted  
**Author:** Executive Project Manager & Chief Systems Architect  
**Workstream:** agentic-core / orchestration / verification / resilience  
**Governing Standard:** BUILD-SPEC.md v2.0, ADR-001, ADR-015, ADR-024, ADR-027  

---

## 1. Context & Reference Analysis

### Primary References:
1. **Reference 1: Hanako (@hanakoxbt)** — *Loops and Graphs: How to Stop Babysitting Agents and Only Approve the Last Step* (`https://x.com/hanakoxbt/status/2091515787366306154`):
   - Proposes the 4-layer taxonomy: Prompts $\to$ Agents $\to$ Loops $\to$ Graphs.
   - Introduces the 4 fundamental node types: Splitter, Worker, Code Node, Gate.
   - Defines the location of loops vs. graphs: *The loop lives inside a node; the graph lives between nodes.*
   - Defines the **Dual Return Paths**:
     - *Correction Edge (Short Return Path):* Rejects ONE failing unit back to the worker with exact reason, evidence, and strict scope. **Iron Rule:** *Return the unit, NOT the batch!*
     - *Learning Edge (Long Return Path):* Feeds derived constraints from accepted results back into the Splitter's brief for all subsequent runs.
   - Establishes **Blast-Radius Gating Policy** (Lane 1: Contained, Lane 2: Wide, Lane 3: Irreversible) over uncalibrated model confidence.

2. **Reference 2: beamnxw (@beamnxw)** — *Agent Harness Engineering vs. Loop Engineering vs. Graph Engineering* (`https://x.com/beamnxw/status/2081022966645535079`):
   - Deconstructs the conflated terms into three explicit tiers:
     - **Harness Engineering:** The execution environment around the model (tools, sandboxes, MCP, memory, state persistence, context injection, guardrails, killswitch).
     - **Loop Engineering:** Work-and-feedback cycles (verification loop with external graders, evidence-driven stopping rules, bounded retries).
     - **Graph Engineering:** Workflow topology (nodes, directed edges, state transitions, parallel fan-out/fan-in joins, deterministic branching).
   - Core mental model: $\text{Environment (Harness)} \longrightarrow \text{Feedback (Loop)} \longrightarrow \text{Flow (Graph)}$.
   - Diagnostic rubric matching operational failure symptoms to the responsible architectural tier.

3. **Reference 3: Dhairya Karekar (@dkare1009)** — *Andrej Karpathy's Stanford AI Engineering Lecture* (`https://x.com/dkare1009/status/2103764008801280248`):
   - Progression of AI systems: $10\% \text{ LLM} \to 30\% \text{ Prompt} \to 50\% \text{ Agent} \to 70\% \text{ Loop} \to 100\% \text{ Graph}$.
   - Engineering insight: AI engineering is not prompt tweaking; it is constructing robust systems around models (context, memory, tools, feedback loops, graph orchestration).

4. **Reference 4: Ryan Carter (@Grow_withAI)** — *Andrew Ng Masterclass on Graph Engineering* (`https://x.com/Grow_withAI/status/2107099305433780546`):
   - Methodical evolution: single agent $\to$ loop engineering $\to$ graph engineering $\to$ self-improving agents $\to$ full autonomous graph.

5. **Reference 5: ZaraAI (@ZaraAi56190)** — *Google Deep Dive into Graph Engineering* (`https://x.com/ZaraAi56190/status/2108018519803932822`):
   - Workflow graph mechanics: explicit node/edge topology, state machine semantics, continuous autonomous operation, and self-improving graphs.

---

## 2. Problem Statement

Prior agent implementations in the ecosystem suffered from five fatal architectural failure modes:
1. **Batch Destruction on Failure:** When 1 out of 4 subtasks failed verification, naive runners sent the entire batch back, destroying 3 correctly completed subtasks and causing non-deterministic divergence.
2. **Confidence-Score Hallucination:** Relying on LLM self-assessed "confidence" to gate actions allowed catastrophic actions (e.g. database drops) through because hallucinating models routinely rate themselves 0.95+ confident.
3. **Token Waste on Deterministic Transformations:** Running deduplication, sorting, ranking, schema validation, and diff-bounds checks through LLMs added latency (1-3s), financial cost, and hallucination risk to operations that have exact deterministic algorithmic solutions.
4. **Ephemeral Memory Amnesia:** Repeated runs encountered the exact same edge cases because accepted solutions only emitted output artifacts rather than compiling permanent architectural constraints.
5. **Conflated Architectural Vocabulary:** Engineers conflated harness setup (tools/prompts), loops (retries), and graphs (topologies), resulting in chaotic monolithic scripts with unclear separation of concerns.

---

## 3. Architectural Decisions

### D1: The Three-Tier Architectural Stack

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        TIER 3: GRAPH ENGINEERING                       │
│  (Topology, Control Flow, Blast-Radius Slicing, Parallel Fan-Out/In)  │
│  [Splitter Node] ──► [Parallel Workers] ──► [Code Node] ──► [Gate]   │
│         ▲                                                    │         │
│         └────────────── Learning Edge (Long) ────────────────┘         │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│                        TIER 2: LOOP ENGINEERING                        │
│   (Verification & Feedback Cycles INSIDE Nodes; Evidence over Conf)   │
│      produce ──► deterministic check ──► correct ──► repeat (<=3)      │
│      Correction Edge: Return the Unit, NOT the Batch!                  │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│                       TIER 1: HARNESS ENGINEERING                      │
│      (Execution Environment: Tools, Sandboxes, State, Memory, Guard)    │
│  AgentMemory · Graphify · Headroom · Killswitch · Stacking · Adapters │
└────────────────────────────────────────────────────────────────────────┘
```

1. **Harness Tier (Environment):** Managed by `adapters/`, `scripts/lib/`, `AgentMemory`, `Killswitch`, and MCP servers. Supplies the tools, durable storage, and security fences.
2. **Loop Tier (Feedback):** Lives **inside** individual nodes. Wraps agent actions with deterministic evaluators (`pytest`, `verify.py`, schema checks) and bounded retries ($\le 3$).
3. **Graph Tier (Flow):** Orchestrates relationships **between** nodes. Defines fan-out, fan-in joins, deterministic code transforms, gating, and return paths.

### D2: Four Specialized Node Types
- **Splitter Node (`splitter_node`):** Slices objectives along blast-radius dimensions, injects accumulated permanent learning constraints, and sets strict file scopes.
- **Worker Nodes (`coder_node`, `reviewer_node`):** Run in isolated ephemeral contexts, executing bounded internal loops until deterministic test pass or cap.
- **Code Node (`code_node`):** Executes pure deterministic operations (deduplication, ranking, schema checks, diff bounds, result merging) with **ZERO LLM tokens and ZERO variance**.
- **Gate Node (`gate_node`):** Enforces 3-lane blast-radius gating policy, issues unit-level correction payloads, and derives permanent architectural constraints.

### D3: Three-Lane Blast Radius Gating Policy
- **Lane 1: Contained & Reversible:** Isolated files, helper modules, unit tests. Requires deterministic test pass + diff bounds. Autonomous **GREEN**.
- **Lane 2: Wide & Reversible:** Shared libraries, schemas, core configs. Requires deterministic pass + sibling slice non-regression. Autonomous **GREEN**.
- **Lane 3: Irreversible & Critical:** Migrations, state resets, secret modifications, financial operations. **BLOCKED by default (§4 Fail-Closed)** until explicit Two-Key / human approval is provided.

### D4: Dual Return Paths Protocol
1. **Correction Edge (Short Return Path):**
   - **Rule:** *Return the unit, NOT the batch!*
   - Returns ONLY the rejected unit with:
     * `task_id`
     * `verdict: "RED"`
     * `reason`
     * `verdict_evidence` (exact test traceback/assertion)
     * `scope_constraint` (single-file boundary)
     * `attempts` (incremented, capped at 3)
2. **Learning Edge (Long Return Path):**
   - Extracts permanent engineering rules from verified green units.
   - Persists into `state["learned_constraints"]`.
   - Injected into the Splitter's brief for all subsequent runs, permanently preventing recurring errors.

### D5: Canonical Code & Interface Realization
- **L0 Adapter:** `adapters/graph_loop.py` (`GraphLoopAdapter`, capabilities: `run_pipeline`, `evaluate_gate`, `execute_code_transform`, `get_learned_constraints`).
- **Graph State & Workflow:** `agents/graph_state.py` and `agents/langgraph_workflow.py` (checkpointed in SQLite).
- **CLI Utility:** `scripts/graph_engine.py` (`run`, `gate`, `constraints`).
- **MCP Server:** `scripts/langgraph_mcp.py` exposed in `.mcp.json`.
- **Skill:** `.agents/skills/graph-loop-engineering/SKILL.md`.

---

## 4. Operational Invariants & Safeguards

1. **Fail-Closed (§4):** If the killswitch is engaged or heartbeat is stale, graph execution halts immediately. Lane 3 actions are permanently blocked without Two-Key authorization.
2. **Zero-Variance Principle:** Any operation that can be described without subjective words (*judge, assess, summarize*) MUST be executed in a deterministic Code Node without LLM invocation.
3. **Unit Isolation:** Workers must execute in isolated context windows to prevent groupthink convergence across parallel auditors.
4. **Bounded Convergence:** Unit correction attempts are strictly capped at 3. Beyond 3 attempts, the task is marked `UNRESOLVED` and escalated to human oversight.

---

## 5. Verification & Evidence

- **Unit & Engine Tests:** `pytest tests/test_graph_loop_adapter.py tests/test_graph_loop_engine.py` (8/8 tests passed, 100% green).
- **Quality Gates:** `python3 scripts/verify.py --all` (6/6 checks green).
- **Integration CLI Proof:** `python3 scripts/graph_engine.py constraints` and `python3 scripts/graph_engine.py gate` executed successfully.
