"""Streamlit app for Dutch Real Estate Buyers Assistant with RAG and Knowledge Management."""

from __future__ import annotations

import json
import os
import uuid
from typing import Generator, Iterable

import requests
import streamlit as st
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
# from sentence_transformers import SentenceTransformer
from fastembed import TextEmbedding



# =============================================================================
# --- Configuration and Constants ---
# =============================================================================
PAGE_TITLE = "Dutch Real Estate Buyers Assistant"
DEFAULT_MODEL = "llama3:8b"
SYSTEM_PROMPT = (
    "You are an expert assistant helping international buyers navigate the Dutch "
    "real estate market. Provide concise, trustworthy answers, explain regulatory "
    "nuances, highlight risks, and suggest practical next steps. If a question is "
    "outside property purchasing, politely steer the user back on topic."
)
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)

# --- Qdrant Configuration ---
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = "property_docs"

# =============================================================================
# --- Initialize SentenceTransformer/FastEmbed and Qdrant Client ---
# =============================================================================
# os.environ["TORCH_LOAD_EAGER"] = "1"
# embedder = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
# embedder = embedder.to("cpu", non_blocking=True)
# embedding_dim = embedder.get_sentence_embedding_dimension()

# Initialize the lightweight embedder
embedder = TextEmbedding(model_name="BAAI/bge-small-en")

# FastEmbed model metadata
# embedding_dim = embedder.embedding_dimension
embedding_dim = len(list(embedder.embed(["test"]))[0])



qdrant = QdrantClient(url=QDRANT_URL)

# Ensure the vector collection exists
existing_collections = [c.name for c in qdrant.get_collections().collections or []]
if QDRANT_COLLECTION not in existing_collections:
    qdrant.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE),
    )


# =============================================================================
# --- Ollama Streaming Utilities ---
# =============================================================================
class ModelNotFoundError(RuntimeError):
    """Raised when the requested Ollama model cannot be found."""


def _extract_error_message(response: requests.Response) -> str | None:
    """Return a human-readable error message from an Ollama response."""
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        return text or None
    if isinstance(payload, dict):
        message = payload.get("error") or payload.get("message")
        if message:
            return str(message)
    return None


