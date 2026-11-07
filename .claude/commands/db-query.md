---
description: Natural Language to SQLite & LangGraph Checkpoint Inspector (Khairallah Stack #43 Vanna AI / NL-SQL)
---

**NATURAL LANGUAGE TO SQL & DATABASE INSPECTOR**

Inspect and query Marzneshin state databases:
1. **List Tables**: `python3 scripts/db_query_cli.py tables`
2. **View Schema**: `python3 scripts/db_query_cli.py schema <table_name>`
3. **Run Query**: `python3 scripts/db_query_cli.py query "SELECT * FROM checkpoints LIMIT 5"`
4. **Recent Checkpoints**: `python3 scripts/db_query_cli.py checkpoints --limit 10`