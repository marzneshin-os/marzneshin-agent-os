# Leases Directory
This directory holds fencing token lease files for the orchestration system.
Each lease is a JSON file: `{agent}-{target}-{timestamp}.json`
Leases have a TTL of 1 hour and are reaped by @handoff-guardian.
