import sqlite3
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from .graph_state import AgentState
from .graph_nodes import supervisor_node, coder_node, reviewer_node, memory_node

# --- Define Routing Logic ---
def route_next(state: AgentState) -> Literal["Coder", "Memory", "Reviewer", "__end__"]:
    """Route to the next agent based on the supervisor's decision."""
    next_agent = state.get("next_agent", "FINISH")
    if next_agent == "FINISH":
        return END
    return next_agent

# --- Build the Graph ---
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("Supervisor", supervisor_node)
workflow.add_node("Coder", coder_node)
workflow.add_node("Reviewer", reviewer_node)
workflow.add_node("Memory", memory_node)

# Add edges
# We always start with the Supervisor
workflow.add_edge(START, "Supervisor")

# The Supervisor decides who goes next
workflow.add_conditional_edges(
    "Supervisor",
    route_next,
    {
        "Coder": "Coder",
        "Memory": "Memory",
        "Reviewer": "Reviewer",
        "__end__": END
    }
)

# After any worker finishes, they report back to the Supervisor
workflow.add_edge("Coder", "Supervisor")
workflow.add_edge("Reviewer", "Supervisor")
workflow.add_edge("Memory", "Supervisor")

# --- Configure Checkpointer for Persistence ---
# This ensures that state is saved locally and can be accessed across different IDEs via MCP.
# We store the sqlite DB inside the `state/` directory to adhere to marzneshin rules.
db_path = "state/langgraph_checkpoints.sqlite"
conn = sqlite3.connect(db_path, check_same_thread=False)
memory_saver = SqliteSaver(conn)

# Compile the graph
# We add an interrupt before Coder to allow Human-in-the-loop review if needed.
app = workflow.compile(
    checkpointer=memory_saver,
    interrupt_before=["Coder"]
)
