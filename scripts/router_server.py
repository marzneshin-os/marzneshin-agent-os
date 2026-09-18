#!/usr/bin/env python3
"""router_server.py — OpenAI-compatible local HTTP proxy.

Allows tools like Tasklet.ai or ClickUp (via MCP) to talk to the OmniRoute gateway
while leveraging local 9Router optimizations (tokensaver, usage tracking).
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

from adapters.omniroute import OmniRouteAdapter
from adapters.base import IdemClass
from lib import ids, router, clock


class RouterProxyHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
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
                    
            resp = {"object": "list", "data": models}
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        if not self.path.startswith("/v1/chat/completions"):
            self.send_error(404, "Not Found")
            return
            
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        
        try:
            req_data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Bad Request: Invalid JSON")
            return
            
        adapter = OmniRouteAdapter()
        
        # We pass the payload mostly as-is, but add tokensaver flags
        # Defaulting them to True or from headers if needed.
        req_data.setdefault("rtk_enabled", True)
        req_data.setdefault("ponytail_enabled", False)
        
        deadline = clock.now()
        import datetime as dt
        deadline = deadline + dt.timedelta(minutes=5)
        
        try:
            idem_key = ids.new_ulid()
            res = adapter.execute(
                "llm_chat",
                req_data,
                idem_key=idem_key,
                idem_class="none",
                dry_run=False,
                deadline=deadline,
                provenance=[]
            )
            
            if res.ok:
                self.send_response(200)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(res.data).encode("utf-8"))
            else:
                self.send_response(500)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                err = {"error": {"message": str(res.error), "type": "adapter_error"}}
                self.wfile.write(json.dumps(err).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            err = {"error": {"message": str(e), "type": "server_error"}}
            self.wfile.write(json.dumps(err).encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OmniRoute/9Router Local Proxy")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    args = parser.parse_args(argv)
    
    server_address = (args.host, args.port)
    HTTPServer.allow_reuse_address = True
    httpd = HTTPServer(server_address, RouterProxyHandler)
    
    print(f"Starting OmniRoute Local Proxy on http://{args.host}:{args.port}")
    print("Supports OpenAI-compatible /v1/chat/completions")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        httpd.server_close()
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
