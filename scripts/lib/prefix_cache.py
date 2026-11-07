#!/usr/bin/env python3
"""scripts/lib/prefix_cache.py
Deterministic Prompt Prefix Stratification & KV-Cache Adapter for Marzneshin-Agent-OS.
Strictly Python stdlib-only (CLAUDE.md §5 / BUILD-SPEC §2.2). Zero external dependencies.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CACHE_BREAKPOINT_MARKER = "<!-- MARZNESHIN_KV_CACHE_BREAKPOINT_V1 -->"


def canonical_json(data: Any) -> str:
    """Serializes data to a byte-for-byte deterministic JSON string.

    Prevents dict key-ordering drift from invalidating LLM KV cache blocks.
    """
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def strip_volatile_fields(
    payload: Dict[str, Any],
    volatile_keys: Tuple[str, ...] = (
        "generated_at",
        "timestamp",
        "updated_at",
        "heartbeat_at",
        "last_seen",
    ),
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Separates a dictionary into (static_dict, volatile_dict) without mutating the input.

    Ensures timestamps never pollute the static prefix.
    """
    static_part: Dict[str, Any] = {}
    volatile_part: Dict[str, Any] = {}
    for k, v in sorted(payload.items()):
        if k in volatile_keys:
            volatile_part[k] = v
        elif isinstance(v, dict):
            s_sub, v_sub = strip_volatile_fields(v, volatile_keys)
            static_part[k] = s_sub
            if v_sub:
                volatile_part[k] = v_sub
        else:
            static_part[k] = v
    return static_part, volatile_part


@dataclass(frozen=True)
class PrefixEnvelope:
    """Immutable 4-Tier Prompt Prefix Envelope.

    Tiers 0, 1, and 2 form the cacheable static prefix. Tier 3 is the uncached
    dynamic tail (always evaluated fresh for fail-closed safety).
    """

    tier0_os_kernel: str  # CLAUDE.md + BUILD-SPEC.md (§0, §16, §17) + schemas
    tier1_agent_persona: str  # agents/cards + agents/policies + .agents/skills index
    tier2_session_snapshot: str  # Static ADR summaries + TRADEOFF-REGISTER.md + GAP-REPORT
    tier3_dynamic_tail: str  # KillSwitch status + STATE.json + HANDOFF.md + Task input
    prefix_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        combined_static = "\n\n".join(
            [
                self.tier0_os_kernel.strip(),
                self.tier1_agent_persona.strip(),
                self.tier2_session_snapshot.strip(),
            ]
        )
        digest = hashlib.sha256(combined_static.encode("utf-8")).hexdigest()
        object.__setattr__(self, "prefix_sha256", digest)

    @property
    def static_prefix(self) -> str:
        return "\n\n".join(
            [
                self.tier0_os_kernel.strip(),
                self.tier1_agent_persona.strip(),
                self.tier2_session_snapshot.strip(),
            ]
        )

    def render_markdown(self) -> str:
        """Renders full context with explicit breakpoint marker for CONTEXT-PACK.md."""
        return (
            f"{self.static_prefix}\n\n"
            f"{CACHE_BREAKPOINT_MARKER}\n\n"
            f"{self.tier3_dynamic_tail.strip()}\n"
        )

    def to_anthropic_messages(self, user_prompt: str) -> Dict[str, Any]:
        """Formats payload for Anthropic Claude API.

        Places cache_control={'type': 'ephemeral'} on the last static block
        exactly as demonstrated in the benchmark reference.
        """
        return {
            "system": [
                {
                    "type": "text",
                    "text": self.tier0_os_kernel.strip(),
                },
                {
                    "type": "text",
                    "text": f"{self.tier1_agent_persona.strip()}\n\n{self.tier2_session_snapshot.strip()}",
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            "messages": [
                {
                    "role": "user",
                    "content": f"{self.tier3_dynamic_tail.strip()}\n\n{user_prompt.strip()}",
                }
            ],
        }

    def to_openai_or_vllm_messages(
        self, user_prompt: str, model: str = "Qwen/Qwen2.5-Coder-7B-Instruct"
    ) -> Dict[str, Any]:
        """Formats payload for OpenAI API, SGLang, or vLLM OpenAI-compatible server.

        Places 100% of static content in the leading system message to maximize
        RadixTree / Automatic Prefix Caching hits.
        """
        return {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": self.static_prefix,
                },
                {
                    "role": "user",
                    "content": f"{self.tier3_dynamic_tail.strip()}\n\n{user_prompt.strip()}",
                },
            ],
        }


def extract_cache_telemetry(provider: str, response_usage: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts cached_tokens from response usage (e.g. input_tokens_details.cached_tokens)

    for logging into state/budget/ and task receipts.
    """
    input_tokens = int(
        response_usage.get("prompt_tokens") or response_usage.get("input_tokens") or 0
    )
    cached_tokens = 0

    details = response_usage.get("input_tokens_details")
    if isinstance(details, dict) and "cached_tokens" in details:
        cached_tokens = int(details["cached_tokens"] or 0)
    elif "cached_tokens" in response_usage:
        cached_tokens = int(response_usage.get("cached_tokens") or 0)

    hit_ratio = round(cached_tokens / input_tokens, 4) if input_tokens > 0 else 0.0
    return {
        "provider": provider,
        "total_input_tokens": input_tokens,
        "cached_input_tokens": cached_tokens,
        "uncached_input_tokens": max(0, input_tokens - cached_tokens),
        "prefix_cache_hit_ratio": hit_ratio,
    }

