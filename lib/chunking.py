"""
Semantic (agentic) chunking for RAG ingestion.

Inspired by https://github.com/coleam00/ottomator-agents/tree/main/agentic-rag-knowledge-graph
- Split on structure (paragraphs, headings, lists) then group by size.
- For sections longer than max_chunk_size, optionally use LLM to split at semantic boundaries.
- Fallback: sentence-boundary-aware sliding window.

Works with PDF-extracted text (plain text with paragraph breaks).
"""

from __future__ import annotations

import re
import logging
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from openai import OpenAI

logger = logging.getLogger(__name__)

# Defaults aligned with .env
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 150
DEFAULT_MAX_CHUNK_SIZE = 2000
DEFAULT_MIN_CHUNK_SIZE = 100


def _split_on_structure(content: str) -> List[str]:
    """
    Split content on structural boundaries: paragraphs first, then optional
    markdown headers or numbered section starts. Works for PDF-extracted text.
    """
    if not content.strip():
        return []

    text = content.replace("\r\n", "\n").replace("\r", "\n").strip()

    # 1) Split on paragraph breaks (primary for PDF text)
    sections = re.split(r"\n\s*\n+", text)
    sections = [s.strip() for s in sections if s.strip()]

    # 2) Optionally split on markdown headers so "## Next topic" starts a new section
    result = []
    for block in sections:
        parts = re.split(r"(?=\n#{1,6}\s+)", block)
        for p in parts:
            p = p.strip()
            if p:
                result.append(p)
    sections = result if result else sections

    # 3) Optionally split on "1. " or "Section 2." style boundaries (common in gov PDFs)
    result = []
    for block in sections:
        parts = re.split(r"(?=\n(?:Section\s+\d+|Chapter\s+\d+|\d+[.)]\s+))", block, flags=re.IGNORECASE)
        for p in parts:
            p = p.strip()
            if p and len(p) >= 15:  # skip very tiny fragments
                result.append(p)
    sections = result if result else sections
    return sections


def _simple_split(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    min_chunk_size: int = DEFAULT_MIN_CHUNK_SIZE,
) -> List[str]:
    """Sliding-window split with sentence-boundary awareness (fallback)."""
    if not text or not text.strip():
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end >= len(text):
            chunk = text[start:].strip()
            if chunk:
                chunks.append(chunk)
            break
        # Prefer to break at sentence end
        chunk_end = end
        search_start = max(start, end - 250)
        for i in range(end - 1, search_start - 1, -1):
            if i < len(text) and text[i] in ".!?\n":
                chunk_end = i + 1
                break
        chunk = text[start:chunk_end].strip()
        if chunk and len(chunk) >= min_chunk_size:
            chunks.append(chunk)
        start = chunk_end - chunk_overlap
        if start >= len(text):
            break
    return chunks


def _split_long_section_with_llm(
    section: str,
    chunk_size: int,
    max_chunk_size: int,
    min_chunk_size: int,
    client: "OpenAI",
    model: str = "gpt-4o-mini",
) -> List[str]:
    """Use LLM to split a long section at semantic boundaries."""
    prompt = f"""Split the following text into semantically coherent chunks. Each chunk should:
1. Be roughly {chunk_size} characters long (no more than {max_chunk_size})
2. End at natural semantic boundaries (end of paragraph or topic)
3. Remain readable and self-contained

Return ONLY the split text with exactly "---CHUNK---" as the separator between chunks. No other commentary.

Text to split:
{section[:12000]}
"""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        result = (resp.choices[0].message.content or "").strip()
        raw_chunks = [c.strip() for c in result.split("---CHUNK---") if c.strip()]
        valid = [
            c for c in raw_chunks
            if min_chunk_size <= len(c) <= max_chunk_size * 2  # allow slight overflow
        ]
        return valid if valid else _simple_split(section, chunk_size, chunk_size // 2, min_chunk_size)
    except Exception as e:
        logger.warning("LLM chunking failed, using sentence-boundary split: %s", e)
        return _simple_split(section, chunk_size, chunk_size // 2, min_chunk_size)


def chunk_text_semantic(
    content: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    max_chunk_size: int = DEFAULT_MAX_CHUNK_SIZE,
    min_chunk_size: int = DEFAULT_MIN_CHUNK_SIZE,
    openai_client: Optional["OpenAI"] = None,
    use_llm_for_long_sections: bool = True,
    ingestion_model: Optional[str] = None,
) -> List[str]:
    """
    Semantic (agentic) chunking: structure-aware + optional LLM for long sections.

    - Splits on paragraphs, headings, lists.
    - Groups sections into chunks under chunk_size.
    - If a section exceeds max_chunk_size and use_llm_for_long_sections and openai_client
      are set, uses LLM to split that section at semantic boundaries.
    - Fallback: sentence-boundary-aware sliding window.
    """
    if not content or not content.strip():
        return []

    sections = _split_on_structure(content)
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for section in sections:
        if not section.strip():
            continue
        candidate = "\n\n".join(current + [section]) if current else section
        if len(candidate) <= chunk_size:
            current.append(section)
            current_len = len(candidate)
            continue

        # Flush current chunk
        if current:
            chunk = "\n\n".join(current).strip()
            if len(chunk) >= min_chunk_size:
                chunks.append(chunk)
            current = []
            current_len = 0

        # Oversized section: LLM split or simple split
        if (
            len(section) > max_chunk_size
            and use_llm_for_long_sections
            and openai_client is not None
        ):
            sub_chunks = _split_long_section_with_llm(
                section, chunk_size, max_chunk_size, min_chunk_size,
                openai_client, model=ingestion_model or "gpt-4o-mini",
            )
            chunks.extend(sub_chunks)
        elif len(section) > max_chunk_size:
            sub_chunks = _simple_split(section, chunk_size, chunk_overlap, min_chunk_size)
            chunks.extend(sub_chunks)
        else:
            current = [section]
            current_len = len(section)

    if current:
        chunk = "\n\n".join(current).strip()
        if len(chunk) >= min_chunk_size:
            chunks.append(chunk)

    return [c for c in chunks if c.strip()]


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
    semantic: bool = False,
    openai_client: Optional["OpenAI"] = None,
    max_chunk_size: int = DEFAULT_MAX_CHUNK_SIZE,
    min_chunk_size: int = DEFAULT_MIN_CHUNK_SIZE,
    use_llm_for_long_sections: bool = True,
    ingestion_model: Optional[str] = None,
) -> List[str]:
    """
    Single entry point: simple (fixed-size + overlap) or semantic chunking.

    - semantic=False: original sliding-window overlap (fast, no LLM).
    - semantic=True: structure-aware + optional LLM for long sections (better quality, slower).
    """
    if not text or not text.strip():
        return []
    if semantic:
        return chunk_text_semantic(
            text,
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            max_chunk_size=max_chunk_size,
            min_chunk_size=min_chunk_size,
            openai_client=openai_client,
            use_llm_for_long_sections=use_llm_for_long_sections,
            ingestion_model=ingestion_model,
        )
    # Original simple overlap chunking
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
        if start >= len(text):
            break
    return chunks
