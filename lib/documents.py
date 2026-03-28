"""
Documents in vector store: list uploaded documents, upsert new PDFs, and remove documents.

Used by the Documents tab for source tracing, upload, and delete.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from io import BytesIO
from typing import Any

from pypdf import PdfReader

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PDF_STORE_DIR = PROJECT_ROOT / "data" / "pdfs"
PDF_SEARCH_DIRS = [
    PROJECT_ROOT / "data",
    PROJECT_ROOT / "docs",
    PROJECT_ROOT,
]


def list_documents_in_store(qdrant_client: Any, collection_name: str) -> list[dict[str, Any]]:
    """
    List all documents (unique source values) in the collection with chunk counts.
    Returns list of {"source": str, "chunk_count": int}.
    """
    try:
        seen: dict[str, int] = {}
        offset = None
        while True:
            records, offset = qdrant_client.scroll(
                collection_name=collection_name,
                limit=500,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            if not records:
                break
            for r in records:
                src = (r.payload or {}).get("source") or ""
                if src:
                    seen[src] = seen.get(src, 0) + 1
            if offset is None:
                break
        return [{"source": s, "chunk_count": c} for s, c in sorted(seen.items())]
    except Exception as e:
        logger.error("list_documents_in_store failed: %s", e, exc_info=True)
        return []


def delete_document_from_store(qdrant_client: Any, collection_name: str, source: str) -> int:
    """
    Delete all points (chunks) in the collection whose payload source equals the given document name.
    Returns the number of points deleted (from count before delete). Use source exactly as in list_documents_in_store.
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    if not source or not source.strip():
        return 0
    try:
        qdrant_client.delete(
            collection_name=collection_name,
            points_selector=Filter(
                must=[FieldCondition(key="source", match=MatchValue(value=source.strip()))]
            ),
        )

        # Delete the saved PDF (if we have it from ingestion).
        pdf_path = (PDF_STORE_DIR / source.strip())
        try:
            if pdf_path.exists():
                pdf_path.unlink()
        except Exception:
            logger.warning("Failed to delete saved pdf: %s", pdf_path, exc_info=True)

        # Count is not returned by delete(); we report success. Caller can rerun list to refresh.
        return 1
    except Exception as e:
        logger.error("delete_document_from_store failed for %s: %s", source, e, exc_info=True)
        raise


def load_pdf_bytes_from_store(source: str) -> bytes | None:
    """
    Load PDF bytes for UI preview.
    First checks data/pdfs (saved on ingestion), then falls back to common project folders
    to support older docs ingested before PDF persistence was added.
    """
    if not source or not source.strip():
        return None
    source_name = source.strip()
    pdf_path = PDF_STORE_DIR / source_name
    try:
        if pdf_path.exists():
            return pdf_path.read_bytes()
    except Exception:
        logger.warning("Failed to read saved pdf: %s", pdf_path, exc_info=True)

    # Fallback for older ingestions: search common dirs for same filename.
    for base_dir in PDF_SEARCH_DIRS:
        if not base_dir.exists():
            continue
        candidate = base_dir / source_name
        try:
            if candidate.exists() and candidate.is_file():
                return candidate.read_bytes()
        except Exception:
            logger.warning("Failed reading candidate pdf: %s", candidate, exc_info=True)
        try:
            matches = list(base_dir.rglob(source_name))
            for m in matches:
                if m.is_file() and m.suffix.lower() == ".pdf":
                    return m.read_bytes()
        except Exception:
            logger.warning("Fallback pdf lookup failed under %s", base_dir, exc_info=True)
    return None


def extract_text_from_pdf_bytes(data: bytes) -> str:
    """Extract raw text from PDF bytes."""
    reader = PdfReader(BytesIO(data))
    parts = []
    for page in reader.pages:
        part = page.extract_text()
        if part:
            parts.append(part)
    return "\n\n".join(parts)


def _chunk_pdf_by_page(
    file_bytes: bytes,
    chunk_size: int,
    overlap: int,
) -> list[dict[str, Any]]:
    """
    Chunk a PDF per page, preserving page number, chunk_index, and section heading.
    Delegates to lib.chunking.chunk_pdf_with_metadata for consistent metadata
    across both single-upload and batch ingestion.
    """
    from lib.chunking import chunk_pdf_with_metadata

    return chunk_pdf_with_metadata(
        file_bytes,
        chunk_size=chunk_size,
        chunk_overlap=overlap,
    )


def chunk_text_simple(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """Simple overlapping chunks (aligned with ingestion)."""
    if not text or not text.strip():
        return []
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


def upsert_pdf_to_qdrant(
    qdrant_client: Any,
    embedding_client: Any,
    collection_name: str,
    file_name: str,
    file_bytes: bytes,
    chunk_size: int = 800,
    overlap: int = 150,
    embedding_model: str = "text-embedding-3-small",
    vector_dimension: int = 1536,
) -> int:
    """
    Upsert a single PDF: delete existing chunks for this source, then insert new chunks.
    Returns number of chunks inserted. Creates collection if missing.
    """
    from qdrant_client.models import PointStruct, VectorParams, Distance, Filter, FieldCondition, MatchValue

    names = [c.name for c in (qdrant_client.get_collections().collections or [])]
    if collection_name not in names:
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_dimension, distance=Distance.COSINE),
        )

    # Persist original PDF bytes so the UI can preview cited pages.
    PDF_STORE_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = PDF_STORE_DIR / file_name
    try:
        pdf_path.write_bytes(file_bytes)
    except Exception as e:
        logger.warning("Failed to save pdf for preview (%s): %s", pdf_path, e, exc_info=True)

    page_chunks = _chunk_pdf_by_page(
        file_bytes=file_bytes,
        chunk_size=chunk_size,
        overlap=overlap,
    )
    if not page_chunks:
        return 0

    try:
        # Delete existing points for this source
        qdrant_client.delete(
            collection_name=collection_name,
            points_selector=Filter(must=[FieldCondition(key="source", match=MatchValue(value=file_name))]),
        )
    except Exception as e:
        logger.error("Failed to delete existing chunks for %s: %s", file_name, e, exc_info=True)
        raise

    # Embed in batches
    batch_size = 100
    all_embeddings = []
    all_texts = [c["text"] for c in page_chunks]
    for i in range(0, len(all_texts), batch_size):
        batch = [t if t.strip() else " " for t in all_texts[i : i + batch_size]]
        try:
            resp = embedding_client.embeddings.create(input=batch, model=embedding_model)
        except Exception as e:
            logger.error("Embedding batch failed (rate limit or API error): %s", e, exc_info=True)
            raise
        order = {e.index: e.embedding for e in resp.data}
        all_embeddings.extend([order[j] for j in range(len(batch))])

    points = []
    for emb, chunk in zip(all_embeddings, page_chunks):
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=emb,
                payload={
                    "text": chunk["text"],
                    "source": file_name,
                    "page": chunk.get("page"),
                    "chunk_index": chunk.get("chunk_index"),
                    "heading": chunk.get("heading"),
                },
            )
        )
    try:
        qdrant_client.upsert(collection_name=collection_name, points=points)
    except Exception as e:
        logger.error("Upsert to Qdrant failed after delete (data loss risk): %s", e, exc_info=True)
        raise
    return len(points)
