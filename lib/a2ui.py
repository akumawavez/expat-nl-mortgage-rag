"""
Phase 4: A2UI – schema for agent-driven UI directives and renderer helpers.

Directives: show_calculator, show_map, show_sun, show_citations, show_safety.
Streamlit renderer uses these to show the corresponding widget (calculator, map, sun, citations, safety card).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

DirectiveType = Literal["show_calculator", "show_map", "show_sun", "show_citations", "show_safety"]


@dataclass
class A2UIDirective:
    type: DirectiveType
    payload: dict[str, Any] = field(default_factory=dict)


def parse_directives_from_text(text: str) -> list[A2UIDirective]:
    """
    Parse agent output for A2UI directives (e.g. [A2UI: show_calculator] or JSON block).
    Returns list of A2UIDirective.
    """
    directives = []
    text_lower = text.lower()
    if "show calculator" in text_lower or "[a2ui: show_calculator]" in text_lower or "show_calculator" in text_lower:
        directives.append(A2UIDirective("show_calculator", {}))
    if "show map" in text_lower or "[a2ui: show_map]" in text_lower or "show_map" in text_lower:
        directives.append(A2UIDirective("show_map", {}))
    if "show sun" in text_lower or "[a2ui: show_sun]" in text_lower or "show_sun" in text_lower:
        directives.append(A2UIDirective("show_sun", {}))
    if "show citations" in text_lower or "[a2ui: show_citations]" in text_lower:
        directives.append(A2UIDirective("show_citations", {}))
    if "show safety" in text_lower or "[a2ui: show_safety]" in text_lower or "safety card" in text_lower:
        directives.append(A2UIDirective("show_safety", {}))
    return directives


def parse_directives_from_json(data: dict) -> list[A2UIDirective]:
    """Parse directives from structured agent output, e.g. {"directives": [{"type": "show_calculator", "payload": {}}]}."""
    out = []
    for d in data.get("directives") or []:
        t = d.get("type") or d.get("directive")
        if t in ("show_calculator", "show_map", "show_sun", "show_citations", "show_safety"):
            out.append(A2UIDirective(t, d.get("payload") or {}))
    return out
