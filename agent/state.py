"""LangGraph agent state."""

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    user_query: str
    tool_catalog: list[dict[str, Any]]
    plan: dict[str, Any]
    tool_calls: list[dict[str, Any]]
    observations: list[dict[str, Any]]
    iteration: int
    max_iterations: int
    is_complete: bool
    final_answer: str
