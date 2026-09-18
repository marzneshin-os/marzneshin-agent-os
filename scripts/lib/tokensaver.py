"""Token-saving filters for LLM gateway requests (9Router RTK port).

Three layers, each independently bypassable:

  1. **RTK** — compress tool_result content in-place. Auto-detects the tool
     output format from the first 1024 chars and applies the matching filter:
     git-diff, git-status, grep, find, ls, tree, dedup-log, smart-truncate.
     Every filter is wrapped in try/except: if it errors OR the output grows,
     the original text is returned unchanged (fail-open, never break a request).

  2. **Caveman** — injects a terseness instruction into the system prompt.
     Three intensity levels: lite (drop filler), full (fragments OK), ultra
     (telegraphic). Applied by appending to the first system/developer message.

  3. **Ponytail** — YAGNI ladder: injects a scope-narrowing instruction that
     tells the model to skip elaboration the user did not ask for. Hardcoded
     red-lines that are NEVER suppressed: input validation, data-loss prevention,
     security warnings, accessibility.

All three are optional, configured via configs/router.json, and can be
bypassed per-request with header X-9Router-Token-Saver: off.

No network I/O. No third-party imports. Safe for lint-imports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Constants (ported from 9Router open-sse/rtk/constants.js)
# ---------------------------------------------------------------------------

RAW_CAP = 10 * 1024 * 1024        # 10 MiB absolute cap
DETECT_WINDOW = 1024              # autodetect peeks first N chars
GIT_DIFF_HUNK_MAX_LINES = 100
GIT_DIFF_CONTEXT_KEEP = 3
GIT_LOG_MAX_LINES = 200
DEDUP_LINE_MAX = 2000
SMART_TRUNCATE_HEAD = 120
SMART_TRUNCATE_TAIL = 60
SMART_TRUNCATE_MIN_LINES = 250

GREP_PER_FILE_MAX = 10
FIND_PER_DIR_MAX = 10
FIND_TOTAL_DIR_MAX = 20
STATUS_MAX_FILES = 10
STATUS_MAX_UNTRACKED = 10
LS_EXT_SUMMARY_TOP = 5
TREE_MAX_LINES = 200
SEARCH_LIST_PER_DIR_MAX = 10
SEARCH_LIST_TOTAL_DIR_MAX = 20


# ---------------------------------------------------------------------------
# Autodetect: peek at first DETECT_WINDOW chars -> filter name
# ---------------------------------------------------------------------------

_DIFF_PAT = re.compile(r'^diff --git |^--- a/|^\+\+\+ b/', re.MULTILINE)
_STATUS_PAT = re.compile(r'^[MADRCU?! ]{1,2} ', re.MULTILINE)
_GREP_PAT = re.compile(r'^[^\s:]+:\d+:', re.MULTILINE)
_FIND_PAT = re.compile(r'^(\./|/)', re.MULTILINE)
_LS_PAT = re.compile(r'^total \d+', re.MULTILINE)
_TREE_PAT = re.compile(r'^[│├└─ ]+', re.MULTILINE)
_LOG_PAT = re.compile(r'^commit [0-9a-f]{7,40}', re.MULTILINE)


def autodetect(text: str) -> str | None:
    """Peek at the first DETECT_WINDOW chars and return the filter name, or None."""
    window = text[:DETECT_WINDOW]
    if _DIFF_PAT.search(window):
        return "git-diff"
    if _LOG_PAT.search(window):
        return "git-log"
    if _STATUS_PAT.search(window) and len(window.splitlines()) < 50:
        return "git-status"
    if _GREP_PAT.search(window):
        return "grep"
    if _TREE_PAT.search(window):
        return "tree"
    if _LS_PAT.search(window):
        return "ls"
    if _FIND_PAT.search(window):
        return "find"
    lines = window.splitlines()
    if len(lines) > SMART_TRUNCATE_MIN_LINES:
        return "smart-truncate"
    return None


# ---------------------------------------------------------------------------
# Individual filters (each must NEVER raise; caller wraps in try/except too)
# ---------------------------------------------------------------------------

def _filter_git_diff(text: str) -> str:
    """Keep diff headers + limited context around changes."""
    lines = text.splitlines()
    out: list[str] = []
    in_hunk = False
    hunk_lines = 0
    for line in lines:
        if line.startswith("diff --git ") or line.startswith("--- ") or line.startswith("+++ "):
            out.append(line)
            in_hunk = False
            hunk_lines = 0
        elif line.startswith("@@"):
            out.append(line)
            in_hunk = True
            hunk_lines = 0
        elif in_hunk:
            hunk_lines += 1
            if hunk_lines <= GIT_DIFF_HUNK_MAX_LINES:
                out.append(line)
            elif hunk_lines == GIT_DIFF_HUNK_MAX_LINES + 1:
                out.append(f"... [{len(lines) - len(out)} more lines truncated]")
        else:
            out.append(line)
    return "\n".join(out)


def _filter_git_status(text: str) -> str:
    """Cap status output."""
    lines = text.splitlines()
    tracked = [l for l in lines if not l.startswith("??")]
    untracked = [l for l in lines if l.startswith("??")]
    result = tracked[:STATUS_MAX_FILES]
    if len(tracked) > STATUS_MAX_FILES:
        result.append(f"... [{len(tracked) - STATUS_MAX_FILES} more tracked files]")
    result.extend(untracked[:STATUS_MAX_UNTRACKED])
    if len(untracked) > STATUS_MAX_UNTRACKED:
        result.append(f"... [{len(untracked) - STATUS_MAX_UNTRACKED} more untracked files]")
    return "\n".join(result)


def _filter_git_log(text: str) -> str:
    """Truncate git log output."""
    lines = text.splitlines()
    if len(lines) <= GIT_LOG_MAX_LINES:
        return text
    return "\n".join(lines[:GIT_LOG_MAX_LINES]) + f"\n... [{len(lines) - GIT_LOG_MAX_LINES} more lines]"


def _filter_grep(text: str) -> str:
    """Limit matches per file."""
    lines = text.splitlines()
    out: list[str] = []
    file_counts: dict[str, int] = {}
    for line in lines:
        colon = line.find(":")
        if colon > 0:
            fname = line[:colon]
            file_counts[fname] = file_counts.get(fname, 0) + 1
            if file_counts[fname] <= GREP_PER_FILE_MAX:
                out.append(line)
            elif file_counts[fname] == GREP_PER_FILE_MAX + 1:
                out.append(f"  ... [more matches in {fname}]")
        else:
            out.append(line)
    return "\n".join(out)


def _filter_find(text: str) -> str:
    """Limit files per directory."""
    lines = text.splitlines()
    cap = FIND_PER_DIR_MAX * FIND_TOTAL_DIR_MAX
    if len(lines) <= cap:
        return text
    return "\n".join(lines[:cap]) + f"\n... [{len(lines) - cap} more entries]"


def _filter_tree(text: str) -> str:
    """Truncate tree output."""
    lines = text.splitlines()
    if len(lines) <= TREE_MAX_LINES:
        return text
    return "\n".join(lines[:TREE_MAX_LINES]) + f"\n... [{len(lines) - TREE_MAX_LINES} more lines]"


def _filter_ls(text: str) -> str:
    """Keep ls compact."""
    lines = text.splitlines()
    if len(lines) <= 100:
        return text
    return "\n".join(lines[:100]) + f"\n... [{len(lines) - 100} more entries]"


def _filter_smart_truncate(text: str) -> str:
    """Keep head + tail, elide middle."""
    lines = text.splitlines()
    if len(lines) <= SMART_TRUNCATE_MIN_LINES:
        return text
    head = lines[:SMART_TRUNCATE_HEAD]
    tail = lines[-SMART_TRUNCATE_TAIL:]
    elided = len(lines) - SMART_TRUNCATE_HEAD - SMART_TRUNCATE_TAIL
    return "\n".join(head) + f"\n\n... [{elided} lines elided]\n\n" + "\n".join(tail)


def _filter_dedup_log(text: str) -> str:
    """Deduplicate repeated consecutive lines."""
    lines = text.splitlines()
    if len(lines) <= DEDUP_LINE_MAX:
        return text
    out: list[str] = []
    prev = None
    repeat = 0
    for line in lines[:DEDUP_LINE_MAX]:
        if line == prev:
            repeat += 1
        else:
            if repeat > 0:
                out.append(f"  ... [repeated {repeat} more times]")
            out.append(line)
            prev = line
            repeat = 0
    if repeat > 0:
        out.append(f"  ... [repeated {repeat} more times]")
    if len(lines) > DEDUP_LINE_MAX:
        out.append(f"... [{len(lines) - DEDUP_LINE_MAX} more lines]")
    return "\n".join(out)


_FILTERS: dict[str, Any] = {
    "git-diff": _filter_git_diff,
    "git-status": _filter_git_status,
    "git-log": _filter_git_log,
    "grep": _filter_grep,
    "find": _filter_find,
    "tree": _filter_tree,
    "ls": _filter_ls,
    "smart-truncate": _filter_smart_truncate,
    "dedup-log": _filter_dedup_log,
}


# ---------------------------------------------------------------------------
# RTK: compress tool_result content
# ---------------------------------------------------------------------------

def compress_tool_result(text: str) -> tuple[str, str | None]:
    """Apply the best-matching filter. Returns (result, filter_name).

    Fail-safe: if the filter errors OR the output is larger, return the
    original text unchanged.
    """
    if not text or len(text) < 200:
        return text, None
    if len(text) > RAW_CAP:
        truncated = text[:RAW_CAP] + f"\n... [truncated at {RAW_CAP} bytes]"
        return truncated, "raw-cap"
    name = autodetect(text)
    if name is None:
        if len(text.splitlines()) > SMART_TRUNCATE_MIN_LINES:
            name = "smart-truncate"
        else:
            return text, None
    fn = _FILTERS.get(name)
    if fn is None:
        return text, None
    try:
        result = fn(text)
        if len(result) >= len(text):
            return text, None
        return result, name
    except Exception:
        return text, None


# ---------------------------------------------------------------------------
# Caveman: system prompt injection for terseness
# ---------------------------------------------------------------------------

CAVEMAN_LEVELS = ("lite", "full", "ultra")

_SHARED_BOUNDARIES = (
    "Code blocks, file paths, commands, errors, URLs: keep exact. "
    "Security warnings, irreversible action confirmations, "
    "multi-step ordered sequences: write normal. Resume terse style after."
)

_SHARED_NO_DECORATION = (
    'No decorative emoji. No narrating tool calls. '
    'No status phrases ("Sure!", "Of course!"). '
    'State the thing, the action, the reason. Then next step.'
)

CAVEMAN_PROMPTS: dict[str, str] = {
    "lite": (
        "Respond tersely. Keep grammar and full sentences but drop filler, "
        "hedging and pleasantries (just/really/basically/sure/of course). "
        f"{_SHARED_BOUNDARIES} {_SHARED_NO_DECORATION}"
    ),
    "full": (
        "Respond like terse caveman. All technical substance stays exact, "
        "only fluff dies. Drop: articles (a/an/the), filler, pleasantries, "
        f"hedging. Fragments OK. {_SHARED_BOUNDARIES} {_SHARED_NO_DECORATION}"
    ),
    "ultra": (
        "Respond ultra-terse. Maximum compression. Telegraphic. "
        "Strip conjunctions. One word when one word enough. "
        f"{_SHARED_BOUNDARIES} {_SHARED_NO_DECORATION}"
    ),
}


# ---------------------------------------------------------------------------
# Ponytail: YAGNI scope-narrowing with hardcoded red-lines
# ---------------------------------------------------------------------------

PONYTAIL_RED_LINES = (
    "NEVER suppress: input validation, data-loss prevention warnings, "
    "security advisories, accessibility requirements, license/legal notices, "
    "irreversible-action confirmations."
)

PONYTAIL_PROMPT = (
    "Answer only what was asked. Skip unrequested elaboration, caveats the "
    "user did not ask for, and alternative approaches unless directly "
    f"relevant. {PONYTAIL_RED_LINES}"
)


# ---------------------------------------------------------------------------
# System prompt injection (format-aware)
# ---------------------------------------------------------------------------

def inject_system_prompt(body: dict, prompt: str) -> None:
    """Append a prompt to the system message in an OpenAI-shaped request body.

    Handles: messages[] (chat completions) and instructions (responses API).
    Does NOT handle Claude/Gemini native formats — those go through the
    gateway's translator, not through this library.
    """
    if not body or not prompt:
        return
    if isinstance(body.get("instructions"), str):
        body["instructions"] = f'{body["instructions"]}\n\n{prompt}'
        return
    arr = body.get("messages") or body.get("input")
    if not isinstance(arr, list):
        return
    for msg in arr:
        if isinstance(msg, dict) and msg.get("role") in ("system", "developer"):
            if isinstance(msg.get("content"), str):
                msg["content"] = f'{msg["content"]}\n\n{prompt}'
            elif isinstance(msg.get("content"), list):
                msg["content"].append({"type": "text", "text": prompt})
            else:
                msg["content"] = prompt
            return
    arr.insert(0, {"role": "system", "content": prompt})


# ---------------------------------------------------------------------------
# apply_token_saver: the main entry point
# ---------------------------------------------------------------------------

@dataclass
class TokenSaverResult:
    """Metrics from a single pass of the token saver."""
    rtk_filter: str | None = None
    rtk_original_len: int = 0
    rtk_compressed_len: int = 0
    caveman_level: str | None = None
    ponytail_applied: bool = False

    @property
    def rtk_savings_ratio(self) -> float:
        if self.rtk_original_len == 0:
            return 0.0
        return 1.0 - (self.rtk_compressed_len / self.rtk_original_len)

    def to_dict(self) -> dict:
        return {
            "rtk_filter": self.rtk_filter,
            "rtk_savings_ratio": round(self.rtk_savings_ratio, 3),
            "caveman_level": self.caveman_level,
            "ponytail_applied": self.ponytail_applied,
        }


def apply_token_saver(
    body: dict,
    *,
    rtk_enabled: bool = True,
    caveman_level: str | None = None,
    ponytail_enabled: bool = False,
) -> TokenSaverResult:
    """Apply RTK compression + Caveman + Ponytail to an OpenAI-shaped body.

    Mutates ``body`` in place. Returns metrics for receipt logging.
    """
    result = TokenSaverResult()

    if rtk_enabled:
        messages = body.get("messages") or body.get("input") or []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") != "tool":
                continue
            content = msg.get("content")
            if isinstance(content, str) and len(content) > 200:
                original_len = len(content)
                compressed, filter_name = compress_tool_result(content)
                if filter_name:
                    msg["content"] = compressed
                    result.rtk_filter = filter_name
                    result.rtk_original_len += original_len
                    result.rtk_compressed_len += len(compressed)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text = part.get("text", "")
                        if len(text) > 200:
                            original_len = len(text)
                            compressed, filter_name = compress_tool_result(text)
                            if filter_name:
                                part["text"] = compressed
                                result.rtk_filter = filter_name
                                result.rtk_original_len += original_len
                                result.rtk_compressed_len += len(compressed)

    if caveman_level and caveman_level in CAVEMAN_PROMPTS:
        inject_system_prompt(body, CAVEMAN_PROMPTS[caveman_level])
        result.caveman_level = caveman_level

    if ponytail_enabled:
        inject_system_prompt(body, PONYTAIL_PROMPT)
        result.ponytail_applied = True

    return result


def measure(original_body: dict, compressed_body: dict) -> dict:
    """Compare two request bodies and return savings metrics."""
    import json
    orig_len = len(json.dumps(original_body, ensure_ascii=False))
    comp_len = len(json.dumps(compressed_body, ensure_ascii=False))
    return {
        "original_bytes": orig_len,
        "compressed_bytes": comp_len,
        "saved_bytes": orig_len - comp_len,
        "savings_ratio": round(1.0 - comp_len / orig_len, 3) if orig_len > 0 else 0.0,
    }
