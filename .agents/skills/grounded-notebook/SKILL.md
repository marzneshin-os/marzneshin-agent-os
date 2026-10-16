---
name: grounded-notebook
description: Citation-Grounded Knowledge Notebook Engine (Synthesizing NotebookLM and Antigravity paradigms, ADR-026).
metadata:
  origin: liam-turner-notebooklm-antigravity-adr-026
---

# Grounded Notebook Knowledge Engine (NotebookLM × Antigravity)

Use this skill when researching project requirements, ingesting documentation, verifying architectural invariants, querying specifications with verifiable source citations, or preventing agent hallucinations before writing code.

## Core Capabilities

1. **Grounded Query (`query`)**:
   - BM25-scored lexical retrieval across indexed workspace documents.
   - Attributed citations with exact line numbers: `[<doc_name>#L<start>-L<end>]`.
   - Content hash verification to guarantee evidence authenticity.
   - CLI: `python3 scripts/grounded_notebook_cli.py query --id <notebook_id> --query "<query>"`
   - MCP tool: `notebook_query`
   - LangGraph worker tool: `grounded_notebook_query`

2. **Adversarial Grounding Verification (`verify`)**:
   - Evaluates whether candidate claims or planned code changes are grounded in indexed specifications.
   - Computes grounding confidence score and returns supporting citations or unsupported gaps.
   - CLI: `python3 scripts/grounded_notebook_cli.py verify --id <notebook_id> --statement "<statement>"`
   - MCP tool: `notebook_verify_grounding`
   - LangGraph worker tool: `grounded_notebook_verify`

3. **Multi-Source Synthesis (`synthesize`)**:
   - Cross-references multiple documents on a topic with source attribution.
   - CLI: `python3 scripts/grounded_notebook_cli.py synthesize --id <notebook_id> --topic "<topic>"`
   - MCP tool: `notebook_synthesize`

4. **Notebook Management (`create`, `ingest`, `list`)**:
   - CLI create: `python3 scripts/grounded_notebook_cli.py create --id <id> --title "<title>"`
   - CLI ingest: `python3 scripts/grounded_notebook_cli.py ingest --id <id> --file <path>`
   - CLI list: `python3 scripts/grounded_notebook_cli.py list`
   - MCP tools: `notebook_create`, `notebook_ingest`, `notebook_list`

## Recommended Workflow: "Information → Understanding → Creation → Execution"
1. **Ingest Specs**: Ingest relevant ADRs, BUILD-SPEC, or documentation into a task notebook.
2. **Query Grounding**: Query the notebook for exact invariant line spans before modifying code.
3. **Verify Claims**: Verify implementation statements against the notebook before committing changes.
