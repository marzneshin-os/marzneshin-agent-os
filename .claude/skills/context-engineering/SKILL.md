---
name: context-engineering
description: Context engineering, KV-cache optimization, and context degradation prevention based on Muratcan Koylan's reference architecture (Khairallah Stack Tool #29). Use when structuring long sessions, minimizing token waste, handling high-output tool results, or optimizing Anthropic prompt caching.
---

# Context Engineering & KV-Cache Optimization

Context Engineering curates, filters, and structures everything entering Claude Code's attention window to prevent context rot, attention scarcity, and lost-in-the-middle degradation.

## 1. Prompt Caching Discipline (Anthropic KV-Cache)
- **Stable Prefixes**: Keep system instructions and rule definitions byte-identical across prompts to trigger Anthropic's 90% cache discount.
- **Dynamic Content at the Tail**: Append session-specific queries, diffs, and tool outputs at the bottom of the prompt, never inserting dynamic tokens above static rule blocks.

## 2. Observation Masking (Handling Heavy Tool Outputs)
- Do NOT dump raw multi-megabyte log files or full test dumps into context.
- Use targeted filtering (`grep`, `head -n 40`, `tail -n 40`, `wc -l`) to surface only actionable signal.
- In `hooks/pre_tool.py` and `hooks/pre_compact.py`, repetitive command logs are automatically summarized.

## 3. Progressive Disclosure
- Load details on-demand: Keep `SKILL.md` files concise (< 400 lines).
- Store reference tables and auxiliary documentation in subfolders (`references/`, `docs/`) and fetch only when explicitly triggered.

## 4. Context Compaction Cadence
- Execute `/compact` or `python3 scripts/compact.py` after major task milestones to reconstruct `STATE.json` and reset working memory.
- Monitor token costs with `/cost` or `python3 scripts/cost_tracker.py status`.