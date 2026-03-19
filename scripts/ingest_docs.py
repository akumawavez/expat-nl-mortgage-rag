"""
Phase 1: Document ingestion for Expat NL Mortgage RAG.

Loads all PDFs from the project (gov docs + root) into Qdrant using OpenAI embeddings.
Default: DELETE everything in the project collection, then INSERT all found PDFs (full replace).
Use --no-replace to only add/upsert without clearing (rare).

Chunking:
  Default: fixed-size overlapping chunks (fast).
  --semantic: agentic/semantic chunking (structure-aware + optional LLM for long sections).
  See lib/chunking.py (inspired by agentic-rag-knowledge-graph).

Usage:
  From project root (expat-nl-mortgage-rag):
    python scripts/ingest_docs.py
    python scripts/ingest_docs.py --semantic   # better chunks, slower
  To add PDFs without clearing existing data:
    python scripts/ingest_docs.py --no-replace
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

# Load .env from project root (parent of scripts/)
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
os.chdir(_project_root)

import dotenv  # noqa: E402
dotenv.load_dotenv(_project_root / ".env")

from pypdf import PdfReader  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.models import Distance, VectorParams, PointStruct  # noqa: E402

from lib.chunking import chunk_text as chunk_text_lib  # noqa: E402
from lib.provider import get_llm_client, get_embedding_client  # noqa: E402


# -----------------------------------------------------------------------------
# Config from env
# -----------------------------------------------------------------------------
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "property_docs")
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "150"))
MAX_CHUNK_SIZE = int(os.environ.get("MAX_CHUNK_SIZE", "1500"))
VECTOR_DIMENSION = int(os.environ.get("VECTOR_DIMENSION", "1536"))  # text-embedding-3-small
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
INGESTION_LLM_CHOICE = os.environ.get("INGESTION_LLM_CHOICE") or os.environ.get("LLM_CHOICE", "gpt-4o-mini")
# Clients use lib.provider so OpenRouter works when LLM_PROVIDER=openrouter / EMBEDDING_PROVIDER=openrouter


def extract_text_from_pdf(path: Path) -> str:
    """Extract raw text from a PDF file."""
    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        part = page.extract_text()
        if part:
            parts.append(part)
    return "\n\n".join(parts)


def find_pdfs(doc_dirs: list[Path]) -> list[Path]:
    """Collect all PDF paths from the given directories (non-recursive for root, one level for subdirs)."""
    pdfs = []
    for d in doc_dirs:
        d = Path(d).resolve()
        if not d.exists():
            continue
        if d.is_file() and d.suffix.lower() == ".pdf":
            pdfs.append(d)
            continue
        for f in d.iterdir():
            if f.suffix.lower() == ".pdf":
                pdfs.append(f)
    return sorted(set(pdfs))


def embed_texts(client, texts: list[str], model: str = EMBEDDING_MODEL) -> list[list[float]]:
    """Get embeddings for a list of texts (batched to respect API limits)."""
    batch_size = 100
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        # OpenAI expects non-empty strings
        batch = [t if t.strip() else " " for t in batch]
        resp = client.embeddings.create(input=batch, model=model)
        order = {e.index: e.embedding for e in resp.data}
        all_embeddings.extend([order[j] for j in range(len(batch))])
    return all_embeddings


def ensure_collection(qdrant: QdrantClient, collection: str, dimension: int) -> None:
    """Create collection if it does not exist."""
    names = [c.name for c in (qdrant.get_collections().collections or [])]
    if collection not in names:
        qdrant.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
        )
        print(f"Created collection {collection!r} with dimension {dimension}.")
    else:
        print(f"Using existing collection {collection!r}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest PDFs into Qdrant for Phase 1 RAG.")
    parser.add_argument(
        "--docs-dir",
        action="append",
        default=[],
        help="Directory or file to scan for PDFs (default: 'gov docs' and '.').",
    )
    parser.add_argument(
        "--no-replace",
        action="store_true",
        help="Do NOT delete existing data; only add/upsert (default is delete all then insert).",
    )
    parser.add_argument(
        "--semantic",
        action="store_true",
        help="Use semantic (agentic) chunking: structure-aware + LLM for long sections (slower, better chunks).",
    )
    args = parser.parse_args()

    doc_dirs = args.docs_dir
    if not doc_dirs:
        doc_dirs = [
            _project_root / "gov docs",
            _project_root,
        ]

    doc_paths = find_pdfs([Path(p) for p in doc_dirs])
    if not doc_paths:
        print("No PDFs found. Add --docs-dir to point to folders or a PDF file.")
        sys.exit(1)

    print(f"Found {len(doc_paths)} PDF(s).")
    embedding_client = get_embedding_client()
    llm_client = get_llm_client() if args.semantic else None
    qdrant = QdrantClient(url=QDRANT_URL)

    # Default: delete everything for this project, then insert again
    if not args.no_replace:
        if QDRANT_COLLECTION in [c.name for c in qdrant.get_collections().collections or []]:
            qdrant.delete_collection(collection_name=QDRANT_COLLECTION)
            print(f"Deleted collection {QDRANT_COLLECTION!r} (full replace mode).")
        ensure_collection(qdrant, QDRANT_COLLECTION, VECTOR_DIMENSION)
    else:
        ensure_collection(qdrant, QDRANT_COLLECTION, VECTOR_DIMENSION)
        print("Append mode: existing data kept; new PDFs will be added.")

    if args.semantic:
        print("Chunking: semantic (structure + LLM for long sections).")

    total_points = 0
    for path in doc_paths:
        try:
            rel_name = path.relative_to(_project_root)
        except ValueError:
            rel_name = path.name
        print(f"Processing {rel_name} ...")
        try:
            text = extract_text_from_pdf(path)
        except Exception as e:
            print(f"  Skip: {e}")
            continue
        chunks = chunk_text_lib(
            text,
            chunk_size=CHUNK_SIZE,
            overlap=CHUNK_OVERLAP,
            semantic=args.semantic,
            openai_client=llm_client,
            max_chunk_size=MAX_CHUNK_SIZE,
            use_llm_for_long_sections=args.semantic,
            ingestion_model=INGESTION_LLM_CHOICE,
        )
        if not chunks:
            print(f"  No text chunks from {rel_name}, skipping.")
            continue
        embeddings = embed_texts(embedding_client, chunks)
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=emb,
                payload={"text": chunk, "source": str(rel_name)},
            )
            for emb, chunk in zip(embeddings, chunks)
        ]
        qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points)
        total_points += len(points)
        print(f"  Upserted {len(points)} chunks.")
    print(f"Done. Total chunks in store: {total_points}.")


if __name__ == "__main__":
    main()
