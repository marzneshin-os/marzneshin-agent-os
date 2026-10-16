---
name: ecc-harness
description: Everything Claude Code (ECC) Universal Agent Harness, AgentShield Security Auditor, and Continuous Learning Instincts Engine.
---

# ECC Harness for Claude Code

Execute AgentShield security audits, query continuous learning instincts, and synchronize cross-agent rules.

## Commands

- Audit security: `python3 scripts/ecc_cli.py scan`
- Query instincts: `python3 scripts/ecc_cli.py instincts`
- Learn instinct: `python3 scripts/ecc_cli.py instincts learn --trigger "<regex>" --rule-action "<action>"`
- Harness audit: `python3 scripts/ecc_cli.py audit`
