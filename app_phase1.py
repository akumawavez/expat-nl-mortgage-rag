"""
Phase 1 RAG: Expat NL Mortgage Assistant.

Uses OpenAI for chat and embeddings, Qdrant for retrieval. Run scripts/ingest_docs.py
first to populate the vector store (full replace), or add PDFs via the sidebar (upsert per document).

  streamlit run app_phase1.py
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from io import BytesIO

import dotenv
dotenv.load_dotenv(Path(__file__).resolve().parent / ".env")

import streamlit as st
from qdrant_client import QdrantClient
from lib.provider import (
    get_llm_client,
    get_embedding_client,
    get_available_llm_providers,
    get_default_llm_models,
)
from qdrant_client.models import PointStruct, VectorParams, Distance
from pypdf import PdfReader

# -----------------------------------------------------------------------------
# Config from env
# -----------------------------------------------------------------------------
PAGE_TITLE = "Expat NL Mortgage RAG (Phase 1)"
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "property_docs")
MAX_SEARCH_RESULTS = int(os.environ.get("MAX_SEARCH_RESULTS", "10"))
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "150"))
VECTOR_DIMENSION = int(os.environ.get("VECTOR_DIMENSION", "1536"))
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
LLM_CHOICE_DEFAULT = os.environ.get("LLM_CHOICE", "gpt-4o-mini")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")

SYSTEM_PROMPT = (
    "You are an expert assistant helping expats and international buyers with Dutch mortgages "
    "and property in the Netherlands. Use ONLY the provided context from official and trusted "
    "documents to answer. If the context does not contain enough information, say so and suggest "
    "where to look (e.g. tax authority, mortgage advisor). Keep answers concise and actionable."
)


@st.cache_resource
def get_qdrant() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


def get_embedding(client, text: str) -> list[float]:
    resp = client.embeddings.create(input=[text], model=EMBEDDING_MODEL)
    return resp.data[0].embedding


def ensure_collection(qdrant: QdrantClient) -> None:
    """Create collection if it does not exist (e.g. for first PDF upload)."""
    names = [c.name for c in (qdrant.get_collections().collections or [])]
    if QDRANT_COLLECTION not in names:
        qdrant.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIMENSION, distance=Distance.COSINE),
        )


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks (same as ingestion script)."""
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


def extract_text_from_pdf_bytes(data: bytes) -> str:
    """Extract raw text from PDF bytes (uploaded file)."""
    reader = PdfReader(BytesIO(data))
    parts = []
    for page in reader.pages:
        part = page.extract_text()
        if part:
            parts.append(part)
    return "\n\n".join(parts)


def embed_texts_batch(client, texts: list[str]) -> list[list[float]]:
    """Get embeddings for a list of texts (batched, same as ingestion script)."""
    if not texts:
        return []
    batch_size = 100
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = [t if t.strip() else " " for t in texts[i : i + batch_size]]
        resp = client.embeddings.create(input=batch, model=EMBEDDING_MODEL)
        order = {e.index: e.embedding for e in resp.data}
        all_embeddings.extend([order[j] for j in range(len(batch))])
    return all_embeddings


def delete_points_by_source(qdrant: QdrantClient, source: str) -> None:
    """Remove all points with payload.source == source (upsert: replace this document)."""
    qdrant.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector={
            "filter": {
                "must": [{"key": "source", "match": {"value": source}}]
            }
        },
    )


def upsert_pdf_in_qdrant(
    qdrant: QdrantClient,
    embedding_client,
    file_name: str,
    text: str,
) -> int:
    """
    Upsert a single document: delete existing chunks for this source, then insert new chunks.
    Returns number of chunks inserted.
    """
    ensure_collection(qdrant)
    chunks = chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    if not chunks:
        return 0
    delete_points_by_source(qdrant, file_name)
    embeddings = embed_texts_batch(embedding_client, chunks)
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=emb,
            payload={"text": chunk, "source": file_name},
        )
        for emb, chunk in zip(embeddings, chunks)
    ]
    qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points)
    return len(points)


def retrieve_context(qdrant: QdrantClient, query_vector: list[float], top_k: int = MAX_SEARCH_RESULTS) -> str:
    try:
        results = qdrant.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_vector,
            limit=top_k,
        )
        docs = [hit.payload.get("text", "") for hit in results if hit.payload]
        return "\n\n---\n\n".join(docs) if docs else ""
    except Exception:
        return ""


def stream_chat_api(client, model: str, messages: list[dict], placeholder) -> str:
    """Stream from OpenAI-compatible API (OpenAI / OpenRouter)."""
    full = ""
    for chunk in client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
    ):
        if chunk.choices and chunk.choices[0].delta.content:
            full += chunk.choices[0].delta.content
            placeholder.markdown(full + "▌")
    placeholder.markdown(full)
    return full


def stream_chat_ollama(model: str, messages: list[dict], placeholder) -> str:
    """Stream from local Ollama."""
    import json
    import requests
    base = OLLAMA_URL.rstrip("/")
    payload = {"model": model, "messages": messages, "stream": True}
    full = ""
    try:
        r = requests.post(f"{base}/api/chat", json=payload, stream=True, timeout=600)
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            data = json.loads(line)
            if data.get("message", {}).get("content"):
                full += data["message"]["content"]
                placeholder.markdown(full + "▌")
    except Exception:
        raise
    placeholder.markdown(full)
    return full


