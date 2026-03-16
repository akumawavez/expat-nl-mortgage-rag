"""
Phase 4: Multi-agent – orchestrator routes to specialist agents (retrieval, location, calculator).

Orchestrator decides which specialist(s) to invoke from the user query; each specialist
uses existing tools (retrieval, nearby_places, osrm, area_safety, calculator logic).
Returns combined context, tool_calls, and optional A2UI directives.
"""
from __future__ import annotations

from typing import Any

# Specialist names for tool-usage visibility
SPEC_RETRIEVAL = "retrieval_agent"
SPEC_LOCATION = "location_agent"
SPEC_CALCULATOR = "calculator_agent"


def route_query(query: str) -> list[str]:
    """
    Route user query to specialist(s). Returns list of specialist names to invoke.
    Simple keyword-based routing; can be replaced by LLM-based router.
    """
    q = query.lower().strip()
    specialists = []
    if any(w in q for w in ("near", "address", "commute", "distance", "route", "safety", "area", "poi", "school", "supermarket")):
        specialists.append(SPEC_LOCATION)
    if any(w in q for w in ("monthly", "mortgage", "calculate", "bruto", "maandlast", "hypotheek", "eigen inleg", "kosten koper")):
        specialists.append(SPEC_CALCULATOR)
    # Retrieval for document questions (default)
    if any(w in q for w in ("deduct", "tax", "nhg", "belasting", "document", "interest", "hypotheekrente", "guarantee")) or not specialists:
        specialists.append(SPEC_RETRIEVAL)
    return list(dict.fromkeys(specialists))  # preserve order, no dupes


def run_orchestrator(
    query: str,
    retrieval_fn: callable,
    location_fn: callable,
    calculator_fn: callable,
) -> tuple[str, list[dict], list[dict], list[str]]:
    """
    Run orchestrator: route query, invoke specialists, aggregate results.
    Each fn(query) returns (context_str, tool_calls).
    Returns (combined_context, all_tool_calls, a2ui_directives, specialists_invoked).
    """
    specialists = route_query(query)
    combined = []
    tool_calls = []
    directives = []
    for spec in specialists:
        tool_calls.append({"tool": spec, "args": {"query": query[:80]}})
        if spec == SPEC_RETRIEVAL:
            ctx, tc = retrieval_fn(query)
            combined.append(ctx)
            tool_calls.extend(tc)
        elif spec == SPEC_LOCATION:
            ctx, tc = location_fn(query)
            combined.append(ctx)
            tool_calls.extend(tc)
            directives.append("show_map")
        elif spec == SPEC_CALCULATOR:
            ctx, tc = calculator_fn(query)
            combined.append(ctx)
            tool_calls.extend(tc)
            directives.append("show_calculator")
    a2ui = [{"type": d, "payload": {}} for d in directives]
    return "\n\n---\n\n".join(c for c in combined if c), tool_calls, a2ui, specialists
