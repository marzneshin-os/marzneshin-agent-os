---
name: headroom
description: Context compression and optimization layer for AI coding agents. Compresses tool outputs, logs, files, and conversation history before reaching LLMs. Provides CCR (Compress-Cache-Retrieve), output token reduction, and cross-agent memory.
trigger: /headroom
---

# Headroom — Context Compression & Optimization

Headroom compresses everything your AI agent reads — tool outputs, logs, RAG chunks, files, and conversation history — before it reaches the LLM. Same answers, fraction of the tokens.

## Architecture

```
 Your Agent / App (Claude Code, Antigravity IDE, CCR, Cursor)
        │
        ▼
 ┌────────────────────────────────────────────────────┐
 │  Headroom Proxy (http://127.0.0.1:8787)            │
 │  ────────────────────────────────────────────────  │
 │  SmartCrusher (JSON) · CodeCompressor (AST)        │
 │  CCR Cache (Local store of originals)              │
 │  Output Token Shaper (HEADROOM_OUTPUT_SHAPER=1)    │
 └────────────────────────────────────────────────────┘
        │   compressed prompt + retrieval tool
        ▼
 LLM Provider (Anthropic, Gemini, OpenAI, DeepSeek, FreeLLMAPI)
```

## Available MCP Tools

When the Headroom MCP server is active, the agent has access to:

1. `headroom_retrieve`:
   - Retrieves full original content from the local CCR cache when needed.
   - Used when a compressed summary marker is encountered and exact unabridged content is required.
2. `headroom_compress`:
   - Compresses arbitrary input messages, logs, or JSON payloads on demand.
3. `headroom_stats`:
   - Returns real-time token savings, compression ratios, and cache metrics.

## CLI & Service Commands

- Start local proxy:
  ```bash
  headroom proxy --port 8787
  ```
- Run health check:
  ```bash
  headroom doctor
  ```
- Inspect savings:
  ```bash
  headroom savings
  headroom output-savings
  ```
- Cross-agent learning:
  ```bash
  headroom learn --verbosity
  headroom learn --verbosity --apply
  ```
