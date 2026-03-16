"""Tests for lib.chunking (PDF/chunking helpers used in ingestion)."""
import pytest
from lib.chunking import chunk_text


def test_chunk_text():
    """chunk_text (simple mode) splits by size and overlap."""
    text = "a" * 200
    chunks = chunk_text(text, chunk_size=80, overlap=20)
    assert len(chunks) >= 2
    assert all(len(c) <= 80 + 20 for c in chunks)


def test_chunk_text_empty():
    assert chunk_text("", chunk_size=100, overlap=20) == []
    assert chunk_text("   ", chunk_size=100, overlap=20) == []
