# 🧠 Harness² Level-2 Experience Ledger (`state/EXPERIENCE.md`)

Structured experiential memory persisted across `marzneshin-agent-os` tasks using the Google Research Harness² Triplet Schema (`Cue` / `Lesson` / `Empirical Evidence`).

## Entry `4d217b061407` — 2026-10-23T09:41:33.796042+00:00
- **Cue:** NEXUS x Harness² V3 integration across marzneshin-agent-os governance and self-correct.ts
- **Lesson:** Use non-destructive AST/marker patching with fail-closed rollback and parallel C_inv/C_dom probing.
- **Empirical Evidence:** Verified via scripts/harness2.py status, verify-sync, and test/harness2-self-correct.test.ts

## Entry `7e50f2b705df` — 2026-10-23T09:58:55.516604+00:00
- **Cue:** NEXUS x Harness² V3 integration across marzneshin-agent-os governance and self-correct.ts
- **Lesson:** Use non-destructive AST/marker patching with fail-closed rollback and parallel C_inv/C_dom probing.
- **Empirical Evidence:** Verified via scripts/harness2.py status, verify-sync, and test/harness2-self-correct.test.ts

## Entry `e05fb2870839` — 2026-10-23T10:00:37.749128+00:00
- **Cue:** NEXUS x Harness² V3 integration across marzneshin-agent-os governance and self-correct.ts
- **Lesson:** Use non-destructive AST/marker patching with fail-closed rollback and parallel C_inv/C_dom probing.
- **Empirical Evidence:** Verified via scripts/harness2.py status, verify-sync, and test/harness2-self-correct.test.ts

## Entry `0ad360e54883` — 2026-10-23T10:06:52.616990+00:00
- **Cue:** NEXUS x Harness² V3 integration across marzneshin-agent-os governance and self-correct.ts
- **Lesson:** Use non-destructive AST/marker patching with fail-closed rollback and parallel C_inv/C_dom probing.
- **Empirical Evidence:** Verified via scripts/harness2.py status, verify-sync, and test/harness2-self-correct.test.ts

## Entry `f58f70d5a235` — 2026-10-23T10:15:57.726807+00:00
- **Cue:** NEXUS x Harness² V3 integration across marzneshin-agent-os governance and self-correct.ts
- **Lesson:** Use non-destructive AST/marker patching with fail-closed rollback and parallel C_inv/C_dom probing.
- **Empirical Evidence:** Verified via scripts/harness2.py status, verify-sync, and test/harness2-self-correct.test.ts

## Entry `1bb421e89cef` — 2026-10-23T10:19:53.998877+00:00
- **Cue:** NEXUS x Harness² V3 integration across marzneshin-agent-os governance and self-correct.ts
- **Lesson:** Use non-destructive AST/marker patching with fail-closed rollback and parallel C_inv/C_dom probing.
- **Empirical Evidence:** Verified via scripts/harness2.py status, verify-sync, and test/harness2-self-correct.test.ts

## Entry `5c85006da485` — 2026-10-23T10:27:06.326544+00:00
- **Cue:** NEXUS x Harness² V3 integration across marzneshin-agent-os governance and self-correct.ts
- **Lesson:** Use non-destructive AST/marker patching with fail-closed rollback and parallel C_inv/C_dom probing.
- **Empirical Evidence:** Verified via scripts/harness2.py status, verify-sync, and test/harness2-self-correct.test.ts

## Entry `d3f1c237f5f5` — 2026-10-24T10:07:52.816500+00:00
- **Cue:** NEXUS x Harness² V3 integration across marzneshin-agent-os governance and self-correct.ts
- **Lesson:** Use non-destructive AST/marker patching with fail-closed rollback and parallel C_inv/C_dom probing.
- **Empirical Evidence:** Verified via scripts/harness2.py status, verify-sync, and test/harness2-self-correct.test.ts

## Entry `662f8f3f54da` — 2026-10-24T21:45:21.334096+00:00
- **Cue:** Phase 5 ADR-033 AgentRouter Unified Multi-Harness Mesh (gpt-6.1sol 24/7 unlimited stateless scrub, gpt-6-astra 03:00/15:00 BJT window, dual-protocol gateway)
- **Lesson:** Strip stateful reasoning tokens for gpt-6.1sol to prevent cross-node Decryption Failure, strip billing_summary SSE frames, and bridge Anthropic /v1/messages to OpenAI /v1/chat/completions locally.
- **Empirical Evidence:** Verified via test/agentrouter-mesh.test.ts, test/python/test_agentrouter_mesh.py, sim/harness.py, verify.py (7/7), and two_key_gate.py (APPROVED).

## Entry `2b08e5efd001` — 2026-10-26T21:30:03.285844+00:00
- **Cue:** Prompt Caching & KV Cache Prefix Contiguity (ADR-034)
- **Lesson:** LLM prompt caching relies on exact prefix hash contiguity from token 0. To prevent TTFT degradation from 0.8s to 184s, enforce Inverted Pyramid ordering: Zone 1 (immutable system prompt, no timestamps) -> Zone 2 (alphabetized tool definitions) -> Zone 3 (settled memories) -> Zone 4 (Anthropic ephemeral breakpoint >=1024 tok) -> Zone 5 (dynamic timestamps and user request at prompt tail). Cross-protocol gateways must map cached_tokens to cache_read_input_tokens and pass cache_prompt: true to local engines without stripping cache controls during stateless scrubbing.
- **Empirical Evidence:** 1874 vitest tests passed across 184 files (test/prompt-caching.test.ts); 62 python tests passed (test/python/test_prompt_caching_gateway.py); atomic_sync PASS.
