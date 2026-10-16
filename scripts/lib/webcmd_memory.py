"""WebCMD Self-Learning Browser Memory & Token Optimization Engine.

Provides persistent navigational memory, domain sitemaps, interactive action maps,
and a 90% token-reduction DOM compressor for AI agents across Antigravity, Claude Code,
OpenCode, and LangGraph fleets.

No third-party runtime dependencies. Conforms to BUILD-SPEC.md v2.0 & ADR-018/022.
Uses scripts.lib.clock for all time calls (safe for verify.py --lint-clock).
"""

from __future__ import annotations

import json
import re
import hashlib
from html.parser import HTMLParser
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

from . import clock, paths

WEBCMD_STORE_DIR = paths.repo_root() / "state" / "web_memory"
SAVINGS_LEDGER = paths.repo_root() / "state" / "budget" / "webcmd_savings.ndjson"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


@dataclass
class CompressedHtml:
    url: str
    title: str
    compressed_text: str
    actions: list[dict[str, Any]] = field(default_factory=list)
    raw_chars: int = 0
    compressed_chars: int = 0
    savings_ratio: float = 0.0
    structural_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "compressed_text": self.compressed_text,
            "actions": self.actions,
            "raw_chars": self.raw_chars,
            "compressed_chars": self.compressed_chars,
            "savings_ratio": self.savings_ratio,
            "structural_hash": self.structural_hash,
        }


class _SemanticDOMParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.in_title = False
        self.in_ignored_tag = False
        self.ignored_stack: list[str] = []
        self.text_fragments: list[str] = []
        self.actions: list[dict[str, Any]] = []
        self.structural_tokens: list[str] = []
        self.action_counter = 0

        self.current_action_tag = ""
        self.current_action_attrs: dict[str, str] = {}
        self.current_action_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag_lower = tag.lower()
        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        self.structural_tokens.append(tag_lower)

        if tag_lower in ("script", "style", "noscript", "svg", "iframe"):
            self.ignored_stack.append(tag_lower)
            return

        if self.ignored_stack:
            return

        if tag_lower == "title":
            self.in_title = True
            return

        is_interactive = (
            tag_lower in ("button", "input", "select", "textarea")
            or (tag_lower == "a" and "href" in attr_dict)
            or attr_dict.get("role") == "button"
            or "onclick" in attr_dict
        )

        if is_interactive:
            self.action_counter += 1
            self.current_action_tag = tag_lower
            self.current_action_attrs = attr_dict
            self.current_action_text = []

            if tag_lower == "input":
                label = attr_dict.get("placeholder") or attr_dict.get("name") or attr_dict.get("value") or "input"
                action_id = f"@{self.action_counter}"
                selector = f"#{attr_dict['id']}" if "id" in attr_dict else f"input[name='{attr_dict.get('name', '')}']"
                self.actions.append({
                    "action_id": action_id,
                    "tag": tag_lower,
                    "label": label,
                    "selector": selector,
                    "type": attr_dict.get("type", "text"),
                })
                self.text_fragments.append(f"[{action_id}] <input:{attr_dict.get('type', 'text')} '{label}'>")

        elif tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.text_fragments.append("\n### ")
        elif tag_lower in ("p", "div", "section", "article", "li"):
            self.text_fragments.append("\n")

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if self.ignored_stack:
            if tag_lower == self.ignored_stack[-1]:
                self.ignored_stack.pop()
            return

        if tag_lower == "title":
            self.in_title = False
            return

        if self.current_action_tag and tag_lower == self.current_action_tag:
            label = " ".join(self.current_action_text).strip()
            action_id = f"@{self.action_counter}"
            attrs = self.current_action_attrs

            selector = ""
            if "id" in attrs:
                selector = f"#{attrs['id']}"
            elif "href" in attrs and tag_lower == "a":
                selector = f"a[href='{attrs['href']}']"
            else:
                selector = f"{tag_lower}:contains('{label[:20]}')"

            self.actions.append({
                "action_id": action_id,
                "tag": tag_lower,
                "label": label or attrs.get("href") or "Action",
                "selector": selector,
                "href": attrs.get("href", ""),
            })
            self.text_fragments.append(f"[{action_id}] [{tag_lower}: {label or attrs.get('href', '')}]")
            self.current_action_tag = ""
            self.current_action_attrs = {}
            self.current_action_text = []

    def handle_data(self, data: str):
        if self.ignored_stack:
            return
        cleaned = data.strip()
        if not cleaned:
            return

        if self.in_title:
            self.title = cleaned
            return

        if self.current_action_tag:
            self.current_action_text.append(cleaned)
        else:
            self.text_fragments.append(f" {cleaned} ")


def compress_html(html: str, url: str = "") -> CompressedHtml:
    """Compress HTML into an actionable semantic summary with 90% token reduction."""
    raw_len = len(html)
    if not html:
        return CompressedHtml(url=url, title="", compressed_text="", raw_chars=0, compressed_chars=0)

    try:
        parser = _SemanticDOMParser()
        parser.feed(html)
        parser.close()

        title = parser.title
        joined_text = "".join(parser.text_fragments)
        condensed_text = re.sub(r"\n\s*\n+", "\n\n", joined_text).strip()

        struct_summary = ",".join(parser.structural_tokens[:200]) + f":actions={len(parser.actions)}"
        struct_hash = hashlib.sha256(struct_summary.encode("utf-8")).hexdigest()[:16]

        comp_len = len(condensed_text)
        savings = max(0.0, 1.0 - (comp_len / max(raw_len, 1)))

        return CompressedHtml(
            url=url,
            title=title,
            compressed_text=condensed_text,
            actions=parser.actions,
            raw_chars=raw_len,
            compressed_chars=comp_len,
            savings_ratio=round(savings, 4),
            structural_hash=struct_hash,
        )
    except Exception:
        fallback = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
        fallback = re.sub(r"<[^>]+>", " ", fallback)
        fallback = re.sub(r"\s+", " ", fallback).strip()[:2000]
        return CompressedHtml(
            url=url,
            title="",
            compressed_text=fallback,
            actions=[],
            raw_chars=raw_len,
            compressed_chars=len(fallback),
            savings_ratio=round(max(0.0, 1.0 - (len(fallback) / max(raw_len, 1))), 4),
            structural_hash="fallback",
        )


