---
name: fastmcp
description: FastMCP tool development and server harness for Python (Khairallah Stack Tool #20). Use when authoring new MCP tools, scaffolding stdio servers, or exposing Python functions to Claude Code.
---

# FastMCP Python Development Harness

FastMCP provides an ultra-minimal, type-safe pattern for authoring Model Context Protocol (MCP) servers in Python without external dependency bloat.

## Quickstart

```python
from lib.fastmcp_harness import FastMCP

mcp = FastMCP("demo-tools", version="1.0.0")

@mcp.tool(description="Calculate factorial of an integer")
def factorial(n: int) -> int:
    import math
    return math.factorial(n)

if __name__ == "__main__":
    mcp.run_stdio()
```

## Core Rules
1. **Type Annotations**: Always annotate parameter and return types (`int`, `str`, `float`, `bool`, `list`, `dict`) so input schemas generate automatically.
2. **Docstrings**: Write clear docstrings on functions; FastMCP uses them directly as tool descriptions for LLMs.
3. **Stdlib-Only**: Keep server scripts lightweight and compliant with `scripts/verify.py --lint-imports`.