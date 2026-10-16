# Implementation Plan: FreeLLMAPI Universal Free-Tier Token Pool & Resilient Gateway Architecture

**Date:** 2026-10-01  
**Author:** Antigravity AI Engineering Council  
**Workstream:** agentic-core / inference-gateway  
**Target:** Production-Grade Cross-Agent Free-Tier Aggregation & Fast Inference  
**Video Reference:** https://youtu.be/lVauGVmaYhA?is=PBvbBdOiyYArymy0 ("FreeLLMAPI Setup: Connect Claude for free 7.4B AI Tokens")  

---

## 1. Executive Summary & Video Analysis
The reference video introduces **FreeLLMAPI** (by tashfeenahmed), an open-source architecture that aggregates free developer tiers across 34+ LLM providers (including Groq, Google AI Studio/Gemini, Mistral, Cerebras, SambaNova, Together AI, DeepInfra, OpenRouter Free, HuggingFace, Cloudflare Workers AI, GitHub Models) into a single resilient OpenAI- and Anthropic-compatible gateway. It unlocks an estimated **7.4 Billion tokens/month** in combined capacity through:
1. **Unified Token Pool**: Multiplexing API keys across providers with automatic rate-limit cooldown (429/402 backoff).
2. **Transparent Protocol Translation**: Exposing both OpenAI `/v1/chat/completions` and Anthropic `/v1/messages` formats so coding agents (Claude Code, Antigravity, OpenCode, Cursor, Cline) can connect seamlessly.
3. **Smart Failover Chains**: Multi-tier fallback routing across providers and models to guarantee zero-downtime agent loops.
4. **Encrypted Key Vault**: Secure credential storage with AES-256-GCM / environment resolution.

In Marzneshin Agent OS, this capability integrates directly into the existing L0 Adapter layer (`adapters/freellm.py`), shared library layer (`scripts/lib/freellm_pool.py`), local router proxy (`scripts/router_server.py`), CLI tooling (`scripts/freellm_cli.py`), MCP servers (`scripts/mcp_freellm.py`), and cross-agent rule harnesses.

---

## Phase 1: Core Shared Capability (`scripts/lib/freellm_pool.py`)
- [x] Task 1.1: Implement `FreeLLMProvider` and catalog defining 34+ supported free-tier providers, rate limits, models, base URLs, and token quotas.
- [x] Task 1.2: Implement `KeyVault` supporting AES-256-GCM encrypted persistence, secure fallback to environment variables, and memory redaction.
- [x] Task 1.3: Implement `FreeLLMPoolManager` with multi-key rotation, automatic 429/402 cooldown timers (sliding window), key health metrics, and token tracking (~7.4B total capacity).
- [x] Task 1.4: Implement `SmartFallbackRouter` with domain-specific fallback ladders (`coding`, `reasoning`, `eval`, `general`).
- [x] Task 1.5: Implement unit tests in `tests/test_freellm_pool.py`.

## Phase 2: L0 System Adapter & Simulation Fake (`adapters/freellm.py`, `sim/fakes/freellm.py`)
- [x] Task 2.1: Implement `FreeLLMAdapter` adhering strictly to BUILD-SPEC §4 Adapter protocol (CircuitBreaker, IdempotencyStore, deadline, dry_run, provenance, rollback).
- [x] Task 2.2: Implement `FreeLLMFake` in `sim/fakes/freellm.py` for deterministic simulation without network I/O.
- [x] Task 2.3: Register capability payloads in `adapters/contract.py` (`llm_chat`, `llm_messages`, `pool_status`, `rotate_key`, `test_provider`).
- [x] Task 2.4: Implement contract and unit tests in `tests/test_freellm_adapter.py`.

## Phase 3: Gateway Proxy & Protocol Translation (`scripts/router_server.py`)
- [x] Task 3.1: Add Anthropic `/v1/messages` endpoint to `scripts/router_server.py` allowing Claude Code direct native connectivity (`ANTHROPIC_BASE_URL`).
- [x] Task 3.2: Implement SSE streaming support (`stream: true`) for chat completions and messages.
- [x] Task 3.3: Expose diagnostics endpoints `/v1/freellm/status` and `/v1/freellm/catalog`.
- [x] Task 3.4: Update `configs/router.json` and `configs/keys_pool.json` with FreeLLMAPI pool definitions and combos.

## Phase 4: CLI Interface & MCP Server Integration
- [x] Task 4.1: Implement `scripts/freellm_cli.py` with subcommands: `status`, `catalog`, `test`, `rotate`, `keys`, `serve`, `export-env`.
- [x] Task 4.2: Implement `scripts/mcp_freellm.py` stdio JSON-RPC 2.0 MCP server.
- [x] Task 4.3: Register `freellm-pool` in root `.mcp.json`.
- [x] Task 4.4: Expose `freellm_pool_status` and `freellm_test_provider` in `agents/graph_nodes.py` WORKER_TOOLS.

## Phase 5: Cross-Agent Directives & SSOT Parity
- [x] Task 5.1: Create `.agents/skills/freellm-pool/SKILL.md` and `.agents/rules/freellm-pool.md` (Antigravity).
- [x] Task 5.2: Create `.claude/skills/freellm-pool/SKILL.md` and update `CLAUDE.md` (Claude Code).
- [x] Task 5.3: Create `.cursor/rules/freellm-pool.mdc` and update `.cursorrules`, `.clinerules`, `.windsurfrules`, `.kilorules`, `GEMINI.md`.

## Phase 6: Verification, Validation & Health Gates
- [x] Task 6.1: Run `python3 scripts/verify.py --all` (all 6 invariant gates pass: chain, events, schemas, agent-cards, lint-imports, lint-clock).
- [x] Task 6.2: Run full test suite: `python3 -m unittest discover -s tests`.
- [x] Task 6.3: Run `python3 scripts/freellm_cli.py status` and `python3 scripts/freellm_cli.py catalog`.
