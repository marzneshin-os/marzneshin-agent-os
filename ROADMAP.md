# Marzneshin Agent OS - Roadmap & System Thinking Map

## System Thinking Map (نقشه تفکر سیستمی)

The Marzneshin Agent OS operates as a fully autonomous, parallel multi-agent system. The holistic dynamics of the system ensure that every code modification is context-aware, rigorously tested, and automatically healed in case of failure.

### Core System Dynamics

```mermaid
graph TD
    %% Core Inputs
    Goal[User Goal / Trigger] --> Runner[Autonomous Runner CLI]
    
    %% Orchestration
    Runner --> Super[Supervisor Node]
    Mem[(AgentMemory)] -.->|Retrieves Context| Super
    Graph[(Graphify)] -.->|Architecture Query| Super

    %% Parallel Fan-Out
    Super -->|TaskSpecs| Router{Parallel Router}
    Router -->|Dispatch| Coder[Coder Subagent]
    Router -->|Dispatch| Coder2[Coder Subagent n]
    Router -->|Dispatch| Reviewer[Reviewer Subagent]
    
    %% Workers Operation
    Coder -->|Execute Tools| CodeBase[(Workspace)]
    Coder2 -->|Execute Tools| CodeBase
    Reviewer -->|Run verify.py| CodeBase

    %% Fan-In
    Coder -->|TaskResult| Aggregator[Aggregator Node]
    Coder2 -->|TaskResult| Aggregator
    Reviewer -->|TaskResult| Aggregator

    %% Feedback Loop
    Aggregator -->|Synthesize| LoopCheck{Goal Met?}
    LoopCheck -->|No (Failures)| Super
    LoopCheck -->|Yes| End((End & Handoff))

    %% WebCMD Optimization
    WebMem[(WebCMD Browser Memory)] -.->|90% Reduced DOM & Sitemaps| Coder
    WebMem -.->|90% Reduced DOM & Sitemaps| Coder2
    Coder -.->|Stealth Fetch & Learn| Web[(External Web / Docs)]
    Web -.->|DOM Semantic Reduction| WebMem

    %% System Guards
    Watchdog[Watchdog / Killswitch] -.- CodeBase
    Watchdog -.->|Fails Closed on Timeout| Runner
```

### Components

1. **Autonomous Runner (`scripts/autonomous_runner.py`)**: The entry point for one-click autonomous execution. Emits a cryptographic receipt upon green completion.
2. **Supervisor**: Analyzes goals, reads from `AgentMemory` and `Graphify` to understand the overarching system, and decomposes the goal into parallelizable `TaskSpecs`.
3. **Parallel Dispatcher**: Routes tasks concurrently to instances of the Coder and Reviewer nodes.
4. **Coder**: An isolated worker that receives a specific task, accesses necessary tools (`read_workspace_file`, `write_workspace_file`, `run_terminal_command`), and executes changes.
5. **Reviewer**: A quality-gate worker that validates structural integrity and runs verification suites (`python3 scripts/verify.py --all`).
6. **Aggregator**: Consolidates results from parallel workers, preventing context bloat.
7. **Watchdog / Killswitch**: A fail-closed daemon that monitors agent activity and aborts operations if health invariants (e.g., maximum lease time) are breached.
8. **WebCMD Browser Memory Layer (`scripts/lib/webcmd_memory.py` & `adapters/webcmd.py`)**: A persistent self-learning memory layer that caches domain navigation graphs, maps interactive action selectors, and reduces web browsing token consumption by up to 90% across Antigravity, Claude Code, OpenCode, and LangGraph fleets.

9. **AWS Bedrock Promotional Credit Pool & Zero-Cost Guardrail Engine (`scripts/lib/aws_bedrock_credits.py` & `adapters/aws_bedrock.py`)**: Multi-account promotional credit pool leveraging AWS Builder ID onboarding grants ($100-$200/account) for zero-cost foundation model execution (Claude 3.5 Sonnet, Llama 3.3, Mistral) with strict fail-closed safety buffer ($5.00), 180-day grant expiration fencing, and resource teardown governance.

## Roadmap

- [x] Phase 1: Shared-context single-thread loop.
- [x] Phase 2: Isolation of Subagent State (Task-Result paradigm).
- [x] Phase 3: Parallel Fan-Out / Fan-In with LangGraph `Send`.
- [x] Phase 4: Operational Autonomous Tools integration.
- [x] Phase 5: Deep Graphify Integration for God Nodes and Impact Analysis.
- [x] Phase 6: Cloud/Edge distributed worker deployment.
- [x] Phase 7: Cross-Agentic WebCMD Self-Learning Browser Memory Layer (90% Token Reduction & Navigation Sitemaps).
- [x] Phase 8: Google Antigravity Account Doctor, Eligibility Remediation & Health Recovery (ADR-025).
- [x] Phase 9: Grounded Notebook Knowledge Engine — Synthesizing NotebookLM Citation Grounding with Antigravity Autonomous Execution (ADR-026).
- [x] Phase 10: System 1 Typed Decisions & Jev+Claude Stacking Engine — 440x Cheaper Fast-Path Non-Autoregressive Routing & Guardrail Gating (ADR-027).
- [x] Phase 11: Three-Tier Harness-Loop-Graph Engineering — 4-Node Taxonomy (Splitter, Worker, CodeNode, Gate), 3-Lane Blast-Radius Gating & Dual Return Paths (ADR-028).
- [x] Phase 12: AWS Bedrock Promotional Credit Pool & Zero-Cost Guardrail Engine — Multi-Account Builder ID Grants ($100-$200/account), 6-Month Expiration Fencing & Resource Teardown Governance (ADR-029).
