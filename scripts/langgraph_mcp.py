import os
import sys
from pathlib import Path

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uuid
import asyncio
from typing import Any
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
import mcp.types as types
from langchain_core.messages import HumanMessage

# Import our compiled LangGraph workflow
from agents.langgraph_workflow import app as graph_app

# Create the MCP Server instance
mcp_server = Server("marzneshin-langgraph")

@mcp_server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List the MCP tools exposed by our LangGraph integration.
    """
    return [
        types.Tool(
            name="start_multiagent_task",
            description="Start a new task using the LangGraph Multi-Agent system (Supervisor + Workers).",
            inputSchema={
                "type": "object",
                "properties": {
                    "objective": {"type": "string", "description": "The task or question to process."},
                },
                "required": ["objective"]
            }
        ),
        types.Tool(
            name="check_task_status",
            description="Check the current status and pending actions of an existing LangGraph thread.",
            inputSchema={
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string", "description": "The ID of the thread to check."}
                },
                "required": ["thread_id"]
            }
        ),
        types.Tool(
            name="provide_feedback",
            description="Provide human feedback to a suspended LangGraph thread and resume it.",
            inputSchema={
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string", "description": "The ID of the thread."},
                    "feedback": {"type": "string", "description": "Your feedback or instruction to continue."}
                },
                "required": ["thread_id", "feedback"]
            }
        )
    ]

@mcp_server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle tool executions.
    """
    if name == "start_multiagent_task":
        objective = arguments.get("objective")
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        
        # Initialize state with the human request
        initial_state = {"messages": [HumanMessage(content=objective)]}
        
        # Run graph until it hits an interrupt (Human-in-the-loop) or END
        # Using stream to process events if needed, but for MCP a synchronous run to first yield is good
        final_state = None
        for state_update in graph_app.stream(initial_state, config):
            final_state = state_update
            
        result_text = f"Task started. Thread ID: {thread_id}\n\nCurrent state:\n{final_state}"
        return [types.TextContent(type="text", text=result_text)]
        
    elif name == "check_task_status":
        thread_id = arguments.get("thread_id")
        config = {"configurable": {"thread_id": thread_id}}
        
        # Get current state from sqlite checkpointer
        state = graph_app.get_state(config)
        next_steps = state.next
        
        status_text = f"Thread ID: {thread_id}\nPending nodes: {next_steps}\n"
        if state.values:
            msgs = state.values.get("messages", [])
            last_msg = msgs[-1].content if msgs else "No messages."
            status_text += f"\nLast Message:\n{last_msg}"
            
        return [types.TextContent(type="text", text=status_text)]
        
    elif name == "provide_feedback":
        thread_id = arguments.get("thread_id")
        feedback = arguments.get("feedback")
        config = {"configurable": {"thread_id": thread_id}}
        
        # Inject feedback and resume
        graph_app.update_state(config, {"messages": [HumanMessage(content=feedback)]})
        
        final_state = None
        for state_update in graph_app.stream(None, config): # Resume with None input
            final_state = state_update
            
        result_text = f"Thread {thread_id} resumed.\n\nNew state:\n{final_state}"
        return [types.TextContent(type="text", text=result_text)]
        
    else:
        raise ValueError(f"Unknown tool: {name}")

async def run_stdio():
    # Run the MCP server via stdio
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="marzneshin-langgraph",
                server_version="1.0.0",
                capabilities=mcp_server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                )
            )
        )

def run_sse(host: str = "127.0.0.1", port: int = 8005):
    import uvicorn
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from mcp.server.sse import SseServerTransport

    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="marzneshin-langgraph",
                    server_version="1.0.0",
                    capabilities=mcp_server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    )
                )
            )

    async def handle_messages(request):
        await sse.handle_post_message(request.scope, request.receive, request._send)

    async def health(request):
        return JSONResponse({
            "status": "ok",
            "service": "marzneshin-langgraph",
            "transport": "sse",
            "tools": ["start_multiagent_task", "check_task_status", "provide_feedback"]
        })

    routes = [
        Route("/", endpoint=health, methods=["GET"]),
        Route("/health", endpoint=health, methods=["GET"]),
        Route("/sse", endpoint=handle_sse, methods=["GET"]),
        Route("/messages/", endpoint=handle_messages, methods=["POST"]),
    ]

    app = Starlette(debug=False, routes=routes)
    uvicorn.run(app, host=host, port=port, log_level="warning")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Marzneshin LangGraph Multi-Agent MCP Server")
    parser.add_argument("--port", type=int, default=None, help="TCP port to run SSE/HTTP server (e.g. 8005). If omitted, runs via stdio.")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface to bind (default: 127.0.0.1)")
    args = parser.parse_args()

    if args.port:
        run_sse(host=args.host, port=args.port)
    else:
        asyncio.run(run_stdio())

if __name__ == "__main__":
    main()
