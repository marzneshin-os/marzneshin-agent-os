---
name: ponytail
description: YAGNI decision ladder — forces a 7-step evaluation before writing any code. Think like a lazy senior dev whose code never breaks because they barely write any. Use when user invokes /ponytail, before implementing features, or when reviewing for over-engineering.
argument-hint: "[lite | ultra | review | audit]"
user-invocable: true
---

# Ponytail — The Lazy Senior Dev's Decision Ladder

Think like a lazy senior dev whose code is never broken because they barely write any code.

## Quick Start

Climb the 7-rung ladder before writing any code. Stop at the lowest rung that solves the issue:

```text
Rung 1: Does this need to exist at all? (Challenge requirement)
Rung 2: Does standard library handle it? (Node/Python built-ins)
Rung 3: Does platform/browser handle it? (HTML/CSS/Web APIs)
Rung 4: Does an already-installed dependency handle it?
Rung 5: Can it be solved in one line?
Rung 6: Write strict minimum (no speculative abstractions)
Rung 7: Document shortcut in code
```

## Modes & Commands

- `/ponytail`: Enforce ladder on upcoming feature or task.
- `/ponytail lite`: Implement as requested, but flag if a simpler alternative existed.
- `/ponytail ultra` Aggressively challenge requirements; prefer deletion over addition.
- `/ponytail-review`: Review git diff for premature generalization, bloat, and unused abstractions.
- `/ponytail-audit`: Audit codebase for dead paths, single-impl interfaces, and redundant dependencies.

## Guardrails

- Never sacrifice security, accessibility, or core correctness for brevity.
- Never strip required validation at system boundaries.
- Document intentional shortcuts clearly.

## See Also

- `caveman`: Token optimization and output compression.
- `EXAMPLES.md`: Real-world ladder walkthroughs across rungs 1 to 7.

## Troubleshooting

See ../_shared/TROUBLESHOOTING.md for common plugin issues.
