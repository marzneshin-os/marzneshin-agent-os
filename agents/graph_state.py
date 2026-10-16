from typing import Annotated, Sequence, TypedDict, Any, Literal
import operator
from langchain_core.messages import BaseMessage

BlastRadius = Literal["contained", "wide", "irreversible"]
Reversibility = Literal["high", "medium", "none"]
GateVerdict = Literal["GREEN", "RED", "BLOCKED"]


class TaskSpec(TypedDict, total=False):
    task_id: str
    assigned_to: str
    title: str
    description: str
    target_files: list[str]
    scope_constraint: str
    memory_context: str
    iteration: int
    blast_radius: BlastRadius
    reversibility: Reversibility
    attempts: int
    max_attempts: int
    verdict_evidence: str
    is_code_node: bool
    code_transform_op: str
    code_transform_payload: dict[str, Any]


class TaskResult(TypedDict, total=False):
    task_id: str
    worker: str
    status: Literal["SUCCESS", "FAILED", "BLOCKED"]
    verdict: GateVerdict
    blast_radius: BlastRadius
    reversibility: Reversibility
    summary: str
    artifacts_created: list[str]
    test_output: str
    tests_passed: bool
    scope_violations: list[str]
    attempts_used: int
    derived_constraint: str
    error: str | None


class AgentState(TypedDict, total=False):
    """
    Context-Isolated State for Marzneshin Multi-Agent System (Graph & Loop Engineering).
    Prevents Context Window exhaustion by decoupling monolithic message history.
    Workers only receive TaskSpec and return TaskResult summaries.
    Supports 4-layer taxonomy: Prompts -> Agents -> Loops -> Graphs.
    """
    objective: str
    current_task: str
    pending_tasks: list[TaskSpec]
    completed_results: Annotated[list[TaskResult], operator.add]
    rejected_units: list[TaskSpec]
    learned_constraints: Annotated[list[str], operator.add]
    active_workers: list[str]
    next_agent: str
    iteration: int
    max_iterations: int
    final_report: str
    blast_radius_summary: dict[str, int]
    gate_verdicts: Annotated[list[dict[str, Any]], operator.add]
    agent_memory: dict[str, Any]
    fsp_events: Annotated[list[dict[str, Any]], operator.add]
    messages: Annotated[Sequence[BaseMessage], operator.add]
