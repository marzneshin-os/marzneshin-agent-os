"""Receipts — the proof-of-work artifact (BUILD-SPEC §3.3, revised G5/G18/D9).

Two fixes to v1.0 live here.

**Five statuses (G5).** v1.0 required "receipt completeness = 100%, always,
else the build fails". That is unsatisfiable: an agent killed mid-task — which
the chaos suite kills on purpose — never writes one, so the build stays red
forever and by week two somebody disables the gate. Losing the gate loses all
auditability, so the invariant had to become enforceable instead of moral:

    complete   | finished, verification green
    failed     | finished, negative result — a valid, complete receipt
    abandoned  | deliberately cancelled, reason recorded
    crashed    | tombstone written by the reaper (lease expired, no receipt)
    superseded | replaced by a newer task, points at the successor

The KPI is now "100% of tasks have a receipt in *some* status", plus a separate
`crash_rate < 2%`. A crash is still a defect — it just is not a lie.

**Hash chain (G18).** Receipts were standalone files, so any agent with write
access could rewrite history and only git would notice. Each receipt now
carries `prev_receipt_hash` for its workstream, forming a tamper-evident chain
verifiable offline by verify_chain(). Cost: one extra field.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any

from . import clock, paths
from .atomic import CorruptState, read_json, write_json_atomic
from .ids import canonical_json, sha256_str
from .redact import redact_obj, scan_obj

SCHEMA_VERSION = "2.0.0"  # ADR-002 D11: aligned with BUILD-SPEC §3

# Genesis link for a workstream's first receipt.
GENESIS_HASH = "sha256:" + "0" * 64

# ADR-007. The budget is the Owner's number and is unchanged; only the window
# it is measured over is defined here.
CRASH_RATE_BUDGET = 0.02
CRASH_WINDOW = 50        # trailing receipts the budget judges
MIN_CRASH_SAMPLE = 50    # below this, crash_rate cannot resolve a 2% budget


class Status(str, Enum):
    COMPLETE = "complete"
    FAILED = "failed"
    ABANDONED = "abandoned"
    CRASHED = "crashed"
    SUPERSEDED = "superseded"

    @property
    def terminal_ok(self) -> bool:
        """Whether this status represents an orderly ending. `crashed` does not:
        it feeds crash_rate."""
        return self is not Status.CRASHED


class ReceiptError(RuntimeError):
    pass


@dataclass
class Change:
    path: str
    commit: str | None = None
    diff_stat: str | None = None
    content_hash: str | None = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"path": self.path}
        for k in ("commit", "diff_stat", "content_hash"):
            v = getattr(self, k)
            if v:
                d[k] = v
        return d


@dataclass
class Verification:
    check: str
    result: str  # pass | fail | skipped | inconclusive
    evidence: str
    metric: dict | None = None
    note: str | None = None
    # §3.3: who checked, and were they independent of the author (§10 SoD).
    verifier: str | None = None
    independent_of_author: bool | None = None
    # §5.7 statistical gate. "Green" without power is noise (G12), so a canary
    # or probe check carries its own sample size and p-value or it is not a
    # conclusive check at all.
    n: int | None = None
    n_min: int | None = None
    stat_test: str | None = None
    p_value: float | None = None
    conclusive: bool | None = None
    probe_fleet: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"check": self.check, "result": self.result, "evidence": self.evidence}
        for k in ("metric", "note", "verifier", "n", "n_min", "stat_test",
                  "p_value", "conclusive"):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        if self.independent_of_author is not None:
            d["independent_of_author"] = self.independent_of_author
        if self.probe_fleet:
            d["probe_fleet"] = self.probe_fleet
        return d


@dataclass
class Rollback:
    method: str
    tested: bool
    tested_at: str | None = None
    evidence: str | None = None
    # §3.3: "tested: true without tested_at and tested_in is invalid".
    tested_in: str | None = None      # sim | staging | prod
    max_ttr_s: int | None = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"method": self.method, "tested": self.tested}
        for k in ("tested_at", "evidence", "tested_in", "max_ttr_s"):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        return d


@dataclass
class SimEvidence:
    """Proof a change went green in sim/ before touching production (I11).

    Without this field the invariant "no new code reaches production without
    passing sim" has no enforcement point, which makes ADR-001 D6 decorative.
    `seeds` is what makes a failure reproducible rather than anecdotal.
    """
    scenarios: list[str]
    seeds: list[int]
    result: str                       # pass | fail | inconclusive
    report: str | None = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"scenarios": self.scenarios, "seeds": self.seeds,
                             "result": self.result}
        if self.report:
            d["report"] = self.report
        return d


@dataclass
class Idempotency:
    """Which of the three classes governed this task (G4/§3.5)."""
    class_: str                       # forever | scoped | none
    key: str | None = None
    components: list[str] = field(default_factory=list)
    ttl_s: int | None = None
    target_epoch: str | None = None
    env_epoch: str | None = None
    attempt: int = 1
    retry_of: str | None = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"class": self.class_, "attempt": self.attempt}
        for k, name in (("key", "key"), ("ttl_s", "ttl_s"),
                        ("target_epoch", "target_epoch"), ("env_epoch", "env_epoch"),
                        ("retry_of", "retry_of")):
            v = getattr(self, k)
            if v is not None:
                d[name] = v
        if self.components:
            d["components"] = self.components
        return d


@dataclass
class InputProvenance:
    """Origin and trust of one input field (I16/§15.2).

    Recorded in the receipt, not just evaluated at decision time: "no capability
    was built from untrusted content" has to be auditable after the fact.
    """
    field_path: str
    source: str
    trust: str                        # owner | internal | untrusted
    sanitizer: str | None = None
    content_hash: str | None = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"field": self.field_path, "source": self.source,
                             "trust": self.trust}
        if self.sanitizer:
            d["sanitizer"] = self.sanitizer
        if self.content_hash:
            d["content_hash"] = self.content_hash
        return d


@dataclass
class Receipt:
    task_id: str
    agent: str
    workstream: str
    status: Status
    autonomy_level: str
    intent: str
    started_at: str
    completed_at: str = ""
    inputs_hash: str = ""
    changes: list[Change] = field(default_factory=list)
    verification: list[Verification] = field(default_factory=list)
    policy_decisions: list[dict] = field(default_factory=list)
    cost: dict = field(default_factory=dict)
    rollback: Rollback | None = None
    handoff_note: str = ""
    prev_receipt_hash: str = GENESIS_HASH
    correlation_id: str | None = None
    fencing_token: int | None = None
    seed: int | None = None
    model: str | None = None
    reason: str = ""            # §10: one sentence, "why I did this"
    supersedes: str | None = None
    superseded_by: str | None = None
    control_room_task: str | None = None
    # §3.3 required fields, added by ADR-002 D12/D13.
    chain_index: int = 0
    sim_evidence: SimEvidence | None = None
    idempotency: Idempotency | None = None
    input_provenance: list[InputProvenance] = field(default_factory=list)
    agent_lineage: str | None = None
    transport: str | None = None
    world: str = "prod"
    autonomy_shadow: dict | None = None
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "agent": self.agent,
            "workstream": self.workstream,
            "status": self.status.value,
            "autonomy_level": self.autonomy_level,
            "intent": self.intent,
            # §3.3 names this why_one_sentence; the python field stays `reason`
            # for readability. Both are written with the same value so
            # spec-conformant tooling and existing code both work (ADR-002 D12).
            "reason": self.reason,
            "why_one_sentence": self.reason,
            "started_at": self.started_at,
            "completed_at": self.completed_at or clock.iso(),
            "inputs_hash": self.inputs_hash,
            "chain_index": self.chain_index,
            "world": self.world,
            "changes": [c.to_dict() for c in self.changes],
            "verification": [v.to_dict() for v in self.verification],
            "policy_decisions": self.policy_decisions,
            "cost": self.cost,
            "handoff_note": self.handoff_note,
            "prev_receipt_hash": self.prev_receipt_hash,
        }
        if self.rollback:
            d["rollback"] = self.rollback.to_dict()
        if self.sim_evidence:
            d["sim_evidence"] = self.sim_evidence.to_dict()
        if self.idempotency:
            d["idempotency"] = self.idempotency.to_dict()
        if self.input_provenance:
            d["input_provenance"] = [p.to_dict() for p in self.input_provenance]
        for k in ("correlation_id", "fencing_token", "seed", "model",
                  "supersedes", "superseded_by", "control_room_task",
                  "agent_lineage", "transport", "autonomy_shadow"):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        return d

    @property
    def touches_code_or_config(self) -> bool:
        """Whether any change lands on a path where I11 demands sim evidence.

        Docs, ADRs and reports are excluded: requiring a simulation run to
        publish a markdown file would make the gate absurd, and a gate that is
        absurd in the common case gets bypassed in the important one.
        """
        return any(_is_code_or_config(c.path) for c in self.changes)


# Paths whose mutation is "new code or config reaching production" (I11).
_CODE_CONFIG_PREFIXES = (
    "scripts/", "hooks/", "adapters/", "gateway/", "sim/", "agents/",
    "configs/", "infra/", "analytics/schemas/", "analytics/models/",
    "security/iam/", "security/policies/", "mcp/", "plugins/",
    ".github/workflows/",
)
_CODE_CONFIG_SUFFIXES = (".py", ".yaml", ".yml", ".json", ".tf", ".sh", ".toml")
_DOC_SUFFIXES = (".md", ".txt", ".rst")


def _is_code_or_config(path: str) -> bool:
    p = path.replace("\\", "/").lstrip("./")
    if p.endswith(_DOC_SUFFIXES):
        return False
    if p.startswith(_CODE_CONFIG_PREFIXES):
        return True
    return p.endswith(_CODE_CONFIG_SUFFIXES)


# Keys excluded from the receipt's own content hash.
#   prev_receipt_hash — the chain link, verified separately by walking the chain
#   receipt_hash / content_hash — the hash cannot cover itself
#   _path — a read-time convenience, never part of the record
_UNHASHED_KEYS = frozenset({"prev_receipt_hash", "receipt_hash", "content_hash", "_path"})


def content_hash(receipt: dict) -> str:
    """Hash of a receipt, excluding the chain link and the hash fields.

    `prev_receipt_hash` is excluded so the hash is a property of the receipt's
    own content. The link is verified separately by walking the chain.
    """
    body = {k: v for k, v in receipt.items() if k not in _UNHASHED_KEYS}
    return sha256_str(canonical_json(body))


def _head(workstream: str) -> dict:
    path = paths.receipt_head_file(workstream)
    try:
        return read_json(path, default={"hash": GENESIS_HASH, "task_id": None,
                                        "count": 0, "chain_index": -1})
    except CorruptState:
        raise ReceiptError(
            f"receipt chain head for {workstream!r} is corrupt. Run "
            f"scripts/verify.py --chain --repair-head to rebuild it from receipts on disk."
        )


def _set_head(workstream: str, *, hash_: str, task_id: str, count: int,
              chain_index: int) -> None:
    write_json_atomic(paths.receipt_head_file(workstream),
                      {"hash": hash_, "task_id": task_id, "count": count,
                       "chain_index": chain_index, "updated_at": clock.iso()})


def _has_untrusted(r: Receipt) -> bool:
    return any(p.trust == "untrusted" for p in r.input_provenance)


def _autonomy_number(level: str) -> int | None:
    """Parse 'L2' -> 2. Returns None for 'unknown' (tombstones)."""
    text = (level or "").strip().upper()
    if text.startswith("L") and text[1:].isdigit():
        return int(text[1:])
    return None


def _validate_for_status(r: Receipt) -> list[str]:
    """Status-specific required fields.

    This is where the DoD is actually enforced. `complete` demands verification
    evidence and a *tested* rollback (§19); `failed` demands a failed check so
    a failure cannot be recorded as a shrug; `crashed` demands nothing beyond
    identity because by definition nobody was there to fill it in.
    """
    problems: list[str] = []
    if not r.intent.strip():
        problems.append("intent is empty")
    if not r.reason.strip():
        problems.append("reason is empty (§10: every agent states why in one sentence)")
    if not r.inputs_hash:
        problems.append("inputs_hash is missing")

    if r.status is Status.COMPLETE:
        if not r.verification:
            problems.append("status=complete requires at least one verification entry")
        if any(v.result == "fail" for v in r.verification):
            problems.append("status=complete but a verification check failed")
        if not any(v.result == "pass" for v in r.verification):
            problems.append("status=complete requires at least one passing check")
        for v in r.verification:
            if not v.evidence:
                problems.append(f"verification {v.check!r} has no evidence reference")
        if r.rollback is None:
            problems.append("status=complete requires a rollback plan (I7)")
        elif not r.rollback.tested:
            problems.append("status=complete requires rollback.tested=true (§19)")
        else:
            # §3.3: "tested: true without tested_at and tested_in is invalid.
            # An untested rollback is a rollback that does not exist."
            if not r.rollback.tested_at:
                problems.append("rollback.tested=true requires tested_at (§3.3)")
            if not r.rollback.tested_in:
                problems.append(
                    "rollback.tested=true requires tested_in (sim|staging|prod) — "
                    "an untested rollback is no rollback (§3.3)")
            elif r.rollback.tested_in not in ("sim", "staging", "prod"):
                problems.append(
                    f"rollback.tested_in must be one of sim|staging|prod, "
                    f"got {r.rollback.tested_in!r} (schema enum — free text here "
                    f"fails the artifact gate after the fact)")

        # I11: sim evidence gates code and config reaching production.
        if r.touches_code_or_config and r.world != "sim":
            changed = [c.path for c in r.changes if _is_code_or_config(c.path)]
            if r.sim_evidence is None:
                problems.append(
                    "status=complete on code/config changes requires sim_evidence "
                    f"(I11 — no new code reaches production without going green in "
                    f"sim/ first). Changed: {', '.join(changed[:3])}")
            elif r.sim_evidence.result != "pass":
                problems.append(
                    f"sim_evidence.result is {r.sim_evidence.result!r}, not 'pass'. "
                    f"Red or inconclusive sim means production entry is forbidden (I11).")
            elif not r.sim_evidence.seeds:
                problems.append(
                    "sim_evidence requires at least one seed, otherwise the run is "
                    "not reproducible and proves nothing (§16)")

        # I16: an untrusted-derived input caps autonomy at L1, without exception.
        autonomy_num = _autonomy_number(r.autonomy_level)
        if _has_untrusted(r) and autonomy_num is not None:
            if autonomy_num > 1:
                problems.append(
                    f"input_provenance contains untrusted content but autonomy_level is "
                    f"{r.autonomy_level} — I16 caps this at L1 with no exceptions")
    elif r.status is Status.FAILED:
        if not r.verification:
            problems.append("status=failed requires the failing check to be recorded")
    elif r.status is Status.ABANDONED:
        if not r.handoff_note.strip():
            problems.append("status=abandoned requires handoff_note explaining why")
    elif r.status is Status.SUPERSEDED:
        if not r.superseded_by:
            problems.append("status=superseded requires superseded_by")
    return problems


def write(receipt: Receipt, *, on: date | None = None, strict: bool = True) -> Path:
    """Persist a receipt, linking it into its workstream chain.

    Raises ReceiptError when the receipt does not satisfy its status contract,
    which is what makes hooks/task_complete.py able to exit non-zero (I3).
    """
    # The world is a property of the environment, not of the receipt — set it
    # BEFORE validating, since the sim_evidence rule (I11) depends on it: a
    # receipt produced INSIDE a simulation must not demand sim evidence.
    receipt.world = paths.current_world()
    problems = _validate_for_status(receipt)
    if problems and strict:
        raise ReceiptError(
            f"receipt {receipt.task_id} is incomplete:\n  - " + "\n  - ".join(problems)
        )

    head = _head(receipt.workstream)
    receipt.prev_receipt_hash = head["hash"]
    # chain_index, not a timestamp, defines chain order (ADR-002 D13). Under a
    # virtual clock thousands of receipts can share one instant, so ordering by
    # completed_at would produce phantom chain breaks in the very simulation
    # meant to prove the chain works.
    receipt.chain_index = int(head.get("chain_index", -1)) + 1
    body = receipt.to_dict()

    scan = scan_obj(body, where="$")
    if not scan.clean:
        # Never refuse to record work because of a secret; record it redacted
        # and flag it. Refusing would create an incentive to skip the receipt.
        body = redact_obj(body)
        body["redacted"] = True
        body["redaction_findings"] = scan.to_dict()["findings"]

    digest = content_hash(body)
    # §3.3 calls this receipt_hash; content_hash is the pre-existing name. Both
    # carry the same value so either reader works (ADR-002 D12).
    body["content_hash"] = digest
    body["receipt_hash"] = digest
    day = on or clock.now().date()
    path = paths.receipt_file(receipt.task_id, day)
    write_json_atomic(path, body)
    _set_head(receipt.workstream, hash_=digest, task_id=receipt.task_id,
              count=int(head.get("count", 0)) + 1, chain_index=receipt.chain_index)
    return path


def write_tombstone(*, task_id: str, agent: str, workstream: str, reason: str,
                    started_at: str | None = None, fencing_token: int | None = None,
                    evidence: str | None = None) -> Path:
    """Write a `crashed` receipt for a task nobody finished.

    Called by the reaper (heartbeat, every 15m) when a lease expires with no
    receipt on disk. This is the mechanism that keeps "100% of tasks have a
    receipt" true without lying about outcomes (G5).
    """
    r = Receipt(
        task_id=task_id,
        agent=agent,
        workstream=workstream,
        status=Status.CRASHED,
        autonomy_level="unknown",
        intent="(unknown — task did not report before dying)",
        reason=f"tombstone written by reaper: {reason}",
        started_at=started_at or clock.iso(),
        completed_at=clock.iso(),
        inputs_hash=sha256_str(f"tombstone:{task_id}"),
        handoff_note=(
            "Reconstructed by the reaper, not by the worker. Treat all state "
            "touched by this task as unverified until re-checked (§11.1 STEP 3)."
        ),
        fencing_token=fencing_token,
        verification=[Verification(check="reaper.detect", result="fail",
                                   evidence=evidence or "state/locks (expired lease, no receipt)",
                                   note=reason)],
    )
    return write(r, strict=False)


def read(task_id: str, *, on: date | None = None) -> dict | None:
    path = paths.receipt_file(task_id, on or clock.now().date())
    if path.exists():
        return read_json(path, default=None)
    # Task may have been written on a different day than the caller assumes.
    root = paths.repo_root() / "receipts"
    if root.exists():
        for candidate in root.rglob(f"{paths.slug(task_id)}.json"):
            return read_json(candidate, default=None)
    return None


def list_all() -> list[dict]:
    root = paths.repo_root() / "receipts"
    if not root.exists():
        return []
    out = []
    for f in sorted(root.rglob("*.json")):
        if f.parent.name == "_chain":
            continue
        try:
            data = read_json(f, default=None)
        except CorruptState:
            out.append({"_unreadable": paths.rel(f)})
            continue
        if data:
            data["_path"] = paths.rel(f)
            out.append(data)
    return out


def verify_chain(workstream: str | None = None) -> dict:
    """Walk each workstream's receipt chain and report tampering.

    Detects: a rewritten receipt (content_hash mismatch), a removed receipt
    (broken link), and a head pointer that disagrees with the files on disk.
    """
    by_ws: dict[str, list[dict]] = {}
    for r in list_all():
        if "_unreadable" in r:
            continue
        ws = r.get("workstream", "unknown")
        if workstream and ws != workstream:
            continue
        by_ws.setdefault(ws, []).append(r)

    report: dict[str, Any] = {"checked_at": clock.iso(), "workstreams": {}, "ok": True}
    for ws, receipts in by_ws.items():
        # Order by chain_index (ADR-002 D13). completed_at is only a tie-break
        # for legacy receipts written before chain_index existed.
        receipts.sort(key=lambda r: (int(r.get("chain_index", 0)),
                                     r.get("completed_at", ""), r.get("task_id", "")))
        problems: list[str] = []
        expected_prev = GENESIS_HASH
        expected_index = 0
        for r in receipts:
            recomputed = content_hash(r)
            stored = r.get("receipt_hash") or r.get("content_hash")
            if stored and recomputed != stored:
                problems.append(
                    f"{r.get('task_id')}: receipt_hash mismatch — receipt was modified "
                    f"after being written"
                )
            if r.get("prev_receipt_hash") != expected_prev:
                problems.append(
                    f"{r.get('task_id')}: broken chain link — expected prev "
                    f"{expected_prev[:16]}…, found {str(r.get('prev_receipt_hash'))[:16]}… "
                    f"(a receipt may have been deleted or reordered)"
                )
            if int(r.get("chain_index", expected_index)) != expected_index:
                problems.append(
                    f"{r.get('task_id')}: chain_index is {r.get('chain_index')}, expected "
                    f"{expected_index} — a receipt is missing from the sequence"
                )
            expected_prev = stored or recomputed
            expected_index += 1

        head = _head(ws)
        if receipts and head.get("hash") != expected_prev:
            problems.append(
                f"head pointer {str(head.get('hash'))[:16]}… does not match last receipt "
                f"{expected_prev[:16]}… (run scripts/verify.py --chain --repair-head)"
            )
        report["workstreams"][ws] = {"count": len(receipts), "ok": not problems,
                                     "problems": problems,
                                     "head_index": head.get("chain_index")}
        if problems:
            report["ok"] = False
    return report


def repair_head(workstream: str) -> dict:
    """Rebuild a workstream's head pointer from the receipts on disk.

    Only the *pointer* is rebuilt. If the receipts themselves disagree with each
    other, verify_chain still fails afterwards — this is deliberate: a repair
    tool that could paper over tampering would defeat the chain it maintains.
    """
    rows = [r for r in list_all()
            if "_unreadable" not in r and r.get("workstream") == workstream]
    if not rows:
        _set_head(workstream, hash_=GENESIS_HASH, task_id="", count=0, chain_index=-1)
        return {"workstream": workstream, "count": 0, "head": GENESIS_HASH,
                "chain_index": -1, "note": "no receipts on disk; head reset to genesis"}
    rows.sort(key=lambda r: (int(r.get("chain_index", 0)), r.get("completed_at", "")))
    last = rows[-1]
    digest = last.get("receipt_hash") or last.get("content_hash") or content_hash(last)
    index = int(last.get("chain_index", len(rows) - 1))
    _set_head(workstream, hash_=digest, task_id=last.get("task_id", ""),
              count=len(rows), chain_index=index)
    return {"workstream": workstream, "count": len(rows), "head": digest,
            "chain_index": index, "task_id": last.get("task_id")}


def _recency_key(r: dict) -> tuple:
    """Newest-last ordering. Under a virtual clock many receipts share one
    timestamp (ADR-002 D13), so chain_index is the real tie-break."""
    return (r.get("completed_at") or r.get("started_at") or "",
            int(r.get("chain_index", 0)),
            r.get("task_id", ""))


def stats(window: int | None = None) -> dict:
    """Receipt KPIs per G5: coverage by status plus crash_rate.

    ADR-007: crash_rate is measured over the trailing `window` receipts, not
    over all history. Lifetime crashes / lifetime receipts is a ratchet — 4
    crashes hold the gate red until 200 receipts exist, so the metric stops
    tracking reliability and starts rewarding tombstone deletion. The lifetime
    numbers stay in the payload; the window changes what the *budget* judges,
    never what the record shows.
    """
    window = CRASH_WINDOW if window is None else window
    all_receipts = [r for r in list_all() if "_unreadable" not in r]
    counts: dict[str, int] = {s.value: 0 for s in Status}
    for r in all_receipts:
        st = r.get("status", "complete")
        counts[st] = counts.get(st, 0) + 1

    lifetime_total = len(all_receipts)
    lifetime_crashed = counts.get(Status.CRASHED.value, 0)

    recent = sorted(all_receipts, key=_recency_key)[-window:] if window > 0 else []
    recent_crashed = sum(1 for r in recent
                         if r.get("status") == Status.CRASHED.value)
    denom = len(recent) or 1
    crash_rate = recent_crashed / denom

    return {
        "total": lifetime_total,
        "by_status": counts,
        "crash_rate": round(crash_rate, 4),
        "crash_rate_budget": CRASH_RATE_BUDGET,
        "crash_rate_ok": crash_rate <= CRASH_RATE_BUDGET,
        # A window this short cannot resolve a 2% budget at all: one crash in
        # 14 reads as 7%. Callers that need to distinguish "unreliable" from
        # "too early to tell" read this instead of re-deriving it.
        "sample_sufficient": len(recent) >= MIN_CRASH_SAMPLE,
        "window": window,
        "window_size": len(recent),
        "crashed_window": recent_crashed,
        # Lifetime figures are retained deliberately: the window must never be
        # a way to make past crashes disappear from the record.
        "crash_rate_lifetime": round(lifetime_crashed / (lifetime_total or 1), 4),
        "crashed_lifetime": lifetime_crashed,
        "unreadable": sum(1 for r in list_all() if "_unreadable" in r),
    }
