---
description: Specification-Driven Development (GitHub Spec Kit — Khairallah Stack #06)
---

**SPECIFICATION-DRIVEN DEVELOPMENT (SDD)**

Follow the 4-phase GitHub Spec Kit workflow:
1. **The Spec**: Define *what* to build and *why* (user scenarios, boundary conditions, invariant mapping) in `specs/SPEC-<feature>.md`.
2. **The Blueprint**: Detail data schemas, interfaces, error handling, and rollback strategy.
3. **The Tasks**: Decompose into incremental, bite-sized tasks using Task Master AI (`python3 scripts/taskmaster_cli.py init specs/SPEC-<feature>.md`).
4. **Verification Criteria**: Every scenario must specify concrete test commands that pass 100% green before sign-off.