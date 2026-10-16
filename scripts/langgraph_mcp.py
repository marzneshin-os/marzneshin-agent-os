#!/usr/bin/env python3
"""Marzneshin LangGraph Multi-Agent MCP Server.

Implements Model Context Protocol (MCP) over stdio and SSE for:
- Antigravity
- Claude Code
- OpenCode / Cursor / Windsurf
- Graph & Loop Engineering (Prompts -> Agents -> Loops -> Graphs)
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uuid
import json
import asyncio
from typing import Any
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
import mcp.types as types
from langchain_core.messages import HumanMessage

from agents.langgraph_workflow import app as graph_app
from agents.graph_state import AgentState, TaskSpec, TaskResult
from agents.gate_nodes import evaluate_unit_gate
from adapters.graph_loop import GraphLoopAdapter

# Create the MCP Server instance
mcp_server = Server("marzneshin-langgraph")
adapter = GraphLoopAdapter(world="prod")


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
        ),
        types.Tool(
            name="start_graph_pipeline",
            description="Start an autonomous multi-agent pipeline using Graph & Loop engineering with blast-radius scoping and dual return paths.",
            inputSchema={
                "type": "object",
                "properties": {
                    "objective": {"type": "string", "description": "The mission objective to slice and execute."},
                    "max_iterations": {"type": "integer", "description": "Maximum loop iterations (default: 3).", "default": 3},
                    "allow_irreversible": {"type": "boolean", "description": "Whether to permit Lane 3 irreversible actions (Two-Key authorization).", "default": False}
                },
                "required": ["objective"]
            }
        ),
        types.Tool(
            name="evaluate_unit_gate",
            description="Evaluate a unit TaskResult against blast-radius gating policy (contained vs wide vs irreversible) with short/long return paths.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "ID of the unit to evaluate."},
                    "blast_radius": {"type": "string", "enum": ["contained", "wide", "irreversible"], "description": "Blast radius tier."},
                    "tests_passed": {"type": "boolean", "description": "Whether deterministic tests passed."},
                    "test_output": {"type": "string", "description": "Output or traceback from tests."},
                    "scope_violations": {"type": "array", "items": {"type": "string"}, "description": "Any files modified outside designated scope."},
                    "allow_irreversible": {"type": "boolean", "description": "Explicit approval for irreversible lane.", "default": False}
                },
                "required": ["task_id", "blast_radius", "tests_passed"]
            }
        ),
        types.Tool(
            name="query_learning_constraints",
            description="Query permanent architectural and engineering constraints learned across Graph & Loop runs.",
            inputSchema={
                "type": "object",
                "properties": {}
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

        for state_update in graph_app.stream(initial_state, config):
            pass

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

    elif name == "start_graph_pipeline":
        objective = arguments.get("objective", "Execute Graph & Loop Pipeline")
        max_iter = arguments.get("max_iterations", 3)
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        constraints_res = adapter.execute(
            "get_learned_constraints", {},
            idem_key=f"mcp-lc-{thread_id}", idem_class="none",
            dry_run=False, deadline=None, provenance=[]
        ) if hasattr(adapter, "_learned_constraints") else {"data": {"constraints": []}}
        learned = constraints_res.data.get("constraints", []) if hasattr(constraints_res, "data") else []

        initial_state: AgentState = {
            "objective": objective,
            "current_task": objective,
            "pending_tasks": [],
            "completed_results": [],
            "rejected_units": [],
            "learned_constraints": list(learned),
            "iteration": 0,
            "max_iterations": max_iter,
            "active_workers": ["Supervisor", "Splitter", "Coder", "CodeNode", "Reviewer", "Gate"]
        }

        for _ in graph_app.stream(initial_state, config):
            pass

        state = graph_app.get_state(config)
        vals = state.values if state else {}
        results = vals.get("completed_results", [])
        gate_verdicts = vals.get("gate_verdicts", [])
        report = vals.get("final_report", "Graph & Loop cycle finished.")

        green_c = sum(1 for v in gate_verdicts if v.get("verdict") == "GREEN")
        red_c = sum(1 for v in gate_verdicts if v.get("verdict") == "RED")
        blocked_c = sum(1 for v in gate_verdicts if v.get("verdict") == "BLOCKED")

        result_text = (
            f"Graph & Loop Pipeline Finished\n"
            f"Thread ID: {thread_id}\n"
            f"Total Slices: {len(results)}\n"
            f"Gate Verdicts: GREEN={green_c}, RED={red_c}, BLOCKED={blocked_c}\n"
            f"Permanent Constraints Learned: {len(vals.get('learned_constraints', []))}\n\n"
            f"Mission Report:\n{report}"
        )
        return [types.TextContent(type="text", text=result_text)]

    elif name == "evaluate_unit_gate":
        task_id = arguments.get("task_id", "T1")
        blast_radius = arguments.get("blast_radius", "contained")
        tests_passed = arguments.get("tests_passed", False)
        test_output = arguments.get("test_output", "")
        scope_violations = arguments.get("scope_violations", [])
        allow_irrev = arguments.get("allow_irreversible", False)

        task_res: TaskResult = {
            "task_id": task_id,
            "blast_radius": blast_radius,
            "tests_passed": tests_passed,
            "test_output": test_output,
            "scope_violations": scope_violations,
            "status": "SUCCESS" if tests_passed else "FAILED"
        }
        res = evaluate_unit_gate(task_res, allow_irreversible=allow_irrev)
        return [types.TextContent(type="text", text=json.dumps(res, indent=2))]

    elif name == "query_learning_constraints":
        constraints = getattr(adapter, "_learned_constraints", [
            "Always enforce fail-closed safety controls (§4)",
            "Return the unit, not the batch on verification failure",
            "Use deterministic code nodes for zero-variance data transforms",
        ])
        return [types.TextContent(type="text", text=json.dumps({"learned_constraints": constraints, "count": len(constraints)}, indent=2))]

    else:
        raise ValueError(f"Unknown tool: {name}")


async def run_stdio():
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="marzneshin-langgraph",
                server_version="2.1.0",
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
                    server_version="2.1.0",
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
            "tools": [
                "start_multiagent_task",
                "check_task_status",
                "provide_feedback",
                "start_graph_pipeline",
                "evaluate_unit_gate",
                "query_learning_constraints"
            ]
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
