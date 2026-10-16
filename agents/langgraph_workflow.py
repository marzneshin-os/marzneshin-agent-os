import sqlite3
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langgraph.checkpoint.sqlite import SqliteSaver

from .graph_state import AgentState, TaskSpec
from .graph_nodes import (
    supervisor_node,
    splitter_node,
    coder_node,
    reviewer_node,
    memory_node,
    aggregator_node,
)
from .code_nodes import code_node
from .gate_nodes import gate_node


def parallel_router(state: AgentState):
    """
    Fan-Out router:
    If next_agent is 'FINISH', route to END.
    If next_agent is 'parallel_dispatch':
      Routes pending_tasks or rejected_units in parallel via Send:
      - is_code_node or assigned_to == 'CodeNode' -> Send('CodeNode', task)
      - assigned_to == 'Reviewer' -> Send('Reviewer', task)
      - otherwise -> Send('Coder', task)
    """
    next_agent = state.get("next_agent", "FINISH")
    if next_agent == "FINISH":
        return END

    pending = state.get("pending_tasks", []) or state.get("rejected_units", [])
    if pending and next_agent == "parallel_dispatch":
        sends = []
        for task in pending:
            assigned = task.get("assigned_to", "Coder").capitalize()
            is_code = task.get("is_code_node", False) or assigned == "Codenode"
            if is_code:
                sends.append(Send("CodeNode", task))
            elif assigned == "Reviewer":
                sends.append(Send("Reviewer", task))
            else:
                sends.append(Send("Coder", task))
        if sends:
            return sends

    if next_agent in ("Coder", "CodeNode", "Reviewer", "Memory", "Aggregator", "Gate", "Splitter", "Supervisor"):
        return next_agent

    return END


# --- Build the Graph ---
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("Supervisor", supervisor_node)
workflow.add_node("Splitter", splitter_node)
workflow.add_node("Coder", coder_node)
workflow.add_node("CodeNode", code_node)
workflow.add_node("Reviewer", reviewer_node)
workflow.add_node("Memory", memory_node)
workflow.add_node("Aggregator", aggregator_node)
workflow.add_node("Gate", gate_node)

# Add edges
# Always start at Supervisor
workflow.add_edge(START, "Supervisor")

# Supervisor branches to parallel workers, Splitter, Gate, or END
workflow.add_conditional_edges(
    "Supervisor",
    parallel_router,
    ["Coder", "CodeNode", "Reviewer", "Memory", "Aggregator", "Gate", "Splitter", END]
)

# Splitter branches to parallel workers
workflow.add_conditional_edges(
    "Splitter",
    parallel_router,
    ["Coder", "CodeNode", "Reviewer", "Memory", "Aggregator", "Gate", END]
)

# Parallel workers fan-in to Aggregator
workflow.add_edge("Coder", "Aggregator")
workflow.add_edge("CodeNode", "Aggregator")
workflow.add_edge("Reviewer", "Aggregator")
workflow.add_edge("Memory", "Supervisor")

# Aggregator loops to Gate (Blast-Radius Gating)
workflow.add_edge("Aggregator", "Gate")

# Gate routes:
# If rejected units -> Correction Edge: dispatches only the rejected units back to workers!
# If all passed or max iterations -> routes to Supervisor or parallel_dispatch
workflow.add_conditional_edges(
    "Gate",
    parallel_router,
    ["Coder", "CodeNode", "Reviewer", "Supervisor", END]
)

# Checkpointer configuration
db_path = "state/langgraph_checkpoints.sqlite"
conn = sqlite3.connect(db_path, check_same_thread=False)
memory_saver = SqliteSaver(conn)

# Compile the graph
app = workflow.compile(
    checkpointer=memory_saver
)
