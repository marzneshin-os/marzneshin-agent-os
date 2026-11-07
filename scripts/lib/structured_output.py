"""Structured Output Engine inspired by Instructor and Pydantic-AI (Khairallah Stack Tools #15 & #44).

Enforces schema-validated, type-safe JSON outputs from LLM responses across
LangGraph nodes, FreeLLM pool, and Claude Code sessions.
Zero external dependencies: Python 3 stdlib only, compliant with lint-imports.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from . import clock, paths


@dataclass
class StructuredOutputResult:
    """Result of structured output extraction and validation."""
    data: Optional[Dict[str, Any]]
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    raw_text: str = ""
    validated_at: str = field(default_factory=clock.iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "data": self.data,
            "is_valid": self.is_valid,
            "errors": self.errors,
            "raw_text": self.raw_text[:200] if len(self.raw_text) > 200 else self.raw_text,
            "validated_at": self.validated_at
        }


def extract_json_block(text: str) -> Optional[Dict[str, Any]]:
    """Extract and parse JSON object from markdown code fence, text, or raw string."""
    if not text:
        return None
    cleaned = text.strip()

    # 1. Direct parse attempt
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # 2. Markdown json code block
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", cleaned, re.DOTALL)
    if m:
        try:
            parsed = json.loads(m.group(1))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    # 3. First balanced curly bracket block
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        candidate = cleaned[start_idx : end_idx + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    return None


def validate_schema(data: Any, schema: Dict[str, Any], path: str = "$") -> Tuple[bool, List[str]]:
    """Validate data against a JSON schema definition (stdlib pure python)."""
    errors: List[str] = []

    if not isinstance(data, dict):
        return False, [f"{path}: expected JSON object (dict), got {type(data).__name__}"]

    # Required fields check
    required_fields = schema.get("required", [])
    for req in required_fields:
        if req not in data:
            errors.append(f"{path}.{req}: required field is missing")

    properties = schema.get("properties", {})
    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict
    }

    for prop_name, prop_val in data.items():
        if prop_name not in properties:
            if schema.get("additionalProperties") is False:
                errors.append(f"{path}.{prop_name}: unexpected additional property")
            continue

        prop_spec = properties[prop_name]
        expected_type_str = prop_spec.get("type")
        if expected_type_str and expected_type_str in type_map:
            expected_py_type = type_map[expected_type_str]
            # Handle boolean vs integer edge case in python (bool is subclass of int)
            if expected_type_str == "integer" and isinstance(prop_val, bool):
                errors.append(f"{path}.{prop_name}: expected integer, got boolean")
            elif not isinstance(prop_val, expected_py_type):
                errors.append(f"{path}.{prop_name}: expected {expected_type_str}, got {type(prop_val).__name__}")

        # Enum check
        if "enum" in prop_spec and prop_val not in prop_spec["enum"]:
            errors.append(f"{path}.{prop_name}: value '{prop_val}' is not in allowed enum {prop_spec['enum']}")

        # Nested object validation
        if expected_type_str == "object" and isinstance(prop_val, dict) and "properties" in prop_spec:
            nested_valid, nested_errors = validate_schema(prop_val, prop_spec, f"{path}.{prop_name}")
            if not nested_valid:
                errors.extend(nested_errors)

    return (len(errors) == 0), errors


def enforce_structured_output(raw_response: str, schema: Dict[str, Any]) -> StructuredOutputResult:
    """Extract and validate structured output against target schema."""
    extracted = extract_json_block(raw_response)
    if extracted is None:
        return StructuredOutputResult(
            data=None,
            is_valid=False,
            errors=["Failed to parse valid JSON object from LLM response."],
            raw_text=raw_response
        )

    is_valid, errors = validate_schema(extracted, schema)
    return StructuredOutputResult(
        data=extracted,
        is_valid=is_valid,
        errors=errors,
        raw_text=raw_response
    )


def format_schema_prompt(schema: Dict[str, Any], instruction: str) -> str:
    """Compose a strict prompt compelling the model to return valid structured JSON."""
    schema_str = json.dumps(schema, indent=2)
    return (
        f"{instruction}\n\n"
        f"CRITICAL: You MUST respond ONLY with a valid JSON object matching the JSON Schema below.\n"
        f"Do not include any conversational preamble, commentary, or postscript outside the JSON block.\n\n"
        f"```json\n{schema_str}\n```\n"
    )