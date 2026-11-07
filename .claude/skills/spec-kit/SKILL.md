---
name: spec-kit
description: Specification-Driven Development (SDD) framework inspired by GitHub Spec Kit (Khairallah Stack Tool #06). Use when designing features, writing technical blueprints, or creating verifiable task decompositions before touching implementation code.
---

# Specification-Driven Development (Spec Kit)

Spec Kit enforces the discipline of thinking and specifying before coding. It eliminates "vibe coding" bugs and architectural dead-ends.

## The 4-Phase Pipeline

### Phase 1: The Specification (`specs/SPEC-<name>.md`)
Focus strictly on **WHAT** and **WHY**, not code details:
- **User Scenarios**: Concrete user/agent interaction scenarios with inputs and expected outputs.
- **Project Invariants Mapping**: Explicitly list which `BUILD-SPEC.md` invariants (I1-I17) apply.
- **Non-Goals**: Explicitly declare what is OUT OF SCOPE.
- **Edge Cases & Failure Modes**: Network partition, invalid JSON, missing API keys, rate limits.

### Phase 2: Technical Blueprint
- Component boundaries and data models (Pydantic / Dataclass / JSON Schema).
- Storage and state implications (events, locks, or state plane impacts).
- Reversibility and rollback plan (`rollback.tested = true`).

### Phase 3: Task Decomposition (Task Master)
Feed the specification into Task Master AI:
```bash
python3 scripts/taskmaster_cli.py init specs/SPEC-<name>.md
python3 scripts/taskmaster_cli.py list
```
Each task must be atomic, sequential, and tied to dependencies.

### Phase 4: Verification & Gate
- Every scenario must have a corresponding unit test in `tests/test_<name>.py`.
- Two-Key sign-off: Run `python3 scripts/verify.py --all` before declaring completion.