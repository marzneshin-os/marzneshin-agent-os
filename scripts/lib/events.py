"""Append-only event log (BUILD-SPEC §3.2, revised by ADR-001 D4).

Layout:  state/events/{YYYY-MM-DD}/{actor}.ndjson

One writer per file. That is the whole trick: because an actor only ever
appends to its own file, two agents running in parallel can never produce a
git merge conflict and never need the global CAS that G6 rejected.

Ordering, without a global sequence number:
  - `event_id` is a ULID  -> lexicographic sort == time sort, no coordination
  - `actor_seq`           -> per-actor monotonic, so a gap means a lost event
  - `causation_id`        -> the causal chain, which is what actually matters

Events are immutable. There is no update() and no delete(). Compaction writes
a new snapshot; it never rewrites history.
"""

from __future__ import annotations

try:
    import fcntl  # POSIX advisory locks (stdlib)
except ImportError:  # pragma: no cover — non-POSIX fallback
    fcntl = None

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterator

from . import clock, paths
from .atomic import append_ndjson, read_json, read_ndjson, write_json_atomic
from .ids import canonical_json, new_ulid, sha256_str
from .redact import redact_obj, scan_obj

SCHEMA_VERSION = "2.0.0"  # ADR-002 D11: aligned with BUILD-SPEC §3

# Closed vocabulary. An unknown type is a bug, not an extension point:
# add it here and to analytics/schemas/event.schema.json in the same commit.
EVENT_TYPES = frozenset({
    # session / lifecycle
    "session.started", "session.ended", "handoff.written",
    # lease
    "lease.acquired", "lease.renewed", "lease.released", "lease.expired", "lease.revoked",
    # task
    "task.created", "task.claimed", "task.started", "task.completed", "task.failed",
    "task.abandoned", "task.crashed", "task.superseded",
    # a2a
    "a2a.dispatched", "a2a.received", "a2a.cancelled", "a2a.completed", "a2a.failed",
    "a2a.replayed", "transport.degraded", "transport.restored",
    # verification / policy
    "verify.passed", "verify.failed", "policy.evaluated", "policy.denied",
    "approval.requested", "approval.granted", "approval.timeout",
    # state
    "state.compacted", "receipt.written", "receipt.chain.verified",
    "event.gap.detected",
    # narrative state (ADR-008): the phase/slice pointer and the decision log.
    # Without these two, `slice` was derivable only from a session.started
    # payload — so a mid-phase slice change had no event to carry it and
    # STATE.active_slice went stale for three days (VS-3 vs VS-4), and an ADR
    # could not be announced on the log at all.
    "slice.transitioned", "decision.recorded", "decision.declined",
    # llm
    "llm.chat",
    # safety
    "killswitch.engaged", "killswitch.released", "killswitch.unknown",
    "guardrail.breached", "rollback.executed", "autonomy.changed", "autonomy.shadow_decision", "autonomy.promoted", "autonomy.demoted", "autonomy.quarantined", "autonomy.reviewed",
    "budget.reserved", "budget.settled", "budget.exceeded",
    # ops
    "probe.sampled", "slo.breached", "incident.opened", "incident.closed",
    "agent.heartbeat", "agent.dead", "sim.scenario.run",
    # continuity (VS-4)
    "event.anomaly.registered", "drill.cold_restore.completed",
    "owner.heartbeat", "deadman.engaged", "deadman.escalated",
    # succession (VS-4, §11.1): the flow as an auditable state machine — one
    # event per step, so a half-finished succession is visible on the log.
    "member.removed", "succession.started", "succession.frozen",
    "succession.revoked", "succession.reconstructed", "succession.reassigned",
    "succession.verified", "succession.completed", "succession.failed",
    # escrow (VS-4, §11.2): the encrypted recovery bundle's build/verify trail.
    "escrow.built", "escrow.verified",
    # adversarial review & continuity (VS-5)
    "review.requested", "review.rejected", "review.approved", "continuity.scored",
    # canary & config pipeline (VS-7)
    "canary.deployed", "canary.promoted", "canary.held", "canary.inconclusive", "canary.rolled_back",
    # growth & funnel events (VS-8, §13.1)
    "funnel.visit", "funnel.signup", "funnel.trial_started",
    "checkout.initiated", "checkout.completed", "checkout.failed",
    "connection.success", "connection.failure", "campaign.attributed",
    # experiment loop events (VS-9, §13.4)
    "experiment.created", "experiment.readout", "experiment.shipped",
    "experiment.killed", "experiment.stopped", "experiment.negative_result",
})

ACTOR_KINDS = frozenset({"agent", "human", "system", "workflow", "sim"})


