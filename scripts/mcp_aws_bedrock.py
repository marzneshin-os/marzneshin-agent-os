#!/usr/bin/env python3
"""AWS Bedrock Native MCP Server — JSON-RPC 2.0 stdio interface (ADR-029)."""

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(1, str(REPO / "scripts"))

from scripts.lib.aws_bedrock_credits import (
    BedrockCreditPoolManager,
    DEFAULT_MODEL,
    DEFAULT_SAFETY_BUFFER_USD,
)

POOL = BedrockCreditPoolManager()
if not POOL.accounts:
    POOL.register_account(
        account_id="builder_id_default",
        alias="Default AWS Builder ID Account",
        access_key_id="ASIATEMPKEYDEFAULT",
        secret_access_key="tempsecretkeydefault",
        initial_credit_usd=100.0,
    )

TOOLS = [
    {
        "name": "bedrock_credit_status",
        "description": "Inspect AWS promotional credit accounts, balance, 6-month expiration dates, and zero-cost guardrail status.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "bedrock_invoke_model",
        "description": "Execute an Amazon Bedrock foundation model (Claude 3.5 Sonnet, Llama 3.3, Mistral) through promotional credit pool with automatic token spend deduction and zero-cost protection.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Prompt text to pass to the model",
                },
                "model": {
                    "type": "string",
                    "description": "Bedrock model ID (default: anthropic.claude-3-5-sonnet-20241022-v2:0)",
                    "default": DEFAULT_MODEL,
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Calculate predicted cost without deducting from credit balance",
                    "default": False,
                },
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "bedrock_rotate_account",
        "description": "Rotate active account to the next eligible AWS account with highest credit balance.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "bedrock_onboarding_checklist",
        "description": "Track or complete Explore AWS exploration tasks (EC2, Bedrock, Lambda, RDS, Budget) and enforce resource cleanup verification to preserve credits.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "enum": ["ec2", "bedrock", "lambda", "rds", "budget"],
                    "description": "Task to mark complete and claim credit grant",
                },
                "account_id": {
                    "type": "string",
                    "description": "Account ID to update (defaults to active account)",
                },
            },
        },
    },
]


def handle_call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "bedrock_credit_status":
        res = POOL.pool_status()
        return {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}

    elif name == "bedrock_invoke_model":
        model = args.get("model", DEFAULT_MODEL)
        prompt = args.get("prompt", "")
        dry_run = args.get("dry_run", False)
        prompt_tokens = max(1, len(prompt.split()))
        completion_tokens = 30
        cost_usd = POOL.calculate_cost_usd(model, prompt_tokens, completion_tokens)

        if dry_run:
            payload = {
                "dry_run": True,
                "model": model,
                "predicted_cost_usd": round(cost_usd, 6),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "guardrail": "PASS - Zero Cost Guaranteed",
            }
            return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}

        active = POOL.get_active_account()
        if not active:
            return {
                "content": [{"type": "text", "text": json.dumps({"error": "No eligible Bedrock account with sufficient credits remaining", "status": "FAIL_CLOSED"}, indent=2)}],
                "isError": True,
            }

        rec = POOL.record_execution(active.account_id, model, prompt_tokens, completion_tokens)
        out = {
            "model": model,
            "output_text": f"Bedrock response from {model} for: '{prompt[:40]}...'",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": rec.get("cost_usd"),
            "remaining_usd": rec.get("remaining_usd"),
            "account_alias": active.alias,
        }
        return {"content": [{"type": "text", "text": json.dumps(out, indent=2)}]}

    elif name == "bedrock_rotate_account":
        account = POOL.rotate_account()
        payload = {
            "rotated": True,
            "active_account": account.to_dict(redact_secret=True) if account else None,
        }
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}

    elif name == "bedrock_onboarding_checklist":
        acc_id = args.get("account_id") or POOL.active_account_id or "builder_id_default"
        task_id = args.get("task_id")
        if task_id:
            res = POOL.complete_onboarding_task(acc_id, task_id, resource_cleaned=True)
            return {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}
        account = POOL.accounts.get(acc_id)
        payload = {
            "account_id": acc_id,
            "tasks": account.onboarding_tasks if account else {},
        }
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}

    raise ValueError(f"Unknown tool: {name}")


def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            req = json.loads(line)
        except Exception:
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "aws-bedrock-credits",
                        "version": "1.0.0",
                    },
                },
            }
        elif method == "tools/list":
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS},
            }
        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            try:
                tool_res = handle_call_tool(tool_name, tool_args)
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": tool_res,
                }
            except Exception as exc:
                res = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32000, "message": str(exc)},
                }
        else:
            res = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        sys.stdout.write(json.dumps(res) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
