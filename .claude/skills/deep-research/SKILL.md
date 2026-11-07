---
name: deep-research
description: 8-Phase Deep Research pipeline with citation ledgers and source triangulation inspired by 199 Biotechnologies (Khairallah Stack Tool #30). Use when conducting complex architecture reviews, evaluating external libraries, or compiling multi-source evidence reports.
---

# 8-Phase Deep Research Protocol

Deep Research transforms casual search into rigorous, verifiable technical investigation.

## The 8 Phases

1. **Scoping**: Formulate precise technical hypotheses, decision matrices, and evaluation criteria.
2. **Search Discovery**:
   - Query **Tavily Search** (`tavily_search`) for clean, LLM-optimized web results without SEO fluff.
   - Query **Context7** (`context7`) for live, version-accurate documentation of target libraries.
3. **Data Extraction**: Extract full-text content via `tavily_extract` or `scripts/webcmd_cli.py`.
4. **Triangulation**: Validate any critical claim, benchmark, or API signature across at least two independent reputable sources.
5. **Credibility Scoring**: Score sources based on authority:
   - Tier 1: Official repository source code, vendor docs, release tags.
   - Tier 2: Established engineering benchmarks, technical RFCs.
   - Tier 3: Community posts, forum discussions (requires cross-validation).
6. **Citation Ledger**: Maintain a structured evidence ledger:
   `[ID] Claim -> Source URL -> Exact Quote -> Verified (Y/N)`
7. **Adversarial Red-Teaming**: Challenge initial findings: "What breaks if this assumption is wrong? What are the hidden costs or deprecations?"
8. **Structured Synthesis**: Output a clear Markdown report with summary recommendations, tradeoffs table, and implementation steps.