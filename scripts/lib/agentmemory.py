"""AgentMemory client helper."""
import json
import urllib.request
import urllib.parse
import urllib.error
import os

AGENTMEMORY_URL = os.environ.get("AGENTMEMORY_URL", "http://localhost:3111")

def call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Invokes the agentmemory REST API instead of spawning an MCP process."""
    try:
        if tool_name == "memory_save":
            url = f"{AGENTMEMORY_URL}/agentmemory/remember"
            data = {"content": arguments.get("content")}
        elif tool_name == "memory_smart_search":
            url = f"{AGENTMEMORY_URL}/agentmemory/smart-search"
            data = {"query": arguments.get("query"), "limit": arguments.get("limit", 10)}
        elif tool_name == "memory_search":
            url = f"{AGENTMEMORY_URL}/agentmemory/search"
            data = {"q": arguments.get("query")}
        else:
            return f"AgentMemory error: REST mapping for {tool_name} not implemented."

        req = urllib.request.Request(
            url,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        if data is not None:
            req.data = json.dumps(data).encode("utf-8")
        
        with urllib.request.urlopen(req, timeout=5) as response:
            resp_data = json.loads(response.read().decode())
            return json.dumps(resp_data, ensure_ascii=False)
            
    except urllib.error.URLError as e:
        return f"AgentMemory error: Could not connect to {AGENTMEMORY_URL} - {e}"
    except Exception as e:
        return f"AgentMemory error: {e}"
