import sqlite3
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langgraph.checkpoint.sqlite import SqliteSaver

from .graph_state import AgentState, TaskSpec
from .graph_nodes import (
    supervisor_node,
    coder_node,
    reviewer_node,
    memory_node,
    aggregator_node,
)


def parallel_router(state: AgentState):
    """
    Fan-Out router:
    If next_agent is 'FINISH', route to END.
    If next_agent is 'parallel_dispatch', dispatch pending_tasks in parallel via Send.
    Otherwise, route to the designated single node.
    """
    next_agent = state.get("next_agent", "FINISH")
    if next_agent == "FINISH":
        return END

    pending = state.get("pending_tasks", [])
    if pending and next_agent == "parallel_dispatch":
        sends = []
        for task in pending:
            assigned = task.get("assigned_to", "Coder").capitalize()
            if assigned in ("Coder", "Reviewer"):
                sends.append(Send(assigned, task))
            else:
                sends.append(Send("Coder", task))
        if sends:
            return sends

    if next_agent in ("Coder", "Reviewer", "Memory", "Aggregator"):
        return next_agent

    return END


# --- Build the Graph ---
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("Supervisor", supervisor_node)
workflow.add_node("Coder", coder_node)
workflow.add_node("Reviewer", reviewer_node)
workflow.add_node("Memory", memory_node)
workflow.add_node("Aggregator", aggregator_node)

# Add edges
# Always start at Supervisor
workflow.add_edge(START, "Supervisor")

# Supervisor branches to parallel workers or END
workflow.add_conditional_edges(
    "Supervisor",
    parallel_router,
    ["Coder", "Reviewer", "Memory", "Aggregator", END]
)

# Parallel workers fan-in to Aggregator
workflow.add_edge("Coder", "Aggregator")
workflow.add_edge("Reviewer", "Aggregator")
workflow.add_edge("Memory", "Supervisor")

# Aggregator loops back to Supervisor for adjudication / next milestone
workflow.add_edge("Aggregator", "Supervisor")

# Checkpointer configuration
db_path = "state/langgraph_checkpoints.sqlite"
conn = sqlite3.connect(db_path, check_same_thread=False)
memory_saver = SqliteSaver(conn)

# Compile the graph
app = workflow.compile(
    checkpointer=memory_saver
)
