# Autonomous Campaign & Lineage Workspace Engine (TopView AI Capability Integration)
## System-Level Architectural Specification & Implementation Design

- **Status**: Proposed / Approved by User (Approach A)
- **Author**: Antigravity Assistant & Superpowers Architect
- **Target Project**: `agentmemory` v0.9.29 / `marzneshin-agent-os`
- **Specification Date**: 2026-09-30

---

## 1. Video Analysis & Capability Deconstruction

### 1.1 Source & Demonstration Summary
- **Source Video**: YouTube Short `rgSR8ggOwV4` by InsiderForce (*"This Claude MCP Tool Replaces Your Entire Marketing Stack in One Workspace - TopView AI MCP"*).
- **Core Technology**: TopView AI MCP integration in Claude Code / Cursor / AI Assistants.
- **Trigger**: Ingestion of a single product/project asset (e.g. uploading an image or product spec) with the simple prompt: *"Launch a campaign for this"*.
- **Orchestration**: Automatically dispatches a 3-agent autonomous specialist pipeline:
  1. **Market Intelligence & Trend Agent**: Reads real-time market trends, viral formats, and competitor benchmarks from social and commerce channels (TikTok, YouTube, Amazon).
  2. **Strategy & Audience Synthesis Agent**: Formulates complete marketing strategy, target personas, hook angles, and creative content briefs.
  3. **Creative Production Engine**: Generates scripts, image concepts, visual prompts, and video creative assets from leading models.
- **Interface & Lineage**: The entire output lands in a unified interactive **Campaign Workspace & Canvas**:
  - *"Every insight next to the strategy it inspired."*
  - *"Every strategy next to the creative it produced."*
  - Complete bi-directional provenance, trace links, and side-by-side inspection.

### 1.2 The Problem It Solves
- **Fragmented Tooling**: In traditional setups, trend research, strategy writing, asset prompting, and memory retention happen across disconnected tools and tabs.
- **Loss of Lineage**: Marketers and autonomous agents lose the context of *why* an asset was generated, *which* strategic angle it targets, and *what* market insight motivated that angle.
- **Friction in Multi-Agent Delegation**: Users typically have to manually prompt multiple separate agents and stitch their outputs together.

### 1.3 Technical Capability Required in `agentmemory` / `marzneshin-agent-os`
1. **Asset Ingestion & Multimodal Anchor**: Accept an asset (image path/hash via `image-store.ts`, URL, or product document) and instantiate a `Campaign` entity.
2. **Three-Tier Specialist Pipeline Execution**:
   - `Phase 1: Intelligence / Insights Extraction` (trends, audience signals, competitor angles).
   - `Phase 2: Strategy & Brief Formulation` (core value prop, target segments, creative hooks).
   - `Phase 3: Creative Asset Generation` (ad copy, visual concepts, video scripts, asset prompts).
3. **Graph Lineage & Provenance**: Link `Insight` -> `Strategy` -> `Creative` nodes in the `agentmemory` knowledge graph with typed relations (`INSPIRED_BY`, `GENERATED_FROM`).
4. **Interactive Campaign Canvas in Viewer Dashboard**: Provide a visual canvas layout in `agentmemory`'s web dashboard (port 3113) that renders the column-based cards (Insights | Strategies | Creatives) with interactive lineage connectors.
5. **Universal Tool Surface**: Expose the capability via MCP tools (`memory_campaign_create`, `memory_campaign_get`, `memory_campaign_list`, `memory_campaign_canvas`) and REST endpoints (`/agentmemory/campaigns/*`) accessible across Antigravity, Claude Code, and OpenCode.

---

## 2. Existing Project Architecture Analysis

### 2.1 Core Framework & Primitives
- **Engine**: Built exclusively on `iii-engine` (Worker / Function / Trigger architecture).
  - All operations register as `sdk.registerFunction("mem::...", handler)`.
  - All state persists via `StateKV` (`kv.get`, `kv.set`, `kv.list`, `kv.delete`).
  - Underlying database is SQLite via iii-engine's `StateModule` (`./data/state_store.db`).
- **MCP Server**:
  - `src/mcp/tools-registry.ts`: Tool definitions + `getAllTools()`.
  - `src/mcp/server.ts`: JSON-RPC tool dispatch switch/case.
  - `src/mcp/standalone.ts`: Stdio MCP server for CLI tools.
- **REST Layer**:
  - `src/triggers/api.ts`: 130 endpoints on port 3111 with token authentication (`checkAuth`).
- **Multimodal & Image Subsystem**:
  - `src/utils/image-store.ts`: Local content-addressable storage (`SHA-256` hashing, validation, disk quotas).
  - `src/functions/vision-search.ts`: Image embeddings via CLIP / local / OpenAI vision models (`mem::vision-embed`, `mem::vision-search`).
