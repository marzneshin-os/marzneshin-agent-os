"""Relevance AI account health check and auto-rotation.

Provides account pool management, health monitoring, blueprint
snapshot/deploy, and automatic credential rotation — all without
external dependencies (uses urllib from stdlib).

Usage from other modules:
    from lib import relevance_health as rh
    status = rh.quick_check()          # "HEALTHY" | "LOW_CREDITS" | "DEAD"
    rh.auto_rotate()                   # switch to next healthy account
    rh.snapshot_all()                   # export resources to local JSON
    rh.deploy_all()                    # recreate resources from blueprints
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from . import clock

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_DIR = REPO_ROOT / "state" / "relevance-ai"
BLUEPRINTS_DIR = STATE_DIR / "blueprints"
POOL_FILE = STATE_DIR / "account-pool.json"
ENV_FILE = REPO_ROOT / ".env"

# Health status constants
HEALTHY = "HEALTHY"
LOW_CREDITS = "LOW_CREDITS"
DEAD = "DEAD"

# Timeout for API calls (seconds) — kept short for session_start budget
_TIMEOUT = 5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_dirs() -> None:
    """Create blueprint directories if they don't exist."""
    for sub in ("agents", "tools", "workforces"):
        (BLUEPRINTS_DIR / sub).mkdir(parents=True, exist_ok=True)


def _read_pool() -> dict:
    """Read account pool from file, bootstrapping from .env if needed."""
    if POOL_FILE.exists():
        with open(POOL_FILE, encoding="utf-8") as f:
            return json.load(f)

    # Bootstrap: try to create pool from current .env
    pool = {"active_index": 0, "accounts": []}
    env_account = _read_env_credentials()
    if env_account:
        env_account["label"] = "env-bootstrap"
        env_account["added_at"] = clock.now().isoformat()
        pool["accounts"].append(env_account)
        _ensure_dirs()
        _write_pool(pool)
    return pool


