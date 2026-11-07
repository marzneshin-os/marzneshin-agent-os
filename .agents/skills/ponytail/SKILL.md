---
name: ponytail
description: YAGNI decision ladder — forces a 7-step evaluation before writing any code. Think like a lazy senior dev whose code never breaks because they barely write any. Use when user invokes /ponytail, before implementing features, or when reviewing for over-engineering.
---

# Ponytail: The 7-Step YAGNI Decision Ladder

Code not written has zero bugs, requires zero maintenance, and consumes zero runtime memory.

## The 7-Step Ladder

Before writing any new function, class, package, or abstraction, climb this ladder:

1. **Step 1: Do we need to do this at all?**
   - Is this an actual immediate requirement or a speculative future scenario?
   - If speculative: STOP. Do not write code.

2. **Step 2: Does the standard library already do this?**
   - Check Python standard library (`pathlib`, `subprocess`, `json`, `dataclasses`, `functools`, `typing`).
   - If yes: Use stdlib. Do not add a dependency or helper.

3. **Step 3: Does existing project code already do this?**
   - Check `scripts/lib/` or existing utilities before creating duplicates.
   - If yes: Call the existing function.

4. **Step 4: Can a simple pure function solve it?**
   - Avoid creating classes, design patterns, factories, and managers if a 5-line pure function suffices.

5. **Step 5: Can we delete or simplify code instead of adding?**
   - The best diff is a net negative line count.

6. **Step 6: Is the interface minimal and impossible to misuse?**
   - Accept the simplest data structure (e.g. `dict`, `str`, `Path`) instead of complex nested config objects.

7. **Step 7: If code must be written, write surgical code.**
   - Touch only what is strictly necessary. No speculative parameters, no premature abstractions.

## Modes
- `/ponytail`: Evaluate proposed implementation against the 7-step ladder.
- `/ponytail-audit`: Scan a pull request or file for over-engineering, dead code, and speculative abstractions.
