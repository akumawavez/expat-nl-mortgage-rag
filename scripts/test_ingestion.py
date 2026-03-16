"""
Test script: verify Phase 1 ingestion and Qdrant state.

Run from project root:
  python scripts/test_ingestion.py

Prints:
  - Qdrant connectivity and collection existence
  - Point count and vector dimension
  - Sample retrieval result (if any data)
  - Clear PASS/FAIL and next steps
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
os.chdir(_project_root)

import dotenv
dotenv.load_dotenv(_project_root / ".env")

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "property_docs")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")

# Sample query used to test retrieval
TEST_QUERY = "mortgage eligibility income requirement"


def main() -> None:
    print("=" * 60)
    print("Phase 1 ingestion test – Qdrant + collection + retrieval")
    print("=" * 60)
    print(f"QDRANT_URL       = {QDRANT_URL}")
    print(f"QDRANT_COLLECTION= {QDRANT_COLLECTION}")
    print()

    # --- 1. Qdrant connection ---
    print("[1] Qdrant connection ...")
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=QDRANT_URL)
        # Trigger a simple API call to verify connectivity
        _ = client.get_collections()
        print("    OK – Qdrant is reachable.")
    except Exception as e:
        print(f"    FAIL – Cannot connect to Qdrant: {e}")
        print("    → Start Qdrant (e.g. Docker) and ensure QDRANT_URL is correct.")
        sys.exit(1)

    # --- 2. Collection exists ---
    print("\n[2] Collection existence ...")
    collections = [c.name for c in client.get_collections().collections or []]
    if QDRANT_COLLECTION not in collections:
        print(f"    FAIL – Collection {QDRANT_COLLECTION!r} not found.")
        print(f"    Existing collections: {collections or '(none)'}")
        print("    → Run: python scripts/ingest_docs.py")
        sys.exit(1)
    print(f"    OK – Collection {QDRANT_COLLECTION!r} exists.")

    # --- 3. Collection info (count, vector size) ---
    print("\n[3] Collection details ...")
    try:
        info = client.get_collection(QDRANT_COLLECTION)
        points_count = info.points_count
        vector_size = None
        if getattr(info, "config", None) and getattr(info.config, "params", None):
            vector_size = getattr(info.config.params, "size", None)
        if vector_size is None and points_count:
            # Infer from first point
            pts, _ = client.scroll(collection_name=QDRANT_COLLECTION, limit=1, with_vectors=True)
            if pts and getattr(pts[0], "vector", None):
                vector_size = len(pts[0].vector) if isinstance(pts[0].vector, (list,)) else getattr(pts[0].vector, "__len__", lambda: None)()
        print(f"    Points (chunks) = {points_count}")
        print(f"    Vector size     = {vector_size or 'N/A'}")
        if points_count == 0:
            print("    FAIL – Collection is empty. No documents ingested.")
            print("    → Run: python scripts/ingest_docs.py")
            sys.exit(1)
        print("    OK – Collection has data.")
    except Exception as e:
        print(f"    FAIL – Could not get collection info: {e}")
        sys.exit(1)

    # --- 4. Sample retrieval (optional; needs embedding API) ---
    print("\n[4] Sample retrieval ...")
    try:
        from lib.provider import get_embedding_client
        embedding_client = get_embedding_client()
    except RuntimeError as e:
        print(f"    SKIP – Cannot get embedding client: {e}")
    else:
        try:
            emb_resp = embedding_client.embeddings.create(input=[TEST_QUERY], model=EMBEDDING_MODEL)
            query_vector = emb_resp.data[0].embedding
            results = client.search(
                collection_name=QDRANT_COLLECTION,
                query_vector=query_vector,
                limit=2,
            )
            if not results:
                print("    WARN – Search returned no results (unexpected if points > 0).")
            else:
                print(f"    Query: {TEST_QUERY!r}")
                for i, hit in enumerate(results, 1):
                    source = hit.payload.get("source", "?")
                    text = (hit.payload.get("text") or "")[:200]
                    print(f"    Result {i}: source={source!r}, score={hit.score:.4f}")
                    print(f"      snippet: {text!r}...")
                print("    OK – Retrieval works.")
        except Exception as e:
            print(f"    WARN – Retrieval test failed (e.g. OpenAI quota/error): {e}")
            print("    Ingestion state is still valid; retrieval in the app uses the same API.")

    # --- Summary ---
    print("\n" + "=" * 60)
    print("RESULT: PASS – Ingestion is in place; app should have context.")
    print("  If the app still says 'nothing loaded', restart the Streamlit app.")
    print("=" * 60)


if __name__ == "__main__":
    main()
