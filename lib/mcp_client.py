"""
Phase 4: MCP client – list and call tools from MCP servers.

When MCP server(s) are configured, tools (e.g. OSRM, search, safety) are registered
and can be invoked by the agent; tool usage appears in Tools Used.
"""
from __future__ import annotations

from typing import Any, Callable

# In-memory registry of "MCP" tools (name -> callable) for demo without full MCP SDK.
# Real implementation would use MCP protocol to discover and call remote tools.
_MCP_TOOLS: dict[str, Callable[..., tuple[Any, list[dict]]]] = {}


def register_mcp_tool(name: str, fn: Callable[..., tuple[Any, list[dict]]]) -> None:
    """Register a tool that will appear as MCP in Tools Used."""
    _MCP_TOOLS[name] = fn


def list_mcp_tools() -> list[str]:
    """Return names of registered MCP tools."""
    return list(_MCP_TOOLS.keys())


def call_mcp_tool(name: str, **kwargs: Any) -> tuple[Any, list[dict]]:
    """
    Call a registered MCP tool by name. Returns (result, tool_calls_for_ui).
    If tool not found, returns (None, [{"tool": f"mcp_{name}", "args": kwargs}]).
    """
    if name in _MCP_TOOLS:
        result, tool_calls = _MCP_TOOLS[name](**kwargs)
        return result, tool_calls
    return None, [{"tool": f"mcp_{name}", "args": kwargs}]


def register_default_mcp_tools() -> None:
    """Register demo tools so MCP has at least one tool (e.g. osrm_commute wrapper)."""
    try:
        from lib.location import osrm_commute
        def mcp_osrm(origin: str, destination: str):
            res, tc = osrm_commute(origin, destination)
            tc = [{"tool": "mcp_osrm_commute", "args": {"origin": origin[:50], "destination": destination[:50]}}]
            return res, tc
        register_mcp_tool("osrm_commute", mcp_osrm)
    except Exception:
        pass
