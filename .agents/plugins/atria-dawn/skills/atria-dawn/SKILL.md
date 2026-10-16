---
name: atria-dawn
description: High-performance orchestration of the Shanghai AI Lab 744B MoE Atria-Dawn-Preview model for agentic coding, deep architecture reasoning, heavy codebase refactoring, and test generation using the 100M free token pool.
---

# Atria-Dawn 744B MoE Skill

This skill allows Antigravity agents to offload computationally heavy tasks, massive code generation, or complex debugging to the 744-Billion parameter Mixture-of-Experts **Atria-Dawn-Preview** model via MCP or direct CLI execution.

## When to Use

1. **Heavy Codebase Generation**: Generating entire modules, extensive tests, or full boilerplate without burning primary agent context/tokens.
2. **Deep Diagnostic Debugging**: Root-cause analysis on complex multi-file bugs or stack traces.
3. **Architectural Review**: Second-opinion reasoning on algorithmic tradeoffs and data structures.

## Available MCP Tools

* `atria_reason`: Run deep architectural reasoning with Atria-Dawn-Preview.
* `atria_generate_code`: Generate complete production-grade modules and functions.
* `atria_debug_code`: Provide code + stack trace to get exact fixes.
* `atria_health`: Verify API key validity, connectivity, and token latency.

## Terminal Execution

To launch Claude Code using Atria-Dawn in your terminal:
- In WSL / Linux: `./scripts/launch_claude_atria.sh`
- In Windows PowerShell: `.\scripts\launch_claude_atria.ps1`
