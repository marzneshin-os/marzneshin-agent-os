# Architecture Specification: Fast Inference Multi-Channel Routing & Resilient Acceleration Layer

**Document ID:** `SPEC-2026-10-01-FAST-INFERENCE`  
**Status:** Approved / In Implementation  
**Author:** Antigravity Architect  
**Target Systems:** Antigravity IDE, Claude Code, OpenCode, Cursor, Codex, Grok  
**Reference Video:** `https://youtube.com/shorts/J_xP1PhUmqg` (InsiderForce: "Claude Code, Codex, and Cursor Just Got Ten Times Faster With This One Tool")

---

## 1. Executive Summary & Problem Statement

### 1.1 The Video Technology Demystified
The reference video highlights **Fast Inference**: an acceleration and multi-channel routing layer positioned between coding agents (Claude Code, Cursor, Codex, Antigravity) and upstream AI model backends. It addresses three critical agentic bottlenecks:
1. **Agentic Latency Drag:** Coding agents execute iterative multi-turn loops (file reading, AST parsing, reflection, synthesis, tool dispatch). High inference latency compounds with every turn, reducing developer flow.
2. **Provider Fragility & Session Termination:** Rate limits (HTTP 429), gateway timeouts (HTTP 504), and upstream degradations crash long-running agent workflows mid-task.
3. **Multi-Model Access Friction:** High-speed reasoning models (Kimi K3, GLM 5.2, DeepSeek V4) and frontier foundational models (Claude Opus 5, GPT 5.6) require separate subscriptions, keys, and base URLs.

### 1.2 The Production-Grade Architectural Solution
Rather than introducing an external black-box dependency, `agentmemory` implements the **Fast Inference Router & Resilient Multi-Channel Engine** directly in its core provider and functions layer. This provides:
- **Dynamic Lowest-Latency Routing:** Probes channel latencies (both passive during execution and active via benchmarking) and steers requests to the fastest responsive channel.
- **Zero-Stall Failover & Circuit Breaking:** Per-channel circuit breakers with automatic sub-second failover to secondary/tertiary channels when a channel 429s or times out.
- **Multi-Model Gateway:** Out-of-the-box support for heterogeneous models (Kimi K3, GLM 5.2, DeepSeek V4, Claude Opus 5, GPT 5.6, Gemini, local vLLM/Ollama) with unified or channel-specific credentials.
- **Universal Cross-Agent Accessibility:** Accessible uniformly via 4 MCP tools, 4 REST endpoints, and the Viewer dashboard across Antigravity, Claude Code, Cursor, and OpenCode.

---

## 2. System-Level Architecture Model

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          Agentic Coding Environments                             │
│   [ Antigravity IDE ]      [ Claude Code ]      [ OpenCode ]      [ Cursor/Codex ]│
└────────────┬──────────────────────┬─────────────────────┬─────────────────┬──────┘
             │                      │                     │                 │
             │ stdio / SSE (MCP)    │ HTTP (REST)         │ stdio (MCP)     │
             ▼                      ▼                     ▼                 ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             agentmemory Core Boundary                            │
