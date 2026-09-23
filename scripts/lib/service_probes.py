"""
scripts/lib/service_probes.py — High-Resolution Semantic Health Prober

Marzneshin OS stdlib-only service probe fleet.
Provides semantic health checks, millisecond latency measurements,
process RSS memory accounting, and circuit breaker metrics for all 12 services.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path
from urllib import error, request

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = REPO_ROOT / "configs" / "services.json"


def measure_http_probe(
    port: int,
    path: str = "/",
    expected_status: list[int] | None = None,
    timeout_s: float = 2.5
) -> dict:
    """Probe an HTTP endpoint with high-resolution latency tracking (stdlib-only)."""
    expected = expected_status or [200]
    clean_path = ("/" + path.lstrip("/")) if path else "/"
    url = f"http://127.0.0.1:{port}{clean_path}"
    
    start = time.perf_counter()
    try:
        req = request.Request(url, headers={"User-Agent": "Marzneshin-HealthProbe/2.0"})
        with request.urlopen(req, timeout=timeout_s) as resp:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            code = resp.getcode()
            ok = code in expected
            return {
                "ok": ok,
                "status_code": code,
                "latency_ms": latency_ms,
                "error": None if ok else f"Unexpected status {code} (expected {expected})"
            }
    except error.HTTPError as he:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        ok = he.code in expected
        return {
            "ok": ok,
            "status_code": he.code,
            "latency_ms": latency_ms,
            "error": None if ok else f"HTTP {he.code}: {he.reason}"
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "ok": False,
            "status_code": None,
            "latency_ms": latency_ms,
            "error": str(e)
        }


def measure_process_probe(process_match: str) -> dict:
    """Probe a background process by pattern match and calculate RSS memory."""
    start = time.perf_counter()
    try:
        res = subprocess.run(
            ["pgrep", "-f", process_match],
            capture_output=True,
            text=True,
            timeout=3.0
        )
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        if res.returncode != 0:
            return {
                "ok": False,
                "pids": [],
                "rss_mb": 0.0,
                "latency_ms": latency_ms,
                "error": f"No process matching '{process_match}' found"
            }
            
        pids = [int(p) for p in res.stdout.strip().splitlines() if p.isdigit()]
        if not pids:
            return {
                "ok": False,
                "pids": [],
                "rss_mb": 0.0,
                "latency_ms": latency_ms,
                "error": "No matching PID parsed"
            }
            
        # Sum RSS memory across matched PIDs from /proc (Linux) or ps
        total_rss_kb = 0
        for pid in pids:
            proc_status = Path(f"/proc/{pid}/status")
            if proc_status.exists():
                try:
                    with open(proc_status, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            if line.startswith("VmRSS:"):
                                parts = line.split()
                                if len(parts) >= 2 and parts[1].isdigit():
                                    total_rss_kb += int(parts[1])
                except Exception:
                    pass
                    
        rss_mb = round(total_rss_kb / 1024.0, 2)
        return {
            "ok": True,
            "pids": pids,
            "rss_mb": rss_mb,
            "latency_ms": latency_ms,
            "error": None
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "ok": False,
            "pids": [],
            "rss_mb": 0.0,
            "latency_ms": latency_ms,
            "error": str(e)
        }


def measure_port_probe(port: int, timeout_s: float = 1.0) -> dict:
    """Check TCP connectivity on local port."""
    start = time.perf_counter()
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout_s):
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return {"ok": True, "latency_ms": latency_ms, "error": None}
    except Exception as e:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"ok": False, "latency_ms": latency_ms, "error": str(e)}


def probe_single_service(name: str, svc_config: dict) -> dict:
    """Execute the configured probe for a service definition."""
    health_cfg = svc_config.get("health", {})
    probe_type = health_cfg.get("type", "port")
    port = svc_config.get("port")
    
    if probe_type == "http" and port:
        path = health_cfg.get("path", "/")
        expected = health_cfg.get("expected_status", [200])
        timeout = float(health_cfg.get("timeout_s", 2.5))
        probe_res = measure_http_probe(port, path, expected, timeout)
    elif probe_type == "process":
        proc_match = svc_config.get("process_match") or name
        probe_res = measure_process_probe(proc_match)
    elif port:
        probe_res = measure_port_probe(port)
    else:
        probe_res = {"ok": False, "latency_ms": 0.0, "error": "Unknown probe configuration"}
        
    status = "UP" if probe_res.get("ok") else "DOWN"
    return {
        "service": name,
        "status": status,
        "probe_type": probe_type,
        "port": port,
        "latency_ms": probe_res.get("latency_ms", 0.0),
        "rss_mb": probe_res.get("rss_mb", 0.0),
        "pids": probe_res.get("pids", []),
        "error": probe_res.get("error")
    }


def probe_all_services(config_file: Path | str | None = None) -> list[dict]:
    """Probe all services defined in configs/services.json."""
    cfg_path = Path(config_file) if config_file else CONFIG_PATH
    if not cfg_path.exists():
        return []
        
    with open(cfg_path, "r", encoding="utf-8") as f:
        services_dict = json.load(f)
        
    reports = []
    for name, svc in services_dict.items():
        report = probe_single_service(name, svc)
        reports.append(report)
    return reports
