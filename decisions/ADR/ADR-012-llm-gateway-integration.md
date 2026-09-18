# ADR-012: LLM Gateway Integration (OmniRoute / 9Router)

**Date**: 2026-08-28
**Status**: Accepted
**Context**: Marzneshin Agent OS requires the ability to securely route LLM requests (e.g. for chat, analysis, or generation) through an intelligent gateway. The user requested integration with Tasklet.ai / ClickUp via MCP and using OmniRoute / 9Router as the intelligent proxy that sits between the OS and the raw API providers (like OpenAI, Anthropic). The gateway performs load balancing, usage tracking, quota management, and token optimization (via RTK filters, caveman terseness, and ponytail scope-narrowing).

## Decision
1. **Adapter Architecture**: We introduced `OmniRouteAdapter` inside `adapters/omniroute.py` to encapsulate the REST API calls to the local proxy / 9Router gateway.
2. **Governance & Sim-safe execution**: The capability `llm.chat` was added to `scripts/lib/events.py` and `scripts/lib/policy.py`. Risk matrix entry `read_analyze` / `internal_artifact` applies. In simulation runs (`sim.py`), requests hit a local fake adapter (`sim/fakes/omniroute.py`) which ensures reproducible token outputs without spending real USD.
3. **Usage Tracking (Token Saver)**: We integrated the `lib.tokensaver` which compresses and optimizes LLM requests. Output from LLMs and token metrics are logged to `data/router_usage.jsonl` (handled inside `OmniRouteAdapter`).
4. **CLI & Proxy Interface**: Added `scripts/router.py` to allow user CLI access for testing/debugging models and viewing quota. Added `scripts/router_server.py` as an OpenAI-compatible HTTP proxy to allow Tasklet.ai and ClickUp (via MCP bridge) to securely query the gateway using the Marzneshin network namespace and tracking.

## Consequences
- **Positive**: Agents can use LLMs with a hard spending cap, token optimization, and full simulation support. Tools like Tasklet can consume Marzneshin LLM resources safely via the local proxy.
- **Negative**: The router proxy needs to be running (`python3 scripts/router_server.py`) for external tools to hit it.
- **Mitigation**: We can containerize or supervise the proxy process using `systemd` or similar in the future.

## References
- `configs/router.json` for API keys and combo settings.
- `adapters/contract.py` for adapter enforcement rules.
