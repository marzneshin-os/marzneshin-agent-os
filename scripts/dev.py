#!/usr/bin/env python3
"""
Marzneshin Agent OS - Unified Service Manager
Starts all local services defined in configs/services.json
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import clock, service_probes
from urllib import request, error

# Colors for output
COLORS = [
    "\033[36m", # Cyan
    "\033[32m", # Green
    "\033[33m", # Yellow
    "\033[35m", # Magenta
    "\033[34m", # Blue
]
RESET = "\033[0m"

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "configs" / "services.json"
LOG_DIR = PROJECT_ROOT / "state" / "logs"

processes: dict[str, subprocess.Popen] = {}

def get_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"Error: {CONFIG_PATH} not found.")
        sys.exit(1)
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def check_port(port: int) -> bool:
    """Check if a local port is in use."""
    import socket
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.5):
            return True
    except OSError:
        return False

def start_services(only: list[str] = None):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    config = get_config()
    
    target_services = list(config.keys())
    if only:
        target_services = [s for s in only if s in config]
        if not target_services:
            print(f"None of the specified services ({only}) found in config.")
            return

    for idx, svc_name in enumerate(target_services):
        svc = config[svc_name]
        port = svc.get("port")
        
        # Check if already running
        if port and check_port(port):
            print(f"{COLORS[idx % len(COLORS)]}[{svc_name}] Already running on port {port}{RESET}")
            continue

        if not port:
            cmd = svc.get("command", "")
            script = svc.get("process_match") or (cmd.split()[-1] if cmd else "")
            if script:
                try:
                    res = subprocess.run(["pgrep", "-f", script], capture_output=True, text=True, timeout=2)
                    pids = [p for p in res.stdout.strip().split("\n") if p]
                    if pids:
                        print(f"{COLORS[idx % len(COLORS)]}[{svc_name}] Already running (stdio PID {','.join(pids)}){RESET}")
                        continue
                except Exception:
                    pass

        cmd = svc.get("command")
        if not cmd:
            continue
            
        print(f"{COLORS[idx % len(COLORS)]}[{svc_name}] Starting...{RESET}")
        
        env = os.environ.copy()
        for k, v in svc.get("env", {}).items():
            # Resolve relative paths
            if v.startswith("./"):
                v = str(PROJECT_ROOT / v[2:])
            env[k] = v
            
        log_file = LOG_DIR / f"{svc_name}.log"
        f_out = open(log_file, "a")
        
        p = subprocess.Popen(
            cmd,
            shell=True,
            cwd=PROJECT_ROOT,
            env=env,
            stdout=f_out,
            stderr=subprocess.STDOUT
        )
        processes[svc_name] = p
        
    if not processes:
        print("No new services started.")
        return
        
    print("\nPress Ctrl+C to stop all services.")
    try:
        while True:
            clock.sleep(1)
            # Check if any died
            for name, p in list(processes.items()):
                if p.poll() is not None:
                    print(f"[{name}] exited with code {p.returncode}")
                    del processes[name]
            if not processes:
                break
    except KeyboardInterrupt:
        print("\nStopping services...")
        for name, p in processes.items():
            print(f"[{name}] Terminating...")
            p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()
        print("All services stopped.")


CORE_TOOLS = ["agentmemory", "headroom", "codeburn", "graphify", "memory_sync", "kimi_k3", "claude_mem"]

def stop_services(only: list[str] = None):
    config = get_config()
    target_services = list(config.keys())
    if only:
        target_services = [s for s in only if s in config]
    
    print(f"Stopping services: {', '.join(target_services)}...")
    for name in target_services:
        svc = config[name]
        port = svc.get("port")
        check_ports = svc.get("check_ports", [port] if port else [])
        for p in check_ports:
            if p:
                subprocess.run(["fuser", "-k", f"{p}/tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        script = svc.get("process_match") or (svc.get("command", "").split()[-1] if svc.get("command") else "")
        if script:
            subprocess.run(["pkill", "-f", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[{name}] Stopped.")

def status_services():
    config = get_config()
    print(f"{'SERVICE':<18} {'PORT/PID':<14} {'STATUS':<10} {'LATENCY':<12} {'MEMORY':<12} {'DETAIL'}")
    print("-" * 80)
    for name, svc in config.items():
        probe = service_probes.probe_single_service(name, svc)
        status_raw = probe["status"]
        if status_raw == "UP":
            status_str = "[32mUP[0m"
        else:
            status_str = "[31mDOWN[0m"

        port_or_pid = str(probe["port"]) if probe.get("port") else (f"PID {','.join(map(str, probe['pids'][:2]))}" if probe.get("pids") else "N/A")
        lat_str = f"{probe['latency_ms']:.1f} ms"
        mem_str = f"{probe['rss_mb']:.1f} MB" if probe.get("rss_mb", 0) > 0 else "-"
        detail = probe.get("error") or "healthy"
        print(f"{name:<18} {port_or_pid:<14} {status_str:<19} {lat_str:<12} {mem_str:<12} {detail[:25]}")

def main():
    parser = argparse.ArgumentParser(description="Unified Service Manager")
    parser.add_argument("action", choices=["start", "status", "stop", "restart", "health"], help="Action to perform")
    parser.add_argument("--only", nargs="+", help="Only apply to specific services")
    parser.add_argument("--tools", action="store_true", help="Target only the 4 core tools (agentmemory, headroom, codeburn, graphify)")
    
    args = parser.parse_args()
    target = CORE_TOOLS if args.tools else args.only
    
    if args.action == "start":
        start_services(target)
    elif args.action == "status":
        status_services()
    elif args.action == "stop":
        stop_services(target)
    elif args.action == "restart":
        stop_services(target)
        clock.sleep(1)
        start_services(target)
    elif args.action == "health":
        import subprocess as _sp
        _sp.run([sys.executable, str(PROJECT_ROOT / "scripts" / "watchdog.py"), "status"])

if __name__ == "__main__":
    main()
