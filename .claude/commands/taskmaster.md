---
description: Task Master AI Pipeline — PRD to structured DAG tasks with dependencies (Khairallah Stack #18)
---

**TASK MASTER AI ORCHESTRATION**

Manage the structured execution pipeline:
1. **Check Status**: `python3 scripts/taskmaster_cli.py status`
2. **View Pipeline**: `python3 scripts/taskmaster_cli.py list`
3. **Execute Next Task**: `python3 scripts/taskmaster_cli.py next`
4. **Start Work**: `python3 scripts/taskmaster_cli.py start <TASK_ID>`
5. **Complete Work**: `python3 scripts/taskmaster_cli.py complete <TASK_ID> --receipt <RECEIPT_ID>`

Rule: Never skip tasks or start a task whose dependencies are not marked COMPLETED.