@dataclass
class Actor:
    kind: str
    id: str
    session: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in ACTOR_KINDS:
            raise ValueError(f"unknown actor kind {self.kind!r}; allowed: {sorted(ACTOR_KINDS)}")

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"kind": self.kind, "id": self.id}
        if self.session:
            d["session"] = self.session
        return d

    @property
    def partition(self) -> str:
        return f"{self.kind}-{self.id}"


@dataclass
class Subject:
    kind: str
    id: str

    def to_dict(self) -> dict:
        return {"kind": self.kind, "id": self.id}


@dataclass
class Event:
    type: str
    actor: Actor
    subject: Subject
    payload: dict = field(default_factory=dict)
    correlation_id: str | None = None
    causation_id: str | None = None
    inputs_hash: str | None = None
    event_id: str = ""
    ts: str = ""
    actor_seq: int = 0
    redacted: bool = False
    # §3.2 required fields, added by ADR-002 D14.
    world: str = "prod"
    transport: str | None = None
    tick_level: str | None = None
    trust: str = "internal"
    seed: int | None = None
    redaction_map: list = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        d = {
            "event_id": self.event_id,
            "actor_seq": self.actor_seq,
            "ts": self.ts,
            "type": self.type,
            "actor": self.actor.to_dict(),
            "subject": self.subject.to_dict(),
            "payload": self.payload,
            "schema_version": self.schema_version,
            "world": self.world,
            "trust": self.trust,
            "redacted": self.redacted,
            "redaction_map": self.redaction_map,
        }
        if self.correlation_id:
            d["correlation_id"] = self.correlation_id
        if self.causation_id:
            d["causation_id"] = self.causation_id
        if self.inputs_hash:
            d["inputs_hash"] = self.inputs_hash
        if self.transport:
            d["transport"] = self.transport
        if self.tick_level:
            d["tick_level"] = self.tick_level
        if self.seed is not None:
            d["seed"] = self.seed
        return d


class EventLogError(RuntimeError):
    pass


TRUST_LEVELS = frozenset({"owner", "internal", "untrusted"})


def _watermarks_lock():
    """Exclusive advisory lock guarding watermark read-modify-write (VS-4).

    The 2026-07-30 qa-gate collision: two concurrent emitters (the T1 file
    processor and the T2 result poller) both read watermark 4 and both
    emitted seq 5 and 6 — duplicate actor_seq values that detect_gaps now
    flags forever, because the raw log is immutable (§3.2). Read-modify-write
    across two file operations is only safe under a kernel lock.

    Every caller opens its OWN fd for the lock file: flock semantics then
    serialize threads inside one process and processes on one host alike.
    """
    lock_path = paths.event_watermarks_file().with_name("_watermarks.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = open(lock_path, "a", encoding="utf-8")
    if fcntl is not None:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX)  # type: ignore
    elif __import__("os").name == "nt":
        import msvcrt
        msvcrt.locking(fd.fileno(), msvcrt.LK_LOCK, 1)
    return fd


def _next_actor_seq(actor: Actor, on: date, world: str) -> int:
    """Next per-actor sequence number, from a durable watermark (ADR-002 D18).

    The previous implementation scanned back a fixed seven days. An agent idle
    longer than that — a nightly recon, a monthly drill, a standby agent —
    restarted at 1, and detect_gaps reported the restart as a phantom gap. A
    detector that fires falsely is a detector somebody disables, which is
    exactly how G5 lost receipt coverage.

    The watermark is authoritative, but never trusted blindly: we take the max
    of watermark and what is actually on disk, so a lost or rolled-back
    watermark file cannot make the counter go backwards and manufacture
    duplicate sequence numbers. The whole read-scan-write runs under an
    exclusive file lock, or two concurrent emitters allocate the same number
    (the qa-gate incident above).
    """
    key = f"{world}:{actor.partition}"
    lock_fd = _watermarks_lock()
    try:
        marks = read_json(paths.event_watermarks_file(), default={}) or {}
        high = int(marks.get(key, 0))

        day = on
        for _ in range(7):
            path = paths.event_file(actor.partition, day, world=world)
            if path.exists():
                rows = read_ndjson(path)
                if rows:
                    high = max(high, max(int(r.get("actor_seq", 0)) for r in rows))
                    break
            day = date.fromordinal(day.toordinal() - 1)

        nxt = high + 1
        marks[key] = nxt
        write_json_atomic(paths.event_watermarks_file(), marks, pretty=False)
        return nxt
    finally:
        if fcntl is not None:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
        elif __import__("os").name == "nt":
            import msvcrt
            msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
        lock_fd.close()


