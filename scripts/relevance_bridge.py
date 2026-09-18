#!/usr/bin/env python3
"""
Marzneshin OS - Relevance AI & Hybrid Local Model Gateway
Bridges Relevance AI Cloud Agents with local agentmemory and CCR fallback.
Runs an OpenAI-compatible server on port 8086.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from lib import clock

DEFAULT_REGION = os.getenv("RELEVANCE_REGION", "d7b62b")
DEFAULT_PROJECT = os.getenv("RELEVANCE_PROJECT", "0bf8c17c-7c8f-5ad8-b562-aa63cc0d294c")
DEFAULT_AGENT_ID = os.getenv("RELEVANCE_AGENT_ID", "379378bc-e747-42ef-a407-a42d4f0b84e7")
API_KEY = os.getenv("RELEVANCE_AI_API_KEY", "")
PORT = int(os.getenv("RELEVANCE_BRIDGE_PORT", "8086"))

CCR_URL = "http://127.0.0.1:3456/v1/chat/completions"
CCR_KEY = os.getenv("CCR_API_KEY", "")
CCR_MODEL = os.getenv("CCR_MODEL", "Google Gemini (AI Studio)/gemini-3.7-flash")
LOCAL_KIMI_URL = os.getenv("LOCAL_KIMI_URL", "http://127.0.0.1:8085/v1/chat/completions")


def trigger_relevance_agent(message: str, agent_id: str = DEFAULT_AGENT_ID, timeout: int = 45) -> str:
    """Trigger an agent on Relevance AI and poll for completion."""
    url = f"https://api-{DEFAULT_REGION}.stack.tryrelevance.com/latest/agents/trigger"
    headers = {
        "Authorization": f"{DEFAULT_PROJECT}:{API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "agent_id": agent_id,
        "message": {"role": "user", "content": message},
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=12) as res:
            data = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if hasattr(e, "read") else str(e)
        raise RuntimeError(f"Relevance AI HTTP {e.code}: {body}")

    task_id = data.get("task_id")
    if not task_id:
        raise ValueError("No task_id returned from Relevance AI trigger")

    # Poll for result
    poll_url = f"https://api-{DEFAULT_REGION}.stack.tryrelevance.com/latest/agents/tasks/{task_id}"
    start_iso = clock.iso()
    while clock.age_seconds(start_iso) < timeout:
        clock.sleep(2)
        poll_req = urllib.request.Request(poll_url, headers=headers)
        try:
            with urllib.request.urlopen(poll_req, timeout=10) as res:
                pdata = json.loads(res.read().decode("utf-8"))
                status = pdata.get("status")
                if status == "completed":
                    msgs = pdata.get("output", {}).get("messages", [])
                    if msgs:
                        return msgs[-1].get("content", "Task completed.")
                    return str(pdata.get("output", "Done"))
                elif status in ("failed", "cancelled"):
                    raise RuntimeError(f"Relevance AI agent task {status}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise

    raise TimeoutError(f"Relevance AI task {task_id} timed out after {timeout}s")


def trigger_ccr_fallback(messages: list[dict], model: str = CCR_MODEL) -> str:
    """Fallback to local CCR gateway (Gemini 3.7 / 3.8 / Kimi K3)."""
    headers = {
        "Authorization": f"Bearer {CCR_KEY}",
        "Content-Type": "application/json",
    }
    # Ensure messages format is compatible
    clean_messages = []
    for m in messages:
        clean_messages.append({
            "role": m.get("role", "user"),
            "content": str(m.get("content", ""))
        })
    payload = {
        "model": model,
        "messages": clean_messages,
    }
    req = urllib.request.Request(CCR_URL, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            data = json.loads(res.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if hasattr(e, "read") else str(e)
        raise RuntimeError(f"CCR HTTP {e.code}: {body}")


def trigger_kimi_k3_local(messages: list[dict]) -> str:
    """Fallback to local Kimi K3 MoE server on port 8085."""
    headers = {"Content-Type": "application/json"}
    clean_messages = []
    for m in messages:
        clean_messages.append({
            "role": m.get("role", "user"),
            "content": str(m.get("content", ""))
        })
    payload = {
        "model": "kimi-k3",
        "messages": clean_messages,
    }
    req = urllib.request.Request(LOCAL_KIMI_URL, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            data = json.loads(res.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if hasattr(e, "read") else str(e)
        raise RuntimeError(f"Local Kimi K3 HTTP {e.code}: {body}")


def smart_generate(messages: list[dict], requested_model: str) -> tuple[str, str]:
    """Resilient generation: Relevance AI -> CCR Primary -> CCR Secondary -> Local Kimi K3."""
    prompt = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in messages])

    # 1. Try Relevance AI Agent (Frontier Claude Sonnet 5)
    try:
        content = trigger_relevance_agent(prompt)
        return content, "relevance/claude-sonnet-5"
    except Exception as rel_err:
        print(f"[SmartBridge] Relevance AI unavailable ({rel_err}). Routing to CCR fallback...")

    # 2. Try CCR Primary (Gemini 3.7 Flash)
    try:
        content = trigger_ccr_fallback(messages, CCR_MODEL)
        return content, f"ccr/{CCR_MODEL}"
    except Exception as ccr_err:
        print(f"[SmartBridge] CCR Primary failed ({ccr_err}). Routing to CCR Secondary...")

    # 3. Try CCR Secondary (Gemini 3.8 Flash)
    try:
        content = trigger_ccr_fallback(messages, "Google Gemini (AI Studio)/gemini-3.8-flash")
        return content, "ccr/gemini-3.8-flash"
    except Exception as sec_err:
        print(f"[SmartBridge] CCR Secondary failed ({sec_err}). Routing to Local Kimi K3...")

    # 4. Try Local Kimi K3 MoE on port 8085
    try:
        content = trigger_kimi_k3_local(messages)
        return content, "local/kimi-k3"
    except Exception as local_err:
        print(f"[SmartBridge] Local Kimi K3 fallback failed ({local_err})...")
        raise RuntimeError("All configured model gateways failed.")


class RelevanceBridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        sys.stderr.write(f"[SmartBridge] {args[0]} {args[1]}\n")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        if self.path == "/v1/models":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            models = [
                {"id": "relevance/claude-sonnet-5", "object": "model", "owned_by": "relevance-ai"},
                {"id": "relevance/gpt-5.6", "object": "model", "owned_by": "relevance-ai"},
                {"id": "relevance/claude-opus-5", "object": "model", "owned_by": "relevance-ai"},
                {"id": "ccr/gemini-3.7-flash", "object": "model", "owned_by": "ccr"},
                {"id": "local/kimi-k3", "object": "model", "owned_by": "local-moe"},
            ]
            self.wfile.write(json.dumps({"object": "list", "data": models}).encode("utf-8"))
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            status_data = {
                "status": "healthy",
                "tier1_relevance_agent": DEFAULT_AGENT_ID,
                "tier2_ccr_gateway": CCR_URL,
                "tier2_model": CCR_MODEL,
                "tier3_model": "Google Gemini (AI Studio)/gemini-3.8-flash",
                "tier4_local_moe": LOCAL_KIMI_URL,
            }
            self.wfile.write(json.dumps(status_data).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/v1/chat/completions":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
            messages = body.get("messages", [])
            model = body.get("model", "auto")

            try:
                answer, used_model = smart_generate(messages, model)
                resp = {
                    "id": f"chatcmpl-smart-{int(clock.now().timestamp())}",
                    "object": "chat.completion",
                    "created": int(clock.now().timestamp()),
                    "model": used_model,
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": answer},
                        "finish_reason": "stop"
                    }],
                    "usage": {
                        "prompt_tokens": sum(len(m.get("content", "")) // 4 for m in messages),
                        "completion_tokens": len(answer) // 4,
                        "total_tokens": (sum(len(m.get("content", "")) for m in messages) + len(answer)) // 4
                    }
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(resp).encode("utf-8"))
            except Exception as e:
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                err_resp = {"error": {"message": str(e)}}
                self.wfile.write(json.dumps(err_resp).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def run_server():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), RelevanceBridgeHandler)
    print(f"\n{'='*60}")
    print(f" Marzneshin Smart AI Gateway running on port {PORT}")
    print(f" Tier 1: Relevance AI Agent ({DEFAULT_AGENT_ID})")
    print(f" Tier 2: CCR Gateway ({CCR_MODEL})")
    print(f" Tier 3: CCR Gateway (gemini-3.8-flash)")
    print(f" Tier 4: Local Kimi K3 MoE ({LOCAL_KIMI_URL})")
    print(f"{'='*60}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Smart AI Gateway...")
        server.server_close()


if __name__ == "__main__":
    run_server()
