# ADR-026: Grounded Notebook Knowledge Engine (Synthesizing NotebookLM and Antigravity Paradigms)

**Date:** 2026-10-10  
**Status:** Accepted  
**Author:** Executive Project Manager & Chief Systems Architect  
**Workstream:** agentic-core / knowledge-grounding / autonomous-execution  
**Governing Standard:** BUILD-SPEC.md v2.0, ADR-001, ADR-015, ADR-022, ADR-024, ADR-025  

---

## 1. Context & Reference Analysis

### Primary Reference:
- **Source:** Liam Turner (@liam_turner_ai, Oct 4, 2026) — *NotebookLM vs Antigravity*
- **URL:** `https://x.com/liam_turner_ai/status/2106551861692231883`
- **Core Premise:** One helps you explore and understand information. The other turns your ideas into real action. Which one is better for your workflow?
  - **NotebookLM:** Research assistant, upload documents/PDFs/notes, simplify complex topics, summarize, ask questions, discover insights, organize research. *Research -> Understand -> Learn*.
  - **Antigravity:** AI-powered creation, development, workflows, goal execution, building. *Set a goal -> Let AI help you get things done*.
  - **The Unifying Shift:** *Information -> Understanding -> Creation -> Execution*. The future belongs to smarter AI workflows that bridge grounded knowledge exploration and autonomous action.

### Relevance to Marzneshin Agent OS:
1. **The System Divide:**
   - Marzneshin Agent OS features a powerful autonomous execution layer (Antigravity paradigm: LangGraph worker nodes, MCP servers, adapters, terminal commands).
   - However, agents operating autonomously often suffer from 'action without grounding' — hallucinating API surfaces, misremembering BUILD-SPEC constraints, making changes based on ungrounded assumptions, or drifting from project specifications.
2. **The Missing Primitive:**
   - Marzneshin lacks an integrated, citation-grounded knowledge notebook engine that enables agents to ingest workspace documents (ADRs, specs, guidelines, schemas, code modules), generate deterministic line-anchored citations, query knowledge with strict source attribution, synthesize multi-source evidence, and run adversarial verification against hallucinated claims.
3. **The Architectural Bridge:**
   - By creating the **Grounded Notebook Knowledge Engine**, we inject NotebookLM-grade evidence grounding directly into the Antigravity-grade execution loop of Marzneshin Agent OS.

---

## 2. Architectural Decisions

### D1: Core Shared Library (`scripts/lib/grounded_notebook.py`)
- Standard library only (`json`, `hashlib`, `re`, `pathlib`, `typing`, `dataclasses`, `math`). Strictly compliant with `scripts/verify.py --lint-imports`.
- Clock-disciplined via `scripts.lib.clock` (`scripts/verify.py --lint-clock`).
- Deterministic chunking: Paragraph- and line-aware chunking preserving 1-indexed line spans (`start_line`, `end_line`) and SHA-256 content hashes.
- Citation-grounded retrieval: Token matching scoring relevance, returning explicit citations in `[source_id#Lstart-Lend]` format with verification hashes.
- Grounding verification: Evaluates candidate claims against indexed source chunks, computing a grounding confidence score, returning supporting citations or identifying unsupported aspects.
- Path traversal protection: Enforces sandbox boundaries, rejecting paths outside allowed roots.
- Durability: Persists notebooks to `state/notebooks/<notebook_id>.json` with full audit metadata.

### D2: L0 System Adapter (`adapters/grounded_notebook.py`)
- Inherits from `adapters.base.Adapter` (BUILD-SPEC.md v2.0 §4).
- Exposes capabilities:
  - `create_notebook`: Initializes an isolated or task-scoped notebook.
  - `ingest_sources`: Ingests files or textual content into the notebook with chunking.
  - `grounded_query`: Returns ranked, citation-anchored chunks for a question.
  - `synthesize_sources`: Cross-references multiple documents on a topic with source attribution.
  - `verify_grounding`: Adversarial fact-check of a statement against indexed sources.
  - `list_notebooks`: Lists available knowledge notebooks.
  - `get_notebook`: Fetches notebook summary and source manifests.
- Idempotency per declared class (`forever` for creation/ingestion).
- Circuit breaker (5 consecutive errors -> open 60s) and hard deadlines.
- Real `dry_run` support: Simulates chunking/querying without state writes.

### D3: Simulation Fake (`sim/fakes/grounded_notebook.py`)
- In-memory fake passing all 9 checks (C1–C9) of `adapters.contract.run_contract`.
- Enables deterministic, offline testing of simulation scenarios.

### D4: CLI & MCP Server Exposure
- CLI: `scripts/grounded_notebook_cli.py` providing subcommands (`create`, `ingest`, `query`, `synthesize`, `verify`, `list`).
- MCP Server: `scripts/mcp_grounded_notebook.py` registered in root `.mcp.json`.
- LangGraph worker tools: Registered in `agents/graph_nodes.py` as `grounded_notebook_query` and `grounded_notebook_verify` so coding and reviewing agents can verify source specs before making code changes.

### D5: Cross-Agent Governance & Skills
- Agent skills in `.agents/skills/grounded-notebook/SKILL.md` and `.claude/skills/grounded-notebook/SKILL.md`.
- System rules in `.agents/rules/grounded-notebook.md` and `.cursor/rules/grounded-notebook.mdc`.

---

## 3. System-Thinking Map & Data Flow

```text
External Documents & Specs (Markdown, ADRs, Code, Configs)
                           │
                           ▼
          ┌───────────────────────────────────┐
          │     Grounded Notebook Engine      │
          │   scripts/lib/grounded_notebook   │
          └───────────────────────────────────┘
              │                           │
  Deterministic Chunking          Citation Anchors
  & Content Fingerprinting     [doc#L12-L45, sha256]
              │                           │
              └─────────────┬─────────────┘
                            ▼
          ┌───────────────────────────────────┐
          │  L0 Adapter & Simulation Fake     │
          │    adapters/grounded_notebook     │
          │    sim/fakes/grounded_notebook    │
          └───────────────────────────────────┘
              │                           │
         Contract C1-C9            Real Dry-Run &
        Full Verification           Circuit Breaker
              │                           │
              └─────────────┬─────────────┘
                            ▼
      ┌───────────────────────────────────────────┐
      │          Unified Interfaces               │
      │  CLI: scripts/grounded_notebook_cli.py    │
      │  MCP: scripts/mcp_grounded_notebook.py    │
      └───────────────────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
┌───────────────────────────┐ ┌───────────────────────────┐
│  LangGraph Worker Agents  │ │    Cross-Agent Editors    │
│  - coder_node (Grounding) │ │  (Antigravity, Claude,    │
│  - reviewer_node (Verify) │ │   Cursor, Windsurf)       │
└───────────────────────────┘ └───────────────────────────┘
              │                           │
              └─────────────┬─────────────┘
                            ▼
     "Information → Understanding → Creation → Execution"
```

---

## 4. Verification & Two-Key Review Strategy

1. **Key 1 (QA Verification):**
   - Unit tests in `tests/test_grounded_notebook.py`.
   - Contract tests in `tests/test_grounded_notebook_adapter.py` running `run_contract` on both fake and adapter.
   - Zero CI regressions on `python3 scripts/verify.py --all` (all 6 checks green).
2. **Key 2 (Adversarial Review):**
   - Strict audit of path traversal sanitization.
   - Verification of clock discipline (zero direct wall-clock calls).
   - Verification of dry-run mutation isolation.
