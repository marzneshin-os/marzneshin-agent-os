---
name: freellm-pool
description: FreeLLMAPI Universal Free-Tier Token Pool & Resilient Fast-Inference Gateway (~7.4B tokens/month across 34+ providers with automatic failover, multi-key rotation, and zero-downtime routing).
metadata:
  origin: tashfeenahmed-freellmapi
---

# FreeLLMAPI Universal Free-Tier Token Pool & Resilient Gateway

Use this skill when running coding agents (Claude Code, Antigravity, OpenCode, Cursor, Cline) with zero paid token consumption, high-speed LPU/wafer inference, or multi-provider failover.

## Core Capabilities

1. **Massive Token Pool Aggregation**:
   - Aggregates 34+ free-tier AI providers (Google Gemini, Groq, Cerebras, Mistral, SambaNova, Together, DeepInfra, OpenRouter Free, HuggingFace, Cloudflare, GitHub Models, etc.).
   - Pooled capacity: ~7.4 Billion to 9.55 Billion free tokens/month.
   - Run status check: `python3 scripts/freellm_cli.py status`.

2. **Zero-Downtime Smart Routing & Fallback**:
   - Automatic 429/402 rate-limit cooldown: when one provider or key hits quota, requests seamlessly route to the next candidate in the ladder.
   - Domain ladders:
     - `coding`: Codestral, Qwen 2.5 Coder 32B, DeepSeek Coder, Llama 3.3 70B
     - `reasoning`: DeepSeek R1, Gemini 2.5 Flash, Qwen 2.5 72B, o3-mini
     - `fast`: Groq Llama 3.1 8B, Cerebras Llama 3.1 8B, Cloudflare Edge
   - Inspect catalog: `python3 scripts/freellm_cli.py catalog --domain coding`.

3. **Multi-Key Pool Rotation**:
   - Automatically rotates multiple API keys per provider to circumvent per-key rate limits.
   - Force rotate: `python3 scripts/freellm_cli.py rotate <provider>`.

4. **Claude Code & OpenAI Compatibility**:
   - Claude Code connects directly via Anthropic protocol `/v1/messages`.
   - Setup environment:
     ```bash
     export ANTHROPIC_BASE_URL="http://127.0.0.1:3001/v1"
     export ANTHROPIC_API_KEY="free"
     export OPENAI_BASE_URL="http://127.0.0.1:3001/v1"
     export OPENAI_API_KEY="free"
     ```
   - Start local gateway daemon: `python3 scripts/freellm_cli.py serve --port 3001`.
