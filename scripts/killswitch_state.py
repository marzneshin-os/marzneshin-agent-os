"""Fail-closed kill-switch state parsing shared by automation entry points."""
import json
from pathlib import Path


RUNNING = "running"
PAUSED = "paused"
STOPPED = "stopped"
_MISSING = object()
_INVALID = object()
_VERDICTS = {RUNNING, PAUSED, STOPPED}


def _read_object(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as source:
            value = json.load(source)
    except FileNotFoundError:
        return _MISSING
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _INVALID
    return value if isinstance(value, dict) else _INVALID


def _validated_verdict(value):
    return value if isinstance(value, str) and value in _VERDICTS else STOPPED


def read_verdict(killswitch_file: Path, state_file: Path) -> str:
    """Return running, paused, or stopped; malformed or absent state stops."""
    killswitch = _read_object(Path(killswitch_file))
    if killswitch is not _MISSING:
        if killswitch is _INVALID:
            return STOPPED
        return _validated_verdict(killswitch.get("verdict"))

    state = _read_object(Path(state_file))
    if state is _MISSING or state is _INVALID:
        return STOPPED
    section = state.get("kill_switch")
    if not isinstance(section, dict):
        return STOPPED
    return _validated_verdict(section.get("verdict"))
