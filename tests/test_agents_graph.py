"""LangGraph orchestrator matches classic run_orchestrator for mocked specialists."""
from __future__ import annotations

import pytest

from lib.agents import run_orchestrator
from lib.agents_graph import run_orchestrator_langgraph


def _ret(q: str) -> tuple[str, list[dict]]:
    return f"ctx-r:{q[:20]}", [{"tool": "vector_search", "args": {}}]


def _loc(q: str) -> tuple[str, list[dict]]:
    return f"ctx-l:{q[:20]}", [{"tool": "nearby_places", "args": {}}]


def _calc(q: str) -> tuple[str, list[dict]]:
    return f"ctx-c:{q[:20]}", [{"tool": "calc", "args": {}}]


@pytest.mark.parametrize(
    "query",
    [
        "NHG guarantee and interest rate for documents",
        "school near my address in Amsterdam",
        "monthly mortgage payment calculate bruto",
        "distance route to supermarket and NHG tax deduct",
    ],
)
def test_langgraph_matches_classic_orchestrator(query: str) -> None:
    classic = run_orchestrator(query, _ret, _loc, _calc)
    graph = run_orchestrator_langgraph(query, _ret, _loc, _calc)
    assert graph[0] == classic[0]
    assert graph[1] == classic[1]
    assert graph[2] == classic[2]
    assert graph[3] == classic[3]
