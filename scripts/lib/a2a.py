"""A2A bus: envelope build/validate, registry, idempotency, transport router.

BUILD-SPEC §3.5 (envelope) + §5 (transports) + §5.4 (task state machine) +
§5.5 (route selection, health, fallback). One envelope serves every
transport; moving between T1/T2/T3 changes zero content.

  T1 (git-transport, baseline)   envelope JSON -> state/a2a/inbox/{agent}/,
                                  processed -> outbox/ -> processed/ (I17:
                                  inbox files are moved, never deleted)
  T2 (moxt-transport, fast path) dispatch record -> state/a2a/t2/ + assignment
                                  on the Moxt Workflow (VS-3 wires the real
                                  workflow; lib never does network I/O, G9)

Fallback (§5.5): 3 consecutive failures on the preferred route mark it
degraded and traffic moves to T1 with a transport.degraded event; 5
consecutive health successes restore it (hysteresis, no flapping).

Idempotency (§3.5): forever/scoped/none per capability, key always carries a
time dimension. A repeat send with the same key returns the stored result
without re-executing — that is the "repeat = no re-execution" proof.

Every state transition emits an event (§5.4). No module here does network
I/O; the T2 client is injected (sim: MoxtFake; prod: platform-side bridge).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import atomic, clock, events, ids, paths, policy, validate

SCHEMA_VERSION = "2.0.0"

# §5.5 thresholds
FAIL_THRESHOLD = 3      # consecutive failures -> degraded, fall back to T1
RECOVER_THRESHOLD = 5   # consecutive health successes -> restore preferred
T2_HEALTH_FRESH_S = 300  # prod T2 heartbeat older than this = unavailable (fail-closed)

TASK_STATES = ("created", "admitted", "queued", "running", "verifying",
               "completed", "failed", "cancelled")


class A2AError(RuntimeError):
    """Bus-level failure (invalid envelope, unknown route, transport down)."""


# --- registry ---------------------------------------------------------------

_REGISTRY_CACHE: dict | None = None


def registry(*, reload: bool = False) -> dict:
    """Load agents/registry.json (JSON so lib stays stdlib-only, ADR-005 D27)."""
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE is None or reload:
        data = atomic.read_json(paths.registry_file(), default=None)
        if not isinstance(data, dict) or "agents" not in data:
            # fail-closed: an unreadable registry means no routing at all
            raise A2AError(f"registry unreadable at {paths.rel(paths.registry_file())}")
        _REGISTRY_CACHE = data
    return _REGISTRY_CACHE


def clear_registry_cache() -> None:
    global _REGISTRY_CACHE
    _REGISTRY_CACHE = None


def agent_entry(agent_id: str) -> dict:
    entry = registry().get("agents", {}).get(agent_id)
    if entry is None:
        raise A2AError(f"agent {agent_id!r} not in registry (fail-closed)")
    if entry.get("revoked"):
        # §11.1 STEP 2 (REVOKE): a succeeded member's A2A scope dies here.
        # Fail-closed like every other safety control (I12): revoked == absent.
        raise A2AError(f"agent {agent_id!r} access revoked (fail-closed, §11.1 REVOKE)")
    return entry


def capability_overrides() -> dict:
    """Registry capability section in the shape policy.idempotency_spec wants.
    None values are omitted: a missing ttl means 'use the class default'."""
    out = {}
    for name, spec in registry().get("capabilities", {}).items():
        idem = spec.get("idempotency", {})
        entry = {k: v for k, v in (("class", idem.get("class")),
                                   ("ttl", idem.get("ttl"))) if v is not None}
        if entry:
            out[name] = entry
    return out


# --- envelope ---------------------------------------------------------------

def build_envelope(*, sender: str, to: str, capability: str,
                   input: dict, input_provenance: list[dict],
                   priority: str = "normal", transport: str | None = None,
                   autonomy_requested: str = "L2",
                   deadline_s: int = 3600, env_epoch: str | None = None,
                   target_epoch: str | None = None, seed: int | None = None,
                   correlation_id: str | None = None, causation_id: str | None = None,
                   callback: dict | None = None) -> dict:
    """Compose and schema-validate one §3.5 envelope.

    The idempotency key is derived, never caller-supplied: class and TTL come
    from policy (capability risk class), tightened only by the registry.
    """
    entry = agent_entry(to)  # fail-closed on unknown recipient
    if capability not in entry.get("capabilities", []):
        raise A2AError(
            f"{to!r} does not declare capability {capability!r} in the registry")
    inputs_hash = ids.sha256_obj(input)
    idem = policy.build_idempotency_key(
        capability=capability, sender=sender, recipient=to,
        inputs_hash=inputs_hash, env_epoch=env_epoch, target_epoch=target_epoch,
        overrides=capability_overrides())
    chosen = transport or entry.get("transports", {}).get("preferred", "T1")
    env = {
        "schema_version": SCHEMA_VERSION,
        "task_id": f"A2A-{ids.new_ulid()}",
        "created_at": clock.iso(),
        "from": sender,
        "to": to,
        "capability": capability,
        "transport": chosen,
        "idempotency": {
            "class": idem["class"],
            "ttl_s": idem.get("ttl_seconds", 0),
            "components": (["cap", "inputs_hash", "target_epoch"] if idem["class"] == "forever"
                           else ["from", "to", "capability", "inputs_hash", "env_epoch"]),
            "key": idem.get("key"),
            "env_epoch": env_epoch,
            "target_epoch": target_epoch,
            "attempt": 1,
            "retry_of": None,
        },
        "input": input,
        "input_provenance": input_provenance,
        "deadline": clock.to_iso(clock.now() + _dt_seconds(deadline_s)),
        "priority": priority,
        "correlation_id": correlation_id or ids.new_correlation_id(),
        "callback": callback or {"T1": f"state/a2a/outbox/{sender}/", "T2": None, "T3": None},
        "autonomy_requested": autonomy_requested,
        "world": paths.current_world(),
        "seed": seed,
        "trace_id": ids.sha256_str(ids.new_ulid())[:32],
    }
    if causation_id:
        env["causation_id"] = causation_id
    problems = validate_envelope(env)
    if problems:
        raise A2AError("envelope failed schema validation: " + "; ".join(problems))
    return env


def _dt_seconds(s: float):
    from datetime import timedelta
    return timedelta(seconds=s)


def validate_envelope(env: dict) -> list[str]:
    """Schema-validate an envelope. Returns a list of problems ([] = valid)."""
    result = validate.validate(env, "a2a-envelope")
    if result.ok:
        return []
    return list(result.errors) or ["schema invalid"]


# --- idempotency store ------------------------------------------------------

def _idem_path(key: str) -> Path:
    safe = key.replace("sha256:", "").replace("/", "_")
    return paths.a2a_idem_dir() / f"{safe}.json"


def idem_lookup(key: str | None) -> dict | None:
    """Return the stored dispatch record if the key is still valid, else None."""
    if not key:
        return None
    entry = atomic.read_json(_idem_path(key), default=None)
    if not entry:
        return None
    expires = entry.get("expires_at")
    if expires and clock.age_seconds(expires) > 0:
        return None  # scoped key aged out: a stale result is worse than none (§3.5)
    return entry


def idem_save(key: str | None, record: dict, *, ttl_s: int = 0) -> None:
    if not key:
        return  # class none: never durably deduped (§3.5)
    body = dict(record)
    body["key"] = key
    body["stored_at"] = clock.iso()
    body["expires_at"] = (clock.to_iso(clock.now() + _dt_seconds(ttl_s)) if ttl_s else None)
    atomic.write_json_atomic(_idem_path(key), body)


# --- transport health + router (§5.5) ----------------------------------------

def _health() -> dict:
    return atomic.read_json(paths.transport_health_file(), default={}) or {}


def _save_health(h: dict) -> None:
    atomic.write_json_atomic(paths.transport_health_file(), h)


def transport_state(name: str) -> dict:
    return _health().get(name, {"consecutive_failures": 0, "consecutive_successes": 0,
                                "degraded": False})


def record_transport_result(name: str, ok: bool, *, actor: events.Actor,
                            detail: str = "") -> bool:
    """Update health counters. Returns True if the route is currently usable.

    Emits transport.degraded / transport.restored exactly at the threshold
    crossings — the audit trail for §5.5 fallback decisions.
    """
    h = _health()
    st = h.get(name, {"consecutive_failures": 0, "consecutive_successes": 0,
                      "degraded": False})
    if ok:
        st["consecutive_successes"] = st.get("consecutive_successes", 0) + 1
        st["consecutive_failures"] = 0
        if st.get("degraded") and st["consecutive_successes"] >= RECOVER_THRESHOLD:
            st["degraded"] = False
            events.emit("transport.restored", actor,
                        events.Subject(kind="transport", id=name),
                        {"after_successes": st["consecutive_successes"]}, transport=name)
    else:
        st["consecutive_failures"] = st.get("consecutive_failures", 0) + 1
        st["consecutive_successes"] = 0
        if not st.get("degraded") and st["consecutive_failures"] >= FAIL_THRESHOLD:
            st["degraded"] = True
            events.emit("transport.degraded", actor,
                        events.Subject(kind="transport", id=name),
                        {"after_failures": st["consecutive_failures"], "detail": detail},
                        transport=name)
    h[name] = st
    _save_health(h)
    return not st.get("degraded")


class T2Client:
    """Interface the platform side implements. Lib never does network I/O (G9).

    deliver(envelope) -> {"ref": "moxt://task/<id>"}   (raises on failure)
    healthz() -> bool                                   (fresh = usable)
    """

    def deliver(self, envelope: dict) -> dict:  # pragma: no cover - interface
        raise NotImplementedError

    def healthz(self) -> bool:  # pragma: no cover - interface
        raise NotImplementedError


class FileT2Client(T2Client):
    """Prod T2 bridge: dispatch records on disk + heartbeat freshness.

    The actual Moxt Workflow assignment is performed by the platform side
    (the operator agent via Moxt tools); this client records the dispatch,
    maps envelope <-> workflow task, and treats a stale/missing heartbeat as
    unavailable (fail-closed — 'I don't know' equals 'stopped', rule 6).
    """

    def deliver(self, envelope: dict) -> dict:
        rec = {
            "task_id": envelope["task_id"],
            "moxt_ref": None,  # filled by the platform side after assignment
            "status": "pending_assignment",
            "envelope": envelope,
            "recorded_at": clock.iso(),
        }
        path = paths.a2a_t2_dir() / f"{envelope['task_id']}.json"
        atomic.write_json_atomic(path, rec)
        return {"ref": f"file://{paths.rel(path)}", "status": "pending_assignment"}

    def healthz(self) -> bool:
        beat = atomic.read_json(paths.a2a_t2_health_file(), default=None)
        if not beat or not beat.get("heartbeat_at"):
            return False
        return clock.age_seconds(beat["heartbeat_at"]) <= T2_HEALTH_FRESH_S


def t2_heartbeat(*, source: str) -> None:
    """Platform side calls this to prove the T2 path is alive."""
    atomic.write_json_atomic(paths.a2a_t2_health_file(),
                             {"heartbeat_at": clock.iso(), "source": source})


def choose_route(agent_id: str, *, t2_client: T2Client | None = None,
                 actor: events.Actor | None = None) -> str:
    """Preferred transport if usable, else T1 (§5.5). T1 is always usable."""
    entry = agent_entry(agent_id)
    preferred = entry.get("transports", {}).get("preferred", "T1")
    allowed = entry.get("transports", {}).get("allowed", ["T1"])
    actor = actor or events.Actor(kind="system", id="a2a-router")
    if preferred == "T1" or "T2" not in allowed:
        return "T1"
    st = transport_state("T2")
    client = t2_client or FileT2Client()
    # Always probe — also when degraded: the §5.5 recovery rule (5 consecutive
    # greens) can only ever trigger if a degraded route still gets health
    # checks. This is the half-open probe, and it is cheap.
    usable = bool(client.healthz())
    record_transport_result("T2", usable, actor=actor, detail="healthz")
    if transport_state("T2").get("degraded"):
        return "T1"
    return "T2" if usable else "T1"


# --- send / process -----------------------------------------------------------

@dataclass
class DispatchResult:
    ok: bool
    task_id: str
    transport: str
    state: str
    replayed: bool = False
    ref: str | None = None
    reason: str = ""
    policy_decision: dict | None = None

    def to_dict(self) -> dict:
        return {"ok": self.ok, "task_id": self.task_id, "transport": self.transport,
                "state": self.state, "replayed": self.replayed, "ref": self.ref,
                "reason": self.reason, "policy": self.policy_decision}


def send(envelope: dict, *, t2_client: T2Client | None = None,
         actor: events.Actor | None = None) -> DispatchResult:
    """Route one envelope: policy gate -> idempotency -> transport. §5.4 states."""
    actor = actor or events.Actor(kind="agent", id=envelope.get("from", "unknown"))
    subject = events.Subject(kind="task", id=envelope["task_id"])
    corr = envelope.get("correlation_id")

    # --- policy gate (runs identically on every transport, §6) ---
    prov = [policy.Provenance(field_path=p["field"], source=p["source"],
                              trust=policy.Trust(p["trust"]),
                              content_hash=p.get("content_hash"),
                              sanitizer=p.get("sanitizer") or "envelope-v1")
            for p in envelope.get("input_provenance", [])]
    requested = int(envelope.get("autonomy_requested", "L2").lstrip("L"))
    ceiling = agent_entry(envelope["to"]).get("autonomy_max", "L3")
    decision = policy.evaluate(
        capability=envelope["capability"], agent=envelope["to"],
        autonomy_requested=requested, agent_ceiling=int(ceiling.lstrip("L")),
        provenance=prov)
    events.emit("policy.evaluated", actor, subject,
                {"decision": decision.decision.value, "reason": decision.reason,
                 "capability": envelope["capability"]}, correlation_id=corr)
    if not decision.allowed:
        events.emit("a2a.failed", actor, subject,
                    {"state": "failed", "reason": f"policy: {decision.reason}"},
                    correlation_id=corr)
        return DispatchResult(ok=False, task_id=envelope["task_id"],
                              transport=envelope["transport"], state="failed",
                              reason=f"policy denied: {decision.reason}",
                              policy_decision=decision.to_dict())

    # --- idempotency: repeat = return stored result, no re-execution (§3.5) ---
    key = envelope.get("idempotency", {}).get("key")
    hit = idem_lookup(key)
    if hit:
        events.emit("a2a.replayed", actor, subject,
                    {"key": key, "stored_at": hit.get("stored_at")},
                    correlation_id=corr, transport=envelope["transport"])
        t_val = hit.get("transport", envelope.get("transport"))
        return DispatchResult(ok=True, task_id=envelope["task_id"],
                              transport=str(t_val) if t_val is not None else "unknown",
                              state=str(hit.get("state", "queued")), replayed=True,
                              ref=hit.get("ref"),
                              reason="idempotent replay: stored result returned, nothing re-executed",
                              policy_decision=decision.to_dict())

    # --- route + deliver ---
    route = choose_route(envelope["to"], t2_client=t2_client, actor=actor)
    envelope["transport"] = route  # content unchanged except the route marker
    try:
        if route == "T2":
            client = t2_client or FileT2Client()
            out = client.deliver(envelope)
            record_transport_result("T2", True, actor=actor)
            ref = out.get("ref")
        else:
            path = paths.a2a_inbox(envelope["to"]) / f"{envelope['task_id']}.json"
            atomic.write_json_atomic(path, envelope)
            ref = paths.rel(path)
    except Exception as exc:
        if route == "T2":
            record_transport_result("T2", False, actor=actor, detail=str(exc))
            # §5 governing principle: the gateway can die and the system must
            # continue with degraded LATENCY, not a stop. The same envelope —
            # zero content change (§3.5) — falls back to the T1 baseline.
            envelope["transport"] = "T1"
            path = paths.a2a_inbox(envelope["to"]) / f"{envelope['task_id']}.json"
            atomic.write_json_atomic(path, envelope)
            route = "T1"
            ref = paths.rel(path)
        else:
            events.emit("a2a.failed", actor, subject,
                        {"state": "failed", "reason": f"T1 deliver: {exc}"},
                        correlation_id=corr, transport="T1")
            return DispatchResult(ok=False, task_id=envelope["task_id"],
                                  transport="T1", state="failed",
                                  reason=f"T1 deliver failed: {exc}",
                                  policy_decision=decision.to_dict())

    events.emit("a2a.dispatched", actor, subject,
                {"state": "queued", "capability": envelope["capability"],
                 "to": envelope["to"], "ref": ref},
                correlation_id=corr, transport=route)
    idem_save(key, {"task_id": envelope["task_id"], "transport": route,
                    "state": "queued", "ref": ref},
              ttl_s=int(envelope.get("idempotency", {}).get("ttl_s") or 0))
    return DispatchResult(ok=True, task_id=envelope["task_id"], transport=route,
                          state="queued", ref=ref,
                          reason="admitted and queued",
                          policy_decision=decision.to_dict())


@dataclass
class ProcessResult:
    task_id: str
    ok: bool
    state: str
    handler_result: dict | None = None
    error: str | None = None
    replayed: bool = False

    def to_dict(self) -> dict:
        return {"task_id": self.task_id, "ok": self.ok, "state": self.state,
                "result": self.handler_result, "error": self.error,
                "replayed": self.replayed}


def process_inbox(agent_id: str, handlers: dict[str, Callable[[dict], dict]], *,
                  actor: events.Actor | None = None) -> list[ProcessResult]:
    """Drain one agent's T1 inbox. The agent executes; the bus records (I17).

    handlers: capability -> callable(envelope) -> result dict. A raise means
    task failed (the envelope is still archived — audit before comfort).
    """
    actor = actor or events.Actor(kind="agent", id=agent_id)
    inbox = paths.a2a_inbox(agent_id)
    results: list[ProcessResult] = []
    if not inbox.exists():
        return results
    for path in sorted(inbox.glob("A2A-*.json")):
        env = atomic.read_json(path, default=None)
        if env is None:
            continue  # unreadable file stays for a human; fail-closed, not deleted
        subject = events.Subject(kind="task", id=env["task_id"])
        corr = env.get("correlation_id")
        events.emit("a2a.received", actor, subject,
                    {"state": "running", "capability": env.get("capability")},
                    correlation_id=corr, transport="T1")
        handler = handlers.get(env.get("capability", ""))
        try:
            if handler is None:
                raise A2AError(f"no handler for capability {env.get('capability')!r}")
            out = handler(env) or {}
            state, ok, error = "completed", True, None
        except Exception as exc:
            out, state, ok, error = {"error": str(exc)}, "failed", False, str(exc)
        result_doc = {"task_id": env["task_id"], "state": state, "result": out,
                      "processed_at": clock.iso(), "agent": agent_id,
                      "envelope": env}
        atomic.write_json_atomic(paths.a2a_outbox(agent_id) / path.name, result_doc)
        archive = dict(result_doc)
        archive["archived_from"] = paths.rel(path)
        atomic.write_json_atomic(paths.a2a_processed(agent_id) / path.name, archive)
        path.unlink()  # moved, not deleted: the archive copy is the proof (I17)
        key = env.get("idempotency", {}).get("key")
        if key:
            idem_save(key, {"task_id": env["task_id"], "transport": "T1",
                            "state": state, "ref": paths.rel(paths.a2a_processed(agent_id) / path.name)},
                      ttl_s=int(env.get("idempotency", {}).get("ttl_s") or 0))
        events.emit("a2a.completed" if ok else "a2a.failed", actor, subject,
                    {"state": state, "error": error},
                    correlation_id=corr, transport="T1")
        results.append(ProcessResult(task_id=env["task_id"], ok=ok, state=state,
                                     handler_result=out, error=error))
    return results


def process_t2_record(task_id: str, handlers: dict[str, Callable[[dict], dict]], *,
                      agent_id: str, actor: events.Actor | None = None) -> ProcessResult:
    """Execute one T2-delivered task (§5.2): the envelope arrived via the Moxt
    Workflow assignment, not the T1 inbox. Symmetric to process_inbox: execute,
    write outbox + processed archive, update the idempotency store and the T2
    dispatch record. The Moxt-side status/comment is the platform mirror.
    """
    actor = actor or events.Actor(kind="agent", id=agent_id)
    rec_path = paths.a2a_t2_dir() / f"{task_id}.json"
    rec = atomic.read_json(rec_path, default=None)
    if rec is None:
        raise A2AError(f"no T2 dispatch record for {task_id!r}")
    env = rec["envelope"]
    subject = events.Subject(kind="task", id=task_id)
    corr = env.get("correlation_id")
    events.emit("a2a.received", actor, subject,
                {"state": "running", "capability": env.get("capability"),
                 "moxt_ref": rec.get("moxt_ref")},
                correlation_id=corr, transport="T2")
    handler = handlers.get(env.get("capability", ""))
    try:
        if handler is None:
            raise A2AError(f"no handler for capability {env.get('capability')!r}")
        out = handler(env) or {}
        state, ok, error = "completed", True, None
    except Exception as exc:
        out, state, ok, error = {"error": str(exc)}, "failed", False, str(exc)
    result_doc = {"task_id": task_id, "state": state, "result": out,
                  "processed_at": clock.iso(), "agent": agent_id,
                  "envelope": env, "moxt_ref": rec.get("moxt_ref")}
    name = f"{task_id}.json"
    atomic.write_json_atomic(paths.a2a_outbox(agent_id) / name, result_doc)
    atomic.write_json_atomic(paths.a2a_processed(agent_id) / name,
                             dict(result_doc, archived_from=paths.rel(rec_path)))
    rec["status"] = state
    rec["processed_at"] = result_doc["processed_at"]
    atomic.write_json_atomic(rec_path, rec)
    key = env.get("idempotency", {}).get("key")
    if key:
        idem_save(key, {"task_id": task_id, "transport": "T2", "state": state,
                        "ref": paths.rel(paths.a2a_processed(agent_id) / name)},
                  ttl_s=int(env.get("idempotency", {}).get("ttl_s") or 0))
    events.emit("a2a.completed" if ok else "a2a.failed", actor, subject,
                {"state": state, "error": error, "moxt_ref": rec.get("moxt_ref")},
                correlation_id=corr, transport="T2")
    return ProcessResult(task_id=task_id, ok=ok, state=state,
                         handler_result=out, error=error)


def queue_depth(agent_id: str) -> int:
    inbox = paths.a2a_inbox(agent_id)
    return len(list(inbox.glob("A2A-*.json"))) if inbox.exists() else 0
