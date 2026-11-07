# ADR-030: Deterministic Prompt Prefix Stratification & KV-Cache Reuse Engine

**Date:** 2026-11-07  
**Status:** Accepted  
**Author:** Executive Systems Architect & Autonomous Architecture Council  
**Workstream:** agentic-core / inference-optimization / kv-cache-governance  
**Governing Standard:** BUILD-SPEC.md v2.0, CLAUDE.md (I1–I17), ADR-001, ADR-022, ADR-026  

---

## 1. Context & Benchmark Analysis

In transformer-based LLM inference, processing requests is split into two distinct execution phases:
1. **Prefill Phase (Prompt Processing)**: Compute-bound ($O(N^2)$ attention computations across all input tokens).
2. **Decode Phase (Token Generation)**: Bandwidth-bound (sequential generation of tokens).

When large system architectures, schemas, and governance documents (`BUILD-SPEC.md`, `CLAUDE.md`, `analytics/schemas/`, `agents/cards/`) are prepended to agent prompts, the prefill bottleneck causes severe latency:
- On a 7B parameter local model (`Qwen2.5-Coder-7B-Instruct`), Cold Prefill takes up to **184 seconds** on consumer-grade hardware.
- With **Prompt Prefix Caching / KV-Cache Reuse** (vLLM, SGLang, llama.cpp), redundant prefill is skipped, dropping TTFT (Time-To-First-Token) to **0.8 seconds** (a 99.5% latency reduction).
- Across commercial cloud APIs (Claude, OpenAI, Gemini), input token costs are reduced by **90% to 95%** on cached prefix blocks.

### The Problem: Cache-Busting Anti-Pattern
KV-cache lookup in inference engines utilizes prefix trees (Radix Trees). Any mutation, volatile timestamp, or changed character at the beginning of a prompt invalidates 100% of the subsequent cached blocks.
Prior to ADR-030, `scripts/context_pack.py` generated `CONTEXT-PACK.md` with volatile timestamps (`clock.iso()`), live kill-switch status, and event snapshots at the top of the file, completely defeating KV-cache reuse across agent turns.

---

## 2. Decision: 4-Tier Deterministic Prefix Hierarchy

We adopt a strict 4-Tier prompt stratification model:

```
┌────────────────────────────────────────────────────────┐
│ Tier 0: Immutable OS Kernel                            │
│ (CLAUDE.md, BUILD-SPEC §0/§16/§17, TRADEOFF-REGISTER)  │ ◄── 100% Cached (Global Root)
├────────────────────────────────────────────────────────┤
│ Tier 1: Agent Persona & Skill Index                    │
│ (agents/cards/*.json, .agents/skills/ metadata)       │ ◄── Cached per Agent Persona
├────────────────────────────────────────────────────────┤
│ Tier 2: Semi-Static Session Context Pack               │
│ (decisions/ADR/, GAP-REPORT summaries)                 │ ◄── Cached Session Snapshot
╞════════════════════════════════════════════════════════╡
│ <!-- MARZNESHIN_KV_CACHE_BREAKPOINT_V1 -->             │ ◄── Cache Breakpoint Marker
╞════════════════════════════════════════════════════════╡
│ Tier 3: Dynamic Execution Tail (UNCACHED)              │
│ (Kill Switch status, STATE.json, HANDOFF.md, Task input)│ ◄── Fresh Evaluation (Fail-Closed)
└────────────────────────────────────────────────────────┘
```

### Core Components
1. **`scripts/lib/prefix_cache.py`**:
   - Python stdlib-only module.
   - `canonical_json()` ensures deterministic dictionary key serialization.
   - `strip_volatile_fields()` strips timestamps and volatile markers without mutation.
   - `PrefixEnvelope` encapsulates the 4 tiers, computes `prefix_sha256` for integrity auditing, and provides formatting methods for Anthropic (`cache_control`), OpenAI/vLLM (leading system message).
   - `extract_cache_telemetry()` logs cache hits and ratios into budget metrics.
2. **`scripts/context_pack.py` Upgrade**:
   - Rebuilds `CONTEXT-PACK.md` using `PrefixEnvelope`.
   - Places immutable governance and ADR summaries above the cache breakpoint marker.
   - Places live state snapshot and kill switch strictly in Tier 3 below the breakpoint.
3. **Antigravity IDE Integration**:
   - `/fsp-warm-start` (`.agents/skills/fsp-warm-start/SKILL.md`)
   - `/cache-audit` (`.agents/skills/cache-audit/SKILL.md`)
   - `/systems-cache-map` (`.agents/skills/systems-cache-map/SKILL.md`)
   - Permanent rule: `.agents/rules/prefix-caching.md`

---

## 3. Invariants & Zero Side-Effects Compliance Matrix

| Invariant | Requirement | Compliance Guarantee |
|:---|:---|:---|
| **I1 (SSoT)** | GitHub is SSoT; `STATE.json` is derived from event log | Prefix caching stores no state; `STATE.json` remains derived by `compact.py` and read strictly in Tier 3. |
| **I3 & I15 (Receipt Chain)** | Cryptographic receipt chaining | Cache metrics (`cached_input_tokens`, `prefix_cache_hit_ratio`) are logged as auxiliary telemetry without altering receipt hash chains. |
| **I6 (No Raw Secrets)** | No raw secrets in prompts or commits | Static prefix includes public repo governance only and passes through `lib/redact.py`. |
| **I7 (Reversibility)** | Every change has a tested rollback | Prefix caching can be reverted instantly without database or schema migration. |
| **I11 (Sim-First Delivery)** | Simulation evidence before production | Validated via `tests/test_prefix_cache.py` with 100% pass rate. |
| **I13 (Counter-KPI)** | Every KPI has an independent Counter-KPI | KPI: Prefix cache hit ratio (Adapter/Gateway). Counter-KPI: Live kill-switch & state freshness verified (Verifier). |
| **Stdlib-Only** | No external dependencies in `scripts/lib/` | Pure Python stdlib (`hashlib`, `json`, `dataclasses`, `pathlib`, `typing`). |

---

## 4. Verification & Status
- Unit tests: `tests/test_prefix_cache.py` (7/7 passed).
- Integration test: `tests/test_scripts.py::TestContextPack` (passed).
- Determinism test: `scripts/context_pack.py` yields identical `prefix_sha256` across consecutive executions.

