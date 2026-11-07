---
description: Instructor & Pydantic-AI Structured Outputs & Schema Enforcement (Khairallah Stack #15 & #44)
---

**STRUCTURED OUTPUTS (INSTRUCTOR & PYDANTIC-AI)**

Enforce 100% schema-compliant outputs:
1. **Schema Definition**: Define JSON Schema or Pydantic model in `analytics/schemas/`.
2. **Format Prompt**: Use `structured_output.format_schema_prompt(schema, prompt)`.
3. **Validate**: Extract and validate using `structured_output.enforce_structured_output(response, schema)`.
4. **Auto-Retry**: On validation error, feed error details back into the next inference cycle.