# --- anomaly registry (VS-4, ADR-006) ----------------------------------------

def register_anomaly(*, actor_partition: str, day: str, kind: str,
                     seqs: list[int], event_ids: list[str], adr: str, by: str,
                     note: str = "", world: str | None = None) -> dict:
    """Register an explained actor_seq anomaly as an ADR-cited exception.

    Raw events are immutable (§3.2): historical damage cannot be edited away,
    only explained. A registered anomaly tells detect_gaps "these (actor, seq)
    pairs have a documented cause" — anything NOT registered still fails the
    gate, so the detector loses none of its teeth. The registry file is
    script-written (never hand-edited, same rule as the log itself) and every
    registration emits an audit event.

    `kind` is "duplicate_seq" or "missing_seq"; `event_ids` binds the
    exception to exactly the offending events; `adr` is the decision record
    that explains the incident and the fix.
    """
    if kind not in ("duplicate_seq", "missing_seq"):
        raise EventLogError(f"unknown anomaly kind {kind!r}")
    if not adr:
        raise EventLogError("an anomaly without an ADR reference is not registrable")
    w = world or paths.current_world()
    entry = {
        "actor": actor_partition,
        "day": day,
        "kind": kind,
        "seqs": sorted({int(s) for s in seqs}),
        "event_ids": sorted(event_ids),
        "adr": adr,
        "note": note,
        "world": w,
        "registered_by": by,
        "registered_at": clock.iso(),
    }
    reg_path = paths.anomalies_file()
    registry = read_json(reg_path, default=None) or {"schema_version": SCHEMA_VERSION,
                                                     "anomalies": []}
    # Idempotent on (actor, day, kind): re-registering refreshes, never stacks.
    kept = [a for a in registry.get("anomalies", [])
            if not (a.get("actor") == actor_partition and a.get("day") == day
                    and a.get("kind") == kind and a.get("world", "prod") == w)]
    kept.append(entry)
    registry["anomalies"] = kept
    write_json_atomic(reg_path, registry)
    emit("event.anomaly.registered",
         Actor(kind="system", id="events"),
         Subject(kind="actor", id=actor_partition),
         {"day": day, "kind": kind, "seqs": entry["seqs"], "adr": adr, "by": by},
         trust="internal")
    return entry


def _registered_seqs(*, world: str) -> dict[str, set[int]]:
    """actor_partition -> set of seqs covered by a registered anomaly."""
    registry = read_json(paths.anomalies_file(), default=None) or {}
    pairs: dict[str, set[int]] = {}
    for a in registry.get("anomalies", []):
        if a.get("world", "prod") != world:
            continue
        pairs.setdefault(a.get("actor", ""), set()).update(
            int(s) for s in a.get("seqs", []))
    return pairs


def list_anomalies(*, world: str | None = None) -> list[dict]:
    registry = read_json(paths.anomalies_file(), default=None) or {}
    items = registry.get("anomalies", [])
    if world is None:
        return list(items)
    return [a for a in items if a.get("world", "prod") == world]


def emit(
    type: str,
    actor: Actor,
    subject: Subject,
    payload: dict | None = None,
    *,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    inputs_hash: str | None = None,
    transport: str | None = None,
    tick_level: str | None = None,
    trust: str = "internal",
    strict_types: bool = True,
) -> Event:
    """Append one event. Returns the stored event (ids and ts filled in).

    Secrets are redacted before persisting, never after (I6). If redaction
    changed anything, `redacted: true` is recorded along with the JSON paths
    that were touched, so an auditor knows the payload is not verbatim and
    knows exactly where (§3.2: "removal without recording is forbidden").

    `world` comes from the environment, not from a parameter: a caller must not
    be able to talk its way into the production partition (ADR-002 D14).
    """
    if strict_types and type not in EVENT_TYPES:
        raise EventLogError(
            f"unknown event type {type!r}. Add it to events.EVENT_TYPES and "
            f"analytics/schemas/event.schema.json in the same commit."
        )
    if trust not in TRUST_LEVELS:
        raise EventLogError(f"unknown trust level {trust!r}; allowed: {sorted(TRUST_LEVELS)}")

    world = paths.current_world()
    c = clock.get_clock()
    if getattr(c, "kind", "real") == "virtual" and world != "sim":
        # A virtual clock only exists inside sim/ and tests. Letting it write to
        # the production partition would poison every KPI derived from it, and
        # the poisoning would be invisible because the rows look real.
        raise EventLogError(
            "a virtual clock is active but MARZ_WORLD is not 'sim'. Refusing to "
            "write simulated events into the production partition (§3.2). Set "
            "MARZ_WORLD=sim for simulated runs."
        )

    raw_payload = payload or {}
    scan = scan_obj(raw_payload, where="$.payload")
    safe_payload = redact_obj(raw_payload) if not scan.clean else raw_payload

    now = clock.now()
    ev = Event(
        type=type,
        actor=actor,
        subject=subject,
        payload=safe_payload,
        correlation_id=correlation_id,
        causation_id=causation_id,
        inputs_hash=inputs_hash,
        event_id=new_ulid(),
        ts=clock.to_iso(now),
        actor_seq=_next_actor_seq(actor, now.date(), world),
        redacted=not scan.clean,
        world=world,
        transport=transport,
        tick_level=tick_level,
        trust=trust,
        seed=getattr(c, "seed", None) if world == "sim" else None,
        redaction_map=[f.where for f in scan.findings],
    )
    append_ndjson(paths.event_file(actor.partition, now.date(), world=world), ev.to_dict())
    return ev


