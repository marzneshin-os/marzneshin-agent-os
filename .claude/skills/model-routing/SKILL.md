---
name: model-routing
description: Model Gateway routing resilience, circuit breaking, and multi-provider failover inspired by Portkey and OmniRoute (Khairallah Stack Tools #49 & #50). Use when configuring model combos, monitoring provider quotas, or troubleshooting rate limits.
---

# Model Gateway Routing & Resilience

Manage multi-provider LLM routing, failovers, and quotas across OmniRoute, CCR, xKiro, FreeModels, and FreeLLMAPI pool.

## Key Principles
1. **Circuit Breaking**: Automatically trip provider circuits on consecutive 429 rate limits or timeouts.
2. **Fallback Cascades**: Chain fast/cheap models first, cascading to reasoning models on complex tasks.
3. **Budget Caps**: Enforce hard dollar and token limits before switching providers.

## CLI Tools
- `python3 scripts/router_cli.py status`: View gateway operational matrix.
- `python3 scripts/router_cli.py combos`: Inspect routing cascades.
- `python3 scripts/router_cli.py test <gateway>`: Test endpoint reachability.