- **Graph & Knowledge Representation**:
  - `src/functions/graph.ts`: Bi-directional relation graph (`mem::graph-link`, `mem::graph-query`, `mem::graph-traverse`).
- **Dashboard & Presentation**:
  - `src/viewer/server.ts` & `src/viewer/index.html`: Web dashboard on port 3113 with SVG/DOM graph, search, timeline, and audit logs.
- **Agent Orchestration**:
  - `.agents/skills/marzneshin-orchestration/`: Tier 0 specialist agents.
  - `.agents/skills/multi-agent-orchestration/`: CEO pattern subagent dispatch.

---

## 3. Architectural Location & Integration Point

### 3.1 Correct Layer
The capability belongs in the **Shared Core Functions Layer** of `agentmemory`:
- **Function Implementation**: `src/functions/campaign.ts` (`mem::campaign-orchestrate`, `mem::campaign-get`, `mem::campaign-list`, `mem::campaign-canvas`).
- **State Layer**: `src/state/schema.ts` (`KV.campaigns = "campaigns"`) and `src/types.ts` (`Campaign`, `CampaignInsight`, `CampaignStrategy`, `CampaignCreative`).
- **Graph Lineage**: Uses existing `mem::graph-link` to establish bi-directional edges in `KV.graphNodes` and `KV.graphEdges`.
- **Viewer / Canvas Presentation**: Extends `src/viewer/index.html` with a Canvas view and `src/viewer/server.ts` with `/api/campaigns/canvas` data endpoint.
- **MCP Interface**: Exposes 4 new MCP tools in `src/mcp/tools-registry.ts` and `src/mcp/server.ts`.
- **REST Interface**: Exposes 4 new REST endpoints in `src/triggers/api.ts`.
- **Audit & Governance**: Records operations via `recordAudit(kv, "campaign_create")`.

