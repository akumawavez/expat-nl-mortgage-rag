"""
Retrieval module for Phase 1: vector search and hybrid (vector + keyword) with RRF merge.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Default RRF constant (reciprocal rank fusion)
RRF_K = 60


def _rrf_merge(
    ranked_ids: list[list[Any]],
    k: int = RRF_K,
) -> list[Any]:
    """Merge multiple ranked lists of document IDs using Reciprocal Rank Fusion."""
    scores: dict[Any, float] = {}
    for rank_list in ranked_ids:
        for r, doc_id in enumerate(rank_list):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + r + 1)
    return sorted(scores.keys(), key=lambda x: -scores[x])


def vector_search(
    qdrant_client: Any,
    collection_name: str,
    query_vector: list[float],
    limit: int = 10,
    query_text: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Run vector similarity search. Returns (chunks, tool_calls) for UI.
    chunks: list of {text, source, score}; tool_calls: for "Tools Used" display.
    Uses query_points (Qdrant client 1.7+); search() was removed in newer clients.
    """
    try:
        response = qdrant_client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
        )
        results = getattr(response, "points", []) or []
    except Exception as e:
        logger.error("Vector search failed: %s", e, exc_info=True)
        return [], [{"tool": "vector_search", "args": {"error": str(e)}}]

    chunks = []
    for hit in results:
        if not hit.payload:
            continue
        chunks.append({
            "text": hit.payload.get("text", ""),
            "source": hit.payload.get("source", ""),
            "page": hit.payload.get("page"),
            "chunk_index": hit.payload.get("chunk_index"),
            "heading": hit.payload.get("heading"),
            "score": getattr(hit, "score", None),
        })

    tool_calls = [
        {"tool": "vector_search", "args": {"query": (query_text or "<embedding>")[:80], "limit": limit}},
    ]
    return chunks, tool_calls


def hybrid_retrieve(
    qdrant_client: Any,
    collection_name: str,
    query_vector: list[float],
    query_text: str,
    limit: int = 10,
    vector_limit: int | None = None,
    rrf_k: int = RRF_K,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Hybrid retrieval: vector search + keyword re-rank over same set, merged with RRF.
    Returns (chunks, tool_calls) for UI. tool_calls list can be shown in "Tools Used".
    Uses query_points (Qdrant client 1.7+); search() was removed in newer clients.
    """
    if vector_limit is None:
        vector_limit = max(limit * 2, 30)

    try:
        response = qdrant_client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=vector_limit,
        )
        results = getattr(response, "points", []) or []
    except Exception as e:
        logger.error("Hybrid retrieve (vector) failed: %s", e, exc_info=True)
        return [], [{"tool": "hybrid_retrieve", "args": {"error": str(e)}}]

    if not results:
        return [], [{"tool": "hybrid_retrieve", "args": {"query": query_text[:80], "limit": limit}}]

    # Vector order (rank list 1)
    vector_order = [hit.id for hit in results]
    id_to_point = {hit.id: hit for hit in results}

    # Keyword score: count of query terms in text (simple re-rank)
    query_terms = set(query_text.lower().split())
    query_terms.discard("")
    if not query_terms:
        keyword_order = vector_order
    else:
        def kw_score(doc_id: Any) -> int:
            text = (id_to_point[doc_id].payload or {}).get("text", "") or ""
            return sum(1 for t in query_terms if t in text.lower())

        keyword_order = sorted(vector_order, key=kw_score, reverse=True)

    # RRF merge
    merged_ids = _rrf_merge([vector_order, keyword_order], k=rrf_k)[:limit]

    chunks = []
    for doc_id in merged_ids:
        p = id_to_point.get(doc_id)
        if not p or not p.payload:
            continue
        chunks.append({
            "text": p.payload.get("text", ""),
            "source": p.payload.get("source", ""),
            "page": p.payload.get("page"),
            "chunk_index": p.payload.get("chunk_index"),
            "heading": p.payload.get("heading"),
            "score": getattr(p, "score", None),
        })

    tool_calls = [
        {"tool": "hybrid_retrieve", "args": {"query": query_text[:80], "limit": limit}},
    ]
    return chunks, tool_calls
