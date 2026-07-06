"""LangGraph loop: discover → plan → execute → observe → respond."""

from __future__ import annotations

import json
import os
from typing import Any, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from agent.mcp_manager import MCPMarketplace
from agent.state import AgentState

MAX_ITERATIONS_DEFAULT = 5


def build_graph(marketplace: MCPMarketplace):
    llm = ChatAnthropic(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        temperature=0,
    )

    async def discover_tools(state: AgentState) -> dict[str, Any]:
        catalog = await marketplace.discover_all()
        tool_catalog = [t.to_llm_dict() for t in catalog]
        summary = ", ".join(t.qualified_name for t in catalog) or "(none)"
        return {
            "tool_catalog": tool_catalog,
            "messages": [
                SystemMessage(
                    content=f"Discovered {len(catalog)} tools from MCP marketplace: {summary}"
                )
            ],
            "iteration": 0,
            "max_iterations": state.get("max_iterations", MAX_ITERATIONS_DEFAULT),
            "observations": [],
            "is_complete": False,
        }

    async def plan(state: AgentState) -> dict[str, Any]:
        catalog_json = json.dumps(state.get("tool_catalog", []), indent=2)
        obs_text = _format_observations(state.get("observations", []))
        prompt = f"""You are a planner for an MCP tool marketplace agent.

User request: {state.get("user_query", "")}

Available tools (qualified_name = server__tool):
{catalog_json}

Previous tool results:
{obs_text or "None yet."}

Decide the next step. Return ONLY valid JSON with this shape:
{{
  "reasoning": "brief explanation",
  "is_complete": false,
  "tool_calls": [
    {{"qualified_name": "server__tool", "arguments": {{}}}}
  ]
}}

Rules:
- Use qualified_name exactly as listed.
- Set is_complete true only when you have enough information to answer the user without more tools.
- When is_complete is true, tool_calls must be [].
- Order tool_calls for dependencies (e.g. search before fetch_page).
- Use at most 3 tool calls per iteration.
"""
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        plan = _parse_json(response.content)
        return {
            "plan": plan,
            "is_complete": bool(plan.get("is_complete")),
            "tool_calls": plan.get("tool_calls", []),
        }

    async def execute_tool(state: AgentState) -> dict[str, Any]:
        new_observations = list(state.get("observations", []))
        for call in state.get("tool_calls", []):
            qname = call.get("qualified_name", "")
            args = call.get("arguments", {})
            try:
                result = await marketplace.call_qualified(qname, args)
                new_observations.append(
                    {
                        "qualified_name": qname,
                        "arguments": args,
                        "result": result.content,
                        "error": result.is_error,
                    }
                )
            except Exception as exc:
                new_observations.append(
                    {
                        "qualified_name": qname,
                        "arguments": args,
                        "result": str(exc),
                        "error": True,
                    }
                )
        return {"observations": new_observations}

    def observe(state: AgentState) -> dict[str, Any]:
        iteration = state.get("iteration", 0) + 1
        max_it = state.get("max_iterations", MAX_ITERATIONS_DEFAULT)
        forced = iteration >= max_it
        complete = state.get("is_complete", False) or forced
        return {"iteration": iteration, "is_complete": complete}

    async def respond(state: AgentState) -> dict[str, Any]:
        obs_text = _format_observations(state.get("observations", []))
        prompt = f"""Answer the user based on tool results. Be concise and helpful.

User: {state.get("user_query", "")}

Tool results:
{obs_text or "No tools were run."}
"""
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        text = response.content if isinstance(response.content, str) else str(response.content)
        return {
            "final_answer": text,
            "messages": [AIMessage(content=text)],
        }

    def route_after_observe(state: AgentState) -> Literal["plan", "respond"]:
        if state.get("is_complete"):
            return "respond"
        return "plan"

    graph = StateGraph(AgentState)
    graph.add_node("discover_tools", discover_tools)
    graph.add_node("plan", plan)
    graph.add_node("execute_tool", execute_tool)
    graph.add_node("observe", observe)
    graph.add_node("respond", respond)

    graph.set_entry_point("discover_tools")
    graph.add_edge("discover_tools", "plan")
    graph.add_edge("plan", "execute_tool")
    graph.add_edge("execute_tool", "observe")
    graph.add_conditional_edges("observe", route_after_observe, {"plan": "plan", "respond": "respond"})
    graph.add_edge("respond", END)

    return graph.compile()


def _format_observations(observations: list[dict[str, Any]]) -> str:
    lines = []
    for o in observations:
        status = "ERROR" if o.get("error") else "OK"
        lines.append(
            f"- [{status}] {o.get('qualified_name')}({json.dumps(o.get('arguments', {}))}): "
            f"{o.get('result', '')[:2000]}"
        )
    return "\n".join(lines)


def _parse_json(content: str | list) -> dict[str, Any]:
    text = content if isinstance(content, str) else str(content)
    text = text.strip()
    if "```" in text:
        start = text.find("```")
        end = text.rfind("```")
        inner = text[start + 3 : end].strip()
        if inner.startswith("json"):
            inner = inner[4:].strip()
        text = inner
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "reasoning": "Failed to parse plan",
            "is_complete": False,
            "tool_calls": [],
        }
