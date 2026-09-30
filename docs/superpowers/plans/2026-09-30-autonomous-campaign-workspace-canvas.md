# Autonomous Campaign & Lineage Workspace Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Autonomous Multi-Agent Campaign & Lineage Workspace Engine (TopView AI capability) natively within `agentmemory` v0.9.29 with multimodal asset ingestion, 3-tier subagent pipeline (Intelligence -> Strategy -> Creative), bi-directional graph lineage, viewer canvas on port 3113, 4 MCP tools, and 4 REST endpoints.

**Architecture:** A native core subsystem built on iii-engine primitives (`registerFunction`, `registerTrigger`, `StateKV`), persisting campaigns in SQLite `state_store.db`, linking nodes in the typed knowledge graph (`INSPIRED_BY`, `GENERATED_FROM`), exposing a side-by-side interactive Canvas in the Web Viewer, and strictly adhering to all 8 consistency rules of `AGENTS.md`.

**Tech Stack:** TypeScript (ESM), `iii-sdk`, SQLite via iii-engine `StateModule`, Vitest, Vanilla HTML/CSS Canvas in Viewer.

**Spec:** [`docs/superpowers/specs/2026-09-30-autonomous-campaign-workspace-canvas-design.md`](file:///c:/Ubuntu/home/asus/code/marzneshin-agent-os/docs/superpowers/specs/2026-09-30-autonomous-campaign-workspace-canvas-design.md)

## Global Constraints
- TypeScript ESM only (`"type": "module"`).
- No code comments explaining WHAT code does — use clear naming instead.
- Strict consistency updates across all 8 files for MCP tools (54 -> 58) and REST endpoints (130 -> 134).
- REST endpoints must whitelist fields — never pass raw request body to `sdk.trigger()`.
- Use `recordAudit()` for state-changing operations.
- Zero breaking changes to existing memory, search, or graph tools. All 1,710 existing tests must stay passing.

---

### Task 1: Schema and Types Definition

**Files:**
- Modify: `src/state/schema.ts`
- Modify: `src/types.ts`
- Test: `test/campaign-schema.test.ts`

**Interfaces:**
- Produces:
  - `KV.campaigns: "campaigns"`
  - `Campaign`, `CampaignInsight`, `CampaignStrategy`, `CampaignCreative` interfaces
  - `AuditEntry.operation: ... | "campaign_create" | "campaign_delete"`

- [x] **Step 1: Write the failing test**

Create `test/campaign-schema.test.ts`:
```typescript
import { describe, it, expect } from "vitest";
import { KV } from "../src/state/schema.js";
import type { Campaign, CampaignInsight, CampaignStrategy, CampaignCreative } from "../src/types.js";

describe("Campaign Schema & Types", () => {
  it("defines KV.campaigns scope", () => {
    expect(KV.campaigns).toBe("campaigns");
  });

  it("verifies campaign structure types compile correctly", () => {
    const insight: CampaignInsight = {
      id: "ins-1",
      topic: "Short-form video retention",
      source: "TikTok/YouTube",
      summary: "3-second hook pattern",
      confidence: 0.95,
      timestamp: new Date().toISOString(),
    };
    const strategy: CampaignStrategy = {
      id: "strat-1",
      targetAudience: "Engineers & DevOps",
      valueProp: "Zero configuration deployment",
      hooks: ["Stop debugging configs manually"],
      inspiredByInsightIds: ["ins-1"],
      timestamp: new Date().toISOString(),
    };
    const creative: CampaignCreative = {
      id: "crt-1",
      format: "video-script",
      headline: "How to deploy in 60s",
      body: "Scene 1: terminal opens...",
      visualPrompt: "A sleek dark IDE window",
      generatedFromStrategyIds: ["strat-1"],
      timestamp: new Date().toISOString(),
    };
    const campaign: Campaign = {
      id: "cmp-1",
      name: "Launch Campaign",
      assetRef: "assets/sample.png",
      status: "ready",
      insights: [insight],
      strategies: [strategy],
      creatives: [creative],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    expect(campaign.id).toBe("cmp-1");
    expect(campaign.insights.length).toBe(1);
    expect(campaign.strategies.length).toBe(1);
    expect(campaign.creatives.length).toBe(1);
  });
});
```

- [x] **Step 2: Run test to verify it fails**

Run: `npx vitest run test/campaign-schema.test.ts`
Expected: FAIL with `KV.campaigns is undefined`

- [x] **Step 3: Implement minimal schema & types**

In `src/state/schema.ts`, add:
```typescript
campaigns: "campaigns",
```
In `src/types.ts`, add `Campaign`, `CampaignInsight`, `CampaignStrategy`, `CampaignCreative`, and update `AuditEntry.operation`.

- [x] **Step 4: Run test to verify it passes**

Run: `npx vitest run test/campaign-schema.test.ts`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/state/schema.ts src/types.ts test/campaign-schema.test.ts
git commit -m "feat(campaign): add campaign KV scope and type definitions"
```

---

### Task 2: Core Function Implementation (`src/functions/campaign.ts`)

**Files:**
- Create: `src/functions/campaign.ts`
- Test: `test/campaign.test.ts`

**Interfaces:**
- Consumes: `KV.campaigns`, `ISdk`, `StateKV`, `recordAudit`
- Produces:
  - `mem::campaign-orchestrate`
  - `mem::campaign-get`
  - `mem::campaign-list`
  - `mem::campaign-canvas`

- [x] **Step 1: Write the failing unit and integration tests**

Create `test/campaign.test.ts` testing orchestration, graph lineage creation (`INSPIRED_BY`, `GENERATED_FROM`), campaign retrieval, listing, and canvas payload formatting.

- [x] **Step 2: Run test to verify it fails**

Run: `npx vitest run test/campaign.test.ts`
Expected: FAIL with module `src/functions/campaign.ts` not found.

- [x] **Step 3: Implement `src/functions/campaign.ts`**

Implement `registerCampaignFunctions(sdk: ISdk, kv: StateKV)` with:
1. `mem::campaign-orchestrate`: Generates 3-phase items (Insights, Strategies, Creatives), saves to `KV.campaigns`, and triggers `mem::graph-link` for lineage.
2. `mem::campaign-get`: Fetches campaign by ID.
3. `mem::campaign-list`: Lists all campaigns.
4. `mem::campaign-canvas`: Prepares columnated Canvas payload with node coordinates and connector edges.

- [x] **Step 4: Run test to verify it passes**

Run: `npx vitest run test/campaign.test.ts`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/functions/campaign.ts test/campaign.test.ts
git commit -m "feat(campaign): implement campaign orchestrator and canvas functions"
```

---

### Task 3: REST Endpoints Registration (`src/triggers/api.ts`)

**Files:**
- Modify: `src/triggers/api.ts`
- Test: `test/campaign-api.test.ts`

**Interfaces:**
- Consumes: `checkAuth`, `mem::campaign-*`
- Produces:
  - `POST /agentmemory/campaigns/create`
  - `GET /agentmemory/campaigns/get`
  - `GET /agentmemory/campaigns/list`
  - `GET /agentmemory/campaigns/canvas`

- [x] **Step 1: Write failing REST API test**

Create `test/campaign-api.test.ts` checking authentication, request validation, field whitelisting, and 200 responses.

- [x] **Step 2: Run test to verify it fails**

Run: `npx vitest run test/campaign-api.test.ts`
Expected: FAIL with endpoint not found.

- [x] **Step 3: Register REST endpoints in `src/triggers/api.ts`**

Register the 4 endpoints following the standard project pattern: check auth, whitelist parameters, and invoke `sdk.trigger()`.

- [x] **Step 4: Run test to verify it passes**

Run: `npx vitest run test/campaign-api.test.ts`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/triggers/api.ts test/campaign-api.test.ts
git commit -m "feat(campaign): register authenticated REST endpoints for campaigns"
```

---

### Task 4: MCP Tools Registration (`src/mcp/tools-registry.ts` & `src/mcp/server.ts`)

**Files:**
- Modify: `src/mcp/tools-registry.ts`
- Modify: `src/mcp/server.ts`
- Test: `test/campaign-mcp.test.ts`

**Interfaces:**
- Produces:
  - `memory_campaign_create`
  - `memory_campaign_get`
  - `memory_campaign_list`
  - `memory_campaign_canvas`

- [x] **Step 1: Write failing MCP tool test**

Create `test/campaign-mcp.test.ts` invoking the 4 campaign tools through `src/mcp/server.ts`.

- [x] **Step 2: Run test to verify it fails**

Run: `npx vitest run test/campaign-mcp.test.ts`
Expected: FAIL with unknown tool error.

- [x] **Step 3: Add tool definitions and switch handlers**

In `src/mcp/tools-registry.ts`, define the 4 tools and append them to `getAllTools()`.
In `src/mcp/server.ts`, add the corresponding cases to `mcp::tools::call`.

- [x] **Step 4: Run test to verify it passes**

Run: `npx vitest run test/campaign-mcp.test.ts`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/mcp/tools-registry.ts src/mcp/server.ts test/campaign-mcp.test.ts
git commit -m "feat(campaign): register campaign MCP tools and call handlers"
```

---

### Task 5: Consistency Rules & Registry Synchronization

**Files:**
- Modify: `src/index.ts`
- Modify: `test/mcp-standalone.test.ts`
- Modify: `README.md`
- Modify: `plugin/.claude-plugin/plugin.json`
- Modify: `plugin/plugin.json` (if present)

- [x] **Step 1: Run consistency test to see what fails**

Run: `npx vitest run test/mcp-standalone.test.ts`
Expected: FAIL with tool count mismatch (expected 54, found 58).

- [x] **Step 2: Update all counts across the 5 files**
  - In `src/index.ts`: Register `registerCampaignFunctions(sdk, kv)`, update startup log tool and endpoint counts (54 -> 58 tools, 130 -> 134 endpoints).
  - In `test/mcp-standalone.test.ts`: Assert 58 tools.
  - In `README.md`: Update tool count (54 -> 58) and REST endpoints (130 -> 134).
  - In `plugin/.claude-plugin/plugin.json`: Update tool count in description.

- [x] **Step 3: Run standalone and consistency checks**

Run: `npx vitest run test/mcp-standalone.test.ts`
Expected: PASS

- [x] **Step 4: Commit**

```bash
git add src/index.ts test/mcp-standalone.test.ts README.md plugin/.claude-plugin/plugin.json
git commit -m "chore: synchronize consistency counts for campaign tools and endpoints"
```

---

### Task 6: Viewer Dashboard Campaign Canvas Tab

**Files:**
- Modify: `src/viewer/server.ts`
- Modify: `src/viewer/index.html`
- Test: `test/campaign-viewer.test.ts`

- [x] **Step 1: Write failing viewer test**

Create `test/campaign-viewer.test.ts` checking that `/api/campaigns/canvas` returns valid JSON data and HTML contains the Campaign Canvas tab and view containers.

- [x] **Step 2: Run test to verify it fails**

Run: `npx vitest run test/campaign-viewer.test.ts`
Expected: FAIL

- [x] **Step 3: Implement canvas route and UI markup**

In `src/viewer/server.ts`, add route `/api/campaigns/canvas` fetching data via `mem::campaign-canvas`.
In `src/viewer/index.html`, add the "Campaign Canvas" tab with column layout:
`[ 💡 Market Insights ] ──→ [ 🎯 Campaign Strategy ] ──→ [ 🎨 Creative Assets ]`.

- [x] **Step 4: Run test to verify it passes**

Run: `npx vitest run test/campaign-viewer.test.ts`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add src/viewer/server.ts src/viewer/index.html test/campaign-viewer.test.ts
git commit -m "feat(viewer): add interactive campaign canvas tab and api route"
```

---

### Task 7: Full System Verification and Regression Testing

- [x] **Step 1: Run full test suite**

Run: `npm test`
Expected: All tests pass (1,720+ tests, 0 failures).

- [x] **Step 2: Build project**

Run: `npm run build`
Expected: Build succeeds with 0 TypeScript/tsdown errors.

- [x] **Step 3: Final verification commit**

```bash
git commit --allow-empty -m "chore: verify full campaign engine integration and test suite"
```