def emit_dict(event: dict) -> Path:
    """Append a pre-built event dict. Used by the compactor and by importers
    replaying an archive; skips id/seq assignment on purpose.

    The event's own `world` decides its partition. An archived sim event stays a
    sim event when replayed — replay must not launder it into production.
    """
    for required in ("event_id", "ts", "type", "actor", "subject"):
        if required not in event:
            raise EventLogError(f"event missing required field {required!r}")
    actor = event["actor"]
    partition = f"{actor['kind']}-{actor['id']}"
    day = clock.parse_iso(event["ts"]).date()
    world = event.get("world", "prod")
    return append_ndjson(paths.event_file(partition, day, world=world), event)


def read_day(on: date, *, world: str = "prod") -> list[dict]:
    """All events for a day, across actors, sorted by event_id (== by time).

    Defaults to the production partition: no existing caller sees simulated
    data by accident (ADR-002 D14).
    """
    directory = paths.events_dir(on, world=world)
    if not directory.exists():
        return []
    rows: list[dict] = []
    for f in sorted(directory.glob("*.ndjson")):
        rows.extend(read_ndjson(f))
    rows.sort(key=lambda r: r.get("event_id", ""))
    return rows


def iter_range(start: date, end: date, *, world: str = "prod") -> Iterator[dict]:
    """Inclusive date range, in causal-compatible order."""
    day = start
    while day <= end:
        yield from read_day(day, world=world)
        day = date.fromordinal(day.toordinal() + 1)


def detect_gaps(start: date, end: date, *, world: str = "prod",
                honor_registry: bool = True) -> list[dict]:
    """Find missing actor_seq values — i.e. events that were lost.

    This is the reason actor_seq exists. A gap is not recoverable, but it must
    be *visible*: silent loss in an audit log is worse than a red build.

    With honor_registry (the default), (actor, seq) pairs covered by a
    registered, ADR-cited anomaly are subtracted — the raw events are
    immutable (§3.2), so explained history stays explained. An unregistered
    gap still fails the gate; the detector loses none of its teeth. Pass
    honor_registry=False for the raw forensic view.
    """
    seen: dict[str, list[int]] = {}
    for ev in iter_range(start, end, world=world):
        actor = ev.get("actor", {})
        key = f"{actor.get('kind')}-{actor.get('id')}"
        seen.setdefault(key, []).append(int(ev.get("actor_seq", 0)))
    gaps = []
    for key, seqs in seen.items():
        ordered = sorted(s for s in seqs if s > 0)
        if not ordered:
            continue
        expected = set(range(ordered[0], ordered[-1] + 1))
        missing = sorted(expected - set(ordered))
        duplicates = sorted({s for s in ordered if ordered.count(s) > 1})
        if missing or duplicates:
            gaps.append({"actor": key, "missing_seq": missing, "duplicate_seq": duplicates,
                         "range": [ordered[0], ordered[-1]]})
    if honor_registry and gaps:
        registered = _registered_seqs(world=world)
        explained = []
        for gap in gaps:
            covered = registered.get(gap["actor"], set())
            gap["missing_seq"] = [s for s in gap["missing_seq"] if s not in covered]
            gap["duplicate_seq"] = [s for s in gap["duplicate_seq"] if s not in covered]
            if gap["missing_seq"] or gap["duplicate_seq"]:
                explained.append(gap)
        gaps = explained
    return gaps


def chain_hash(events: list[dict]) -> str:
    """Order-independent digest of an event set, used by compaction to prove a
    snapshot derives from exactly these events."""
    ids = sorted(e.get("event_id", "") for e in events)
    return sha256_str(canonical_json(ids))
