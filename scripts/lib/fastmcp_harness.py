"""FastMCP Tool Development Harness (Khairallah Stack Tool #20).

Lightweight, high-resilience implementation of Jeremiah Lowin's FastMCP pattern
using Python 3 stdlib only. Enables authoring type-safe MCP servers with
@mcp.tool() decorators, automatic schema generation, and zero external dependencies.
"""

from __future__ import annotations

import inspect
import json
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple, get_type_hints

from . import clock


def _py_type_to_json_schema(py_type: Any) -> Dict[str, Any]:
    """Convert standard Python type annotations into JSON Schema type definitions."""
    if py_type is int:
        return {"type": "integer"}
    elif py_type is float:
        return {"type": "number"}
    elif py_type is bool:
        return {"type": "boolean"}
    elif py_type is str:
        return {"type": "string"}
    elif py_type is list or getattr(py_type, "__origin__", None) is list:
        return {"type": "array"}
    elif py_type is dict or getattr(py_type, "__origin__", None) is dict:
        return {"type": "object"}
    return {"type": "string"}


class FastMCP:
    """Zero-dependency FastMCP Server implementation for Marzneshin Agent OS."""

    def __init__(self, name: str, version: str = "1.0.0", description: str = "") -> None:
        self.name = name
        self.version = version
        self.description = description
        self.tools: Dict[str, Callable[..., Any]] = {}
        self.tools_spec: List[Dict[str, Any]] = []
        self.resources: Dict[str, Tuple[str, Callable[[], str]]] = {}

    def tool(self, name: Optional[str] = None, description: Optional[str] = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register a Python function as an MCP tool."""
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = name or fn.__name__
            doc = description or inspect.getdoc(fn) or f"Execute {tool_name}"
            sig = inspect.signature(fn)
            type_hints = get_type_hints(fn)

            properties: Dict[str, Any] = {}
            required: List[str] = []

            for param_name, param in sig.parameters.items():
                if param_name in ("self", "cls"):
                    continue
                param_type = type_hints.get(param_name, str)
                schema_field = _py_type_to_json_schema(param_type)
                schema_field["description"] = f"Parameter {param_name}"
                properties[param_name] = schema_field

                if param.default is inspect.Parameter.empty:
                    required.append(param_name)

            spec = {
                "name": tool_name,
                "description": doc,
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }

            self.tools[tool_name] = fn
            self.tools_spec.append(spec)
            return fn
        return decorator

    def resource(self, uri: str, name: Optional[str] = None, description: Optional[str] = None) -> Callable[[Callable[[], str]], Callable[[], str]]:
        """Decorator to register a read-only resource URI."""
        def decorator(fn: Callable[[], str]) -> Callable[[], str]:
            res_name = name or fn.__name__
            self.resources[uri] = (res_name, fn)
            return fn
        return decorator

    def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Execute a registered tool and return the string result."""
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found on FastMCP server '{self.name}'.")
        fn = self.tools[tool_name]
        res = fn(**args)
        if isinstance(res, (dict, list)):
            return json.dumps(res, indent=2)
        return str(res)

    def run_stdio(self) -> None:
        """Run the JSON-RPC 2.0 stdio event loop."""
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except Exception:
                continue

            method = req.get("method")
            req_id = req.get("id")

            if method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "experimental": {},
                            "tools": {"listChanged": False},
                            "resources": {}
                        },
                        "serverInfo": {
                            "name": self.name,
                            "version": self.version
                        }
                    }
                }
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()

            elif method == "notifications/initialized":
                pass

            elif method == "tools/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": self.tools_spec
                    }
                }
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()

            elif method == "tools/call":
                params = req.get("params", {})
                tool_name = params.get("name", "")
                args = params.get("arguments", {})
                try:
                    text_out = self.execute_tool(tool_name, args)
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": text_out}]
                        }
                    }
                except Exception as e:
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                            "isError": True
                        }
                    }
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()

            elif req_id is not None:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method '{method}' not found"
                    }
                }
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()