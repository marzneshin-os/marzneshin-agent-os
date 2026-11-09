#!/usr/bin/env python3
"""Local Dual-Protocol WAF-Compliant Gateway for AgentRouter (ADR-033).

Provides local routing, protocol bridging, WAF header spoofing, and stateless
scrubbing for https://agentrouter.org models across multi-agent harnesses.
Runs on pure Python 3 standard library.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Iterable, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

AGENTROUTER_MODELS: Dict[str, Dict[str, Any]] = {
    "gpt-6.1sol": {
        "id": "gpt-6.1sol",
        "name": "GPT-6.1 Sol (24/7 Unlimited)",
        "provider": "agentrouter",
        "unlimited": True,
        "release_windows_utc": [],
        "protocols": ["chat_completions", "responses", "anthropic_bridge"],
        "tier": "tier_0",
        "stateless_scrub": True,
        "description": "Unlimited flagship model; requires stateless scrub to prevent cross-node decryption failure.",
    },
    "gpt-6-astra": {
        "id": "gpt-6-astra",
        "name": "GPT-6 Astra (Apex Time-Window)",
        "provider": "agentrouter",
        "unlimited": False,
        "release_windows_utc": ["07:00-09:00", "19:00-21:00"],  # 15:00 & 03:00 Beijing Time
        "protocols": ["chat_completions", "responses", "anthropic_bridge"],
        "tier": "tier_0",
        "stateless_scrub": True,
        "description": "Apex frontier model supplied in 2-hour daily release windows (03:00 and 15:00 BJT).",
    },
    "claude-opus-5": {
        "id": "claude-opus-5",
        "name": "Claude Opus 5",
        "provider": "agentrouter",
        "unlimited": False,
        "release_windows_utc": [],
        "protocols": ["anthropic_messages", "chat_completions"],
        "tier": "tier_0",
        "stateless_scrub": False,
        "description": "Frontier Anthropic reasoning model.",
    },
    "claude-opus-4-8": {
        "id": "claude-opus-4-8",
        "name": "Claude Opus 4.8",
        "provider": "agentrouter",
        "unlimited": False,
        "release_windows_utc": [],
        "protocols": ["anthropic_messages", "chat_completions"],
        "tier": "tier_0",
        "stateless_scrub": False,
        "description": "Anthropic reasoning model fallback.",
    },
    "gpt-5.6-sol": {
        "id": "gpt-5.6-sol",
        "name": "GPT-5.6 Sol",
        "provider": "agentrouter",
        "unlimited": False,
        "release_windows_utc": [],
        "protocols": ["chat_completions", "responses", "anthropic_bridge"],
        "tier": "tier_0",
        "stateless_scrub": True,
        "description": "Frontier OpenAI-compatible fallback.",
    },
    "glm-5.3": {
        "id": "glm-5.3",
        "name": "GLM 5.3",
        "provider": "agentrouter",
        "unlimited": False,
        "release_windows_utc": [],
        "protocols": ["anthropic_messages", "chat_completions"],
        "tier": "tier_1",
        "stateless_scrub": False,
        "description": "Tier 1 high-velocity implementation model.",
    },
    "deepseek-v4-flash": {
        "id": "deepseek-v4-flash",
        "name": "DeepSeek V4 Flash",
        "provider": "agentrouter",
        "unlimited": False,
        "release_windows_utc": [],
        "protocols": ["anthropic_messages", "chat_completions"],
        "tier": "tier_2",
        "stateless_scrub": False,
        "description": "Tier 2 high-throughput mechanical execution and zero-rate fallback.",
    },
}

GATEWAY_CACHE_STATS: Dict[str, int] = {
    "total_requests": 0,
    "cache_hits": 0,
    "cached_tokens": 0,
    "prompt_tokens": 0,
}


def record_cache_usage(cached_tokens: int, prompt_tokens: int = 0) -> None:
    """Record prompt cache usage metrics across all protocols."""
    GATEWAY_CACHE_STATS["total_requests"] += 1
    if cached_tokens > 0:
        GATEWAY_CACHE_STATS["cache_hits"] += 1
        GATEWAY_CACHE_STATS["cached_tokens"] += cached_tokens
    if prompt_tokens > 0:
        GATEWAY_CACHE_STATS["prompt_tokens"] += prompt_tokens


def normalize_gateway_path(path: str) -> str:
    """Normalize inbound API paths, stripping duplicate /v1 prefixes or missing /v1."""
    clean = path.split("?")[0].strip()
    if not clean.startswith("/"):
        clean = "/" + clean
    while clean.startswith("/v1/v1"):
        clean = clean[3:]
    if clean in ("/messages", "/v1/messages"):
        return "/v1/messages"
    if clean in ("/chat/completions", "/v1/chat/completions"):
        return "/v1/chat/completions"
    if clean in ("/responses", "/v1/responses"):
        return "/v1/responses"
    if clean in ("/models", "/v1/models"):
        return "/v1/models"
    if clean in ("/health", "/v1/health"):
        return "/v1/health"
    if not clean.startswith("/v1/"):
        return "/v1" + clean
    return clean


def build_waf_headers(protocol: str, auth_token: str = "") -> Dict[str, str]:
    """Generate spoofed headers to satisfy Aliyun WAF TLS and client fingerprinting."""
    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    proto = protocol.lower().strip()
    if proto in ("openai", "chat_completions", "responses"):
        headers["User-Agent"] = "codex_cli_rs/0.80.0"
        headers["originator"] = "codex_cli_rs"
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
    elif proto in ("anthropic", "anthropic_messages", "anthropic_bridge"):
        headers["User-Agent"] = "claude-cli/1.0.0"
        headers["x-app"] = "cli"
        headers["anthropic-version"] = "2023-06-01"
        if auth_token:
            headers["x-api-key"] = auth_token
            headers["Authorization"] = f"Bearer {auth_token}"
    else:
        headers["User-Agent"] = "codex_cli_rs/0.80.0"
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
    return headers


def scrub_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Strip stateful tokens and non-standard fields that cause Decryption Failure across load balancers."""
    if not isinstance(payload, dict):
        return payload
    cleaned = copy.deepcopy(payload)
    cleaned.pop("output_config", None)

    thinking = cleaned.get("thinking")
    if isinstance(thinking, dict) and thinking.get("type") == "adaptive":
        cleaned.pop("thinking", None)

    model = str(cleaned.get("model", "")).lower()
    model_meta = AGENTROUTER_MODELS.get(model, {})
    stateless = model_meta.get("stateless_scrub", False) or model in (
        "gpt-6.1sol", "gpt-6-astra", "gpt-5.6-sol"
    ) or any(k in cleaned for k in ("previous_response_id", "reasoning_encrypted_content", "encrypted_content"))

    if stateless:
        cleaned.pop("previous_response_id", None)
        cleaned.pop("reasoning_encrypted_content", None)
        cleaned.pop("encrypted_content", None)
        cleaned.pop("store", None)

    return cleaned


