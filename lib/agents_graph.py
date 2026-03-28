"""
LangGraph-based Phase 4 orchestrator: same behavior as run_orchestrator with an explicit graph
(router → specialist nodes → merge). See codedocs/agentic_frameworks_langgraph_plan.md.
"""
from __future__ import annotations

from typing import Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from lib.agents import (
    SPEC_CALCULATOR,
    SPEC_LOCATION,
    SPEC_RETRIEVAL,
    route_query,
)

SpecialistFn = Callable[[str], tuple[str, list[dict]]]


class OrchestratorState(TypedDict, total=False):
    """Graph state; mirrors orchestrator outputs after merge."""

    query: str
    specialists: list[str]
    idx: int
    combined_parts: list[str]
    tool_calls: list[dict]
    directive_types: list[str]
    specialists_invoked: list[str]
    combined_context: str
    a2ui_directives: list[dict]


def _dispatch(state: OrchestratorState) -> str:
    specs = state.get("specialists") or []
    idx = int(state.get("idx", 0))
    if idx >= len(specs):
        return "merge"
    spec = specs[idx]
    if spec == SPEC_RETRIEVAL:
        return "retrieval"
    if spec == SPEC_LOCATION:
        return "location"
    if spec == SPEC_CALCULATOR:
        return "calculator"
    return "merge"


def _router(state: OrchestratorState) -> dict:
    q = state["query"]
    specs = route_query(q)
    return {
        "specialists": specs,
        "idx": 0,
        "combined_parts": [],
        "tool_calls": [],
        "directive_types": [],
        "specialists_invoked": [],
    }


def _make_specialist_nodes(
    retrieval_fn: SpecialistFn,
    location_fn: SpecialistFn,
    calculator_fn: SpecialistFn,
) -> tuple[
    Callable[[OrchestratorState], dict],
    Callable[[OrchestratorState], dict],
    Callable[[OrchestratorState], dict],
]:
    def retrieval_node(s: OrchestratorState) -> dict:
        q = s["query"]
        idx = int(s["idx"])
        spec = s["specialists"][idx]
        tc = list(s.get("tool_calls", []))
        tc.append({"tool": spec, "args": {"query": q[:80]}})
        ctx, extra = retrieval_fn(q)
        tc.extend(extra)
        parts = list(s.get("combined_parts", []))
        if ctx:
            parts.append(ctx)
        invoked = list(s.get("specialists_invoked", []))
        invoked.append(spec)
        return {
            "combined_parts": parts,
            "tool_calls": tc,
            "idx": idx + 1,
            "specialists_invoked": invoked,
        }

    def location_node(s: OrchestratorState) -> dict:
        q = s["query"]
        idx = int(s["idx"])
        spec = s["specialists"][idx]
        tc = list(s.get("tool_calls", []))
        tc.append({"tool": spec, "args": {"query": q[:80]}})
        ctx, extra = location_fn(q)
        tc.extend(extra)
        parts = list(s.get("combined_parts", []))
        if ctx:
            parts.append(ctx)
        dirs = list(s.get("directive_types", []))
        dirs.append("show_map")
        invoked = list(s.get("specialists_invoked", []))
        invoked.append(spec)
        return {
            "combined_parts": parts,
            "tool_calls": tc,
            "directive_types": dirs,
            "idx": idx + 1,
            "specialists_invoked": invoked,
        }

    def calculator_node(s: OrchestratorState) -> dict:
        q = s["query"]
        idx = int(s["idx"])
        spec = s["specialists"][idx]
        tc = list(s.get("tool_calls", []))
        tc.append({"tool": spec, "args": {"query": q[:80]}})
        ctx, extra = calculator_fn(q)
        tc.extend(extra)
        parts = list(s.get("combined_parts", []))
        if ctx:
            parts.append(ctx)
        dirs = list(s.get("directive_types", []))
        dirs.append("show_calculator")
        invoked = list(s.get("specialists_invoked", []))
        invoked.append(spec)
        return {
            "combined_parts": parts,
            "tool_calls": tc,
            "directive_types": dirs,
            "idx": idx + 1,
            "specialists_invoked": invoked,
        }

    return retrieval_node, location_node, calculator_node


def _merge_node(state: OrchestratorState) -> dict:
    parts = [p for p in state.get("combined_parts", []) if p]
    combined = "\n\n---\n\n".join(parts)
    dtypes = state.get("directive_types", [])
    a2ui = [{"type": d, "payload": {}} for d in dtypes]
    return {
        "combined_context": combined,
        "a2ui_directives": a2ui,
    }


def _build_compiled_graph(
    retrieval_fn: SpecialistFn,
    location_fn: SpecialistFn,
    calculator_fn: SpecialistFn,
):
    retrieval_node, location_node, calculator_node = _make_specialist_nodes(
        retrieval_fn, location_fn, calculator_fn
    )
    graph = StateGraph(OrchestratorState)
    graph.add_node("router", _router)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("location", location_node)
    graph.add_node("calculator", calculator_node)
    graph.add_node("merge", _merge_node)

    graph.add_edge(START, "router")
    routes = {
        "retrieval": "retrieval",
        "location": "location",
        "calculator": "calculator",
        "merge": "merge",
    }
    graph.add_conditional_edges("router", _dispatch, routes)
    graph.add_conditional_edges("retrieval", _dispatch, routes)
    graph.add_conditional_edges("location", _dispatch, routes)
    graph.add_conditional_edges("calculator", _dispatch, routes)
    graph.add_edge("merge", END)
    return graph.compile()


def _noop_specialist(_q: str) -> tuple[str, list[dict]]:
    return "", []


def get_orchestrator_graph_mermaid() -> str:
    """
    Mermaid flowchart source for the Phase 4 orchestrator StateGraph topology.
    Structure does not depend on specialist callables (only on routing edges).
    """
    compiled = _build_compiled_graph(_noop_specialist, _noop_specialist, _noop_specialist)
    return compiled.get_graph().draw_mermaid()


def run_orchestrator_langgraph(
    query: str,
    retrieval_fn: SpecialistFn,
    location_fn: SpecialistFn,
    calculator_fn: SpecialistFn,
) -> tuple[str, list[dict], list[dict], list[str]]:
    """
    Run the same routing and specialist calls as run_orchestrator via a LangGraph StateGraph.
    Returns (combined_context, all_tool_calls, a2ui_directives, specialists_invoked).
    """
    app = _build_compiled_graph(retrieval_fn, location_fn, calculator_fn)
    out: OrchestratorState = app.invoke({"query": query})
    return (
        out.get("combined_context") or "",
        out.get("tool_calls") or [],
        out.get("a2ui_directives") or [],
        out.get("specialists_invoked") or [],
    )
