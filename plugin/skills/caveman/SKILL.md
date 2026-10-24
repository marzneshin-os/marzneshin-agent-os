---
name: caveman
description: Token optimization — compresses agent output, drops filler and pleasantries, keeps technical accuracy. Use when the user invokes /caveman, asks for shorter responses, or wants to reduce token waste.
argument-hint: "[lite | full | ultra]"
user-invocable: true
---

# Caveman — Token Optimization

Compress output, eliminate conversational fluff, and cut token spend while preserving technical accuracy.

## Quick Start

Activate caveman mode via slash command or tier argument:
- `/caveman lite` — Drop conversational filler and hedging, maintain normal sentence grammar.
- `/caveman full` — Telegraphic sentences, omit unnecessary articles/pronouns, high compression (Default).
- `/caveman ultra` — Extreme token conservation, keywords, diffs, code only.

## Compression Tiers

### Lite Mode (`/caveman lite`)
- Strip greetings, pleasantries ("Certainly!", "I'd be glad to help"), and apologies.
- Strip conversational hedges ("I think", "It appears that", "You might consider").
- Keep complete technical grammar, explanation of trade-offs, and full code blocks.

### Full Mode (`/caveman full` — Default)
- Telegraphic prose. Drop auxiliary verbs, redundant pronouns, and filler adjectives.
- Bullet points over multi-paragraph essays.
- State facts directly: "Port 3111 busy. Switched to 3112. Restarted daemon."

### Ultra Mode (`/caveman ultra`)
- Pure data: code snippets, diffs, terminal outputs, and 1-3 word verdicts.
- No commentary unless explicitly asked.

## Invariant Rules

1. NEVER compress code, regex, config schemas, URLs, or commands.
2. NEVER skip error messages, diagnostic traces, or file paths.
3. Keep markdown formatting (lists, tables, code fences).
4. If a decision has non-obvious risk, state the risk clearly.

## See Also

- `ponytail`: YAGNI ladder before writing code.
- `EXAMPLES.md`: Concrete before-and-after examples for each tier.

## Troubleshooting

See ../_shared/TROUBLESHOOTING.md for common plugin issues.