def load_available_models() -> list[str]:
    """Fetch the list of locally pulled Ollama models."""
    try:
        response = requests.get(f"{OLLAMA_URL.rstrip('/')}/api/tags", timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return []

    try:
        payload = response.json()
    except ValueError:
        return []

    models = payload.get("models", [])
    return [item.get("name") for item in models if item.get("name")]


def stream_ollama_response(
    messages: Iterable[dict[str, str]], model_name: str
) -> Generator[str, None, None]:
    """Stream a response from the local Ollama server for a given chat history."""
    history = list(messages)
    base_url = OLLAMA_URL.rstrip("/")

    def _stream_chat() -> Generator[str, None, None]:
        payload = {"model": model_name, "messages": history, "stream": True}
        response = requests.post(
            url=f"{base_url}/api/chat",
            json=payload,
            stream=True,
            timeout=600,
        )
        if response.status_code == 404:
            response.close()
            raise FileNotFoundError("chat-endpoint-not-available")
        response.raise_for_status()

        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            data = json.loads(line)
            if "error" in data:
                raise RuntimeError(data["error"])
            if data.get("done"):
                break
            chunk = data.get("message", {}).get("content", "")
            if chunk:
                yield chunk

    def _stream_generate() -> Generator[str, None, None]:
        def build_prompt(history: Iterable[dict[str, str]]) -> str:
            """Convert chat messages to a simple prompt format for /generate."""
            parts: list[str] = []
            for item in history:
                role = item.get("role", "user").capitalize()
                content = item.get("content", "")
                parts.append(f"{role}: {content}")
            parts.append("Assistant:")
            return "\n".join(parts)

        payload = {"model": MODEL_NAME, "prompt": build_prompt(history), "stream": True}
        response = requests.post(
            url=f"{base_url}/api/generate",
            json=payload,
            stream=True,
            timeout=600,
        )
        response.raise_for_status()

        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            data = json.loads(line)
            if "error" in data:
                raise RuntimeError(data["error"])
            if data.get("done"):
                break
            chunk = data.get("response", "")
            if chunk:
                yield chunk

    try:
        yield from _stream_chat()
    except FileNotFoundError:
        yield from _stream_generate()


# =============================================================================
# --- Streamlit UI Utility Functions ---
# =============================================================================
def render_hero_section() -> None:
    """Render the main introduction section for the app."""
    col_left, col_right = st.columns([2, 1])
    with col_left:
        st.title(PAGE_TITLE)
        st.markdown(
            """
            Helping expats and locals confidently navigate property purchases in the Netherlands.

            - Decode bidding strategies, mortgage steps, and legal requirements  
            - Compare neighborhoods with livability, commute, and pricing insights  
            - Gather due diligence tips before you sign or schedule a viewing
            """
        )
        st.markdown(
            "<p style='font-size:1rem; color:#4B5563;'>Ready to explore the Dutch housing market? Ask a question below.</p>",
            unsafe_allow_html=True,
        )
    with col_right:
        st.markdown(
            "<div style='background:#F1F5F9;border-radius:18px;padding:24px;text-align:center;'>"
            "<h3 style='margin-bottom:8px;'>Market Snapshot</h3>"
            "<p style='margin:0;color:#475569;'>Use the assistant to estimate budgets, prepare for bidding rounds, and clarify municipal rules.</p>"
            "</div>",
            unsafe_allow_html=True,
        )


def build_history() -> list[dict[str, str]]:
    """Combine system prompt and past messages into a single conversation history."""
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    history.extend(st.session_state.get("messages", []))
    return history


# =============================================================================
# --- PDF Processing and Qdrant Helper Functions ---
# =============================================================================
def process_pdf(uploaded_file) -> list[str]:
    """Extract text chunks from uploaded PDF for embedding."""
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    # Simple fixed-size chunking for embedding
    chunks = [text[i:i + 1000] for i in range(0, len(text), 1000)]
    return chunks


def store_pdf_in_qdrant(file_name: str, chunks: list[str]):
    """Embed and store PDF chunks in Qdrant."""
    # embeddings = embedder.encode(chunks).tolist()   ---- For Sentence Transformers
    embeddings = list(embedder.embed(chunks))     ## For FastEmbed

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=emb,
            payload={"text": chunk, "source": file_name},
        )
        for emb, chunk in zip(embeddings, chunks)
    ]
    qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points)


# def retrieve_relevant_context(query: str, top_k: int = 3) -> str:
#     """Retrieve top relevant text chunks from Qdrant for a given query."""
#     query_emb = embedder.encode(query).flatten().tolist()
#     search_result = qdrant.search(
#         collection_name=QDRANT_COLLECTION,
#         query_vector=query_emb,
#         limit=top_k,
#     )
#     docs = [hit.payload["text"] for hit in search_result if "text" in hit.payload]
#     return "\n\n".join(docs)

def retrieve_relevant_context(query: str, top_k: int = 3) -> str:
    """Retrieve top relevant text chunks from Qdrant for a given query."""
    query_emb = list(embedder.embed([query]))[0]  # fastembed returns a generator
    search_result = qdrant.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=query_emb,
        limit=top_k,
    )
    docs = [hit.payload["text"] for hit in search_result if "text" in hit.payload]
    return "\n\n".join(docs)


def list_documents() -> list[str]:
    """List all distinct document sources currently in Qdrant."""
    points, _ = qdrant.scroll(
        collection_name=QDRANT_COLLECTION,
        limit=1000,
        with_payload=True,
        with_vectors=False,
    )
    sources = set()
    for p in points:
        if "source" in p.payload:
            sources.add(p.payload["source"])
    return sorted(list(sources))


from qdrant_client.models import Filter, FieldCondition, MatchValue

def delete_document(file_name: str):
    """Delete all vectors associated with a specific file from Qdrant."""
    qdrant.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="source",
                    match=MatchValue(value=file_name)
                )
            ]
        ),
    )