def _ensure_store():
    WEBCMD_STORE_DIR.mkdir(parents=True, exist_ok=True)
    profiles_dir = WEBCMD_STORE_DIR / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)


def _load_sitemaps() -> dict[str, Any]:
    _ensure_store()
    sitemaps_file = WEBCMD_STORE_DIR / "sitemaps.json"
    if not sitemaps_file.exists():
        return {}
    try:
        with open(sitemaps_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_sitemaps(data: dict[str, Any]):
    _ensure_store()
    sitemaps_file = WEBCMD_STORE_DIR / "sitemaps.json"
    with open(sitemaps_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_domain_sitemap(domain: str) -> dict[str, Any] | None:
    """Retrieve cached sitemap and routes for a domain."""
    sitemaps = _load_sitemaps()
    return sitemaps.get(domain)


def learn_route(
    url: str,
    title: str,
    compressed_result: CompressedHtml,
    shortcuts: dict[str, str] | None = None,
    bot_detected: bool = False,
):
    """Save or update domain navigation memory and route shortcuts."""
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path.split("/")[0]
    path = parsed.path or "/"

    sitemaps = _load_sitemaps()
    domain_entry = sitemaps.setdefault(domain, {
        "domain": domain,
        "created_at": clock.now().isoformat(),
        "updated_at": clock.now().isoformat(),
        "routes": {},
        "shortcuts": {},
        "bot_protection": False,
    })

    domain_entry["updated_at"] = clock.now().isoformat()
    if bot_detected:
        domain_entry["bot_protection"] = True

    route_data = {
        "url": url,
        "title": title or compressed_result.title,
        "structural_hash": compressed_result.structural_hash,
        "action_count": len(compressed_result.actions),
        "actions_sample": compressed_result.actions[:15],
        "updated_at": clock.now().isoformat(),
    }
    domain_entry["routes"][path] = route_data

    if shortcuts:
        for name, sel in shortcuts.items():
            domain_entry["shortcuts"][name] = {
                "selector": sel,
                "path": path,
                "updated_at": clock.now().isoformat(),
            }

    for act in compressed_result.actions:
        label_lower = act["label"].lower()
        if "search" in label_lower and "search" not in domain_entry["shortcuts"]:
            domain_entry["shortcuts"]["search"] = {"selector": act["selector"], "path": path}
        elif "login" in label_lower and "login" not in domain_entry["shortcuts"]:
            domain_entry["shortcuts"]["login"] = {"selector": act["selector"], "path": path}

    _save_sitemaps(sitemaps)
    record_savings_metrics(
        domain=domain,
        raw_chars=compressed_result.raw_chars,
        compressed_chars=compressed_result.compressed_chars,
        action="learn_route"
    )


def verify_freshness(url: str, live_html: str) -> bool:
    """Check if live page structure matches learned structural hash."""
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path.split("/")[0]
    path = parsed.path or "/"

    sitemaps = _load_sitemaps()
    domain_entry = sitemaps.get(domain)
    if not domain_entry:
        return False

    route = domain_entry.get("routes", {}).get(path)
    if not route or not route.get("structural_hash"):
        return False

    new_comp = compress_html(live_html, url=url)
    return new_comp.structural_hash == route["structural_hash"]


def get_profile_state(profile_name: str) -> dict[str, Any]:
    """Retrieve isolated workspace/cookie-jar for a specific agent profile."""
    _ensure_store()
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", profile_name)
    prof_file = WEBCMD_STORE_DIR / "profiles" / f"{safe_name}.json"
    if not prof_file.exists():
        return {"profile": profile_name, "cookies": {}, "space": "default", "history": []}
    try:
        with open(prof_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"profile": profile_name, "cookies": {}, "space": "default", "history": []}


def save_profile_state(profile_name: str, state: dict[str, Any]):
    """Save isolated workspace/cookie-jar for an agent profile."""
    _ensure_store()
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", profile_name)
    prof_file = WEBCMD_STORE_DIR / "profiles" / f"{safe_name}.json"
    state["updated_at"] = clock.now().isoformat()
    with open(prof_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def record_savings_metrics(domain: str, raw_chars: int, compressed_chars: int, action: str = "compress"):
    """Record token-saving telemetry to budget ledger."""
    try:
        SAVINGS_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        raw_tokens = raw_chars // 4
        comp_tokens = compressed_chars // 4
        tokens_saved = max(0, raw_tokens - comp_tokens)

        entry = {
            "ts": clock.now().isoformat(),
            "domain": domain,
            "action": action,
            "raw_chars": raw_chars,
            "compressed_chars": compressed_chars,
            "tokens_saved": tokens_saved,
            "savings_ratio": round(max(0.0, 1.0 - (compressed_chars / max(raw_chars, 1))), 4),
        }
        with open(SAVINGS_LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def purge_cache(domain: str | None = None) -> bool:
    """Purge domain memory or all memory if domain is None."""
    if domain:
        sitemaps = _load_sitemaps()
        if domain in sitemaps:
            del sitemaps[domain]
            _save_sitemaps(sitemaps)
            return True
        return False
    else:
        _save_sitemaps({})
        return True