def _write_pool(pool: dict) -> None:
    """Write account pool to file."""
    _ensure_dirs()
    with open(POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(pool, f, indent=2, ensure_ascii=False)


def _read_env_credentials() -> dict | None:
    """Read Relevance AI credentials from .env file."""
    if not ENV_FILE.exists():
        return None
    creds: dict[str, str] = {}
    with open(ENV_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("RELEVANCE_AI_REGION="):
                creds["region"] = line.split("=", 1)[1]
            elif line.startswith("RELEVANCE_AI_PROJECT="):
                creds["project"] = line.split("=", 1)[1]
            elif line.startswith("RELEVANCE_AI_API_KEY="):
                creds["api_key"] = line.split("=", 1)[1]
    if all(k in creds for k in ("region", "project", "api_key")):
        return creds
    return None


def _active_account(pool: dict | None = None) -> dict | None:
    """Get the currently active account from the pool."""
    if pool is None:
        pool = _read_pool()
    if not pool["accounts"]:
        return None
    idx = pool["active_index"] % len(pool["accounts"])
    return pool["accounts"][idx]


def _api_base(account: dict) -> str:
    """Build API base URL for an account."""
    return f"https://api-{account['region']}.stack.tryrelevance.com/latest"


def _auth_header(account: dict) -> str:
    """Build authorization header value."""
    return f"{account['project']}:{account['api_key']}"


def _ssl_context() -> ssl.SSLContext:
    """Create a permissive SSL context for urllib."""
    ctx = ssl.create_default_context()
    return ctx


def _api_call(
    account: dict,
    method: str,
    endpoint: str,
    body: dict | None = None,
    timeout: int = _TIMEOUT,
) -> tuple[int, dict]:
    """Make an API call to Relevance AI.

    Returns (http_status, response_body_dict).
    Status 0 means network/connection error.
    """
    url = f"{_api_base(account)}/{endpoint.lstrip('/')}"
    headers = {
        "Authorization": _auth_header(account),
        "Content-Type": "application/json",
    }

    data = None
    if body is not None or method == "POST":
        data = json.dumps(body or {}).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        ctx = _ssl_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, {"raw": raw.decode(errors="replace")}
    except urllib.error.HTTPError as exc:
        try:
            err_body = json.loads(exc.read().decode(errors="replace"))
        except Exception:
            err_body = {"error": str(exc)}
        return exc.code, err_body
    except Exception as exc:
        return 0, {"error": str(exc)}


def _log_event(event_type: str, details: dict) -> None:
    """Append a rotation event to the Relevance AI event log."""
    log_dir = STATE_DIR / "events"
    log_dir.mkdir(parents=True, exist_ok=True)

    entry = {
        "ts": clock.now().isoformat(),
        "type": event_type,
        **details,
    }

    log_file = log_dir / f"{clock.now().strftime('%Y-%m-%d')}.ndjson"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def quick_check(account: dict | None = None) -> str:
    """Check health of the active (or given) account.

    Returns one of: HEALTHY, LOW_CREDITS, DEAD
    """
    if account is None:
        account = _active_account()
    if account is None:
        return DEAD
    status, _resp = _api_call(account, "GET", "/studios/list")

    if status == 0:
        return DEAD          # Network error
    if status in (401, 403):
        return DEAD          # Auth failed
    if status in (402, 429):
        return LOW_CREDITS   # Payment required / rate-limited
    if 200 <= status < 300:
        return HEALTHY

    # Unknown error — treat as dead (fail-closed per BUILD-SPEC I12)
    return DEAD


def snapshot_all(account: dict | None = None) -> dict:
    """Export all agents, tools, workforces from account to local blueprints.

    Returns dict with counts: {"agents": N, "tools": N, "workforces": N}
    """
    if account is None:
        account = _active_account()
    if account is None:
        return {"error": "No active account"}

    _ensure_dirs()
    counts = {"agents": 0, "tools": 0, "workforces": 0}

    payload = {
        "page_size": 100,
        "filters": [{
            "filter_type": "exact_match",
            "field": "project",
            "condition_value": account["project"]
        }]
    }

    # --- Snapshot agents ---------------------------------------------------
    s, resp = _api_call(account, "POST", "/agents/list", payload)
    if 200 <= s < 300:
        for agent in resp.get("results", []):
            aid = agent.get("agent_id", agent.get("studio_id", "unknown"))
            s2, full = _api_call(account, "GET", f"/agents/{aid}")
            if 200 <= s2 < 300:
                bp = BLUEPRINTS_DIR / "agents" / f"{aid}.json"
                with open(bp, "w", encoding="utf-8") as f:
                    json.dump(full, f, indent=2, ensure_ascii=False)
                counts["agents"] += 1

    # --- Snapshot tools ----------------------------------------------------
    s, resp = _api_call(account, "POST", "/studios/list", payload)
    if 200 <= s < 300:
        for tool in resp.get("results", []):
            tid = tool.get("studio_id", "unknown")
            s2, full = _api_call(account, "GET", f"/studios/{tid}")
            if 200 <= s2 < 300:
                bp = BLUEPRINTS_DIR / "tools" / f"{tid}.json"
                with open(bp, "w", encoding="utf-8") as f:
                    json.dump(full, f, indent=2, ensure_ascii=False)
                counts["tools"] += 1

    # --- Snapshot workforces -----------------------------------------------
    s, resp = _api_call(account, "POST", "/workforces/list", payload)
    if 200 <= s < 300:
        for wf in resp.get("results", []):
            wid = wf.get("workforce_id", "unknown")
            bp = BLUEPRINTS_DIR / "workforces" / f"{wid}.json"
            with open(bp, "w", encoding="utf-8") as f:
                json.dump(wf, f, indent=2, ensure_ascii=False)
            counts["workforces"] += 1

    # --- Save snapshot metadata --------------------------------------------
    meta = {
        "snapshot_at": clock.now().isoformat(),
        "account_label": account.get("label", "unknown"),
        "counts": counts,
    }
    with open(STATE_DIR / "last-snapshot.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    _log_event("relevance.snapshot", meta)
    return counts


def deploy_all(account: dict | None = None) -> dict:
    """Deploy all local blueprints to the given (or active) account.

    Returns dict: {"agents": N, "tools": N, "workforces": N, "errors": [...]}
    """
    if account is None:
        account = _active_account()
    if account is None:
        return {"error": "No active account"}

    _ensure_dirs()
    results: dict = {"agents": 0, "tools": 0, "workforces": 0, "errors": []}

    # --- Deploy tools first (agents depend on them) ------------------------
    tools_dir = BLUEPRINTS_DIR / "tools"
    if tools_dir.exists():
        for bp_file in sorted(tools_dir.glob("*.json")):
            with open(bp_file, encoding="utf-8") as f:
                cfg = json.load(f)
            s, resp = _api_call(account, "POST", "/studios/create", cfg)
            if 200 <= s < 300:
                results["tools"] += 1
            else:
                results["errors"].append(f"Tool {bp_file.stem}: HTTP {s}")

    # --- Deploy agents -----------------------------------------------------
    agents_dir = BLUEPRINTS_DIR / "agents"
    if agents_dir.exists():
        for bp_file in sorted(agents_dir.glob("*.json")):
            with open(bp_file, encoding="utf-8") as f:
                cfg = json.load(f)
            s, resp = _api_call(account, "POST", "/agents/upsert", cfg)
            if 200 <= s < 300:
                results["agents"] += 1
            else:
                results["errors"].append(f"Agent {bp_file.stem}: HTTP {s}")

    # --- Deploy workforces -------------------------------------------------
    wf_dir = BLUEPRINTS_DIR / "workforces"
    if wf_dir.exists():
        for bp_file in sorted(wf_dir.glob("*.json")):
            with open(bp_file, encoding="utf-8") as f:
                cfg = json.load(f)
            s, resp = _api_call(account, "POST", "/workforces/create", cfg)
            if 200 <= s < 300:
                results["workforces"] += 1
            else:
                results["errors"].append(f"Workforce {bp_file.stem}: HTTP {s}")

    # --- Save deploy metadata ----------------------------------------------
    meta = {
        "deployed_at": clock.now().isoformat(),
        "account_label": account.get("label", "unknown"),
        "results": results,
    }
    with open(STATE_DIR / "last-deploy.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    _log_event("relevance.deploy", meta)
    return results


def update_env(region: str, project: str, api_key: str) -> None:
    """Rewrite .env with new Relevance AI credentials, preserving other vars."""
    lines: list[str] = []
    if ENV_FILE.exists():
        with open(ENV_FILE, encoding="utf-8") as f:
            lines = f.readlines()

    # Filter out old Relevance AI lines and their header comment
    new_lines: list[str] = []
    skip_block = False
    for line in lines:
        stripped = line.strip()
        if stripped == "# Relevance AI MCP Configuration":
            skip_block = True
            continue
        if skip_block and stripped == "":
            skip_block = False
            continue
        if stripped.startswith("RELEVANCE_AI_"):
            continue
        skip_block = False
        new_lines.append(line)

    # Ensure trailing newline on last existing line
    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines[-1] += "\n"

    # Append new Relevance AI config block
    new_lines.append("\n# Relevance AI MCP Configuration\n")
    new_lines.append(f"RELEVANCE_AI_REGION={region}\n")
    new_lines.append(f"RELEVANCE_AI_PROJECT={project}\n")
    new_lines.append(f"RELEVANCE_AI_API_KEY={api_key}\n")

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def auto_rotate() -> dict:
    """Auto-rotate to next healthy account, update .env, deploy blueprints.

    Returns: {"success": bool, ...}
    On failure returns {"success": False, "error": str, "all_dead": bool}
    """
    pool = _read_pool()
    n = len(pool["accounts"])

    if n < 2:
        return {
            "success": False,
            "error": (
                "Only one account in pool. Add more with:\n"
                "  python3 scripts/relevance_manager.py add-account"
            ),
            "all_dead": False,
        }

    # Best-effort snapshot of current account before leaving
    current = _active_account(pool)
    if current and quick_check(current) != DEAD:
        try:
            snapshot_all(current)
        except Exception:
            pass  # snapshot is best-effort

    original_idx = pool["active_index"]

    for offset in range(1, n + 1):
        candidate_idx = (original_idx + offset) % n
        candidate = pool["accounts"][candidate_idx]

        if quick_check(candidate) == HEALTHY:
            # --- Switch to this account ------------------------------------
            pool["active_index"] = candidate_idx
            _write_pool(pool)

            update_env(candidate["region"], candidate["project"], candidate["api_key"])

            deploy_result = deploy_all(candidate)

            _log_event("relevance.rotated", {
                "from_index": original_idx,
                "to_index": candidate_idx,
                "to_label": candidate.get("label", "unknown"),
                "deploy": deploy_result,
            })

            return {
                "success": True,
                "new_account": candidate.get("label", f"account-{candidate_idx}"),
                "deploy": deploy_result,
            }

    # All accounts dead
    _log_event("relevance.all_dead", {
        "pool_size": n,
        "checked_at": clock.now().isoformat(),
    })

    return {
        "success": False,
        "error": "All accounts in pool are DEAD or exhausted. Add a new account.",
        "all_dead": True,
    }


def add_account(label: str, region: str, project: str, api_key: str) -> dict:
    """Add a new account to the pool (validates credentials first).

    Returns: {"success": True, ...} or {"error": str}
    """
    pool = _read_pool()

    # Duplicate check
    for acc in pool["accounts"]:
        if acc.get("project") == project:
            return {"error": f"Account with project {project} already exists"}

    new_account = {
        "label": label,
        "region": region,
        "project": project,
        "api_key": api_key,
        "added_at": clock.now().isoformat(),
    }

    # Verify credentials before adding
    health = quick_check(new_account)
    if health == DEAD:
        return {"error": "Account credentials are invalid (health check returned DEAD)"}

    pool["accounts"].append(new_account)
    _write_pool(pool)

    _log_event("relevance.account_added", {
        "label": label,
        "health": health,
        "pool_size": len(pool["accounts"]),
    })

    return {
        "success": True,
        "label": label,
        "health": health,
        "index": len(pool["accounts"]) - 1,
    }


def remove_account(index: int) -> dict:
    """Remove an account from the pool by index."""
    pool = _read_pool()
    if index < 0 or index >= len(pool["accounts"]):
        return {"error": f"Invalid index {index}. Pool has {len(pool['accounts'])} accounts."}

    removed = pool["accounts"].pop(index)
    # Adjust active_index if needed
    if pool["active_index"] >= len(pool["accounts"]):
        pool["active_index"] = 0
    _write_pool(pool)

    return {"success": True, "removed": removed.get("label", "unknown")}


def pool_status() -> dict:
    """Get full pool status with health check for each account."""
    pool = _read_pool()
    status_list = []
    for i, acc in enumerate(pool["accounts"]):
        health = quick_check(acc)
        status_list.append({
            "index": i,
            "label": acc.get("label", "unnamed"),
            "region": acc.get("region", "?"),
            "health": health,
            "active": i == pool["active_index"],
            "added_at": acc.get("added_at", "unknown"),
        })
    return {
        "total": len(pool["accounts"]),
        "active_index": pool["active_index"],
        "accounts": status_list,
    }
