---
trigger: always_on
description: Enforces static-first prompt prefix ordering and preserves Marzneshin-Agent-OS invariants I1-I17 for maximum KV-cache reuse.
---

# Prefix Caching & Context Ordering Rule

1. **Static-First Read Order**: Always read and place static governance files (`CLAUDE.md`, `BUILD-SPEC.md`, `analytics/schemas/`, `agents/cards/`) BEFORE dynamic state files (`state/STATE.json`, `state/HANDOFF.md`, `state/events/`).
2. **Volatile Field Isolation**: Never insert timestamps, random UUIDs, or receipt IDs above `<!-- MARZNESHIN_KV_CACHE_BREAKPOINT_V1 -->` in `CONTEXT-PACK.md` or agent system prompts.
3. **Deterministic JSON**: Always serialize JSON objects included in prompts with `sort_keys=True` and compact separators (via `canonical_json`).
4. **Token Budget Rule**: Output diffs or minimal targeted code changes only, preserving the 60/20/20 session token budget rule from `ONBOARDING.md`.

