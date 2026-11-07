---
name: caveman
description: Token optimization skill — compresses agent output, drops filler and pleasantries, keeps technical accuracy. Use when the user invokes /caveman, asks for shorter responses, or wants to reduce token waste.
---

# Caveman: Token Optimization Skill

"Why use many token when few token do trick?"

## Core Directive
Strip conversational filler, pleasantries, preambles, and postambles. Deliver maximum technical information per token while preserving 100% precision for code, paths, commands, and error diagnoses.

## Modes

### 1. `/caveman lite` (Default when invoked)
- Eliminate conversational fluff ("Sure, I can help with that", "As you requested", "Here is the code").
- State findings, actions, and test results directly.
- Preserve full code blocks, type definitions, and diffs.
- Bullet points over multi-sentence paragraphs.

### 2. `/caveman full`
- Telegraphic phrasing: "Test failed. Line 42. Null pointer. Fixed. Ran tests. 12/12 passed."
- No narrative transitions.
- Absolute minimal prose between tool calls.

### 3. `/caveman ultra`
- Output strictly diffs, commands, and test outputs.
- Zero descriptive prose unless an error halts execution.

## Invariant Rules
- NEVER truncate code, test commands, or error logs.
- NEVER skip verification steps or fabricate certainty.
- Always provide exact clickable file paths `file:///...`.
