"""
Phase 2: Knowledge Graph – extraction and PyVis visualization.

Simple rule-based extraction from text; optional Neo4j write.
PyVis HTML generation for the KG tab.
"""
from __future__ import annotations

import re

# Default sample for demo when no text provided
SAMPLE_TEXT = (
    "Mortgage interest deduction (hypotheekrenteaftrek) applies to owner-occupied homes in the Netherlands. "
    "The Tax Authority (Belastingdienst) oversees tax returns. NHG (Nationale Hypotheek Garantie) provides "
    "guarantees for mortgages. A mortgage advisor (hypotheekadviseur) can help expats."
)


def extract_entities_relations_simple(text: str) -> tuple[list[dict], list[dict]]:
    """
    Simple rule-based extraction: look for (Entity, relation, Entity) patterns.
    Returns (nodes, edges). Nodes have id, label; edges have source, target, label.
    """
    if not text or not text.strip():
        text = SAMPLE_TEXT
    nodes_map: dict[str, dict] = {}
    edges: list[dict] = []

    # Common patterns: "X (Y)", "X - Y", "X is Y", "X provides Y", "X oversees Y", "X can help Y"
    # Normalize and find capitalized phrases and parentheticals
    for m in re.finditer(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\(([^)]+)\)", text):
        entity, alias = m.group(1).strip(), m.group(2).strip()
        for e in (entity, alias):
            if e and e not in nodes_map:
                nodes_map[e] = {"id": e, "label": e}
        if entity != alias:
            edges.append({"source": entity, "target": alias, "label": "alias"})

    for m in re.finditer(r"(NHG|Belastingdienst|hypotheekrenteaftrek|hypotheekadviseur|Nationale Hypotheek Garantie)", text, re.I):
        name = m.group(1)
        if name not in nodes_map:
            nodes_map[name] = {"id": name, "label": name}

    for m in re.finditer(r"(mortgage|Mortgage|hypotheek|Hypotheek)", text):
        term = "Mortgage"
        if term not in nodes_map:
            nodes_map[term] = {"id": term, "label": term}

    # Relations from verbs
    for pattern, rel in [
        (r"(?:oversees?|handles?)\s+([^.]+?)(?:\.|$)", "oversees"),
        (r"(?:provides?)\s+([^.]+?)(?:\.|$)", "provides"),
        (r"(?:can help)\s+([^.]+?)(?:\.|$)", "helps"),
        (r"applies to\s+([^.]+?)(?:\.|$)", "applies_to"),
    ]:
        for m in re.finditer(pattern, text):
            obj = m.group(1).strip()[:40]
            if obj and obj not in nodes_map:
                nodes_map[obj] = {"id": obj, "label": obj}
            if len(nodes_map) > 1 and obj:
                for key in list(nodes_map.keys())[:3]:
                    if key != obj and key in ("Belastingdienst", "NHG", "Mortgage", "Tax Authority"):
                        edges.append({"source": key, "target": obj, "label": rel})
                        break

    nodes = list(nodes_map.values())
    return nodes, edges


def build_pyvis_html(nodes: list[dict], edges: list[dict], height: str = "500px") -> str:
    """Generate PyVis network HTML string for embedding in Streamlit."""
    try:
        from pyvis.network import Network
    except ImportError:
        return "<p>Install pyvis: pip install pyvis</p>"
    net = Network(height=height, directed=True)
    for n in nodes:
        net.add_node(n["id"], label=n.get("label", n["id"]))
    for e in edges:
        net.add_edge(e["source"], e["target"], title=e.get("label", ""))
    return net.generate_html(notebook=False)


def build_kg_from_text(text: str) -> str:
    """Extract nodes/edges from text and return PyVis HTML."""
    nodes, edges = extract_entities_relations_simple(text)
    return build_pyvis_html(nodes, edges)
