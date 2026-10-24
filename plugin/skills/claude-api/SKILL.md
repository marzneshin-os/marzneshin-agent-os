---
name: claude-api
description: Reference implementations and best practices for Anthropic Messages API across 8 languages. Use when implementing Claude API calls, configuring prompt caching, streaming, batch processing, or tool use.
argument-hint: "[language | feature]"
user-invocable: true
---

# Claude API — Anthropic Messages API Reference & Patterns

Production-grade integration patterns for the Anthropic Messages API across Python, TypeScript, Go, Java, C#, PHP, Ruby, and cURL.

## Quick Start

Key API features supported:
- **Prompt Caching:** Cache static system prompts and tools (`cache_control: {type: "ephemeral"}`) to reduce latency and save up to 90% input costs.
- **Tool Use (Function Calling):** Define JSON schemas, handle `tool_use` blocks, and return `tool_result` responses.
- **Streaming:** Server-Sent Events (SSE) handling with token-by-token processing.
- **Message Batches:** Asynchronous bulk processing at 50% discount.
- **Thinking / Extended Reasoning:** Configure `thinking: { type: "enabled", budget_tokens: N }`.

## Core Recommendations

1. Always use the latest model identifiers (`claude-3-7-sonnet-20250219`, `claude-3-5-haiku-20241022`).
2. Mark cache breakpoints on large static context blocks (system instructions, tool definitions).
3. Always validate tool input payloads before executing application logic.
4. Set explicit timeouts and retry on transient HTTP 429 / 529 errors with exponential backoff.

## See Also

- `REFERENCE.md`: Complete code snippets across all 8 supported programming languages.

## Troubleshooting

See ../_shared/TROUBLESHOOTING.md for connectivity and authentication guidance.
