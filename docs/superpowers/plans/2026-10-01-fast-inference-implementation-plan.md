# Implementation Plan: Fast Inference Multi-Channel Routing & Resilient Acceleration Layer

**Plan ID:** `PLAN-2026-10-01-FAST-INFERENCE`  
**Spec Document:** `docs/superpowers/specs/2026-10-01-fast-inference-architecture-design.md`  
**Methodology:** Superpowers Test-Driven Development (TDD) + AGENTS.md Consistency Rules  

---

## Task 1: Schema, Types, and Provider Definitions (TDD)
- **Files:**
  - `src/state/schema.ts`
  - `src/types.ts`
  - `test/fast-inference-schema.test.ts` (New test)
- **Steps:**
  1. Write failing test in `test/fast-inference-schema.test.ts` asserting `KV.fastInference` exists, and interfaces compile.
  2. Run `npx vitest run test/fast-inference-schema.test.ts` -> Verify failure (RED).
  3. Add `fastInference: "mem:fast_inference"` to `KV` object in `src/state/schema.ts`.
  4. Add `FastInferenceChannel`, `FastInferenceRouteRequest`, `FastInferenceRouteResponse`, `FastInferenceConfig`, `FastInferenceBenchmarkResult` interfaces to `src/types.ts`.
  5. Add `"fast-inference"` to `ProviderType` in `src/types.ts`.
  6. Add `"fast_inference_route" | "fast_inference_configure"` to `AuditEntry.operation` in `src/types.ts`.
  7. Run test -> Verify pass (GREEN).
  8. Git commit: `feat(inference): add fast inference schema, types, and audit operations`.

---

## Task 2: Fast Inference Router Engine (TDD)
- **Files:**
  - `src/providers/fast-inference.ts` (New)
  - `src/providers/index.ts`
  - `test/fast-inference-router.test.ts` (New test)
- **Steps:**
  1. Write failing tests in `test/fast-inference-router.test.ts`:
     - Channel selection based on lowest latency (EMA).
     - Circuit breaker trips and skips failed channel to next fastest channel.
     - Mock provider invocation with timing and fallback hop recording.
  2. Run `npx vitest run test/fast-inference-router.test.ts` -> Verify failure (RED).
  3. Implement `FastInferenceRouter` and `FastInferenceProvider` in `src/providers/fast-inference.ts`.
  4. Connect `"fast-inference"` case into `createBaseProvider` in `src/providers/index.ts`.
  5. Run test -> Verify pass (GREEN).
  6. Git commit: `feat(providers): implement FastInferenceRouter with latency-based routing and circuit breaking`.

---

## Task 3: Core iii Functions & State Management (TDD)
- **Files:**
  - `src/functions/fast-inference.ts` (New)
  - `src/index.ts`
  - `test/fast-inference-functions.test.ts` (New test)
- **Steps:**
  1. Write failing tests in `test/fast-inference-functions.test.ts`:
     - `mem::fast-inference-route` returns routed response and updates metrics.
     - `mem::fast-inference-channels` returns channel list with health and latency rankings.
     - `mem::fast-inference-benchmark` probes all channels and records new latency measurements.
     - `mem::fast-inference-configure` allows adding/updating channels.
  2. Run `npx vitest run test/fast-inference-functions.test.ts` -> Verify failure (RED).
  3. Implement `src/functions/fast-inference.ts` with input validation, KV persistence, audit recording.
  4. Register functions in `src/index.ts`.
  5. Run test -> Verify pass (GREEN).
  6. Git commit: `feat(functions): implement fast inference core functions with KV persistence`.

---

## Task 4: MCP Tools Integration (TDD)
- **Files:**
  - `src/mcp/tools-registry.ts`
  - `src/mcp/server.ts`
  - `src/mcp/standalone.ts`
  - `test/fast-inference-mcp.test.ts` (New test)
- **Steps:**
  1. Write failing test in `test/fast-inference-mcp.test.ts` verifying tool definitions and standalone dispatch.
  2. Run test -> Verify failure (RED).
  3. Add 4 tool definitions to `src/mcp/tools-registry.ts` (`memory_fast_inference_route`, `memory_fast_inference_channels`, `memory_fast_inference_benchmark`, `memory_fast_inference_configure`).
  4. Add 4 tool dispatch cases to `src/mcp/server.ts` and `src/mcp/standalone.ts`.
  5. Run test -> Verify pass (GREEN).
  6. Git commit: `feat(mcp): add fast inference MCP tools for cross-agent environments`.

---

## Task 5: REST API Endpoints Integration (TDD)
- **Files:**
  - `src/triggers/api.ts`
  - `test/fast-inference-api.test.ts` (New test)
- **Steps:**
  1. Write failing test in `test/fast-inference-api.test.ts`:
     - `POST /agentmemory/inference/route`
     - `GET /agentmemory/inference/channels`
     - `POST /agentmemory/inference/benchmark`
     - `POST /agentmemory/inference/configure`
  2. Run test -> Verify failure (RED).
  3. Register 4 HTTP endpoints in `src/triggers/api.ts` with authentication and field whitelisting.
  4. Run test -> Verify pass (GREEN).
  5. Git commit: `feat(api): register REST endpoints for fast inference routing and health`.

---

## Task 6: Viewer Dashboard Integration (TDD)
- **Files:**
  - `src/viewer/server.ts`
  - `src/viewer/index.html`
  - `test/fast-inference-viewer.test.ts` (New test)
- **Steps:**
  1. Write test in `test/fast-inference-viewer.test.ts` asserting viewer serves inference channel endpoint and HTML contains Fast Inference UI.
  2. Run test -> Verify failure (RED).
  3. Extend `src/viewer/server.ts` to handle `/api/inference/channels` and `/api/inference/benchmark`.
  4. Extend `src/viewer/index.html` with a Fast Inference Monitor tab (latency cards, health badges, speed charts).
  5. Run test -> Verify pass (GREEN).
  6. Git commit: `feat(viewer): add interactive Fast Inference monitor tab in web dashboard`.

---

## Task 7: Consistency Updates Across Repository (Strict Rule Enforcement)
- **Files:**
  - `src/index.ts` (log line counts: 58 -> 62 tools, 134 -> 138 endpoints)
  - `test/tool-count-consistency.test.ts` (EXPECTED_TOOL_COUNT = 62)
  - `README.md`
  - `AGENTS.md`
  - `plugin/.claude-plugin/plugin.json`
  - `plugin/plugin.json` and `plugin/.mcp.copilot.json`
- **Steps:**
  1. Update counts in all canonical files.
  2. Run `npx vitest run test/tool-count-consistency.test.ts` -> Verify pass.
  3. Git commit: `docs(consistency): synchronize MCP tool count (62) and REST endpoint count (138)`.

---

## Task 8: Full Regression Test & Build Verification
- **Steps:**
  1. Run `npm test` -> Confirm all 165+ files and 1,750+ tests pass with 0 failures.
  2. Run `npm run build` -> Confirm build succeeds cleanly.
  3. Verify cross-agent compatibility (Antigravity, Claude Code, OpenCode).
