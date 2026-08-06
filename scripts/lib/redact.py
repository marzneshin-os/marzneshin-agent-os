"""Secret detection and redaction (Invariant I6).

Two jobs, deliberately separated:
  scan()    -> find secrets. Used by PreToolUse/PreCommit hooks to BLOCK.
  redact()  -> neutralise secrets. Used before anything is persisted or logged.

Design note: this is a defence-in-depth layer, not a replacement for gitleaks.
gitleaks runs in CI over the whole diff; this runs in-process, with no network
and no subprocess, so it stays inside the 3-second hook budget (G9).

Order matters in _PATTERNS: specific provider tokens before generic
assignment patterns, so a GitHub token is reported as such rather than as a
nondescript "high entropy value".
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

MASK = "***REDACTED***"


@dataclass
class Finding:
    kind: str
    severity: str  # high | medium
    where: str
    preview: str  # first 4 chars only, never the secret

    def to_dict(self) -> dict:
        return {"kind": self.kind, "severity": self.severity, "where": self.where, "preview": self.preview}


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.findings

    @property
    def high(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "high"]

    def to_dict(self) -> dict:
        return {"clean": self.clean, "count": len(self.findings),
                "findings": [f.to_dict() for f in self.findings]}


# (name, severity, compiled pattern). Group 1, when present, is the secret.
_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("github_pat_fine", "high", re.compile(r"\b(github_pat_[A-Za-z0-9_]{22,})")),
    ("github_token", "high", re.compile(r"\b((?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,})")),
    ("github_app_jwt", "high", re.compile(r"\b(eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})")),
    ("aws_access_key", "high", re.compile(r"\b((?:AKIA|ASIA)[0-9A-Z]{16})\b")),
    ("aws_secret_key", "high", re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*['\"]?([A-Za-z0-9/+=]{40})")),
    ("slack_token", "high", re.compile(r"\b(xox[baprs]-[A-Za-z0-9-]{10,})")),
    ("slack_webhook", "high", re.compile(r"(https://hooks\.slack\.com/services/[A-Za-z0-9/+_-]{20,})")),
    ("telegram_bot_token", "high", re.compile(r"\b(\d{8,10}:AA[A-Za-z0-9_-]{32,})")),
    ("openai_key", "high", re.compile(r"\b(sk-[A-Za-z0-9_-]{20,})")),
    ("anthropic_key", "high", re.compile(r"\b(sk-ant-[A-Za-z0-9_-]{20,})")),
    ("clickup_token", "high", re.compile(r"\b(pk_\d{6,}_[A-Za-z0-9]{20,})")),
    ("stripe_key", "high", re.compile(r"\b((?:sk|rk)_(?:live|test)_[A-Za-z0-9]{20,})")),
    ("private_key_block", "high", re.compile(r"(-----BEGIN (?:RSA |EC |OPENSSH |PGP |DSA )?PRIVATE KEY-----)")),
    ("jdbc_url_with_password", "high", re.compile(r"((?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^\s:@/]+:[^\s@/]{4,}@)")),
    ("authorization_header", "high", re.compile(r"(?i)authorization\s*[=:]\s*['\"]?((?:bearer|basic|token)\s+[A-Za-z0-9._~+/=-]{12,})")),
    # Generic assignment patterns. Deliberately last, and medium severity:
    # they catch real secrets but also fire on config placeholders.
    ("generic_secret_assign", "medium", re.compile(
        r"(?i)\b(?:api[_-]?key|secret|passwd|password|token|credential|private[_-]?key)\b\s*[=:]\s*['\"]([^'\"\s]{12,})['\"]")),
]

# Values that look like secrets but are not. Keeping this list tight is
# important: every entry is a hole in the scanner.
_ALLOW_VALUES = {
    MASK, "REDACTED", "CHANGEME", "changeme", "example", "EXAMPLE",
    "your-token-here", "xxx", "TODO", "null", "None", "placeholder",
    "sha256:...", "...",
}
_ALLOW_SUBSTRINGS = ("${", "{{", "<%", "$(", "os.environ", "getenv", "secrets.", "vault:", "sops:")


def _is_allowlisted(value: str, *, shape_heuristics: bool = True) -> bool:
    """Whether a candidate is a known non-secret.

    `shape_heuristics` covers the guesses that a value merely *looks* like a
    placeholder — an all-caps name, a run of x's. Those guesses must NOT be
    applied to a hit from a specific provider pattern:

        AKIAIOSFODNN7EXAMPLE  is a real AWS access key ID
                              and also matches ^[A-Z][A-Z0-9_]{4,}$

    Suppressing that match hid every AWS key in the codebase from the scanner,
    which is a silent breach of I6 rather than a false positive. A match on a
    pattern as specific as `AKIA[0-9A-Z]{16}` is evidence in itself, so the
    shape guesses are reserved for the generic assignment patterns where the
    risk runs the other way.
    """
    if value in _ALLOW_VALUES:
        return True
    if any(s in value for s in _ALLOW_SUBSTRINGS):
        return True
    if not shape_heuristics:
        return False
    # Env-var indirection (FOO_TOKEN referencing a name, not a value) and
    # obvious dummies.
    if re.fullmatch(r"[A-Z][A-Z0-9_]{4,}", value):
        return True
    if re.fullmatch(r"(?:x+|X+|0+|a+|test|dummy|fake|sample)[-_]?\w{0,8}", value, re.I):
        return True
    return False


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(value)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def scan_text(text: str, where: str = "<text>") -> ScanResult:
    result = ScanResult()
    if not text:
        return result
    seen: set[tuple[str, str]] = set()
    for kind, severity, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            secret = match.group(1) if match.groups() else match.group(0)
            # Shape guesses only for the generic patterns; a provider-specific
            # hit is not second-guessed.
            if _is_allowlisted(secret, shape_heuristics=(severity != "high")):
                continue
            # A generic hit on a low-entropy value is almost always a
            # placeholder, e.g. password: "development".
            if severity == "medium" and shannon_entropy(secret) < 3.0:
                continue
            key = (kind, secret[:12])
            if key in seen:
                continue
            seen.add(key)
            result.findings.append(
                Finding(kind=kind, severity=severity, where=where, preview=secret[:4] + "…")
            )
    return result


def scan_obj(obj: Any, where: str = "<obj>") -> ScanResult:
    """Scan an arbitrary structure by walking it, so a secret nested in a
    dict value is found with its key path reported."""
    result = ScanResult()

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, (list, tuple)):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif isinstance(node, str):
            for f in scan_text(node, where=path).findings:
                result.findings.append(f)
            # Also catch a bare secret used as a value under a telltale key.
            leaf = path.rsplit(".", 1)[-1].lower().strip("[]0123456789")
            if leaf in {"token", "secret", "password", "passwd", "api_key", "apikey",
                        "credential", "private_key", "authorization"}:
                if len(node) >= 12 and not _is_allowlisted(node) and shannon_entropy(node) >= 3.0:
                    result.findings.append(
                        Finding(kind="secret_valued_key", severity="high", where=path,
                                preview=node[:4] + "…"))

    walk(obj, where)
    # Deduplicate: the same string can match a pattern and the key heuristic.
    unique: dict[tuple, Finding] = {}
    for f in result.findings:
        unique.setdefault((f.kind, f.where, f.preview), f)
    result.findings = list(unique.values())
    return result


def redact_text(text: str) -> str:
    if not text:
        return text
    out = text
    for _kind, severity, pattern in _PATTERNS:
        shape = severity != "high"

        def _sub(m: re.Match, _shape: bool = shape) -> str:
            secret = m.group(1) if m.groups() else m.group(0)
            if _is_allowlisted(secret, shape_heuristics=_shape):
                return m.group(0)
            return m.group(0).replace(secret, MASK)
        out = pattern.sub(_sub, out)
    return out


def redact_obj(obj: Any) -> Any:
    """Deep copy with secrets masked. Applied before ANY persist or log write."""
    if isinstance(obj, dict):
        return {k: (MASK if _sensitive_key(k) and isinstance(v, str) and v and not _is_allowlisted(v)
                    else redact_obj(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj


def _sensitive_key(key: str) -> bool:
    k = key.lower()
    return any(t in k for t in ("token", "secret", "password", "passwd", "api_key", "apikey",
                                "credential", "private_key", "authorization", "cookie"))
