from typing import Annotated, Sequence, TypedDict, Any
import operator
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """
    The State of the LangGraph multi-agent system.
    - messages: Holds the conversation history.
    - current_task: The active task id or objective.
    - next_agent: The next agent to be invoked by the supervisor.
    - agent_memory: Context pulled from the @agentmemory/mcp server.
    - fsp_events: A list of events to be emitted to maintain marzneshin protocol.
    """
    messages: Annotated[Sequence[BaseMessage], operator.add]
    current_task: str
    next_agent: str
    agent_memory: dict[str, Any]
    fsp_events: Annotated[list[dict[str, Any]], operator.add]
