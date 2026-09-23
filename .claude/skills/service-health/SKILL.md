---
name: service-health
description: Quick status and health check inspection for all 12 Marzneshin Agent OS services and watchdog circuit breakers
tools: Bash
user-invocable: true
disable-model-invocation: false
---

# Service Health & Watchdog Status

Inspect the operational health of all 12 Marzneshin Agent OS services and circuit breaker states.

## Workflow

Run the unified health diagnostic:

```bash
python3 scripts/dev.py health
```

This checks:
- HTTP 200 response on official endpoints (agentmemory, ccr, omniroute, langgraph, freellmapi, headroom, codeburn, kimi_k3, relevance_bridge, claude_mem)
- Process supervision (graphify, memory_sync)
- Watchdog circuit breaker state machine (`closed`, `open`, `half-open`)
- Systemd timer `marzneshin-watchdog.timer`