│                                                                                  │
│   ┌──────────────────────────────┐        ┌──────────────────────────────────┐   │
│   │     src/mcp/server.ts        │        │        src/triggers/api.ts       │   │
│   │  memory_fast_inference_*     │        │    /agentmemory/inference/*      │   │
│   └──────────────┬───────────────┘        └─────────────────┬────────────────┘   │
│                  │                                          │                    │
│                  └────────────────────┬─────────────────────┘                    │
│                                       │ sdk.trigger()                            │
│                                       ▼                                          │
│   ┌──────────────────────────────────────────────────────────────────────────┐   │
│   │                  src/functions/fast-inference.ts                         │   │
│   │   • mem::fast-inference-route      • mem::fast-inference-channels        │   │
│   │   • mem::fast-inference-benchmark  • mem::fast-inference-configure       │   │
│   └───────────────────────────────────┬──────────────────────────────────────┘   │
│                                       │                                          │
│                                       ▼                                          │
│   ┌──────────────────────────────────────────────────────────────────────────┐   │
│   │                  src/providers/fast-inference.ts                         │   │
│   │   • FastInferenceRouter (latency scorer, channel selector, metrics)     │   │
│   │   • Per-channel CircuitBreaker & adaptive timeout                        │   │
│   │   • Upstream Channels:                                                   │   │
│   │       ├── Kimi K3 Fast Channel (Moonshot / Local Engine)                 │   │
│   │       ├── GLM 5.2 Fast Channel (Zhipu / SiliconFlow)                     │   │
│   │       ├── DeepSeek V4 Channel (DeepSeek / Together / Fireworks)          │   │
│   │       ├── OpenAI / Azure Channel (GPT-5.6 / gpt-4o)                      │   │
│   │       ├── Anthropic Channel (Claude Opus 5 / Sonnet 5)                   │   │
│   │       └── Local / Custom Gateway (vLLM / Ollama)                         │   │
│   └───────────────────────────────────┬──────────────────────────────────────┘   │
│                                       │                                          │
│                                       ▼                                          │
│   ┌──────────────────────────────────────────────────────────────────────────┐   │
│   │                    State, Persistence & Observability                    │   │
│   │   • KV.fastInference (Channel configs, latency history, metrics)         │   │
│   │   • recordAudit() for governance                                         │   │
│   │   • src/viewer/ (Port :3113) Real-time Fast Inference Monitor            │   │
│   └──────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Component Architecture

### 3.1 State Schema & Types
- **KV Scope:** `KV.fastInference = "mem:fast_inference"` in `src/state/schema.ts`
- **Interfaces (`src/types.ts`):**
  - `FastInferenceChannel`:
    - `id: string`
    - `name: string`
    - `provider: ProviderType | "custom"`
    - `endpoint: string`
    - `model: string`
    - `apiKey?: string`
    - `priority: number`
    - `enabled: boolean`
    - `latencyMs: number`
    - `successRate: number`
    - `failureCount: number`
    - `circuitState: CircuitBreakerState`
    - `lastCheckedAt?: string`
  - `FastInferenceRouteRequest`:
    - `prompt: string`
    - `systemPrompt?: string`
    - `maxTokens?: number`
    - `temperature?: number`
    - `preferredModel?: string`
    - `strategy?: "lowest-latency" | "fallback-chain" | "cost-optimized"`
  - `FastInferenceRouteResponse`:
    - `content: string`
    - `channelId: string`
    - `channelName: string`
    - `model: string`
    - `latencyMs: number`
    - `failoverCount: number`
    - `failoverHops?: string[]`
    - `tokensUsed?: { prompt: number; completion: number; total: number }`
  - `AuditEntry.operation`: extended with `"fast_inference_route"` and `"fast_inference_configure"`

### 3.2 Core Functions (`src/functions/fast-inference.ts`)
1. `mem::fast-inference-route`:
   - Validates input.
   - Evaluates active channels sorted by strategy (default: lowest EMA latency with closed circuit breaker).
   - Attempts invocation against selected channel.
   - If error/timeout occurs, trips circuit breaker, records hop, immediately dispatches to next channel.
   - Returns result with timing metadata and records audit.
2. `mem::fast-inference-channels`:
   - Returns list of all configured channels, live health status, circuit breaker states, and historical EMA latencies.
3. `mem::fast-inference-benchmark`:
   - Runs parallel lightweight ping/probe across all enabled channels.
   - Measures response time (TTFT/latency), updates channel rankings in KV store.
4. `mem::fast-inference-configure`:
   - Dynamically adds, edits, enables, disables channels or changes routing weights.

### 3.3 MCP Tools (`src/mcp/tools-registry.ts` & `src/mcp/server.ts`)
- `memory_fast_inference_route`
- `memory_fast_inference_channels`
- `memory_fast_inference_benchmark`
- `memory_fast_inference_configure`

### 3.4 REST Endpoints (`src/triggers/api.ts`)
- `POST /agentmemory/inference/route`
- `GET /agentmemory/inference/channels`
- `POST /agentmemory/inference/benchmark`
- `POST /agentmemory/inference/configure`

### 3.5 Viewer Dashboard Monitor (`src/viewer/index.html` & `src/viewer/server.ts`)
- Tab **Fast Inference**:
  - Live channel cards showing latency (ms), health status badge (Healthy / Degraded / Tripped), model name, and endpoint.
  - Active fastest channel callout.
  - Failover & recovery event log.
  - "Run Benchmark" interactive button.

---

## 4. Consistency Checklist & Metrics (Strict adherence to `AGENTS.md`)

| Metric / Requirement | Current | After Fast Inference Integration |
|----------------------|---------|-----------------------------------|
| MCP Tools Count      | 58      | **62**                            |
| REST Endpoints Count | 134     | **138**                           |
| KV Scopes            | 30+     | + `KV.fastInference`              |
| Audit Operations     | 40+     | + `fast_inference_route`, `fast_inference_configure` |
| Test Suite           | 1,726   | **1,750+ (100% passing)**         |

---

## 5. Security & Trust Boundaries
- **API Key Redaction:** Channel API keys are never leaked to the viewer UI or in MCP responses; only masked representations (`sk-***`) or channel IDs are returned.
- **Authentication:** All REST endpoints strictly guarded by `checkAuth(req, secret)`.
- **Input Whitelisting:** All payload parameters are whitelisted and strictly typed before passing to `sdk.trigger()`.
- **Zero-LLM Graceful Fallback:** If no external API keys are configured, channels operate in local deterministic mock/heuristic mode, preserving the zero-dependency promise of `agentmemory`.

---

## 6. Verification & Acceptance Criteria
- [ ] Unit tests for `FastInferenceRouter` and channel failover pass.
- [ ] Integration tests for all 4 MCP tools pass.
- [ ] Integration tests for all 4 REST endpoints pass.
- [ ] Benchmark and latency tracking verify sub-second routing.
- [ ] Consistency tests pass (`test/tool-count-consistency.test.ts` updated to 62 tools, 138 endpoints).
- [ ] Viewer dashboard renders Fast Inference monitor tab.
- [ ] `npm test` runs all 1,750+ tests with 0 failures.
- [ ] `npm run build` succeeds cleanly.
