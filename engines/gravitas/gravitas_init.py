"""Project scaffolding for Gravitas host adapters (`gravitas init`).

Copies adapter templates into a project directory without clobbering
existing user configuration: JSON is merged per-key, AGENTS.md is
extended inside idempotent markers, and existing files are never
overwritten (reported as skipped).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

AGENTS_START = "<!-- GRAVITAS-OPENCODE-START"
AGENTS_END = "GRAVITAS-OPENCODE-END -->"


def detect_hosts(root: Path) -> list[str]:
    """Detect configured hosts from project markers (no guessing)."""
    root = Path(root)
    hosts = []
    if ((root / "opencode.json").exists() or (root / "opencode.jsonc").exists()
            or (root / ".opencode").is_dir()):
        hosts.append("opencode")
    if (root / ".agents").is_dir() or (root / "AGENTS.md").exists():
        hosts.append("antigravity")
    return hosts


def detect_ecosystem(root: Path) -> dict:
    """Describe language and discovered validators for init output."""
    try:
        from gravitas_verify import discover_validators
        catalog = discover_validators(Path(root))
        return {"validators": catalog["validators"], "ci": catalog.get("ci", [])}
    except Exception:  # noqa: BLE001 -- discovery is advisory; init must not fail
        return {"validators": [], "ci": []}


def _copy_tree(source: Path, dest: Path, installed: list, skipped: list) -> None:
    if not source.is_dir():
        return
    for item in sorted(source.rglob("*")):
        if item.is_dir():
            continue
        relative = item.relative_to(source)
        target = dest / relative
        if target.exists():
            skipped.append(str(target))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        installed.append(str(target))


def _merge_json(target: Path, fragment: dict, installed: list, skipped: list,
                warnings: list | None = None) -> None:
    current = {}
    if target.exists():
        try:
            current = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            current = None
        if not isinstance(current, dict):
            # Never overwrite a config we cannot parse (comments, trailing
            # commas, non-object root): that would silently destroy user data.
            skipped.append(str(target))
            if warnings is not None:
                warnings.append(f"{target} is not valid JSON; left untouched. "
                                "Merge the Gravitas permission profile manually.")
            return
    changed = False
    for key, value in fragment.items():
        if key not in current:
            current[key] = value
            changed = True
    if not target.exists() or changed:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        installed.append(str(target))
    else:
        skipped.append(str(target))


def _ensure_agents_block(agents_md: Path, snippet: str, installed: list, skipped: list) -> None:
    if agents_md.exists():
        text = agents_md.read_text(encoding="utf-8")
        if AGENTS_START in text:
            skipped.append(str(agents_md))
            return
        text = text.rstrip("\n") + "\n\n" + snippet
    else:
        text = "# Project Instructions\n\n" + snippet
    agents_md.write_text(text, encoding="utf-8")
    installed.append(str(agents_md))


def init_opencode(root: Path, *, profile: str = "balanced", source_root: Path) -> dict:
    """Install OpenCode support into a project directory."""
    root = Path(root).resolve()
    source_root = Path(source_root).resolve()
    adapter = source_root / "adapters" / "opencode"
    installed: list[str] = []
    skipped: list[str] = []
    warnings: list[str] = []

    # Preflight before any mutation: unknown profiles and missing templates
    # fail without leaving a partial scaffold behind.
    profile_path = adapter / "permissions" / f"{profile}.json"
    if not profile_path.exists():
        return {"ok": False, "error": f"unknown profile: {profile}",
                "installed": [], "skipped": [], "warnings": []}
    try:
        fragment = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {"ok": False, "error": f"profile {profile} unreadable: {error}",
                "installed": [], "skipped": [], "warnings": []}
    for required in (adapter / "AGENTS-snippet.md", adapter / "contract-template.json"):
        if not required.exists():
            return {"ok": False, "error": f"adapter template missing: {required.name}",
                    "installed": [], "skipped": [], "warnings": []}

    for skill in ("gravitas", "gravitas-highstakes"):
        skill_src = source_root / "skills" / skill
        if not skill_src.is_dir():
            warnings.append(f"skill source missing: {skill_src}; skipped")
            continue
        _copy_tree(skill_src, root / ".agents" / "skills" / skill,
                   installed, skipped)
    _copy_tree(adapter / "agents", root / ".opencode" / "agents", installed, skipped)
    _copy_tree(adapter / "plugin", root / ".opencode" / "plugins", installed, skipped)

    fragment.pop("$schema", None)
    json_target = root / "opencode.json"
    jsonc_target = root / "opencode.jsonc"
    if not json_target.exists() and jsonc_target.exists():
        # Issue #4: a jsonc-only project must not gain a second opencode.json.
        # Rewriting the .jsonc as strict JSON would strip comments, so leave
        # it untouched and ask the user to merge the profile manually.
        skipped.append(str(jsonc_target))
        warnings.append(
            f"{jsonc_target} exists; left untouched. "
            f"Merge the Gravitas permission profile ({profile}) manually "
            f"from adapters/opencode/permissions/{profile}.json "
            "instead of creating a second opencode.json.")
    else:
        _merge_json(json_target, fragment, installed, skipped, warnings)
        if jsonc_target.exists():
            # Both configs exist: opencode.json is primary; never touch .jsonc.
            if str(jsonc_target) not in skipped:
                skipped.append(str(jsonc_target))
            warnings.append(
                f"{jsonc_target} exists alongside {json_target}; left untouched. "
                "Merge the Gravitas permission profile manually if needed.")

    snippet = (adapter / "AGENTS-snippet.md").read_text(encoding="utf-8")
    _ensure_agents_block(root / "AGENTS.md", snippet, installed, skipped)

    contract_target = root / ".gravitas" / "opencode-contract.json"
    if contract_target.exists():
        skipped.append(str(contract_target))
    else:
        contract_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(adapter / "contract-template.json", contract_target)
        installed.append(str(contract_target))

    # Discovered validators are reported, not auto-bound: binding a
    # validator to acceptance criteria is a task decision, not scaffolding.
    ecosystem = detect_ecosystem(root)
    return {"ok": True, "host": "opencode", "profile": profile,
            "root": str(root), "installed": installed, "skipped": skipped,
            "detected_validators": [v["id"] for v in ecosystem["validators"]],
            "detected_ci": ecosystem["ci"], "warnings": warnings}


def init_antigravity(root: Path, *, source_root: Path) -> dict:
    """Install workspace skills for Antigravity; the Native plugin installs via agy."""
    root = Path(root).resolve()
    source_root = Path(source_root).resolve()
    installed: list[str] = []
    skipped: list[str] = []
    for skill in ("gravitas", "gravitas-highstakes"):
        _copy_tree(source_root / "skills" / skill, root / ".agents" / "skills" / skill,
                   installed, skipped)
    return {"ok": True, "host": "antigravity", "root": str(root),
            "installed": installed, "skipped": skipped,
            "next": "agy plugin install <path-to>/dist/gravitas-antigravity"}
