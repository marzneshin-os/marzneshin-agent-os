---
name: dev-workflow
description: Central development operations runner for Marzneshin Agent OS (status, start, stop, restart, verify)
tools: Bash
user-invocable: true
disable-model-invocation: false
---

# Development Operations Workflow

Execute primary lifecycle and verification commands for Marzneshin Agent OS.

## Commands

```bash
# Check service processes and ports
python3 scripts/dev.py status

# Run deep health check with circuit breaker status
python3 scripts/dev.py health

# Run repository verification suite
python3 scripts/verify.py

# Run watchdog unit tests
pytest tests/test_watchdog.py -v
```
