"""Calculator MCP server — add, subtract, multiply, evaluate_expression."""

import ast
import operator
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Calculator")

_OPERATORS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_safe_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        left, right = _safe_eval(node.left), _safe_eval(node.right)
        if isinstance(node.op, ast.Div) and right == 0:
            raise ValueError("Division by zero")
        return _OPERATORS[type(node.op)](left, right)
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract b from a."""
    return a - b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


@mcp.tool()
def evaluate_expression(expression: str) -> str:
    """Safely evaluate a math expression (numbers, +, -, *, /, **, parentheses)."""
    tree = ast.parse(expression.strip(), mode="eval")
    result = _safe_eval(tree)
    if result == int(result):
        return str(int(result))
    return str(result)


if __name__ == "__main__":
    mcp.run()
