"""Schema validation and version upcasting (G11).

Two modes, on purpose:

  **strict** (CI, scripts/verify.py) requires the `jsonschema` package and does
  full JSON Schema Draft 2020-12 validation. If the package is missing, strict
  mode FAILS rather than degrading — silently validating less than you think is
  worse than not validating.

  **fast** (hooks) does a stdlib-only structural check: required keys, types,
  enums, patterns. It runs in microseconds with no imports beyond the stdlib,
  which is what keeps hooks inside the 3-second budget (G9).

Upcasting (G11): `schema_version` was in v1.0 everywhere, but nothing said what
happens to three months of v1.0 events after a breaking change. An event-sourced
system without upcasters loses replay at its first schema change — which is the
entire value of event sourcing. Upcasters are pure functions registered here and
applied on read.
"""

from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from . import paths
from .atomic import read_json

HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None


class ValidationError(RuntimeError):
    pass


@dataclass
class Result:
    ok: bool
    schema: str
    errors: list[str] = field(default_factory=list)
    mode: str = "fast"

    def raise_if_bad(self) -> "Result":
        if not self.ok:
            raise ValidationError(
                f"{self.schema} validation failed ({self.mode} mode):\n  - "
                + "\n  - ".join(self.errors)
            )
        return self


_SCHEMA_CACHE: dict[str, dict] = {}


def load_schema(name: str) -> dict:
    if name not in _SCHEMA_CACHE:
        path = paths.schema_file(name)
        if not path.exists():
            raise ValidationError(
                f"schema {name!r} not found at {paths.rel(path)}. "
                f"Every persisted artifact must have a schema (BUILD-SPEC §3)."
            )
        _SCHEMA_CACHE[name] = read_json(path, default=None)
    return _SCHEMA_CACHE[name]


def clear_cache() -> None:
    _SCHEMA_CACHE.clear()


# --- fast, stdlib-only validator -------------------------------------------

_TYPE_MAP: dict[str, tuple] = {
    "object": (dict,), "array": (list,), "string": (str,),
    "number": (int, float), "integer": (int,), "boolean": (bool,), "null": (type(None),),
}


