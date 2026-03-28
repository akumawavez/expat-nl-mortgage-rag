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
from io import BytesIO
from typing import Any, List, Optional, TYPE_CHECKING

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

    for section in sections:
        if not section.strip():
            continue
        candidate = "\n\n".join(current + [section]) if current else section
        if len(candidate) <= chunk_size:
            current.append(section)
            continue

        # Flush current chunk
        if current:
            chunk = "\n\n".join(current).strip()
            if len(chunk) >= min_chunk_size:
                chunks.append(chunk)
            current = []

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


# ---------------------------------------------------------------------------
# Heading detection
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(
    r"^(?:"
    r"#{1,6}\s+.+"                                # markdown headers
    r"|(?:Section|Chapter|Article|Part)\s+\d+.*"  # "Section 3 – Foo"
    r"|\d+(?:\.\d+)*\.?\s+[A-Z].*"               # numbered headings like "3.1 Overview"
    r"|[A-Z][A-Z\s,&/\-]{4,60}$"                 # ALL CAPS lines (min 5 chars)
    r")",
    re.MULTILINE,
)


def _detect_heading(line: str) -> str | None:
    """Return the heading text if *line* looks like a section heading, else None."""
    stripped = line.strip()
    if not stripped or len(stripped) < 3:
        return None
    if _HEADING_RE.match(stripped):
        return stripped.lstrip("#").strip()
    return None


def _current_heading_for_position(lines: list[str], pos: int) -> str | None:
    """Walk backwards from *pos* to find the nearest heading."""
    for i in range(pos, -1, -1):
        h = _detect_heading(lines[i])
        if h:
            return h
    return None


# ---------------------------------------------------------------------------
# Page-aware, metadata-rich PDF chunking
# ---------------------------------------------------------------------------

def chunk_pdf_with_metadata(
    file_bytes: bytes,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    semantic: bool = False,
    openai_client: Optional["OpenAI"] = None,
    max_chunk_size: int = DEFAULT_MAX_CHUNK_SIZE,
    min_chunk_size: int = DEFAULT_MIN_CHUNK_SIZE,
    use_llm_for_long_sections: bool = True,
    ingestion_model: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Chunk a PDF while preserving page numbers and section headings.

    Returns a list of dicts:
        {text, page, chunk_index, heading}

    *page* is 1-based.  *heading* is the nearest detected section heading
    (or None).  Works for both batch ingestion and single-document upload
    so that citations always carry rich metadata.
    """
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(file_bytes))
    doc_chunks: list[dict[str, Any]] = []
    chunk_index = 0
    last_heading: str | None = None

    for page_num, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        if not page_text.strip():
            continue
        page_text = page_text.strip()

        lines = page_text.splitlines()
        for line in lines:
            h = _detect_heading(line)
            if h:
                last_heading = h

        if semantic:
            text_chunks = chunk_text_semantic(
                page_text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                max_chunk_size=max_chunk_size,
                min_chunk_size=min_chunk_size,
                openai_client=openai_client,
                use_llm_for_long_sections=use_llm_for_long_sections,
                ingestion_model=ingestion_model,
            )
        else:
            text_chunks = _simple_split(page_text, chunk_size, chunk_overlap, min_chunk_size)
            if not text_chunks and page_text.strip():
                text_chunks = [page_text.strip()]

        for ch in text_chunks:
            ch_lines = ch.splitlines()
            chunk_heading = None
            for cl in ch_lines:
                detected = _detect_heading(cl)
                if detected:
                    chunk_heading = detected
                    break
            heading = chunk_heading or last_heading

            doc_chunks.append({
                "text": ch,
                "page": page_num,
                "chunk_index": chunk_index,
                "heading": heading,
            })
            chunk_index += 1

    return doc_chunks
