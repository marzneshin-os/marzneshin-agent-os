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
from agents.graph_state import AgentState

# Create the MCP Server instance
mcp_server = Server("marzneshin-langgraph")


async def handle_list_tools() -> list[types.Tool]:
    """List the MCP tools exposed by our LangGraph integration."""
    return [
        types.Tool(
            name="start_multiagent_task",
            description="Start a new task using the isolated parallel LangGraph Multi-Agent system.",
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
            description="Provide feedback or next objective to an existing LangGraph thread.",
            inputSchema={
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string", "description": "The ID of the thread."},
                    "feedback": {"type": "string", "description": "Your feedback or instruction."}
                },
                "required": ["thread_id", "feedback"]
            }
        )
    ]


async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    arguments = arguments or {}

    if name == "start_multiagent_task":
        objective = arguments.get("objective", "Execute task")
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        initial_state: AgentState = {
            "objective": objective,
            "current_task": objective,
            "pending_tasks": [],
            "completed_results": [],
            "iteration": 0,
            "max_iterations": 3,
            "messages": [HumanMessage(content=objective)]
        }

        final_update = None
        for state_update in graph_app.stream(initial_state, config):
            final_update = state_update

        # Retrieve saved state
        state = graph_app.get_state(config)
        vals = state.values if state else {}
        results = vals.get("completed_results", [])
        report = vals.get("final_report", "Multi-agent task initiated.")

        result_text = (
            f"Task Started. Thread ID: {thread_id}\n"
            f"Status: {vals.get('next_agent', 'COMPLETED')}\n"
            f"Subagent Tasks Executed: {len(results)}\n\n"
            f"Summary:\n{report}"
        )
        return [types.TextContent(type="text", text=result_text)]

    elif name == "check_task_status":
        thread_id = arguments.get("thread_id", "")
        config = {"configurable": {"thread_id": thread_id}}

        state = graph_app.get_state(config)
        next_steps = state.next if state else []
        vals = state.values if state else {}
        results = vals.get("completed_results", [])
        report = vals.get("final_report", "In progress.")

        status_text = (
            f"Thread ID: {thread_id}\n"
            f"Pending Nodes: {next_steps}\n"
            f"Subagent Results Count: {len(results)}\n\n"
            f"Latest Report:\n{report}"
        )
        return [types.TextContent(type="text", text=status_text)]

    elif name == "provide_feedback":
        thread_id = arguments.get("thread_id", "")
        feedback = arguments.get("feedback", "")
        config = {"configurable": {"thread_id": thread_id}}

        graph_app.update_state(
            config,
            {
                "objective": feedback,
                "current_task": feedback,
                "next_agent": "Supervisor",
                "completed_results": []
            }
        )

        for _ in graph_app.stream(None, config):
            pass

        state = graph_app.get_state(config)
        vals = state.values if state else {}
        report = vals.get("final_report", "Iteration complete.")

        result_text = f"Thread {thread_id} resumed with feedback.\n\nReport:\n{report}"
        return [types.TextContent(type="text", text=result_text)]

    else:
        raise ValueError(f"Unknown tool: {name}")


async def run_stdio():
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="marzneshin-langgraph",
                server_version="2.0.0",
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
                    server_version="2.0.0",
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
    parser.add_argument("--port", type=int, default=None, help="TCP port to run SSE/HTTP server. If omitted, runs via stdio.")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface to bind (default: 127.0.0.1)")
    args = parser.parse_args()

    if args.port:
        run_sse(host=args.host, port=args.port)
    else:
        asyncio.run(run_stdio())


if __name__ == "__main__":
    main()


if hasattr(mcp_server, "list_tools"):
    handle_list_tools = mcp_server.list_tools()(handle_list_tools)
if hasattr(mcp_server, "call_tool"):
    handle_call_tool = mcp_server.call_tool()(handle_call_tool)
