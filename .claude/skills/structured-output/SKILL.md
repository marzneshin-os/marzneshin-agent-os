---
name: structured-output
description: Type-safe structured output generation and schema validation inspired by Instructor and Pydantic-AI (Khairallah Stack Tools #15 & #44). Use when enforcing strict JSON responses, validating agent output, or eliminating malformed LLM outputs.
---

# Structured Output Engine (Instructor / Pydantic-AI)

Enforce 100% schema-compliant outputs from LLMs and agent nodes using `scripts/lib/structured_output.py`.

## Core Pipeline

1. **Schema Formulation**:
   Define JSON Schema or Pydantic model with required fields and types.
2. **Strict Prompting**:
   Use `format_schema_prompt(schema, user_prompt)` to instruct model to emit raw JSON.
3. **Validation & Repair**:
   Call `enforce_structured_output(raw_text, schema)`.
   If validation errors occur, pass `errors` back into the retry loop.

```python
from lib.structured_output import enforce_structured_output, format_schema_prompt

schema = {
    "type": "object",
    "required": ["decision", "confidence"],
    "properties": {
        "decision": {"type": "string", "enum": ["APPROVE", "REJECT", "ESCALATE"]},
        "confidence": {"type": "number"}
    }
}

result = enforce_structured_output(llm_response, schema)
if not result.is_valid:
    print("Schema violations:", result.errors)
```