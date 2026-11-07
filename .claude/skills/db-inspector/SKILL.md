---
name: db-inspector
description: Natural Language friendly SQLite & LangGraph checkpoint inspection (Khairallah Stack Tool #43 Vanna AI / NL-SQL). Use when querying state databases, checking checkpoint lineages, or troubleshooting agent state.
---

# Database & LangGraph State Inspector

Safely query and inspect SQLite databases and LangGraph checkpoints across Marzneshin Agent OS.

## Inspection Workflows
- **Discover Tables**: `python3 scripts/db_query_cli.py tables`
- **Inspect Columns**: `python3 scripts/db_query_cli.py schema checkpoints`
- **Recent Checkpoints**: `python3 scripts/db_query_cli.py checkpoints --limit 10`
- **Execute Safe Queries**:
  ```bash
  python3 scripts/db_query_cli.py query "SELECT thread_id, checkpoint_id FROM checkpoints ORDER BY checkpoint_id DESC LIMIT 5"
  ```

*Rule: The inspector enforces read-only mode (`mode=ro`) to prevent accidental state corruption.*