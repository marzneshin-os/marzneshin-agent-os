#!/usr/bin/env python3
"""Simulation Harness for Marzneshin Autonomous OS.

Runs proposed changes in an isolated simulation environment before production.
Red in sim = forbidden in production (Iron Rule 5).

Commands:
    run    <scenario>   - Run a simulation scenario
    list                - List available scenarios
    status              - Show last simulation result
    reset               - Clear simulation state
"""
import json
import sys
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SIM_DIR = PROJECT_ROOT / "sim"
SIM_STATE = SIM_DIR / "sim_state.json"
SIM_RESULTS = SIM_DIR / "results"
SIM_SCENARIOS = SIM_DIR / "scenarios"


def ensure_dirs():
    SIM_RESULTS.mkdir(parents=True, exist_ok=True)
    SIM_SCENARIOS.mkdir(parents=True, exist_ok=True)


def load_state():
    if SIM_STATE.exists():
        with open(SIM_STATE, "r") as f:
            return json.load(f)
    return {"last_run": None, "total_runs": 0, "last_result": None}


def save_state(state):
    with open(SIM_STATE, "w") as f:
        json.dump(state, f, indent=2)


def run_scenario(name):
    scenario_file = SIM_SCENARIOS / f"{name}.json"
    if not scenario_file.exists():
        print(f"Scenario '{name}' not found in {SIM_SCENARIOS}")
        print(f"Available: {[f.stem for f in SIM_SCENARIOS.glob('*.json')]}")
        return 1

    with open(scenario_file, "r") as f:
        scenario = json.load(f)

    now = datetime.now(timezone.utc).isoformat()
    checks = scenario.get("checks", [])
    results = []

    for check in checks:
        check_type = check.get("type", "file_exists")
        target = check.get("target", "")
        expected = check.get("expected", True)

        if check_type == "file_exists":
            actual = (PROJECT_ROOT / target).exists()
            passed = actual == expected
        elif check_type == "json_valid":
            try:
                with open(PROJECT_ROOT / target, "r") as f:
                    json.load(f)
                actual = True
            except (FileNotFoundError, json.JSONDecodeError):
                actual = False
            passed = actual == expected
        elif check_type == "contains":
            try:
                content = (PROJECT_ROOT / target).read_text()
                actual = check.get("value", "") in content
            except FileNotFoundError:
                actual = False
            passed = actual == expected
        else:
            actual = None
            passed = False

        results.append({
            "check": check.get("name", check_type),
            "passed": passed,
            "expected": expected,
            "actual": actual,
        })

    all_passed = all(r["passed"] for r in results)
    result = {
        "scenario": name,
        "timestamp": now,
        "passed": all_passed,
        "checks": results,
        "verdict": "GREEN" if all_passed else "RED",
    }

    result_file = SIM_RESULTS / f"{name}-{now.replace(':', '-')}.json"
    with open(result_file, "w") as f:
        json.dump(result, f, indent=2)

    state = load_state()
    state["last_run"] = now
    state["total_runs"] = state.get("total_runs", 0) + 1
    state["last_result"] = result["verdict"]
    save_state(state)

    icon = "✅" if all_passed else "❌"
    print(f"{icon} Scenario '{name}': {result['verdict']}")
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['check']}")

    if not all_passed:
        print("\n⛔ RED IN SIM = FORBIDDEN IN PRODUCTION")

    return 0 if all_passed else 1


def list_scenarios():
    ensure_dirs()
    scenarios = list(SIM_SCENARIOS.glob("*.json"))
    if not scenarios:
        print("No scenarios found. Create JSON files in sim/scenarios/")
        return 0
    print(f"Available scenarios ({len(scenarios)}):")
    for s in scenarios:
        print(f"  - {s.stem}")
    return 0


def show_status():
    state = load_state()
    print(json.dumps(state, indent=2))
    return 0


def reset_sim():
    if SIM_RESULTS.exists():
        shutil.rmtree(SIM_RESULTS)
    SIM_RESULTS.mkdir(parents=True, exist_ok=True)
    save_state({"last_run": None, "total_runs": 0, "last_result": None})
    print("Simulation state reset.")
    return 0


def run_all_scenarios():
    ensure_dirs()
    scenarios = sorted(list(SIM_SCENARIOS.glob("*.json")))
    if not scenarios:
        print("No scenarios found.")
        return 0
    passed = 0
    print(f"Running {len(scenarios)} simulation scenarios...")
    for s in scenarios:
        code = run_scenario(s.stem)
        if code == 0:
            passed += 1
        print("-" * 40)
    print(f"Simulation Summary: {passed}/{len(scenarios)} scenarios passed")
    return 0 if passed == len(scenarios) else 1


COMMANDS = {
    "run": lambda: run_scenario(sys.argv[2]) if len(sys.argv) > 2 else print("Usage: harness.py run <scenario>") or 1,
    "run-all": run_all_scenarios,
    "list": list_scenarios,
    "status": show_status,
    "reset": reset_sim,
}


def main():
    ensure_dirs()
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: {sys.argv[0]} {{run|run-all|list|status|reset}}")
        return 1
    return COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())