### 3.2 Architectural Boundary
```
┌────────────────────────────────────────────────────────────────────────┐
│                   Agentic Coding Environments                          │
│   [ Claude Code ]          [ Antigravity IDE ]          [ OpenCode ]   │
└────────────┬────────────────────────────┬──────────────────────────────┘
             │                            │
             │ stdio / SSE (MCP)          │ HTTP POST (REST)
             ▼                            ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        agentmemory Boundary                            │
│  ┌──────────────────────┐              ┌───────────────────────────┐   │
│  │   src/mcp/server.ts  │              │    src/triggers/api.ts    │   │
│  │   memory_campaign_*  │              │    /agentmemory/campaigns │   │
│  └──────────┬───────────┘              └─────────────┬─────────────┘   │
│             │                                        │                 │
│             └───────────────────┬────────────────────┘                 │
│                                 │ sdk.trigger()                        │
│                                 ▼                                      │
│                  ┌─────────────────────────────┐                       │
│                  │  src/functions/campaign.ts  │                       │
│                  │  mem::campaign-orchestrate  │                       │
│                  └──────────────┬──────────────┘                       │
│                                 │                                      │
│         ┌───────────────────────┼───────────────────────┐              │
│         ▼                       ▼                       ▼              │
│  ┌──────────────┐        ┌──────────────┐        ┌──────────────┐      │
│  │ Phase 1:     │        │ Phase 2:     │        │ Phase 3:     │      │
│  │ Intelligence │───────>│ Strategy     │───────>│ Creative     │      │
│  │ & Insights   │        │ & Briefs     │        │ Generation   │      │
│  └──────────────┘        └──────────────┘        └──────────────┘      │
│         │                       │                       │              │
│         └───────────────────────┼───────────────────────┘              │
│                                 ▼                                      │
│                  ┌─────────────────────────────┐                       │
│                  │      State & Knowledge      │                       │
│                  │  • KV.campaigns (Store)     │                       │
│                  │  • Graph (Lineage Edges)    │                       │
│                  │  • image-store (Assets)     │                       │
│                  └──────────────┬──────────────┘                       │
│                                 │                                      │
│                                 ▼                                      │
│                  ┌─────────────────────────────┐                       │
│                  │  src/viewer/ (Port :3113)   │                       │
│                  │  Side-by-Side Canvas Tab    │                       │
│                  │  Insights | Strategy | Ads  │                       │
│                  └─────────────────────────────┘                       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Component Extension vs. Creation

| Component | Action | Rationale |
|-----------|--------|-----------|
| `src/state/schema.ts` | **Extend** | Add `campaigns: "campaigns"` to `KV` object. |
| `src/types.ts` | **Extend** | Add `Campaign`, `CampaignInsight`, `CampaignStrategy`, `CampaignCreative` interfaces and `campaign_create` to `AuditEntry.operation`. |
| `src/utils/image-store.ts` | **Reuse** | Ingest and validate uploaded product images without modifying image hashing or store logic. |
| `src/functions/graph.ts` | **Reuse** | Link nodes (`Insight -> Strategy -> Creative`) using existing graph primitives. |
| `src/functions/campaign.ts` | **Create** | Dedicated clean module containing orchestrator logic and state management. |
| `src/viewer/server.ts` & `index.html` | **Extend** | Add Canvas tab rendering cards with lineage arrows. |
| `src/mcp/tools-registry.ts` & `server.ts` | **Extend** | Register and handle 4 campaign MCP tools. |
| `src/triggers/api.ts` | **Extend** | Register REST endpoints for campaigns. |
| `src/index.ts` | **Extend** | Register campaign functions and update endpoint/tool counts. |

---

## 5. Dependency & Impact Analysis

### 5.1 Inbound & Outbound Dependencies
- **Calls**:
  - `kv.get`, `kv.set`, `kv.list` in `src/state/kv.ts`.
  - `sdk.trigger("mem::graph-link", ...)` for lineage links.
  - `recordAudit(kv, ...)` for tamper-evident audit logging.
  - `resolveProvider()` for LLM-based intelligence/creative generation (fallback to deterministic heuristics when no provider API key is configured).
- **Called By**:
  - MCP handlers: `memory_campaign_create`, `memory_campaign_get`, `memory_campaign_list`, `memory_campaign_canvas`.
  - REST API: `POST /agentmemory/campaigns/create`, `GET /agentmemory/campaigns/get`, `GET /agentmemory/campaigns/list`, `GET /agentmemory/campaigns/canvas`.
  - Viewer: HTTP GET `/api/campaigns/canvas`.

### 5.2 Failure & Degraded Modes
- If no LLM API key is present: The system gracefully generates structured baseline campaign heuristics (zero-LLM mode, consistent with `agentmemory`'s design).
- If an invalid image is provided: Validation returns descriptive 400 error without corrupting state.
- If graph linking fails: Campaign state is still saved; audit logs the partial failure.

---

## 6. Side-Effect Analysis

1. **Functional**:
   - Zero breaking changes to existing memory, graph, or search tools.
   - All 1,710 existing tests continue to pass.
2. **Architectural**:
   - Strictly conforms to iii-engine primitives. No bypasses, no separate database.
   - No cyclic dependencies.
3. **Operational**:
   - Storage overhead: minimal (lightweight JSON records in SQLite `state_store.db`).
   - Memory overhead: negligible (stateless function execution).
4. **Security**:
   - All REST endpoints strictly guarded by `checkAuth(req, secret)`.
   - Whitelist validation on all input fields in `src/triggers/api.ts` and `src/mcp/server.ts`.
5. **Cross-Agent**:
   - Works identically in Antigravity, Claude Code, OpenCode, and Cursor via standardized MCP JSON-RPC and REST.

---

## 7. Consistency Rules Checklist (from `AGENTS.md`)

When adding these MCP tools and REST endpoints:
1. `src/state/schema.ts` — add `campaigns: "campaigns"` to `KV`
2. `src/types.ts` — add interfaces and audit operation
3. `src/functions/campaign.ts` — implement core function logic
4. `src/mcp/tools-registry.ts` — add 4 tool definitions to `getAllTools()`
5. `src/mcp/server.ts` — add 4 switch cases
6. `src/triggers/api.ts` — add 4 REST endpoints
7. `src/index.ts` — register functions + update log line counts (54 -> 58 tools, 130 -> 134 endpoints)
8. `test/mcp-standalone.test.ts` — update tool count assertion (54 -> 58)
9. `README.md` — update tool and endpoint counts
10. `plugin/.claude-plugin/plugin.json` — update tool count
11. `plugin/plugin.json` and `plugin/.mcp.copilot.json` — update tool count
12. New test file: `test/campaign.test.ts` with comprehensive unit and integration coverage.

---

## 8. Definition of Done & Acceptance Criteria

- [ ] All types and KV schemas defined.
- [ ] `src/functions/campaign.ts` registered with iii-engine.
- [ ] Lineage graph links (`Insight -> Strategy -> Creative`) automatically created.
- [ ] Viewer dashboard includes the interactive Campaign Canvas tab.
- [ ] MCP tools registered and callable via stdio / SSE.
- [ ] REST endpoints registered with authentication.
- [ ] Comprehensive test suite in `test/campaign.test.ts` passing.
- [ ] All 1,710+ existing tests passing (`npm test`).
- [ ] Consistency check passing (`npm run consistency:check` if available).
