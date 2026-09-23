---
name: protect-system-state
enabled: true
event: file
conditions:
  - field: file_path
    operator: regex_match
    pattern: (state/(watchdog\.json|STATE\.json|KILL.*|\w+\.sqlite|\w+\.db)|\.env)
action: warn
---

⚠️ **CRITICAL SYSTEM STATE PROTECTION**: You are attempting to edit a sensitive runtime state or credential file (`{file_path}`).
Marzneshin Agent OS manages these state files automatically via `scripts/watchdog.py` and service daemons. Manual edits may cause circuit breaker anomalies or state desynchronization.
