---
description: FastMCP Tool Development & Lightweight Server Harness (Khairallah Stack #20)
---

**FASTMCP TOOL DEVELOPMENT**

Create type-safe Python MCP servers with minimal boilerplate:
1. **Import**: `from lib.fastmcp_harness import FastMCP`
2. **Initialize**: `mcp = FastMCP("my-server")`
3. **Decorate**: Use `@mcp.tool()` with typed function signatures.
4. **Run**: `mcp.run_stdio()`