"""Workstream leases with fencing tokens (BUILD-SPEC §3.6).

The spec gets this right and it is worth restating why: a TTL alone does not
prevent split-brain. A worker can hold a lease, stall (GC pause, network
partition, suspended container), have its lease expire and be reassigned, then
wake up and complete its write — clobbering the new holder.

The fencing token is the only real defence. Every acquisition increments a
repo-wide monotonic counter. Every state write carries the writer's token, and
a write is rejected if its token is lower than the one currently recorded.
The stalled worker wakes up holding token 41, the current holder has 42, and
its write is refused.

  fencing_token >= current  =>  accept
  fencing_token <  current  =>  reject (StaleFencingToken)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from . import clock, paths
from .atomic import CorruptState, read_json, write_json_atomic

DEFAULT_TTL_MINUTES = 90
DEFAULT_HEARTBEAT_SLA_MINUTES = 15


class LeaseError(RuntimeError):
    pass


class LeaseHeld(LeaseError):
    """Another holder has a live lease on this workstream."""


class LeaseNotHeld(LeaseError):
    """Operation requires a lease this caller does not hold."""


class StaleFencingToken(LeaseError):
    """A write arrived with a token older than the current one: split-brain
    was detected and prevented."""


@dataclass
class Lease:
    workstream: str
    holder: str
    session: str
    acquired_at: str
    ttl_min: int
    heartbeat_at: str
    fencing_token: int

    @property
    def expires_at(self) -> str:
        return clock.to_iso(clock.parse_iso(self.acquired_at) + timedelta(minutes=self.ttl_min))

    def expired(self) -> bool:
        return clock.age_seconds(self.acquired_at) > self.ttl_min * 60

    def heartbeat_stale(self, sla_min: int = DEFAULT_HEARTBEAT_SLA_MINUTES) -> bool:
        """Missed heartbeats are the earlier signal. The heartbeat workflow
        uses this to detect a dead agent before the TTL runs out."""
        return clock.age_seconds(self.heartbeat_at) > sla_min * 60

    def to_dict(self) -> dict:
        return {
            "workstream": self.workstream,
            "holder": self.holder,
            "session": self.session,
            "acquired_at": self.acquired_at,
            "ttl_min": self.ttl_min,
            "heartbeat_at": self.heartbeat_at,
            "expires_at": self.expires_at,
            "fencing_token": self.fencing_token,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Lease":
        return cls(
            workstream=d["workstream"],
            holder=d["holder"],
            session=d.get("session", ""),
            acquired_at=d["acquired_at"],
            ttl_min=int(d.get("ttl_min", DEFAULT_TTL_MINUTES)),
            heartbeat_at=d.get("heartbeat_at", d["acquired_at"]),
            fencing_token=int(d["fencing_token"]),
        )


def _next_fencing_token() -> int:
    """Increment and return the repo-wide fencing counter.

    Deliberately a single small file: it is the one place in the system that
    genuinely requires a global monotonic counter, and it is written only on
    lease acquisition (rare), not per event (hot path). That is why removing
    the global event `seq` in D4 was safe while keeping this.
    """
    path = paths.fencing_file()
    try:
        data = read_json(path, default={"current": 0})
    except CorruptState:
        # Never reuse a token after corruption: jump forward, do not reset.
        data = {"current": _highest_token_seen() + 1000}
    token = int(data.get("current", 0)) + 1
    write_json_atomic(path, {"current": token, "updated_at": clock.iso()})
    return token


def _highest_token_seen() -> int:
    highest = 0
    if paths.locks_dir().exists():
        for f in paths.locks_dir().glob("*.lock.json"):
            try:
                d = read_json(f, default={})
            except CorruptState:
                continue
            highest = max(highest, int(d.get("fencing_token", 0)))
    return highest


def current_fencing_token() -> int:
    try:
        return int(read_json(paths.fencing_file(), default={"current": 0}).get("current", 0))
    except CorruptState:
        return _highest_token_seen()


def read(workstream: str) -> Lease | None:
    path = paths.lock_file(workstream)
    if not path.exists():
        return None
    try:
        data = read_json(path, default=None)
    except CorruptState:
        # A corrupt lock is treated as held by an unknown party: fail closed.
        raise LeaseHeld(f"lock file for {workstream!r} is corrupt; manual review required")
    return Lease.from_dict(data) if data else None


def acquire(workstream: str, holder: str, session: str, *,
            ttl_min: int = DEFAULT_TTL_MINUTES, steal_expired: bool = True) -> Lease:
    """Acquire a workstream lease.

    Re-acquiring your own live lease is idempotent and renews it — a worker
    resuming after a context compaction must not deadlock against itself.
    """
    existing = read(workstream)
    if existing:
        if existing.holder == holder and not existing.expired():
            return renew(workstream, holder)
        if not existing.expired():
            raise LeaseHeld(
                f"{workstream!r} held by {existing.holder} until {existing.expires_at} "
                f"(token {existing.fencing_token})"
            )
        if not steal_expired:
            raise LeaseHeld(f"{workstream!r} lease expired but stealing is disabled")

    lease = Lease(
        workstream=workstream,
        holder=holder,
        session=session,
        acquired_at=clock.iso(),
        ttl_min=ttl_min,
        heartbeat_at=clock.iso(),
        fencing_token=_next_fencing_token(),
    )
    write_json_atomic(paths.lock_file(workstream), lease.to_dict())
    return lease


def renew(workstream: str, holder: str) -> Lease:
    """Refresh heartbeat and extend TTL. Does NOT mint a new fencing token:
    the holder's identity has not changed, so downstream writes stay valid."""
    lease = read(workstream)
    if lease is None:
        raise LeaseNotHeld(f"no lease on {workstream!r}")
    if lease.holder != holder:
        raise LeaseNotHeld(f"{workstream!r} held by {lease.holder}, not {holder}")
    lease.heartbeat_at = clock.iso()
    lease.acquired_at = clock.iso()
    write_json_atomic(paths.lock_file(workstream), lease.to_dict())
    return lease


