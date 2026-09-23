from typing import Annotated, Sequence, TypedDict, Any, Literal
import operator
from langchain_core.messages import BaseMessage


class TaskSpec(TypedDict, total=False):
    task_id: str
    assigned_to: str
    title: str
    description: str
    target_files: list[str]
    memory_context: str
    iteration: int


class TaskResult(TypedDict, total=False):
    task_id: str
    worker: str
    status: Literal["SUCCESS", "FAILED", "BLOCKED"]
    summary: str
    artifacts_created: list[str]
    test_output: str
    tests_passed: bool
    error: str | None


class AgentState(TypedDict, total=False):
    """
    Context-Isolated State for Marzneshin Multi-Agent System.
    Prevents Context Window exhaustion by decoupling monolithic message history.
    Workers only receive TaskSpec and return TaskResult summaries.
    """
    objective: str
    current_task: str
    pending_tasks: list[TaskSpec]
    completed_results: Annotated[list[TaskResult], operator.add]
    active_workers: list[str]
    next_agent: str
    iteration: int
    max_iterations: int
    final_report: str
    agent_memory: dict[str, Any]
    fsp_events: Annotated[list[dict[str, Any]], operator.add]
    # Retained for backward compatibility with legacy threads
    messages: Annotated[Sequence[BaseMessage], operator.add]
