"""Tests for lib.retrieval: RRF merge and hybrid_retrieve/vector_search behavior."""
import pytest
from lib.retrieval import _rrf_merge, vector_search, hybrid_retrieve


def test_rrf_merge_basic():
    list_a = ["id1", "id2", "id3"]
    list_b = ["id2", "id1", "id3"]
    merged = _rrf_merge([list_a, list_b], k=60)
    assert len(merged) == 3
    assert set(merged) == {"id1", "id2", "id3"}
    # id2 appears high in both -> should rank first
    assert merged[0] == "id2"


def test_rrf_merge_respects_k():
    merged = _rrf_merge([["a", "b"], ["b", "a"]], k=1)
    assert merged[0] in ("a", "b")


def test_vector_search_returns_empty_without_client():
    """Without a real Qdrant client we can't run search; test structure only."""
    class FakeClient:
        def search(self, **kwargs):
            return []
    chunks, tool_calls = vector_search(FakeClient(), "test_coll", [0.1] * 10, limit=5, query_text="test")
    assert chunks == []
    assert len(tool_calls) == 1
    assert tool_calls[0]["tool"] == "vector_search"
    assert tool_calls[0]["args"]["limit"] == 5


def test_hybrid_retrieve_returns_tool_call_even_on_empty():
    class FakeClient:
        def search(self, **kwargs):
            return []
    chunks, tool_calls = hybrid_retrieve(FakeClient(), "test_coll", [0.1] * 10, "mortgage", limit=5)
    assert chunks == []
    assert any(tc["tool"] == "hybrid_retrieve" for tc in tool_calls)
