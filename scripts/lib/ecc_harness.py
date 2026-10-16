"""Everything Claude Code (ECC) Universal Agent Harness & AgentShield Security Infrastructure.

Governed by BUILD-SPEC.md v2.0, ADR-018, ADR-022, ADR-023, ADR-024.
Python stdlib-only module. Strict virtual time via lib.clock. Secrets redacted via lib.redact.

Subsystems:
1. AgentShield: Proactive security scanner auditing configs, rules, prompts, and code against OWASP LLM vulnerabilities.
2. InstinctStore: Continuous learning engine capturing confidence-scored heuristics into persistent memory.
3. HarnessAudit: Cross-agentic rule and configuration consistency auditor.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from . import clock, paths, redact

# -----------------------------------------------------------------------------
# AgentShield Security Subsystem
# -----------------------------------------------------------------------------

@dataclass
class SecurityFinding:
    rule_id: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    file: str
    line: int
    description: str
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentShieldReport:
    passed: bool
    summary: dict[str, int]
    findings: list[SecurityFinding]
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "summary": self.summary,
            "findings": [f.to_dict() for f in self.findings],
            "timestamp": self.timestamp,
        }


# Signature patterns for AgentShield
PATTERNS_SECRET = [
    (re.compile(r"sk-[a-zA-Z0-9_-]{20,}"), "AS-SEC-001", "CRITICAL", "Potential OpenAI/Anthropic API Key leak"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AS-SEC-001", "CRITICAL", "Potential AWS Access Key ID leak"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "AS-SEC-001", "CRITICAL", "Private Cryptographic Key exposed"),
    (re.compile(r"Bearer\s+ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*"), "AS-SEC-001", "HIGH", "Raw JWT / Bearer token leak"),
]

PATTERNS_INJECTION = [
    (re.compile(r"(?i)ignore\s+(all\s+)?previous\s+instructions"), "AS-INJ-002", "CRITICAL", "Prompt injection directive (jailbreak pattern)"),
    (re.compile(r"(?i)system\s+prompt\s+override"), "AS-INJ-002", "HIGH", "Attempted system prompt override"),
    (re.compile(r"(?i)act\s+as\s+an\s+unrestricted\s+ai"), "AS-INJ-002", "HIGH", "Persona hijack attempt"),
    (re.compile(r"(?i)bypass\s+(all\s+)?(safety|guardrails|filters)"), "AS-INJ-002", "CRITICAL", "Safety bypass invocation"),
]

PATTERNS_UNSAFE_COMMANDS = [
    (re.compile(r"curl\s+[^\r\n|]+?\|\s*(?:bash|sh)"), "AS-CMD-003", "CRITICAL", "Unverified remote script piped directly to shell"),
    (re.compile(r"wget\s+[^\r\n|]+?\|\s*(?:bash|sh)"), "AS-CMD-003", "CRITICAL", "Unverified remote script piped directly to shell"),
    (re.compile(r"\brm\s+-rf\s+/(?:\s+|$)"), "AS-CMD-003", "CRITICAL", "Destructive filesystem root wipe command"),
    (re.compile(r"\b(eval|exec)\s*\(\s*(?:request|input|sys\.argv)"), "AS-CMD-003", "HIGH", "Dynamic code execution from untrusted inputs"),
]


class AgentShieldScanner:
    """Security auditor verifying workspace harness configs, rules, prompts, and code."""

    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root or paths.repo_root()

    def scan_text(self, text: str, filename: str = "<memory>") -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        lines = text.splitlines()

        for idx, line in enumerate(lines, start=1):
            # 1. Secret patterns
            for pattern, rule_id, severity, desc in PATTERNS_SECRET:
                if pattern.search(line):
                    # Check if inside an environment template like ${VAR:-sk-...}
                    actual_sev = severity
                    actual_desc = desc
                    if "${" in line and ":-" in line:
                        actual_sev = "LOW"
                        actual_desc = f"{desc} (template fallback expression detected)"
                    findings.append(
                        SecurityFinding(
                            rule_id=rule_id,
                            severity=actual_sev,
                            file=filename,
                            line=idx,
                            description=actual_desc,
                            remediation="Use environment variables without hardcoded fallbacks. Redact via lib.redact.",
                        )
                    )

            # 2. Injection patterns (only in rule or markdown/prompt files)
            if filename.endswith((".md", ".txt", ".json", ".prompt", ".mdc")):
                for pattern, rule_id, severity, desc in PATTERNS_INJECTION:
                    if pattern.search(line):
                        # Filter out legitimate documentation mentioning the pattern
                        if "pattern" in line.lower() or "audit" in line.lower() or "detect" in line.lower():
                            continue
                        findings.append(
                            SecurityFinding(
                                rule_id=rule_id,
                                severity=severity,
                                file=filename,
                                line=idx,
                                description=desc,
                                remediation="Review prompt boundaries and sanitize untrusted inputs via policy.wrap_untrusted.",
                            )
                        )

            # 3. Unsafe commands
            for pattern, rule_id, severity, desc in PATTERNS_UNSAFE_COMMANDS:
                if pattern.search(line):
                    if "pattern" in line.lower() or "rule" in line.lower() or "detect" in line.lower():
                        continue
                    findings.append(
                        SecurityFinding(
                            rule_id=rule_id,
                            severity=severity,
                            file=filename,
                            line=idx,
                            description=desc,
                            remediation="Do not pipe remote scripts to shell. Use verified package managers or checksummed downloads.",
                        )
                    )

        return findings

    def scan_file(self, file_path: Path) -> list[SecurityFinding]:
        if not file_path.is_file():
            return []
        try:
            rel = str(file_path.relative_to(self.repo_root))
        except ValueError:
            rel = str(file_path)

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            return self.scan_text(content, filename=rel)
        except Exception as e:
            return [
                SecurityFinding(
                    rule_id="AS-ERR-000",
                    severity="HIGH",
                    file=rel,
                    line=1,
                    description=f"Could not read file during security scan: {str(e)}",
                    remediation="Verify file permissions and accessibility.",
                )
            ]

    def scan_workspace(self, targets: list[str] | None = None, strict: bool = False) -> AgentShieldReport:
        findings: list[SecurityFinding] = []

        if targets:
            files_to_scan = [self.repo_root / t for t in targets]
        else:
            # Standard ECC scan surface
            candidates: list[Path] = []
            candidates.extend(self.repo_root.glob("*.md"))
            candidates.extend(self.repo_root.glob("*.json"))
            candidates.extend(self.repo_root.glob(".*rules*"))
            candidates.extend(self.repo_root.glob(".agents/rules/*.md"))
            candidates.extend(self.repo_root.glob(".claude/**/*.json"))
            candidates.extend(self.repo_root.glob(".cursor/**/*.mdc"))
            candidates.extend(self.repo_root.glob("configs/*.json"))
            candidates.extend(self.repo_root.glob("scripts/*.py"))
            candidates.extend(self.repo_root.glob("hooks/*.py"))

            files_to_scan = [c for c in candidates if c.is_file()]

        for f in files_to_scan:
            rel = str(f)
            if ".git" in rel or "__pycache__" in rel or "node_modules" in rel or "state/reports" in rel or "tests" in rel:
                continue
            findings.extend(self.scan_file(f))

        summary = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
        for item in findings:
            if item.severity in summary:
                summary[item.severity] += 1

        passed = summary["CRITICAL"] == 0 and summary["HIGH"] == 0
        if strict and summary["MEDIUM"] > 0:
            passed = False

        report = AgentShieldReport(
            passed=passed,
            summary=summary,
            findings=findings,
            timestamp=clock.now().isoformat(),
        )

        reports_dir = self.repo_root / "state" / "reports"
        try:
            reports_dir.mkdir(parents=True, exist_ok=True)
            report_file = reports_dir / "agentshield_latest.json"
            report_file.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        except Exception:
            pass

        return report


# -----------------------------------------------------------------------------
# Continuous Learning & Instincts Engine
# -----------------------------------------------------------------------------

@dataclass
class Instinct:
    id: str
    trigger: str
    action: str
    rationale: str
    domain: list[str]
    confidence: float = 0.8
    executions_count: int = 0
    success_count: int = 0
    last_validated_at: str = field(default_factory=lambda: clock.now().isoformat())
    provenance: str = "core-initialization"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Instinct:
        return cls(
            id=data["id"],
            trigger=data["trigger"],
            action=data["action"],
            rationale=data.get("rationale", ""),
            domain=data.get("domain", ["general"]),
            confidence=float(data.get("confidence", 0.8)),
            executions_count=int(data.get("executions_count", 0)),
            success_count=int(data.get("success_count", 0)),
            last_validated_at=data.get("last_validated_at", clock.now().isoformat()),
            provenance=data.get("provenance", "manual"),
        )


CORE_INSTINCTS: list[dict[str, Any]] = [
    {
        "id": "inst_stdlib_imports",
        "trigger": r"(?i)scripts/lib/.*\.py",
        "action": "scripts/lib/ must remain strictly stdlib-only. No third-party packages or circular imports.",
        "rationale": "Enforces scripts/verify.py --lint-imports and ensures hooks execute within 3s budget.",
        "domain": ["python", "architecture", "lint"],
        "confidence": 1.0,
        "provenance": "BUILD-SPEC ?7 / ADR-005",
    },
    {
        "id": "inst_clock_discipline",
        "trigger": r"(?i)(scripts|hooks|sim|adapters)/.*\.py",
        "action": "Never invoke datetime now or time time directly; always route through lib.clock.",
        "rationale": "Enforces scripts/verify.py --lint-clock so deterministic virtual time simulation works (D6).",
        "domain": ["python", "simulation", "clock"],
        "confidence": 1.0,
        "provenance": "BUILD-SPEC ?4 / D6",
    },
    {
        "id": "inst_fail_closed_security",
        "trigger": r"(?i)(killswitch|security|adapter|auth|gate)",
        "action": "All security controls, kill switches, and adapter failures must fail-closed (I12).",
        "rationale": "An unreadable or unreachable safety check must be treated as active/refused.",
        "domain": ["security", "safety", "invariants"],
        "confidence": 1.0,
        "provenance": "BUILD-SPEC I12",
    },
    {
        "id": "inst_canonical_receipt",
        "trigger": r"(?i)(task|complete|receipt|execute)",
        "action": "Every executed task must emit a valid receipt with status and evidence before completion (I3).",
        "rationale": "Enforces audit trail and prevents rogue unverified operations.",
        "domain": ["receipts", "fsp", "invariants"],
        "confidence": 1.0,
        "provenance": "BUILD-SPEC I3",
    },
    {
        "id": "inst_secret_redaction",
        "trigger": r"(?i)(secret|token|password|key|event|log|receipt)",
        "action": "Never persist raw secrets. All values must be sanitized via lib.redact (I6).",
        "rationale": "Prevents credential leakage into repository or event logs.",
        "domain": ["security", "privacy", "invariants"],
        "confidence": 1.0,
        "provenance": "BUILD-SPEC I6",
    },
    {
        "id": "inst_adapter_contract_fake",
        "trigger": r"(?i)adapters/.*\.py",
        "action": "Every adapter in adapters/ must have a matching fake in sim/fakes/ passing adapters/contract.py.",
        "rationale": "Enforces airgapped simulation capability for ?16 scenarios.",
        "domain": ["adapters", "contract", "testing"],
        "confidence": 1.0,
        "provenance": "BUILD-SPEC ?4",
    },
]


class InstinctStore:
    """Persistent catalog for continuous learning instincts."""

    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root or paths.repo_root()
        self.store_dir = self.repo_root / "state" / "instincts"
        self.store_file = self.store_dir / "catalog.json"
        self._ensure_store()

    def _ensure_store(self) -> None:
        if not self.store_file.exists():
            self.store_dir.mkdir(parents=True, exist_ok=True)
            initial: dict[str, Any] = {
                "version": "1.0.0",
                "updated_at": clock.now().isoformat(),
                "instincts": CORE_INSTINCTS,
            }
            self.store_file.write_text(json.dumps(initial, indent=2), encoding="utf-8")

    def _load_data(self) -> dict[str, Any]:
        try:
            return json.loads(self.store_file.read_text(encoding="utf-8"))
        except Exception:
            return {"version": "1.0.0", "updated_at": clock.now().isoformat(), "instincts": CORE_INSTINCTS}

    def _save_data(self, data: dict[str, Any]) -> None:
        data["updated_at"] = clock.now().isoformat()
        temp_file = self.store_dir / f"catalog_{os.getpid()}.tmp"
        temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp_file.replace(self.store_file)

    def learn(
        self,
        trigger: str,
        action: str,
        rationale: str,
        domain: list[str] | None = None,
        confidence: float = 0.8,
        provenance: str = "agent-observation",
    ) -> Instinct:
        data = self._load_data()
        digest = hashlib.sha256(f"{trigger}:{action}".encode("utf-8")).hexdigest()[:12]
        inst_id = f"inst_{digest}"

        instinct = Instinct(
            id=inst_id,
            trigger=trigger,
            action=action,
            rationale=rationale,
            domain=domain or ["general"],
            confidence=min(max(confidence, 0.1), 1.0),
            executions_count=1,
            success_count=1,
            last_validated_at=clock.now().isoformat(),
            provenance=provenance,
        )

        existing = {item["id"]: idx for idx, item in enumerate(data.get("instincts", []))}
        if inst_id in existing:
            data["instincts"][existing[inst_id]] = instinct.to_dict()
        else:
            data.setdefault("instincts", []).append(instinct.to_dict())

        self._save_data(data)
        return instinct

    def query(
        self,
        query_str: str | None = None,
        domain: str | None = None,
        min_confidence: float = 0.4,
    ) -> list[Instinct]:
        data = self._load_data()
        results: list[Instinct] = []

        for raw in data.get("instincts", []):
            item = Instinct.from_dict(raw)
            if item.confidence < min_confidence:
                continue

            if domain and domain.lower() not in [d.lower() for d in item.domain]:
                continue

            if query_str:
                matched = False
                try:
                    if re.search(item.trigger, query_str, re.IGNORECASE):
                        matched = True
                except Exception:
                    pass
                if query_str.lower() in item.action.lower() or query_str.lower() in item.rationale.lower():
                    matched = True
                if not matched:
                    continue

            results.append(item)

        results.sort(key=lambda x: x.confidence, reverse=True)
        return results

    def update_confidence(self, instinct_id: str, success: bool) -> Instinct | None:
        data = self._load_data()
        found = False
        target_inst: Instinct | None = None

        for item in data.get("instincts", []):
            if item["id"] == instinct_id:
                inst = Instinct.from_dict(item)
                inst.executions_count += 1
                if success:
                    inst.success_count += 1
                    inst.confidence = min(1.0, round(inst.confidence + 0.05, 2))
                else:
                    inst.confidence = max(0.1, round(inst.confidence - 0.15, 2))
                inst.last_validated_at = clock.now().isoformat()
                item.update(inst.to_dict())
                target_inst = inst
                found = True
                break

        if found:
            self._save_data(data)
        return target_inst


# -----------------------------------------------------------------------------
# Cross-Agent Harness & Rule Parity Subsystem
# -----------------------------------------------------------------------------

@dataclass
class HarnessAuditReport:
    ok: bool
    harnesses_detected: list[str]
    missing_rules: list[str]
    status: dict[str, bool]
    details: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HarnessAudit:
    """Verifies alignment across all coding agent harnesses."""

    REQUIRED_SURFACES = {
        "antigravity": [".agents/rules", ".agents/skills", "GEMINI.md"],
        "claude": [".claude", "CLAUDE.md"],
        "cursor": [".cursorrules"],
        "cline": [".clinerules"],
        "windsurf": [".windsurfrules"],
        "kilo": [".kilorules"],
    }

    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root or paths.repo_root()

    def audit(self) -> HarnessAuditReport:
        detected: list[str] = []
        missing: list[str] = []
        status: dict[str, bool] = {}

        for harness, required in self.REQUIRED_SURFACES.items():
            all_present = True
            for req in required:
                p = self.repo_root / req
                if not p.exists():
                    all_present = False
                    missing.append(f"{harness}:{req}")
            status[harness] = all_present
            if all_present:
                detected.append(harness)

        ok = len(missing) == 0
        details = (
            f"Cross-agent harness parity: {len(detected)}/{len(self.REQUIRED_SURFACES)} active. "
            f"Missing surfaces: {len(missing)}."
        )
        return HarnessAuditReport(
            ok=ok,
            harnesses_detected=detected,
            missing_rules=missing,
            status=status,
            details=details,
        )