def sanitize_sse_lines(lines: Iterable[str]) -> List[str]:
    """Filter out poison SSE frames (billing_summary, data: null) and orphaned blank lines."""
    sanitized: List[str] = []
    in_dropped_frame = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_dropped_frame:
                in_dropped_frame = False
                continue
            sanitized.append(line)
            continue

        if "billing_summary" in stripped or "billing.summary" in stripped:
            in_dropped_frame = True
            continue

        if stripped in ("data: null", "data:null"):
            in_dropped_frame = True
            continue

        if in_dropped_frame:
            continue

        sanitized.append(line)

    return sanitized


def is_decryption_or_channel_error(status_code: int, body_text: str) -> bool:
    """Detect upstream node decryption failure or channel exhaustion requiring failover."""
    if status_code in (500, 502, 503, 504):
        return True
    text = str(body_text).lower()
    error_signatures = [
        "decryption failure",
        "解密失败",
        "cross-resource access",
        "跨资源访问",
        "no available channel",
        "content-blocked",
    ]
    return any(sig in text for sig in error_signatures)


def translate_anthropic_to_openai(anth_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Translate Anthropic /v1/messages payload to OpenAI /v1/chat/completions format."""
    oai_payload: Dict[str, Any] = {}
    model = anth_payload.get("model", "gpt-6.1sol")
    oai_payload["model"] = model

    messages: List[Dict[str, Any]] = []
    system_val = anth_payload.get("system")
    if system_val:
        if isinstance(system_val, list):
            sys_text = "\n".join(b.get("text", "") for b in system_val if isinstance(b, dict))
        else:
            sys_text = str(system_val)
        if sys_text.strip():
            messages.append({"role": "system", "content": sys_text.strip()})

    for msg in anth_payload.get("messages", []):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    text_parts.append(block)
            content_str = "\n".join(text_parts)
        else:
            content_str = str(content)
        messages.append({"role": role, "content": content_str})

    oai_payload["messages"] = messages
    if "max_tokens" in anth_payload:
        oai_payload["max_tokens"] = anth_payload["max_tokens"]
    if "temperature" in anth_payload:
        oai_payload["temperature"] = anth_payload["temperature"]
    if "stream" in anth_payload:
        oai_payload["stream"] = anth_payload["stream"]
    if "cache_prompt" in anth_payload:
        oai_payload["cache_prompt"] = anth_payload["cache_prompt"]

    return oai_payload


def translate_openai_to_anthropic(oai_resp: Dict[str, Any], requested_model: str) -> Dict[str, Any]:
    """Translate OpenAI chat completion response to Anthropic message format with prompt cache telemetry."""
    choices = oai_resp.get("choices", [])
    text_content = ""
    stop_reason = "end_turn"
    if choices:
        first = choices[0]
        msg = first.get("message", {})
        text_content = msg.get("content", "") or ""
        finish_reason = first.get("finish_reason")
        if finish_reason == "length":
            stop_reason = "max_tokens"
        elif finish_reason == "stop":
            stop_reason = "end_turn"

    usage = oai_resp.get("usage", {}) or {}
    timings = oai_resp.get("timings", {}) or {}
    prompt_tokens = usage.get("prompt_tokens", 0) or timings.get("prompt_n", 0)
    output_tokens = usage.get("completion_tokens", 0)

    prompt_tokens_details = usage.get("prompt_tokens_details", {}) or {}
    cached_tokens = (
        prompt_tokens_details.get("cached_tokens", 0)
        or usage.get("cache_read_input_tokens", 0)
        or timings.get("cache_n", 0)
    )
    cache_creation = usage.get("cache_creation_input_tokens", 0)

    record_cache_usage(cached_tokens, prompt_tokens)

    anth_usage: Dict[str, Any] = {
        "input_tokens": prompt_tokens,
        "output_tokens": output_tokens,
    }
    if cached_tokens > 0:
        anth_usage["cache_read_input_tokens"] = cached_tokens
    if cache_creation > 0:
        anth_usage["cache_creation_input_tokens"] = cache_creation

    return {
        "id": oai_resp.get("id", f"msg_{int(time.time() * 1000)}"),
        "type": "message",
        "role": "assistant",
        "model": requested_model,
        "content": [
            {
                "type": "text",
                "text": text_content,
            }
        ],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": anth_usage,
    }


def get_failover_chain(requested_model: str, utc_now: Optional[datetime] = None) -> List[str]:
    """Compute ordered failover chain based on model tier and Astra UTC supply windows."""
    if utc_now is None:
        utc_now = datetime.now(timezone.utc)
    astra_active = utc_now.hour in (7, 8, 19, 20)

    if astra_active:
        priority_pool = [
            "gpt-6-astra",
            "gpt-6.1sol",
            "claude-opus-5",
            "gpt-5.6-sol",
            "glm-5.3",
            "deepseek-v4-flash",
        ]
    else:
        priority_pool = [
            "gpt-6.1sol",
            "claude-opus-5",
            "gpt-6-astra",
            "gpt-5.6-sol",
            "glm-5.3",
            "deepseek-v4-flash",
        ]

    chain = [requested_model]
    for model_id in priority_pool:
        if model_id not in chain and model_id in AGENTROUTER_MODELS:
            chain.append(model_id)
    return chain


class GatewayRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for local dual-protocol gateway."""

    def _send_json(self, status_code: int, data: Any) -> None:
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        norm_path = normalize_gateway_path(self.path)
        if norm_path in ("/v1/health", "/health", "/v1/metrics", "/metrics"):
            port = self.server.server_address[1] if hasattr(self.server, "server_address") else 8787
            now = datetime.now(timezone.utc)
            astra_active = now.hour in (7, 8, 19, 20)
            total_reqs = GATEWAY_CACHE_STATS["total_requests"]
            hits = GATEWAY_CACHE_STATS["cache_hits"]
            hit_rate = round(hits / total_reqs, 4) if total_reqs > 0 else 0.0
            self._send_json(200, {
                "status": "ok",
                "gateway": "agentrouter-mesh",
                "port": port,
                "timestamp": now.isoformat(),
                "astra_window_active": astra_active,
                "model_count": len(AGENTROUTER_MODELS),
                "cache_metrics": {
                    "total_requests": total_reqs,
                    "cache_hits": hits,
                    "cached_tokens": GATEWAY_CACHE_STATS["cached_tokens"],
                    "prompt_tokens": GATEWAY_CACHE_STATS["prompt_tokens"],
                    "cache_hit_rate": hit_rate,
                },
            })
            return

        if norm_path in ("/v1/models", "/models"):
            models_data = [
                {
                    "id": m["id"],
                    "object": "model",
                    "created": 1700000000,
                    "owned_by": m["provider"],
                    "unlimited": m["unlimited"],
                    "tier": m["tier"],
                    "stateless_scrub": m["stateless_scrub"],
                    "release_windows_utc": m["release_windows_utc"],
                }
                for m in AGENTROUTER_MODELS.values()
            ]
            self._send_json(200, {"object": "list", "data": models_data})
            return

        self._send_json(404, {"error": {"message": f"Not found: {self.path}", "type": "invalid_request_error"}})

    def do_POST(self) -> None:
        norm_path = normalize_gateway_path(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception as err:
            self._send_json(400, {"error": {"message": f"Malformed JSON: {err}", "type": "invalid_request_error"}})
            return

        auth_header = self.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        if not token:
            token = self.headers.get("x-api-key", "").strip()
        if not token:
            token = os.environ.get("AGENTROUTER_API_KEY", "").strip()

        upstream_base = os.environ.get("AGENTROUTER_BASE_URL", "https://agentrouter.org/v1").rstrip("/")
        requested_model = payload.get("model", "gpt-6.1sol")
        failover_chain = get_failover_chain(requested_model)

        # Handle Anthropic /v1/messages endpoint
        if norm_path == "/v1/messages":
            target_model_info = AGENTROUTER_MODELS.get(requested_model, {})
            # If model supports Anthropic natively and is not an OpenAI-only model
            if "anthropic_messages" in target_model_info.get("protocols", []):
                upstream_url = f"{upstream_base}/messages"
                headers = build_waf_headers("anthropic", token)
                scrubbed = scrub_payload(payload)
                self._forward_request(upstream_url, headers, scrubbed, requested_model, is_anthropic=True)
            else:
                # Bridge Anthropic to OpenAI route
                oai_payload = translate_anthropic_to_openai(payload)
                oai_payload = scrub_payload(oai_payload)
                upstream_url = f"{upstream_base}/chat/completions"
                headers = build_waf_headers("openai", token)
                self._forward_bridged_request(upstream_url, headers, oai_payload, requested_model, failover_chain, token)
            return

        # Handle OpenAI /v1/chat/completions endpoint
        if norm_path == "/v1/chat/completions":
            upstream_url = f"{upstream_base}/chat/completions"
            headers = build_waf_headers("openai", token)
            scrubbed = scrub_payload(payload)
            self._forward_with_failover(upstream_url, headers, scrubbed, failover_chain, token)
            return

        # Handle Responses endpoint
        if norm_path == "/v1/responses":
            upstream_url = f"{upstream_base}/responses"
            headers = build_waf_headers("responses", token)
            scrubbed = scrub_payload(payload)
            self._forward_with_failover(upstream_url, headers, scrubbed, failover_chain, token)
            return

        self._send_json(404, {"error": {"message": f"Unsupported POST route: {self.path}", "type": "invalid_request_error"}})

    def _forward_request(
        self,
        upstream_url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        model: str,
        is_anthropic: bool = False,
    ) -> None:
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(upstream_url, data=data_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                resp_bytes = resp.read()
                resp_json = json.loads(resp_bytes.decode("utf-8"))
                usage = resp_json.get("usage", {}) or {}
                cached = (
                    usage.get("cache_read_input_tokens", 0)
                    or usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
                )
                prompt_tokens = usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0)
                record_cache_usage(cached, prompt_tokens)
                self._send_json(resp.status, resp_json)
        except urllib.error.HTTPError as http_err:
            body = http_err.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(body)
            except Exception:
                err_json = {"error": {"message": body, "status": http_err.code}}
            self._send_json(http_err.code, err_json)
        except Exception as exc:
            self._send_json(502, {"error": {"message": f"Gateway error: {exc}", "type": "bad_gateway"}})

    def _forward_bridged_request(
        self,
        upstream_url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        original_model: str,
        failover_chain: List[str],
        token: str,
    ) -> None:
        upstream_base = os.environ.get("AGENTROUTER_BASE_URL", "https://agentrouter.org/v1").rstrip("/")
        last_error = "Unknown error"

        for model_candidate in failover_chain:
            payload["model"] = model_candidate
            scrubbed = scrub_payload(payload)
            data_bytes = json.dumps(scrubbed).encode("utf-8")
            req = urllib.request.Request(upstream_url, data=data_bytes, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    resp_bytes = resp.read()
                    oai_json = json.loads(resp_bytes.decode("utf-8"))
                    anth_resp = translate_openai_to_anthropic(oai_json, model_candidate)
                    self._send_json(200, anth_resp)
                    return
            except urllib.error.HTTPError as http_err:
                body = http_err.read().decode("utf-8", errors="replace")
                last_error = f"HTTP {http_err.code}: {body}"
                if is_decryption_or_channel_error(http_err.code, body):
                    continue
                try:
                    err_json = json.loads(body)
                except Exception:
                    err_json = {"error": {"message": body, "status": http_err.code}}
                self._send_json(http_err.code, err_json)
                return
            except Exception as exc:
                last_error = str(exc)
                continue

        self._send_json(503, {
            "error": {
                "message": f"All models in failover chain exhausted: {last_error}",
                "type": "service_unavailable",
                "chain": failover_chain,
            }
        })

    def _forward_with_failover(
        self,
        upstream_url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        failover_chain: List[str],
        token: str,
    ) -> None:
        last_error = "Unknown error"
        for model_candidate in failover_chain:
            payload["model"] = model_candidate
            if "localhost" in upstream_url or "127.0.0.1" in upstream_url:
                payload["cache_prompt"] = True
            scrubbed = scrub_payload(payload)
            data_bytes = json.dumps(scrubbed).encode("utf-8")
            req = urllib.request.Request(upstream_url, data=data_bytes, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    resp_bytes = resp.read()
                    resp_json = json.loads(resp_bytes.decode("utf-8"))
                    usage = resp_json.get("usage", {}) or {}
                    timings = resp_json.get("timings", {}) or {}
                    cached = (
                        usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
                        or usage.get("cache_read_input_tokens", 0)
                        or timings.get("cache_n", 0)
                    )
                    prompt_tokens = usage.get("prompt_tokens", 0) or timings.get("prompt_n", 0)
                    record_cache_usage(cached, prompt_tokens)
                    self._send_json(resp.status, resp_json)
                    return
            except urllib.error.HTTPError as http_err:
                body = http_err.read().decode("utf-8", errors="replace")
                last_error = f"HTTP {http_err.code}: {body}"
                if is_decryption_or_channel_error(http_err.code, body):
                    continue
                try:
                    err_json = json.loads(body)
                except Exception:
                    err_json = {"error": {"message": body, "status": http_err.code}}
                self._send_json(http_err.code, err_json)
                return
            except Exception as exc:
                last_error = str(exc)
                continue

        self._send_json(503, {
            "error": {
                "message": f"All failover candidates exhausted: {last_error}",
                "type": "service_unavailable",
                "chain": failover_chain,
            }
        })

    def log_message(self, format: str, *args: Any) -> None:
        pass


def run_server(port: int = 8787) -> None:
    server_address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(server_address, GatewayRequestHandler)
    print(f"AgentRouter Gateway running at http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down gateway...")
        httpd.shutdown()


def cli_status() -> None:
    now = datetime.now(timezone.utc)
    astra_active = now.hour in (7, 8, 19, 20)
    status_info = {
        "gateway": "AgentRouter Dual-Protocol Mesh Gateway",
        "version": "1.0.0 (ADR-033)",
        "upstream_base_url": os.environ.get("AGENTROUTER_BASE_URL", "https://agentrouter.org/v1"),
        "utc_time": now.isoformat(),
        "astra_window_active": astra_active,
        "astra_supply_windows_utc": ["07:00-09:00", "19:00-21:00"],
        "astra_supply_windows_bjt": ["15:00-17:00", "03:00-05:00"],
        "default_flagship": "gpt-6.1sol",
        "models_count": len(AGENTROUTER_MODELS),
        "models": list(AGENTROUTER_MODELS.keys()),
    }
    print(json.dumps(status_info, indent=2))


def cli_models() -> None:
    print(json.dumps(AGENTROUTER_MODELS, indent=2))


def cli_scrub_test() -> None:
    sample_payload = {
        "model": "gpt-6.1sol",
        "messages": [{"role": "user", "content": "ping"}],
        "previous_response_id": "resp_state_12345",
        "reasoning_encrypted_content": "gAAAAAB...",
        "encrypted_content": "s7d8f9...",
        "output_config": {"format": "strict"},
        "thinking": {"type": "adaptive"},
        "store": True,
    }
    scrubbed = scrub_payload(sample_payload)
    print("Original payload keys:", list(sample_payload.keys()))
    print("Scrubbed payload keys:", list(scrubbed.keys()))
    assert "previous_response_id" not in scrubbed
    assert "reasoning_encrypted_content" not in scrubbed
    assert "encrypted_content" not in scrubbed
    assert "output_config" not in scrubbed
    assert "thinking" not in scrubbed
    assert "store" not in scrubbed
    print("Stateless scrub verification: PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentRouter Local Dual-Protocol Gateway (ADR-033)")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Show gateway status and Astra time-window info")
    subparsers.add_parser("models", help="List AgentRouter model catalog")
    subparsers.add_parser("scrub-test", help="Test stateless scrubbing on sample payload")

    serve_parser = subparsers.add_parser("serve", help="Run local gateway HTTP server")
    serve_parser.add_argument("--port", type=int, default=8787, help="Local port (default: 8787)")

    args = parser.parse_args()

    if args.command == "status":
        cli_status()
    elif args.command == "models":
        cli_models()
    elif args.command == "scrub-test":
        cli_scrub_test()
    elif args.command == "serve":
        run_server(args.port)
    else:
        cli_status()


if __name__ == "__main__":
    main()
