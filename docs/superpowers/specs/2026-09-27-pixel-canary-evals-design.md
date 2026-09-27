# Design Specification: Pixel Canary Model Integration & Next.js Agent Evals Interactive Dashboard

**Date:** 2026-09-27  
**Status:** Approved by User  
**Author:** Antigravity Autonomous Agent  
**Context:** Next.js Agent Evals (Sep 25, 2026) release highlighting `stealth/pixel-canary` (90% pass@4, FREE) tying with GPT 6 Astra ($0.89), accessible via Cline (`cline.bot/desktop`) and Vercel AI Gateway.

---

## 1. Executive Summary & Objective

On September 25, 2026, an anonymous stealth model named **Pixel Canary** was released across Vercel AI Gateway and the Cline coding agent (`cline.bot/desktop`). On the official **Next.js Agent Evals** benchmark (pass@4), it achieved a **90% success rate**—tying with OpenAI's flagship **GPT 6 Astra (90% @ $0.89/task)** and approaching **Claude Fable 5.1 (97% @ $0.72/task)**, while being completely **FREE** ($0.00).

This specification outlines the complete end-to-end implementation for **Marzneshin Autonomous OS**:
1. **Model Router & Gateway Adapter:** Registering Pixel Canary (`stealth/pixel-canary`) as a zero-cost coding provider in `configs/router.json` and creating a Python adapter (`adapters/pixel_canary.py`).
2. **Cline Desktop & Extension Auto-Configurator:** Setting up Cline configuration for both VS Code and standalone Cline Desktop (`cline.bot/desktop`) with custom provider mapping and prompt templates.
3. **Next.js Agent Evals Interactive Benchmark & Web Dashboard:** Building an evaluation harness (`eval/nextjs_agent_evals.py`) and a high-end, responsive dark-mode dashboard (`dashboards/nextjs-agent-evals/`) that exactly matches the photo's bar chart, with interactive toggles for pass@4 vs pass@1, cost calculations, challenge tests, and live model comparison.

---

## 2. Benchmark Data Matrix (Next.js Agent Evals - Sep 25, 2026)

| Model Name | Pass@4 Rate | Pass@1 Rate (Est.) | Cost per Task | Relative Efficiency | Highlighting |
|---|---|---|---|---|---|
| **Claude Fable 5.1 (high)** | **97%** | 88.5% | $0.72 | 1.35 pts / $0.01 | Standard Dark Slate |
| **Pixel Canary** | **90%** | 78.2% | **FREE ($0.00)** | **Inf (Infinite ROI)** | **Golden Accent (#f59e0b)** |
| **GPT 6 Astra (high)** | **90%** | 79.4% | $0.89 | 1.01 pts / $0.01 | Standard Dark Slate |
| **Kimi K3** | **84%** | 71.0% | $0.28 | 3.00 pts / $0.01 | Standard Dark Slate |
| **Claude Sonnet 5** | **81%** | 68.5% | $0.39 | 2.08 pts / $0.01 | Standard Dark Slate |

Benchmark evaluation criteria include:
- App Router layout & server/client boundary resolution
- Server Actions with form status & validation
- React Server Component (RSC) streaming & suspense hydration
- Next.js 15+ cache lifecycle & revalidation
- Route handlers & middleware security

---

## 3. Architecture & System Components

```
 +-------------------------------------------------------------------------+
 |                      Marzneshin Autonomous OS                           |
 |                                                                         |
 |  +-----------------------+              +----------------------------+  |
 |  |  Tier-0 Orchestrator  |  --------->  |   adapters/claudex_loop    |  |
 |  +-----------------------+              +----------------------------+  |
 |              |                                         |                |
 |              v                                         v                |
 |  +-----------------------+              +----------------------------+  |
 |  |  configs/router.json  |  --------->  | adapters/pixel_canary.py   |  |
 |  |  - vercel_gateway     |              | - Vercel AI Gateway client |  |
 |  |  - stealth/pixel-canary              | - Failover & retry logic   |  |
 |  |  - free-mega, smart   |              | - Token stream handling    |  |
 |  +-----------------------+              +----------------------------+  |
 +-------------------------------------------------------------------------+
        |                                                 |
        v                                                 v
 +----------------------------+            +-------------------------------+
 |  Cline (Desktop & VS Code) |            | Next.js Agent Evals Dashboard |
 |  - cline_mcp_settings.json |            | - dashboards/nextjs-evals/    |
 |  - OpenRouter/Custom Proxy |            |   * index.html (Chart UI)     |
 |  - Zero-cost coding engine |            |   * style.css (Dark Gold)     |
 |                            |            |   * app.js (Interactive Evals)|
 +----------------------------+            +-------------------------------+
```

---

## 4. Component Details

### 4.1. Router Configuration (`configs/router.json`)
Add gateway entry:
```json
"vercel_gateway": {
    "enabled": true,
    "base_url": "https://ai-gateway.vercel.sh/v1",
    "api_key": "${VERCEL_GATEWAY_KEY:-free}",
    "description": "Vercel AI Gateway - Host of stealth/pixel-canary (90% Next.js evals, FREE)"
}
```
And include `vercel_gateway:stealth/pixel-canary` in combos (`free-mega`, `smart`, `antigravity`, `fable-flash`).

### 4.2. Adapter (`adapters/pixel_canary.py`)
- Standard OpenAI-compatible API interface with streaming support.
- Configurable endpoints (Vercel Gateway: `https://ai-gateway.vercel.sh/v1`, local proxy, or OpenRouter fallback).
- Header handling (`HTTP-Referer: https://marzneshin.os`, `X-Title: Marzneshin OS`).
- Exponential backoff retry on HTTP 429/503.

### 4.3. Cline Auto-Configuration (`scripts/setup_cline_pixel_canary.py`)
- Inspects both Windows VS Code (`%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev`) and WSL/Linux paths.
- Generates or updates Cline settings with:
  - Provider: `openai-compatible` or `openrouter`
  - Base URL: `https://ai-gateway.vercel.sh/v1`
  - Model ID: `stealth/pixel-canary`
  - Display Name: `Pixel Canary (Free - 90% Next.js Evals)`

### 4.4. Next.js Agent Evals Benchmark Suite & Dashboard
- **Engine (`eval/nextjs_agent_evals.py`):**
  - Defines 12 standard Next.js challenge tasks (App Router layout, Server Actions, Hydration fix, Route Handler auth, ISR revalidation, etc.).
  - Evaluates models across pass@1, pass@4, token cost, latency, and syntax validity.
- **Web Dashboard (`dashboards/nextjs-agent-evals/`):**
  - High-fidelity replica of the user's Telegram photo chart.
  - Golden highlight card & bar for **Pixel Canary (90% - FREE)**.
  - Interactive controls:
    - Metric toggles (Pass@4 vs Pass@1 vs Cost Efficiency).
    - Cost Savings Calculator (e.g. "How much do you save over 1,000 tasks vs GPT 6 Astra? -> $890.00!").
    - Challenge Inspector: inspect task details, code diffs, and eval tests.
    - Live Test Runner: execute or simulate live model evaluation.

---

## 5. Verification Plan
- Unit tests for `adapters/pixel_canary.py` with mock responses.
- Unit tests for `eval/nextjs_agent_evals.py` metric calculations.
- Verification of `configs/router.json` syntax and validity.
- Execution of Cline configuration script.
- Live HTTP server check for the Next.js Agent Evals dashboard.