def release(workstream: str, holder: str, *, force: bool = False) -> None:
    """Release a lease. `force` is for the reaper and the succession protocol."""
    lease = read(workstream)
    if lease is None:
        return
    if lease.holder != holder and not force:
        raise LeaseNotHeld(f"{workstream!r} held by {lease.holder}, not {holder}")
    paths.lock_file(workstream).unlink(missing_ok=True)


def revoke(workstream: str, *, revoked_by: str, reason: str) -> int:
    """Invalidate a lease by minting a NEW fencing token without a holder.

    This is STEP 1 of the succession protocol (§11.1): the departing member's
    in-flight writes must be rejected even if their process is still alive.
    Burning a token is what makes that happen — the old holder's token is now
    strictly lower than current.
    """
    token = _next_fencing_token()
    paths.lock_file(workstream).unlink(missing_ok=True)
    write_json_atomic(
        paths.locks_dir() / f"{paths.slug(workstream)}.revoked.json",
        {"workstream": workstream, "revoked_by": revoked_by, "reason": reason,
         "revoked_at": clock.iso(), "burned_fencing_token": token},
    )
    return token


def assert_writable(workstream: str, holder: str, fencing_token: int) -> None:
    """Gate every state write. Raises unless the caller's token is current.

    Called by hooks/pre_tool.py before any write inside a leased workstream.
    """
    lease = read(workstream)
    if lease is None:
        raise LeaseNotHeld(f"no lease on {workstream!r}: acquire one before writing")
    if lease.holder != holder:
        raise LeaseNotHeld(f"{workstream!r} held by {lease.holder}, not {holder}")
    if fencing_token < lease.fencing_token:
        raise StaleFencingToken(
            f"write rejected: token {fencing_token} < current {lease.fencing_token} "
            f"for {workstream!r}. Split-brain prevented — re-acquire the lease and "
            f"re-read state before retrying."
        )
    if lease.expired():
        raise LeaseNotHeld(f"{workstream!r} lease expired at {lease.expires_at}")


def list_all() -> list[Lease]:
    out: list[Lease] = []
    if not paths.locks_dir().exists():
        return out
    for f in sorted(paths.locks_dir().glob("*.lock.json")):
        try:
            data = read_json(f, default=None)
        except CorruptState:
            continue
        if data:
            out.append(Lease.from_dict(data))
    return out


def find_zombies(sla_min: int = DEFAULT_HEARTBEAT_SLA_MINUTES) -> list[dict[str, Any]]:
    """Leases that are expired or whose holder stopped heartbeating.

    Consumed by the heartbeat workflow and by the Handoff Guardian agent,
    which is the reason that agent was promoted to Tier 0 (ADR-001 D8).
    """
    findings = []
    for lease in list_all():
        reasons = []
        if lease.expired():
            reasons.append("ttl_expired")
        if lease.heartbeat_stale(sla_min):
            reasons.append("heartbeat_stale")
        if reasons:
            findings.append({
                "workstream": lease.workstream,
                "holder": lease.holder,
                "session": lease.session,
                "reasons": reasons,
                "age_seconds": int(clock.age_seconds(lease.acquired_at)),
                "heartbeat_age_seconds": int(clock.age_seconds(lease.heartbeat_at)),
                "fencing_token": lease.fencing_token,
            })
    return findings