def _check(node: Any, schema: dict, path: str, errors: list[str], root: dict) -> None:
    if "$ref" in schema:
        ref = schema["$ref"]
        if ref.startswith("#/"):
            target: Any = root
            for part in ref[2:].split("/"):
                target = target.get(part, {}) if isinstance(target, dict) else {}
            if isinstance(target, dict):
                _check(node, target, path, errors, root)
        return

    for combiner in ("oneOf", "anyOf"):
        if combiner in schema:
            branch_errors: list[list[str]] = []
            for branch in schema[combiner]:
                sub: list[str] = []
                _check(node, branch, path, sub, root)
                if not sub:
                    branch_errors = []
                    break
                branch_errors.append(sub)
            if branch_errors:
                errors.append(f"{path}: does not satisfy {combiner}")
            # allOf/oneOf branches already covered the node's own keywords.

    if "allOf" in schema:
        for branch in schema["allOf"]:
            _check(node, branch, path, errors, root)

    expected = schema.get("type")
    if expected:
        types = expected if isinstance(expected, list) else [expected]
        allowed: tuple = tuple(t for name in types for t in _TYPE_MAP.get(name, ()))
        # bool is a subclass of int in Python; keep them distinct.
        if allowed and (not isinstance(node, allowed)
                        or (isinstance(node, bool) and "boolean" not in types)):
            errors.append(f"{path}: expected type {expected}, got {type(node).__name__}")
            return

    if "enum" in schema and node not in schema["enum"]:
        errors.append(f"{path}: {node!r} not in enum {schema['enum']}")

    if "const" in schema and node != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}")

    if isinstance(node, str):
        if "pattern" in schema and not re.search(schema["pattern"], node):
            errors.append(f"{path}: {node!r} does not match pattern {schema['pattern']!r}")
        if "minLength" in schema and len(node) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength {schema['minLength']}")
        if "maxLength" in schema and len(node) > schema["maxLength"]:
            errors.append(f"{path}: longer than maxLength {schema['maxLength']}")

    if isinstance(node, (int, float)) and not isinstance(node, bool):
        for key, op, label in (("minimum", "<", "below minimum"),
                               ("maximum", ">", "above maximum")):
            if key in schema:
                bad = node < schema[key] if op == "<" else node > schema[key]
                if bad:
                    errors.append(f"{path}: {node} {label} {schema[key]}")

    if isinstance(node, dict):
        for req in schema.get("required", []):
            if req not in node:
                errors.append(f"{path}: missing required property {req!r}")
        props = schema.get("properties", {})
        for key, value in node.items():
            if key in props:
                _check(value, props[key], f"{path}.{key}", errors, root)
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: additional property {key!r} is not permitted")
            elif isinstance(schema.get("additionalProperties"), dict):
                _check(value, schema["additionalProperties"], f"{path}.{key}", errors, root)

    if isinstance(node, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(node):
                _check(item, item_schema, f"{path}[{i}]", errors, root)
        if "minItems" in schema and len(node) < schema["minItems"]:
            errors.append(f"{path}: fewer than minItems {schema['minItems']}")
        if schema.get("uniqueItems"):
            seen = [repr(x) for x in node]
            if len(set(seen)) != len(seen):
                errors.append(f"{path}: items are not unique")


def validate(obj: Any, schema_name: str, *, strict: bool | None = None) -> Result:
    """Validate `obj` against a named schema.

    strict=None means "use jsonschema if available". strict=True means "require
    it", and is what CI passes.
    """
    schema = load_schema(schema_name)
    want_strict = HAS_JSONSCHEMA if strict is None else strict

    if want_strict:
        if not HAS_JSONSCHEMA:
            raise ValidationError(
                "strict validation requested but the 'jsonschema' package is not "
                "installed. Install it (pip install jsonschema) — strict mode does "
                "not fall back to the fast validator, because partial validation "
                "that looks complete is worse than none."
            )
        import jsonschema  # local import: hooks must not pay this cost
        import jsonschema.validators
        validator_cls = jsonschema.validators.validator_for(schema)
        validator_cls.check_schema(schema)
        validator = validator_cls(schema)
        errors = [
            f"$.{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in sorted(validator.iter_errors(obj), key=lambda e: list(e.absolute_path))
        ]
        return Result(ok=not errors, schema=schema_name, errors=errors, mode="strict")

    errors: list[str] = []
    _check(obj, schema, "$", errors, schema)
    return Result(ok=not errors, schema=schema_name, errors=errors, mode="fast")


# --- upcasting (G11) -------------------------------------------------------

Upcaster = Callable[[dict], dict]
_UPCASTERS: dict[tuple[str, str, str], Upcaster] = {}


def register_upcaster(kind: str, from_version: str, to_version: str) -> Callable[[Upcaster], Upcaster]:
    """Register a pure function that migrates one artifact one version forward.

    Chains are applied transitively, so v1.0 -> v1.2 needs only the two
    adjacent upcasters, never a combinatorial matrix.
    """
    def decorator(fn: Upcaster) -> Upcaster:
        _UPCASTERS[(kind, from_version, to_version)] = fn
        return fn
    return decorator


def upcast(obj: dict, kind: str, target_version: str) -> dict:
    """Migrate an artifact forward to `target_version`.

    Never mutates the input. Refuses to guess: if no path exists, it raises,
    because a reader that silently skips unmigratable history has lost replay
    without telling anyone.
    """
    current = obj.get("schema_version", "1.0.0")
    out = dict(obj)
    seen: set[str] = set()
    while current != target_version:
        if current in seen:
            raise ValidationError(f"upcaster cycle detected for {kind} at {current}")
        seen.add(current)
        candidates = [(f, t) for (k, f, t) in _UPCASTERS if k == kind and f == current]
        if not candidates:
            raise ValidationError(
                f"no upcaster from {kind} v{current} to v{target_version}. "
                f"Add analytics/schemas/migrations/{kind}_{current.replace('.', '_')}"
                f"__{target_version.replace('.', '_')}.py before changing the schema."
            )
        _from, to = candidates[0]
        out = _UPCASTERS[(kind, _from, to)](out)
        out["schema_version"] = to
        current = to
    return out


def load_migrations() -> int:
    """Import every module in analytics/schemas/migrations/ so its @register
    decorators run. Returns how many modules were loaded."""
    directory = paths.schemas_dir() / "migrations"
    if not directory.exists():
        return 0
    count = 0
    for module_path in sorted(directory.glob("*.py")):
        if module_path.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(
            f"marzneshin_migrations.{module_path.stem}", module_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            count += 1
    return count
