#!/usr/bin/env python3
"""watchdog.py — production-grade service health monitor and auto-recovery.

Implements the Supervisor + Circuit Breaker pattern for all services defined
in configs/services.json. Designed to be triggered by a systemd timer every
30 seconds.

Three health-check strategies:
  - HTTP:    GET to a configurable path, verify status code + timeout
  - Process: verify PID exists and is alive via pgrep
  - Docker:  docker inspect health status

Circuit breaker state machine (per service):
  CLOSED    -> healthy or recoverable; restart on failure
  OPEN      -> repeated failures; cooldown active, no restart
  HALF_OPEN -> cooldown expired; allow one probe restart

Exponential backoff with +/-20% jitter prevents thundering-herd on recovery.

    watchdog.py check              one round of check + recover
    watchdog.py status             display all services + circuit state
    watchdog.py reset <service>    manually reset a circuit breaker
    watchdog.py reset --all        reset all circuit breakers
    watchdog.py check --json       machine-readable output
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from urllib import request, error as url_error

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import clock, events, paths
from lib.atomic import read_json, write_json_atomic

PROJECT_ROOT = paths.repo_root()
CONFIG_PATH = PROJECT_ROOT / "configs" / "services.json"
STATE_PATH = PROJECT_ROOT / "state" / "watchdog.json"
LOG_DIR = PROJECT_ROOT / "state" / "logs"

CIRCUIT_CLOSED = "closed"
CIRCUIT_OPEN = "open"
CIRCUIT_HALF_OPEN = "half_open"

FAILURE_THRESHOLD = 3
INITIAL_COOLDOWN_S = 60
MAX_COOLDOWN_S = 900
BACKOFF_MULTIPLIER = 2
JITTER_FACTOR = 0.2

COLORS = {
    "green": "\033[32m",
    "red": "\033[31m",
    "yellow": "\033[33m",
    "cyan": "\033[36m",
    "dim": "\033[90m",
    "bold": "\033[1m",
    "reset": "\033[0m",
}


def _color(name, text):
    return f"{COLORS.get(name, '')}{text}{COLORS['reset']}"


def get_config():
    if not CONFIG_PATH.exists():
        print(f"Error: {CONFIG_PATH} not found.", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def load_state():
    default = {"services": {}, "updated_at": None}
    try:
        return read_json(STATE_PATH, default=default) or default
    except Exception:
        return default


def save_state(state):
    state["updated_at"] = clock.iso()
    write_json_atomic(STATE_PATH, state)


def ensure_service_state(state, name):
    if name not in state["services"]:
        state["services"][name] = {
            "circuit": CIRCUIT_CLOSED,
            "consecutive_failures": 0,
            "last_check": None,
            "last_healthy": None,
            "last_restart": None,
            "restart_count": 0,
            "backoff_until": None,
            "cooldown_seconds": INITIAL_COOLDOWN_S,
        }
    return state["services"][name]


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------

def check_port(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def check_http(port, path="/", expected=None, timeout_s=2.0):
    if expected is None:
        expected = [200]
    url = f"http://127.0.0.1:{port}{path}"
    try:
        req = request.Request(url, method="GET")
        resp = request.urlopen(req, timeout=timeout_s)
        code = resp.getcode()
        if code in expected:
            return True, f"HTTP {code}"
        return False, f"HTTP {code} (expected {expected})"
    except url_error.HTTPError as e:
        if e.code in expected:
            return True, f"HTTP {e.code}"
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)[:120]


def check_process(process_match):
    try:
        res = subprocess.run(
            ["pgrep", "-f", process_match],
            capture_output=True, text=True, timeout=3,
        )
        pids = [p for p in res.stdout.strip().split("\n") if p]
        if pids:
            return True, f"PID {','.join(pids[:3])}"
        return False, "no matching process"
    except Exception as e:
        return False, str(e)[:120]


def check_docker(container_name):
    try:
        res = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
            capture_output=True, text=True, timeout=5,
        )
        status = res.stdout.strip()
        if status == "running":
            return True, "running"
        return False, f"status={status}"
    except Exception as e:
        return False, str(e)[:120]


def deep_health_check(name, svc):
    health_cfg = svc.get("health", {})
    check_type = health_cfg.get("type", "auto")

    if check_type == "http" or (check_type == "auto" and svc.get("port")):
        port = svc.get("port")
        if not port:
            return False, "no port configured for HTTP check"
        check_ports = svc.get("check_ports", [port])
        for p in check_ports:
            if not check_port(p):
                return False, f"port {p} not listening"
        path = health_cfg.get("path", "/")
        expected = health_cfg.get("expected_status", [200, 404, 405, 501])
        timeout_s = health_cfg.get("timeout_s", 2)
        return check_http(port, path, expected, timeout_s)

    if check_type == "process" or (check_type == "auto" and not svc.get("port")):
        match = svc.get("process_match")
        if not match:
            cmd = svc.get("command", "")
            match = cmd.split()[-1] if cmd else ""
        if not match:
            return False, "no process_match configured"
        return check_process(match)

    if check_type == "docker":
        container = health_cfg.get("container", name)
        return check_docker(container)

    return False, f"unknown check type: {check_type}"


# ---------------------------------------------------------------------------
# Circuit breaker + backoff
# ---------------------------------------------------------------------------

def compute_jittered_cooldown(base_seconds):
    rng = clock.get_clock().rng()
    jitter = rng.uniform(1.0 - JITTER_FACTOR, 1.0 + JITTER_FACTOR)
    return base_seconds * jitter


def should_attempt_restart(svc_state):
    circuit = svc_state.get("circuit", CIRCUIT_CLOSED)

    if circuit == CIRCUIT_OPEN:
        backoff_until = svc_state.get("backoff_until")
        if backoff_until:
            remaining = -clock.age_seconds(backoff_until)
            if remaining > 0:
                return False, f"circuit OPEN, cooldown {remaining:.0f}s remaining"
        svc_state["circuit"] = CIRCUIT_HALF_OPEN
        return True, "circuit HALF_OPEN, probing"

    if circuit == CIRCUIT_HALF_OPEN:
        return True, "circuit HALF_OPEN, probe attempt"

    return True, "circuit CLOSED"


def record_success(svc_state):
    now = clock.iso()
    svc_state["circuit"] = CIRCUIT_CLOSED
    svc_state["consecutive_failures"] = 0
    svc_state["last_check"] = now
    svc_state["last_healthy"] = now
    svc_state["cooldown_seconds"] = INITIAL_COOLDOWN_S


def record_failure(svc_state):
    now = clock.iso()
    svc_state["last_check"] = now
    svc_state["consecutive_failures"] = svc_state.get("consecutive_failures", 0) + 1

    if svc_state["consecutive_failures"] >= FAILURE_THRESHOLD:
        svc_state["circuit"] = CIRCUIT_OPEN
        cooldown = svc_state.get("cooldown_seconds", INITIAL_COOLDOWN_S)
        jittered = compute_jittered_cooldown(cooldown)
        backoff_until = clock.to_iso(
            clock.now() + dt.timedelta(seconds=jittered)
        )
        svc_state["backoff_until"] = backoff_until
        next_cooldown = min(cooldown * BACKOFF_MULTIPLIER, MAX_COOLDOWN_S)
        svc_state["cooldown_seconds"] = next_cooldown
        return CIRCUIT_OPEN
    return svc_state.get("circuit", CIRCUIT_CLOSED)


# ---------------------------------------------------------------------------
# Restart
# ---------------------------------------------------------------------------

def restart_service(name):
    try:
        proc = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "dev.py"),
             "restart", "--only", name],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_ROOT),
        )
        if proc.returncode == 0:
            return True, proc.stdout.strip()[:200]
        return False, (proc.stderr or proc.stdout).strip()[:200]
    except Exception as e:
        return False, str(e)[:200]


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------

WATCHDOG_ACTOR = events.Actor(kind="system", id="watchdog")


def emit_health_event(event_type, service_name, detail):
    try:
        events.emit(
            event_type,
            WATCHDOG_ACTOR,
            events.Subject(kind="service", id=service_name),
            detail,
            trust="internal",
            strict_types=False,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main check loop
# ---------------------------------------------------------------------------

def run_check(config, state):
    results = []
    for name, svc in config.items():
        svc_state = ensure_service_state(state, name)
        healthy, detail = deep_health_check(name, svc)
        result = {
            "service": name,
            "healthy": healthy,
            "detail": detail,
            "action": "none",
            "circuit": svc_state.get("circuit", CIRCUIT_CLOSED),
        }

        if healthy:
            was_down = svc_state.get("consecutive_failures", 0) > 0
            record_success(svc_state)
            result["circuit"] = CIRCUIT_CLOSED
            if was_down:
                result["action"] = "recovered"
                emit_health_event("service.health.recovered", name, {
                    "detail": detail,
                    "restart_count": svc_state.get("restart_count", 0),
                })
        else:
            can_restart, reason = should_attempt_restart(svc_state)
            result["reason"] = reason

            if can_restart:
                ok, restart_detail = restart_service(name)
                svc_state["last_restart"] = clock.iso()
                svc_state["restart_count"] = svc_state.get("restart_count", 0) + 1

                if ok:
                    result["action"] = "restarted"
                    emit_health_event("service.health.recovered", name, {
                        "detail": f"restarted: {restart_detail}",
                        "restart_count": svc_state["restart_count"],
                    })
                    record_success(svc_state)
                    result["circuit"] = CIRCUIT_CLOSED
                else:
                    result["action"] = "restart_failed"
                    new_circuit = record_failure(svc_state)
                    result["circuit"] = new_circuit
                    if new_circuit == CIRCUIT_OPEN:
                        result["action"] = "circuit_opened"
                        emit_health_event("service.health.circuit_open", name, {
                            "detail": detail,
                            "consecutive_failures": svc_state["consecutive_failures"],
                            "cooldown_seconds": svc_state.get("cooldown_seconds", INITIAL_COOLDOWN_S),
                        })
                    else:
                        emit_health_event("service.health.degraded", name, {
                            "detail": detail,
                            "consecutive_failures": svc_state["consecutive_failures"],
                        })
            else:
                result["action"] = "skipped_backoff"
                svc_state["last_check"] = clock.iso()

        results.append(result)

    save_state(state)
    return results


# ---------------------------------------------------------------------------
# CLI: status
# ---------------------------------------------------------------------------

def print_status(config, state):
    fmt = "{:<18} {:<14} {:<20} {:<22} {:<18} {}"
    print(fmt.format("SERVICE", "PORT", "HEALTH", "CIRCUIT", "FAILS", "LAST HEALTHY"))
    print("-" * 85)
    for name, svc in config.items():
        svc_state = ensure_service_state(state, name)
        port = svc.get("port")
        check_ports = svc.get("check_ports")
        port_str = ", ".join(str(p) for p in check_ports) if check_ports else (str(port) if port else "stdio")

        healthy, detail = deep_health_check(name, svc)
        health_str = _color("green", "UP") if healthy else _color("red", "DOWN")

        circuit = svc_state.get("circuit", CIRCUIT_CLOSED)
        if circuit == CIRCUIT_CLOSED:
            circuit_str = _color("green", "CLOSED")
        elif circuit == CIRCUIT_OPEN:
            circuit_str = _color("red", "OPEN")
        else:
            circuit_str = _color("yellow", "HALF_OPEN")

        failures = svc_state.get("consecutive_failures", 0)
        failures_str = str(failures) if failures == 0 else _color("red", str(failures))

        last_healthy = svc_state.get("last_healthy")
        if last_healthy:
            age = clock.age_seconds(last_healthy)
            if age < 60:
                lh_str = f"{age:.0f}s ago"
            elif age < 3600:
                lh_str = f"{age / 60:.0f}m ago"
            else:
                lh_str = f"{age / 3600:.1f}h ago"
        else:
            lh_str = _color("dim", "never")

        print(fmt.format(name, port_str, health_str, circuit_str, failures_str, lh_str))
    print()


# ---------------------------------------------------------------------------
# CLI: reset
# ---------------------------------------------------------------------------

def reset_circuit(state, service, reset_all):
    if reset_all:
        for svc_state in state.get("services", {}).values():
            svc_state["circuit"] = CIRCUIT_CLOSED
            svc_state["consecutive_failures"] = 0
            svc_state["backoff_until"] = None
            svc_state["cooldown_seconds"] = INITIAL_COOLDOWN_S
        save_state(state)
        print("All circuit breakers reset.")
        return

    if not service:
        print("Specify a service name or --all", file=sys.stderr)
        sys.exit(1)

    svc_state = state.get("services", {}).get(service)
    if not svc_state:
        print(f"Unknown service: {service}", file=sys.stderr)
        sys.exit(1)

    old_circuit = svc_state.get("circuit", CIRCUIT_CLOSED)
    svc_state["circuit"] = CIRCUIT_CLOSED
    svc_state["consecutive_failures"] = 0
    svc_state["backoff_until"] = None
    svc_state["cooldown_seconds"] = INITIAL_COOLDOWN_S
    save_state(state)

    emit_health_event("service.health.circuit_reset", service, {
        "previous_circuit": old_circuit,
        "reset_by": "manual",
    })
    print(f"Circuit breaker for {service} reset ({old_circuit} -> closed).")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log_results(results):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "watchdog.log"
    ts = clock.iso()
    lines = []
    for r in results:
        if r["action"] != "none":
            lines.append(f"[{ts}] {r['service']}: {r['action']} "
                         f"(circuit={r['circuit']}, detail={r.get('detail', '')})\n")
    if lines:
        with open(log_path, "a") as f:
            f.writelines(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="watchdog.py",
        description="Service health monitor with circuit breaker",
    )
    parser.add_argument("action", choices=["check", "status", "reset"],
                        help="Action to perform")
    parser.add_argument("service", nargs="?", default=None,
                        help="Service name (for reset)")
    parser.add_argument("--all", action="store_true", dest="reset_all",
                        help="Reset all circuit breakers")
    parser.add_argument("--json", action="store_true",
                        help="Machine-readable JSON output")

    args = parser.parse_args(argv)
    config = get_config()
    state = load_state()

    if args.action == "check":
        results = run_check(config, state)
        log_results(results)

        if args.json:
            print(json.dumps({
                "ok": all(r["healthy"] or r["action"] == "restarted" for r in results),
                "checked_at": clock.iso(),
                "results": results,
            }, indent=2, ensure_ascii=False))
        else:
            for r in results:
                if r["healthy"] and r["action"] == "none":
                    mark = _color("green", "OK")
                elif r["action"] in ("restarted", "recovered"):
                    mark = _color("yellow", "RESTART")
                elif r["action"] == "circuit_opened":
                    mark = _color("red", "CIRCUIT")
                elif r["action"] == "skipped_backoff":
                    mark = _color("dim", "WAIT")
                else:
                    mark = _color("red", "FAIL")
                print(f"  [{mark}] {r['service']:<18} {r.get('detail', '')}")

        has_open_circuits = any(
            r["circuit"] == CIRCUIT_OPEN for r in results
        )
        return 1 if has_open_circuits else 0

    elif args.action == "status":
        print_status(config, state)
        return 0

    elif args.action == "reset":
        reset_circuit(state, args.service, args.reset_all)
        return 0

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"watchdog: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
