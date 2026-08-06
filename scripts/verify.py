#!/usr/bin/env python3
"""verify.py — the CI gate for every machine-checkable invariant.

One tool, one exit code. What fails here fails the build (BUILD-SPEC §16.1):

    --chain        receipt hash chain per workstream (I15); --repair-head only
                   rebuilds the head *pointer*, never the receipts themselves
    --events       actor_seq gap/duplicate scan over the event log (§3.2)
    --schemas      strict Draft 2020-12 validation of every persisted artifact
                   (STATE, receipts, leases, agent cards) + schema sanity
    --agent-cards  cross-card CI rules from §3.4/§10.4 (I13, owns overlap)
    --lint-imports lib import discipline: acyclic, stdlib+lib only (no network
                   imports, or hooks cannot stay inside the 3s budget — G9)
    --lint-clock   no wall-clock calls outside lib/clock.py (D6: virtual time
                   only works if nothing bypasses it)
    --all          everything above

Exit codes: 0 = green, 1 = a check failed, 2 = the verifier itself could not
establish state (fail closed — a gate that cannot run is a red gate).
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import clock, events, paths, receipts, state, validate  # noqa: E402
from lib.atomic import read_json  # noqa: E402

LIB_DIR = Path(__file__).resolve().parent / "lib"
CODE_ROOT = Path(__file__).resolve().parent.parent  # the tree being linted


def _repo() -> Path:
    """Artifact root: honour MARZNESHIN_OPS_ROOT like every lib module does."""
    return paths.repo_root()


# --- chain -----------------------------------------------------------------

def cmd_chain(args) -> dict:
    if args.repair_head:
        targets = [args.workstream] if args.workstream else [
            r.get("workstream") for r in receipts.list_all() if "_unreadable" not in r
        ]
        valid_targets = {str(ws) for ws in targets if ws}
        repairs = [receipts.repair_head(ws) for ws in sorted(valid_targets)]
    else:
        repairs = []
    report = receipts.verify_chain(workstream=args.workstream)
    return {"check": "chain", "ok": report["ok"], "repairs": repairs, "report": report}


# --- events ----------------------------------------------------------------

def cmd_events(args) -> dict:
    from datetime import timedelta
    end = clock.now().date()
    start = end - timedelta(days=args.days)
    gaps = events.detect_gaps(start, end, world="prod")
    # Transparency, not silence: report what the registry explains (ADR-006)
    # alongside what still fails. ok is decided by the UNEXPLAINED list only.
    raw = events.detect_gaps(start, end, world="prod", honor_registry=False)
    registered = events.list_anomalies(world="prod")
    return {"check": "events", "ok": not gaps,
            "range": [start.isoformat(), end.isoformat()], "gaps": gaps,
            "registered_anomalies": len(registered),
            "raw_gaps_before_registry": raw}


# --- schemas ---------------------------------------------------------------

def _iter_artifact_files() -> list[tuple[str, Path]]:
    """Every persisted artifact that has a schema, as (schema_name, path)."""
    pairs: list[tuple[str, Path]] = []
    if paths.state_file().exists():
        pairs.append(("state", paths.state_file()))
    receipts_root = _repo() / "receipts"
    if receipts_root.exists():
        for f in sorted(receipts_root.rglob("*.json")):
            if f.parent.name != "_chain":
                pairs.append(("receipt", f))
    if paths.locks_dir().exists():
        for f in sorted(paths.locks_dir().glob("*.lock.json")):
            pairs.append(("lease", f))
    if paths.agent_cards_dir().exists():
        for f in sorted(paths.agent_cards_dir().glob("*.json")):
            pairs.append(("agent-card", f))
    a2a_root = paths.state_dir() / "a2a"
    if a2a_root.exists():
        # inbox carries raw envelopes; outbox/processed carry result records
        # (ADR-005 D32). idem/, t2/ and transport_health.json are internal bus
        # runtime state — like events/ and budget/, they are not artifacts.
        for f in sorted((a2a_root / "inbox").rglob("*.json")) if (a2a_root / "inbox").exists() else []:
            pairs.append(("a2a-envelope", f))
        for sub in ("outbox", "processed"):
            d = a2a_root / sub
            if d.exists():
                for f in sorted(d.rglob("*.json")):
                    pairs.append(("a2a-result", f))
    return pairs


def cmd_schemas(args) -> dict:
    problems: list[str] = []
    checked = 0

    # The schemas themselves must be valid Draft 2020-12.
    try:
        import jsonschema  # noqa: F401 — strict mode requires it by design
        import jsonschema.validators
    except ImportError:
        return {"check": "schemas", "ok": False,
                "problems": ["jsonschema package is not installed; strict validation "
                             "cannot run (validate.py refuses to degrade silently)"]}
    for schema_path in sorted(paths.schemas_dir().glob("*.schema.json")):
        try:
            schema = read_json(schema_path, default=None)
            cls = jsonschema.validators.validator_for(schema)
            cls.check_schema(schema)
            checked += 1
        except Exception as exc:
            problems.append(f"{paths.rel(schema_path)}: invalid schema: {exc}")

    migrations = validate.load_migrations()
    validate.clear_cache()

    for name, artifact in _iter_artifact_files():
        try:
            obj = read_json(artifact, default=None)
            result = validate.validate(obj, name, strict=True)
            checked += 1
            if not result.ok:
                problems.append(f"{paths.rel(artifact)}: " + "; ".join(result.errors[:3]))
        except Exception as exc:
            problems.append(f"{paths.rel(artifact)}: {type(exc).__name__}: {exc}")

    return {"check": "schemas", "ok": not problems, "artifacts_checked": checked,
            "migrations_loaded": migrations, "problems": problems}


# --- agent cards (cross-card CI rules, §3.4/§10.4) --------------------------

def cmd_agent_cards(args) -> dict:
    problems: list[str] = []
    cards: list[dict] = []
    cards_dir = paths.agent_cards_dir()
    if cards_dir.exists():
        import yaml  # local import: only this command needs it
        for f in sorted(cards_dir.glob("*.yaml")) + sorted(cards_dir.glob("*.yml")):
            try:
                cards.append(yaml.safe_load(f.read_text(encoding="utf-8")) | {"_file": f.name})
            except Exception as exc:
                problems.append(f"{f.name}: unreadable YAML: {exc}")

    seen_owns: dict[str, str] = {}
    for card in cards:
        cid = card.get("id", card.get("_file", "?"))
        if not card.get("counter_kpi"):
            problems.append(f"{cid}: counter_kpi is empty (I13)")
        if card.get("counter_kpi_owner") == cid:
            problems.append(f"{cid}: counter_kpi_owner == id — an agent cannot guard "
                            f"the metric it is incentivised to game (I13)")
        if not card.get("sim_scenarios_required"):
            problems.append(f"{cid}: sim_scenarios_required is empty (§3.4)")
        for pattern in card.get("owns", []):
            owner = seen_owns.get(pattern)
            if owner and owner != cid:
                problems.append(f"{cid}: owns pattern {pattern!r} overlaps with {owner} (I17)")
            seen_owns[pattern] = cid
        # Idempotency must be defined for every mutating capability.
        idem = card.get("idempotency", {}) or {}
        for cap in card.get("capabilities", []):
            if cap.split(".")[0] in {"read", "analytics"}:
                continue
            if cap not in idem:
                problems.append(f"{cid}: mutating capability {cap!r} has no idempotency "
                                f"class (§3.5)")
    return {"check": "agent-cards", "ok": not problems, "cards": len(cards),
            "problems": problems}


# --- lint: imports ----------------------------------------------------------

_STDLIB = set(sys.stdlib_module_names)


def _lib_imports(path: Path) -> set[str]:
    """Module names a lib file imports AT MODULE LEVEL.

    Function-level imports are deliberately exempt: validate.py imports
    `jsonschema` lazily inside the strict branch so hooks never pay the cost
    (G9). A module-level third-party import would defeat that.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in tree.body:  # top-level statements only
        if isinstance(node, ast.ImportFrom):
            if node.level:  # relative: from . import x / from .x import y
                if node.module:
                    found.add(node.module.split(".")[0])
                for alias in node.names:
                    if not node.module:
                        found.add(alias.name)
            elif node.module:
                found.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
    return found


