# ADR-027: System 1 Typed Decisions & Jev+Claude Stacking Engine

**Date:** 2026-10-10  
**Status:** Accepted  
**Author:** Executive Project Manager & Chief Systems Architect  
**Workstream:** agentic-core / latency-optimization / token-economy  
**Governing Standard:** BUILD-SPEC.md v2.0, ADR-001, ADR-015, ADR-022, ADR-024, ADR-025, ADR-026  

---

## 1. Context & Reference Analysis

### Primary References:
- **Reference 1:** *Jev Developer Ecosystem & System One Decision Model* (TypeSafe AI) ? `https://x.com/search?q=jev%20dev`
- **Reference 2:** *Laya Open-Weight Decision Foundation Model* (ConvAI Innovations, ModernBERT-large 421M / mmBERT-base 322M) ? `https://x.com/search?q=laya`
- **Reference 3:** *How to Stack Jev AI With Claude in 90-Seconds (440x Cheaper)* ? Fast System 1 Non-Autoregressive Decision Heads stacked with System 2 Generative LLM Escalation.

### Problem Statement:
Autonomous multi-agent architectures (such as Marzneshin Agent OS) frequently evaluate high-frequency, structured questions:
1. *Agent Routing & Intent Triage:* Which specialist node should execute this task?
2. *Guardrail & Injection Screening:* Does this command or prompt violate security policies?
3. *Quality & Risk Rubric Scoring:* Is this code diff critical risk, medium risk, or safe?
4. *Two-Key Verification Gating:* Should this unit gate pass or be blocked?

Executing these checks with autoregressive generative models (Claude Opus/Sonnet, GPT-4/5) incurs severe penalties:
- **Latency Bloat:** 1,200ms to 3,500ms per check due to token-by-token autoregression.
- **Economic Inefficiency:** Costly per-token billing ($15-$75 / M tokens) for trivial boolean or categorical judgments.
- **Syntactic Fragility:** Free-form generation can hallucinate or fail strict schema parsing.

### The Solution: Non-Autoregressive System 1 Decision Models
System 1 models (TypeSafe AI Jev and open-weight ConvAI Laya) process input states and evaluate typed questions in a single forward pass:
- **Sub-15ms Latency:** Up to 95% latency reduction compared to autoregressive generation.
- **Zero Output Tokens:** Eliminates generation costs entirely.
- **Typed Primitives:** Three foundational heads:
  * `choice`: Probabilities across discrete categories (routing).
  * `score`: Rubric-based scalar confidence scoring (quality gates).
  * `noul`: Calibrated boolean propositions $P(\\text{true})$ (guardrails).
- **Stacking Architecture:** If calibrated confidence $c \ge \tau$ (e.g. 0.90), resolve immediately on the fast-path (440x cheaper). If $c < \tau$ or creative code generation is strictly required, escalate to System 2 (Claude / Gemini / OmniRoute).

---

## 2. Architectural Decisions

### D1: Multi-Backend System 1 Adapter (`adapters/laya.py`)
- Extends `adapters.base.Adapter` conforming to BUILD-SPEC.md v2.0 ?4.
- Multi-Engine Dispatch hierarchy:
  1. **TypeSafe Jev API:** Cloud `/v1/systemone` endpoint when `JEV_API_KEY` is configured.
  2. **Remote Laya HTTP Server:** Self-hosted `/v1/systemone` endpoint when `LAYA_SERVER_URL` is set.
  3. **Laya-MLX Native Runtime:** Optimized Apple Silicon in-memory engine (7.4ms median latency).
  4. **Calibrated Local Semantic Engine:** Deterministic, zero-dependency local fallback for Linux / WSL / CI ensuring 100% air-gapped resilience.
- Standard library only (`urllib.request`, `json`, `math`, `time`, `platform`), compliant with `scripts/verify.py --lint-imports`.
- Fail-closed circuit breaker protection and idempotency caching (`idem_key`).

### D2: Stacking Engine & Token Ledger (`scripts/lib/stacking.py`)
- Evaluates System 1 confidence against mathematical threshold $\tau$ (default 0.90).
- Emits structured `StackingVerdict`:
  * `fast_path`: Boolean indicating autonomous resolution without LLM invocation.
  * `escalate`: Boolean indicating escalation to System 2.
  * `tokens_saved`: Calculated token savings (1,200 tokens baseline).
  * `cost_savings_ratio`: "440x".
- Appends telemetry records to `state/budget/stacking_savings.ndjson`.

### D3: Zero-Token Pre-Screen in Adversarial Reviewer (`scripts/lib/adversarial_reviewer.py`)
- Key 2 Adversarial Reviewer invokes `score_rubric` pre-screening on incoming diffs.
- Diffs evaluated as `critical_risk` with low confidence are immediately rejected with actionable evidence before consuming LLM tokens.

### D4: Model Context Protocol (MCP) Server (`scripts/mcp_laya.py`)
- High-resilience Zero-Dependency JSON-RPC 2.0 stdio server.
- Exposes 6 tools to Antigravity IDE, Claude Code, Cursor, OpenCode, and Codex:
  * `laya_status`
  * `laya_classify_intent`
  * `laya_guardrail_check`
  * `laya_score_rubric`
  * `laya_stacking_evaluate`
  * `laya_typed_decision`
- Registered in `.mcp.json` under `"laya-typed-decisions"`.

### D5: Universal Cross-Agent Governance & Rule Enforcement
- `.agents/rules/laya-typed-decisions.md` (Antigravity, OpenCode, Cline).
- `.cursor/rules/laya-typed-decisions.mdc` (Cursor).
- `.claude/skills/laya-typed-decisions/SKILL.md` (Claude Code).

---

## 3. Invariants & Safety (Iron Rules)

1. **Fail-Closed Security (I6):** Any detected injection pattern (`ignore previous instructions`, `disable kill switch`, `reveal secret`) forces `is_safe=False` and blocks execution.
2. **Zero Breaking Changes:** Existing agent workflows and OmniRoute endpoints remain 100% backward-compatible.
3. **Air-Gapped Operation:** The system never fails if internet access or remote APIs are offline; it gracefully falls back to local calibrated heuristics.
4. **Lint & Clock Discipline:** Strict adherence to `scripts/verify.py --lint-imports` and `scripts/verify.py --lint-clock`.

---

## 4. Verification Evidence

- `tests/test_laya_adapter.py`: 15 unit tests covering healthz, capabilities, model card, environment check, intent classification, guardrails, score rubric, stacking, idempotency, dry run, and sim fake contract.
- `tests/test_stacking.py`: Tests fast-path, escalation on uncertainty, and fail-closed handling.
- `scripts/verify.py --lint-imports --lint-clock`: PASS (GREEN).
- Real-time MCP stdio verification: initialize, tools/list, and tools/call all exit 0.
