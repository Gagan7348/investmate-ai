"""
InvestMate AI — Tool Registry

Maintains the allowlist of approved tools, their schemas, and provides
validation for tool arguments proposed by the LLM.
"""

from __future__ import annotations

from agent.tools import TOOL_DEFINITIONS, TOOL_MAP


def get_tool_names() -> list[str]:
    """Return names of all registered tools."""
    return list(TOOL_MAP.keys())


def is_valid_tool(name: str) -> bool:
    """Check if a tool name is in the approved allowlist."""
    return name in TOOL_MAP


def get_tool_schemas() -> list[dict]:
    """Return schemas for all tools (used to inform the LLM)."""
    return TOOL_DEFINITIONS


def validate_tool_call(tool_name: str, arguments: dict) -> tuple[bool, str]:
    """
    Validate a tool call proposed by the LLM.

    Returns (is_valid, error_message).
    """
    if not is_valid_tool(tool_name):
        return False, f"Tool '{tool_name}' is not in the approved tool list."

    if "portfolio_id" not in arguments:
        return False, "Missing required argument: portfolio_id"

    # Validate portfolio_id is an integer
    try:
        int(arguments["portfolio_id"])
    except (ValueError, TypeError):
        return False, "portfolio_id must be an integer."

    return True, ""