def cmd_lint_imports(args) -> dict:
    problems: list[str] = []
    graph: dict[str, set[str]] = {}
    lib_modules = {f.stem for f in LIB_DIR.glob("*.py")}

    for f in sorted(LIB_DIR.glob("*.py")):
        if f.stem == "__init__":
            continue
        imports = _lib_imports(f)
        internal = imports & lib_modules - {f.stem}
        graph[f.stem] = internal
        external = imports - lib_modules - _STDLIB
        if external:
            problems.append(
                f"lib/{f.name}: third-party imports {sorted(external)} — lib must stay "
                f"stdlib-only so hooks never pay import or network cost (G9)"
            )

    # Cycle check via iterative topological peel.
    remaining = {m: set(deps) for m, deps in graph.items()}
    while remaining:
        free = [m for m, deps in remaining.items() if not deps & set(remaining)]
        if not free:
            problems.append(f"lib import cycle among: {sorted(remaining)}")
            break
        for m in free:
            del remaining[m]

    return {"check": "lint-imports", "ok": not problems,
            "graph": {m: sorted(d) for m, d in sorted(graph.items())},
            "problems": problems}


# --- lint: clock ------------------------------------------------------------

_BANNED_CLOCK = (
    re.compile(r"\bdatetime\.now\("),
    re.compile(r"\btime\.time\("),
    re.compile(r"\btime\.sleep\("),
    re.compile(r"\bdate\.today\("),
    re.compile(r"\brandom\.(Random|random|seed|getrandbits|uniform|randint|choice)\("),
)
_LINT_CLOCK_DIRS = ("scripts", "hooks", "sim", "adapters")
_CLOCK_EXEMPT_FILES = {("scripts", "lib", "clock.py")}


