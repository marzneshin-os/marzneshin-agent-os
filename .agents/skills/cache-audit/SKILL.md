---
name: cache-audit
description: Audits prompt prefix determinism, verifies that no volatile timestamps or secrets pollute Tiers 0-2, and checks KV cache hit telemetry against the 60/20/20 token budget rule and Counter-KPI I13.
---

# Systems Thinking Prefix Cache Audit

When invoked via `/cache-audit`, perform the following verification without modifying `state/STATE.json` or `receipts/_chain`:

## 1. Prefix Hash Stability Check
Run `python3 scripts/context_pack.py` twice consecutively and verify that `static_prefix_sha256` remains 100% byte-identical.

## 2. Secret & Redaction Scan (Invariant I6)
Verify via `scripts/lib/redact.py` that no raw secrets, tokens, or credentials exist inside `CONTEXT-PACK.md` or `agents/prompts/`.

## 3. Counter-KPI Verification (Invariant I13)
Verify that `TIER-3: DYNAMIC SESSION TAIL` lies strictly below:
```markdown
<!-- MARZNESHIN_KV_CACHE_BREAKPOINT_V1 -->
```
and accurately reflects the live output of `python3 scripts/killswitch.py status`.

## 4. Telemetry Report
Output a Markdown table showing:
- Static Prefix Size (bytes and tokens)
- Prefix SHA-256 Digest
- Breakpoint Position
- Live Kill-Switch Status