# =============================================================================
# --- Main Streamlit Application ---
# =============================================================================
def main() -> None:
    """Main entry point for the Streamlit Dutch Real Estate Buyers Assistant."""
    st.set_page_config(page_title=PAGE_TITLE, page_icon="🏠", layout="wide")

    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    # Two tabs: Assistant (chat) and Knowledge Base (RAG management)
    tab_assistant, tab_knowledge = st.tabs(["💬 Assistant", "🧠 Knowledge Base"])

    # -------------------------------------------------------------------------
    # 💬 CHAT ASSISTANT TAB
    # -------------------------------------------------------------------------
    with tab_assistant:
        with st.sidebar:
            st.header("Assistant Settings")
            st.write(
                f"Connected to your local Ollama server at `{OLLAMA_URL}` using model `{MODEL_NAME}`."
            )
            if st.button("Clear conversation", use_container_width=True):
                st.session_state["messages"] = []
                st.experimental_rerun()

            st.subheader("Tips")
            st.caption(
                "Keep your questions focused on Dutch real estate for best results. "
                f"If the assistant seems slow, confirm `ollama run {MODEL_NAME}` is active."
            )

        render_hero_section()

        # # Display chat history
        for message in st.session_state["messages"]:
            st.chat_message(message["role"]).write(message["content"])

        # Input for user prompt
        if prompt := st.chat_input("Ask about Dutch property buying, financing, or neighborhoods..."):
             
            # Show only the user's raw question in the chat
            st.chat_message("user").write(prompt)

            # Retrieve context from Qdrant
            context = retrieve_relevant_context(prompt)
            if context:
                augmented_prompt = (
                    f"Use the following context extracted from uploaded documents to answer accurately:\n\n"
                    f"{context}\n\n"
                    f"User question: {prompt}"
                )
            else:
                augmented_prompt = prompt

            # Add augmented message to chat history
            # st.session_state["messages"].append({"role": "user", "content": augmented_prompt})

            # Store only the plain user question for history - to avoid accumulation of context as well
            st.session_state["messages"].append({"role": "user", "content": prompt})

            # Build a temporary history for this call
            temp_history = build_history()
            # Replace the latest user message in this temp history with the augmented one
            temp_history[-1]["content"] = augmented_prompt

            # Prepare assistant placeholder
            placeholder = st.chat_message("assistant")
            response_container = placeholder.empty()
            generated_text = ""

            # Show context temporarily (optional, collapsible box)
            if context:
                with st.expander("📄 Context retrieved from uploaded documents", expanded=False):
                    st.markdown(context)

            try:
                for chunk in stream_ollama_response(temp_history, MODEL_NAME):
                    generated_text += chunk
                    response_container.markdown(generated_text)
            except requests.exceptions.RequestException as exc:
                response_container.error(
                    f"Could not reach the Ollama server at `{OLLAMA_URL}`. Details: {exc}"
                )
                st.session_state["messages"].pop()
                return
            except RuntimeError as exc:
                response_container.error(f"Ollama returned an error: {exc}")
                st.session_state["messages"].pop()
                return

            # Store assistant reply
            st.session_state["messages"].append(
                {"role": "assistant", "content": generated_text}
            )

    # -------------------------------------------------------------------------
    # 🧠 KNOWLEDGE MANAGEMENT TAB
    # -------------------------------------------------------------------------
    with tab_knowledge:
        st.header("Knowledge Base Management")
        st.write("Upload, list, and delete documents stored in the Qdrant vector database.")

        # --- Upload PDF Section ---
        st.subheader("📤 Upload New Document")
        uploaded_pdf = st.file_uploader("Upload a property or mortgage-related PDF", type=["pdf"])

        if uploaded_pdf is not None:
            with st.spinner("Processing and embedding your PDF..."):
                chunks = process_pdf(uploaded_pdf)
                store_pdf_in_qdrant(uploaded_pdf.name, chunks)
            st.success(f"Stored {len(chunks)} chunks from {uploaded_pdf.name} in Qdrant.")

        # --- Document Listing Section ---
        st.divider()
        st.subheader("📚 Current Documents in Knowledge Base")

        docs = list_documents()
        if not docs:
            st.info("No documents currently stored in Qdrant.")
        else:
            for doc in docs:
                col1, col2 = st.columns([4, 1])
                col1.markdown(f"- **{doc}**")
                if col2.button("🗑️ Delete", key=f"del_{doc}"):
                    delete_document(doc)
                    st.warning(f"Deleted all vectors for {doc}.")
                    st.experimental_rerun()


# =============================================================================
# --- Entry Point ---
# =============================================================================
if __name__ == "__main__":
    main()
