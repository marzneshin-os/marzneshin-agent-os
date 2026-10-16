#!/usr/bin/env python3
"""router_server.py — OpenAI & Anthropic-compatible local HTTP proxy.

Aggregates 34+ free-tier AI providers via FreeLLMAPI and OmniRoute gateway.
Exposes:
- OpenAI-compatible `/v1/chat/completions` and `/v1/models`
- Anthropic-compatible `/v1/messages` (for Claude Code ANTHROPIC_BASE_URL)
- FreeLLM pool diagnostics `/v1/freellm/status` and `/v1/freellm/catalog`
- Streaming SSE support for real-time interactive coding agents.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

from adapters.omniroute import OmniRouteAdapter
from adapters.freellm import FreeLLMAdapter
from adapters.base import IdemClass
from lib import ids, router, clock
from lib.freellm_pool import (
    FreeLLMPoolManager,
    PROVIDER_CATALOG,
    SmartFallbackRouter,
    get_total_free_tier_capacity,
)


class RouterProxyHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, x-api-key, anthropic-version")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        if self.path.startswith("/v1/models"):
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            config = router.load_config()
            models = []
            for combo, combo_models in config.get("combos", {}).items():
                models.append({"id": combo, "object": "model", "owned_by": "combo"})
                for m in combo_models:
                    models.append({"id": m, "object": "model", "owned_by": "upstream"})

            for pid, p in PROVIDER_CATALOG.items():
                for m in p.models:
                    models.append({"id": f"{pid}:{m}", "object": "model", "owned_by": pid})

            resp = {"object": "list", "data": models}
            self.wfile.write(json.dumps(resp).encode("utf-8"))

        elif self.path.startswith("/v1/freellm/status"):
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            pool = FreeLLMPoolManager()
            status = pool.get_full_pool_status()
            self.wfile.write(json.dumps(status, indent=2).encode("utf-8"))

        elif self.path.startswith("/v1/freellm/catalog"):
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            catalog_data = {
                "total_providers": len(PROVIDER_CATALOG),
                "combined_monthly_tokens": get_total_free_tier_capacity(),
                "providers": {
                    pid: {
                        "name": p.name,
                        "base_url": p.base_url,
                        "monthly_token_quota": p.monthly_token_quota,
                        "rpm": p.rpm,
                        "tpm": p.tpm,
                        "models": p.models,
                        "specialties": p.specialties,
                        "format": p.format,
                        "description": p.description,
                    }
                    for pid, p in PROVIDER_CATALOG.items()
                },
            }
            self.wfile.write(json.dumps(catalog_data, indent=2).encode("utf-8"))

        elif self.path.startswith("/v1/freellm/health") or self.path == "/healthz":
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            resp = {
                "status": "ok",
                "timestamp": clock.iso(),
                "providers_available": len(PROVIDER_CATALOG),
                "proxy": "Marzneshin-FreeLLMAPI-Gateway",
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))

        else:
            self.send_error(404, f"Not Found: {self.path}")

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            req_data = json.loads(body.decode("utf-8")) if body else {}
        except json.JSONDecodeError:
            self.send_error(400, "Bad Request: Invalid JSON")
            return

        # 1. Anthropic native endpoint (/v1/messages)
        if self.path.startswith("/v1/messages"):
            self._handle_anthropic_messages(req_data)
            return

        # 2. OpenAI native endpoint (/v1/chat/completions)
        if self.path.startswith("/v1/chat/completions"):
            self._handle_openai_chat(req_data)
            return

        # 3. FreeLLM Key Rotate endpoint (/v1/freellm/rotate)
        if self.path.startswith("/v1/freellm/rotate"):
            provider = req_data.get("provider", "groq")
            pool = FreeLLMPoolManager()
            new_key = pool.acquire_key(provider)
            from lib.freellm_pool import KeyVault
            resp = {
                "provider": provider,
                "rotated_key": KeyVault.redact(new_key),
                "timestamp": clock.iso(),
            }
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        self.send_error(404, f"Not Found: {self.path}")

    def _handle_anthropic_messages(self, req_data: dict[str, Any]) -> None:
        """Handle Anthropic format messages request (used by Claude Code)."""
        stream = req_data.get("stream", False)
        adapter = FreeLLMAdapter()

        deadline = clock.now() + dt.timedelta(minutes=5)
        idem_key = ids.new_ulid()

        # Translate Anthropic messages payload
        payload = {
            "model": req_data.get("model", "mistral:codestral-latest"),
            "messages": req_data.get("messages", []),
            "domain": "coding",
        }
        if "system" in req_data:
            sys_msg = {"role": "system", "content": req_data["system"]}
            payload["messages"] = [sys_msg] + payload["messages"]

        try:
            res = adapter.execute(
                "llm_messages",
                payload,
                idem_key=idem_key,
                idem_class="none",
                dry_run=False,
                deadline=deadline,
                provenance=[],
            )

            if not res.ok:
                self.send_response(500)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                err = {"type": "error", "error": {"type": "api_error", "message": str(res.error)}}
                self.wfile.write(json.dumps(err).encode("utf-8"))
                return

            if stream:
                # SSE streaming for Anthropic protocol
                self.send_response(200)
                self._send_cors_headers()
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

                # Extract text
                text = "Hello from FreeLLMAPI pool."
                if isinstance(res.data, dict) and "content" in res.data and res.data["content"]:
                    text = res.data["content"][0].get("text", "")

                events = [
                    ("message_start", {"type": "message_start", "message": {"id": f"msg_{idem_key}", "type": "message", "role": "assistant", "model": payload["model"], "content": []}}),
                    ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
                    ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}}),
                    ("content_block_stop", {"type": "content_block_stop", "index": 0}),
                    ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}}),
                    ("message_stop", {"type": "message_stop"}),
                ]
                for ev_name, ev_data in events:
                    self.wfile.write(f"event: {ev_name}\ndata: {json.dumps(ev_data)}\n\n".encode("utf-8"))
                    self.wfile.flush()
            else:
                self.send_response(200)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(res.data).encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            err = {"type": "error", "error": {"type": "server_error", "message": str(e)}}
            self.wfile.write(json.dumps(err).encode("utf-8"))

    def _handle_openai_chat(self, req_data: dict[str, Any]) -> None:
        """Handle standard OpenAI format chat completions."""
        stream = req_data.get("stream", False)
        adapter = OmniRouteAdapter()

        req_data.setdefault("rtk_enabled", True)
        req_data.setdefault("ponytail_enabled", False)

        deadline = clock.now() + dt.timedelta(minutes=5)
        idem_key = ids.new_ulid()

        try:
            res = adapter.execute(
                "llm_chat",
                req_data,
                idem_key=idem_key,
                idem_class="none",
                dry_run=False,
                deadline=deadline,
                provenance=[],
            )

            if not res.ok:
                self.send_response(500)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                err = {"error": {"message": str(res.error), "type": "adapter_error"}}
                self.wfile.write(json.dumps(err).encode("utf-8"))
                return

            if stream:
                self.send_response(200)
                self._send_cors_headers()
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

                content = "Response from FreeLLMAPI/OmniRoute"
                if isinstance(res.data, dict) and "choices" in res.data and res.data["choices"]:
                    content = res.data["choices"][0].get("message", {}).get("content", "")

                chunk = {
                    "id": f"chatcmpl-{idem_key}",
                    "object": "chat.completion.chunk",
                    "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": "stop"}],
                }
                self.wfile.write(f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n".encode("utf-8"))
                self.wfile.flush()
            else:
                self.send_response(200)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(res.data).encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            err = {"error": {"message": str(e), "type": "server_error"}}
            self.wfile.write(json.dumps(err).encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FreeLLMAPI & OmniRoute Multi-Provider Local Proxy")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=3001, help="Port to bind (default: 3001 for FreeLLMAPI)")
    args = parser.parse_args(argv)

    server_address = (args.host, args.port)
    HTTPServer.allow_reuse_address = True
    httpd = HTTPServer(server_address, RouterProxyHandler)

    print("=" * 65)
    print(f"  FreeLLMAPI & OmniRoute Universal Fast-Inference Gateway")
    print(f"  Listening on: http://{args.host}:{args.port}")
    print("=" * 65)
    print("  Endpoints:")
    print("    - OpenAI Chat     : POST /v1/chat/completions")
    print("    - Anthropic Msgs  : POST /v1/messages (Claude Code compatible)")
    print("    - Models Catalog  : GET  /v1/models")
    print("    - Pool Status     : GET  /v1/freellm/status")
    print("    - Free Catalog    : GET  /v1/freellm/catalog")
    print("    - Rotate Key      : POST /v1/freellm/rotate")
    print("=" * 65)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down gateway...")
        httpd.server_close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