def cmd_lint_clock(args) -> dict:
    problems: list[str] = []
    scanned = 0
    for dirname in _LINT_CLOCK_DIRS:
        root = CODE_ROOT / dirname
        if not root.exists():
            continue
        for f in sorted(root.rglob("*.py")):
            rel_parts = f.relative_to(CODE_ROOT).parts
            if rel_parts in _CLOCK_EXEMPT_FILES or "test" in f.stem:
                continue
            scanned += 1
            for lineno, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if "clock-ok" in line:
                    continue  # deliberate, justified inline (see paths._resolve_day)
                for pattern in _BANNED_CLOCK:
                    if pattern.search(line):
                        problems.append(
                            f"{paths.rel(f)}:{lineno}: wall-clock call {line.strip()[:60]!r} "
                            f"— route through lib/clock so sim time works (D6)"
                        )
    return {"check": "lint-clock", "ok": not problems, "files_scanned": scanned,
            "problems": problems}


# --- driver ----------------------------------------------------------------

CHECKS = {
    "chain": cmd_chain,
    "events": cmd_events,
    "schemas": cmd_schemas,
    "agent-cards": cmd_agent_cards,
    "lint-imports": cmd_lint_imports,
    "lint-clock": cmd_lint_clock,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="verify.py",
                                     description="CI gate for machine-checkable invariants")
    for name in CHECKS:
        parser.add_argument(f"--{name}", action="store_true")
    parser.add_argument("--all", action="store_true", help="run every check")
    parser.add_argument("--workstream", help="scope --chain to one workstream")
    parser.add_argument("--repair-head", action="store_true",
                        help="with --chain: rebuild head pointers from receipts on disk first")
    parser.add_argument("--days", type=int, default=7, help="--events lookback window")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    selected = [name for name in CHECKS if getattr(args, name.replace("-", "_"))]
    if args.all or not selected:
        selected = list(CHECKS)

    results: list[dict] = []
    for name in selected:
        try:
            results.append(CHECKS[name](args))
        except Exception as exc:
            results.append({"check": name, "ok": False,
                            "problems": [f"verifier crashed: {type(exc).__name__}: {exc}"]})

    ok = all(r["ok"] for r in results)
    if args.json:
        print(json.dumps({"ok": ok, "results": results}, indent=2,
                         ensure_ascii=False, default=str))
    else:
        for r in results:
            mark = "PASS" if r["ok"] else "FAIL"
            extra = ""
            if r["check"] == "chain" and "report" in r:
                extra = f" ({len(r['report'].get('workstreams', {}))} workstream(s))"
            if r["check"] == "schemas":
                extra = f" ({r.get('artifacts_checked', 0)} artifacts)"
            print(f"[{mark}] {r['check']}{extra}")
            detail = list(r.get("problems", []))
            if r["check"] == "chain":
                for ws in r.get("report", {}).get("workstreams", {}).values():
                    detail.extend(ws.get("problems", []))
            for p in detail[:10]:
                print(f"        - {p}")
        print(f"\nverify: {'GREEN' if ok else 'RED'} ({len(results)} checks)")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"verify: cannot establish state: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
