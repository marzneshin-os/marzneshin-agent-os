---
name: ecc-harness
description: Everything Claude Code (ECC) Universal Agent Harness, AgentShield Security Auditor, and Continuous Learning Instincts Engine.
metadata:
  origin: anthropic-hackathon-ecc
---

# Everything Claude Code (ECC) Universal Agent Harness

Use this skill when performing multi-agent coordination, pre-commit security audits with AgentShield, or consulting persistent engineering instincts.

## Core Capabilities

1. **AgentShield Proactive Security**:
   - Audit files, rules, configs, and MCP permissions for secrets, prompt injections, and unsafe shell commands.
   - Run audit before committing: `python3 scripts/ecc_cli.py scan`.
   - MCP tool: `ecc_agentshield_scan`.
   - LangGraph tool: `ecc_agentshield_audit`.

2. **Continuous Learning Instincts**:
   - Query project conventions and learned architectural rules: `python3 scripts/ecc_cli.py instincts`.
   - Record new lessons: `python3 scripts/ecc_cli.py instincts learn --trigger "<regex>" --rule-action "<rule>" --domain "<domain>"`.
   - MCP tool: `ecc_instinct_query`, `ecc_instinct_learn`.
   - LangGraph tool: `ecc_instinct_lookup`.

3. **Cross-Agentic Parity**:
   - Verify alignment across Antigravity IDE, Claude Code, Cursor, OpenCode, Cline, Windsurf, and Kilo: `python3 scripts/ecc_cli.py sync`.

## Workflow Integration

When starting any task:
1. Consult relevant instincts: `python3 scripts/ecc_cli.py instincts --query "<task_context>"`.
2. Before declaring work complete, run AgentShield: `python3 scripts/ecc_cli.py scan`.
3. If new project conventions or fixes are established, record them into the persistent catalog.