def render_hero() -> None:
    st.title(PAGE_TITLE)
    st.markdown(
        "Ask questions about **Dutch mortgages**, **tax deductions**, **applications**, and **housing** "
        "based on the ingested government and market documents."
    )
    st.caption("Phase 1: RAG over ingested PDFs (OpenAI + Qdrant). Run `python scripts/ingest_docs.py` if the knowledge base is empty.")


def main() -> None:
    st.set_page_config(page_title=PAGE_TITLE, page_icon="🏠", layout="wide")

    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    available_providers = get_available_llm_providers()
    if "selected_provider" not in st.session_state:
        env_provider = (os.environ.get("LLM_PROVIDER") or "openai").strip().lower()
        st.session_state["selected_provider"] = env_provider if env_provider in available_providers else (available_providers[0] if available_providers else "openai")
    if "selected_model" not in st.session_state:
        models = get_default_llm_models(st.session_state["selected_provider"])
        st.session_state["selected_model"] = LLM_CHOICE_DEFAULT if LLM_CHOICE_DEFAULT in models else (models[0] if models else LLM_CHOICE_DEFAULT)

    try:
        embedding_client = get_embedding_client()
    except RuntimeError as e:
        st.error(str(e))
        st.stop()
    qdrant = get_qdrant()

    with st.sidebar:
        st.header("Phase 1 RAG")
        st.subheader("LLM (from .env)")
        provider = st.selectbox(
            "Provider",
            options=available_providers,
            index=available_providers.index(st.session_state["selected_provider"]) if st.session_state["selected_provider"] in available_providers else 0,
            key="sb_provider",
            help="Only providers with keys set in .env are shown.",
        )
        st.session_state["selected_provider"] = provider
        models = get_default_llm_models(provider)
        current_model = st.session_state["selected_model"]
        model_index = models.index(current_model) if current_model in models else 0
        model = st.selectbox(
            "Model",
            options=models,
            index=model_index,
            key="sb_model",
            help="Default from .env LLM_CHOICE / OLLAMA_MODEL. Add LLM_MODELS_OPENAI etc. for more.",
        )
        st.session_state["selected_model"] = model
        st.caption(f"Embeddings: `{EMBEDDING_MODEL}`")
        st.write(f"Qdrant: `{QDRANT_URL}` · `{QDRANT_COLLECTION}`")
        if st.button("Clear conversation", use_container_width=True):
            st.session_state["messages"] = []
            st.rerun()
        top_k = st.slider("Retrieval chunks (top-k)", 3, 20, MAX_SEARCH_RESULTS)

        st.divider()
        st.subheader("Add PDF (upsert)")
        st.caption("Upload adds or replaces this document only. Batch replace: run `python scripts/ingest_docs.py`.")
        uploaded_pdf = st.file_uploader("Upload a PDF", type=["pdf"], key="phase1_pdf_upload")
        if uploaded_pdf is not None:
            with st.spinner("Chunking, embedding, and upserting …"):
                try:
                    raw = uploaded_pdf.read()
                    text = extract_text_from_pdf_bytes(raw)
                    n = upsert_pdf_in_qdrant(qdrant, embedding_client, uploaded_pdf.name, text)
                    st.success(f"Upserted {n} chunks from **{uploaded_pdf.name}**.")
                except Exception as e:
                    st.error(f"Upload failed: {e}")

    render_hero()

    for msg in st.session_state["messages"]:
        st.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input("Ask about Dutch mortgages, tax, or housing..."):
        st.session_state["messages"].append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)

        # Retrieve context from Qdrant
        query_embedding = get_embedding(embedding_client, prompt)
        context = retrieve_context(qdrant, query_embedding, top_k=top_k)

        if context:
            user_content = (
                "Use the following context from our documents to answer. If the answer is not in the context, say so.\n\n"
                "Context:\n" + context + "\n\nQuestion: " + prompt
            )
        else:
            user_content = (
                "No relevant documents were found in the knowledge base. "
                "Please answer based on general knowledge and suggest the user run `python scripts/ingest_docs.py` to load documents.\n\nQuestion: " + prompt
            )

        messages_for_llm = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in st.session_state["messages"][:-1]:
            messages_for_llm.append({"role": m["role"], "content": m["content"]})
        messages_for_llm.append({"role": "user", "content": user_content})

        placeholder = st.chat_message("assistant").empty()
        try:
            prov = st.session_state["selected_provider"]
            mod = st.session_state["selected_model"]
            if prov == "ollama":
                answer = stream_chat_ollama(mod, messages_for_llm, placeholder)
            else:
                llm_client = get_llm_client(provider_override=prov)
                answer = stream_chat_api(llm_client, mod, messages_for_llm, placeholder)
            st.session_state["messages"].append({"role": "assistant", "content": answer})
        except Exception as e:
            placeholder.error(f"Error calling LLM: {e}")
            st.session_state["messages"].pop()


if __name__ == "__main__":
    main()
