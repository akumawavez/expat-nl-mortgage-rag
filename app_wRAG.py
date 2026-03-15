"""Streamlit app for Dutch Real Estate Buyers Assistant."""
from __future__ import annotations

import json
import os
from typing import Generator, Iterable
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
import uuid
import requests
import streamlit as st

PAGE_TITLE = "Dutch Real Estate Buyers Assistant"
# DEFAULT_MODEL = "gpt-oss:20b"
DEFAULT_MODEL = "llama3:8b"
SYSTEM_PROMPT = (
    "You are an expert assistant helping international buyers navigate the Dutch "
    "real estate market. Provide concise, trustworthy answers, explain regulatory "
    "nuances, highlight risks, and suggest practical next steps. If a question is "
    "outside property purchasing, politely steer the user back on topic."
)
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)


# --- RAG setup ---
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = "property_docs"

embedder = SentenceTransformer("all-MiniLM-L6-v2")
embedding_dim = embedder.get_sentence_embedding_dimension()

qdrant = QdrantClient(url=QDRANT_URL)

# Ensure collection exists
if QDRANT_COLLECTION not in [c.name for c in qdrant.get_collections().collections or []]:
    qdrant.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE),
    )



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
        response = requests.get(
            f"{OLLAMA_URL.rstrip('/')}/api/tags",
            timeout=10,
        )
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
    messages: Iterable[dict[str, str]],
    model_name: str,
) -> Generator[str, None, None]:
    """Stream a response from the local Ollama server."""

    history = list(messages)

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

    base_url = OLLAMA_URL.rstrip("/")

    try:
        yield from _stream_chat()
    except FileNotFoundError:
        yield from _stream_generate()


def render_hero_section() -> None:
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
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    history.extend(st.session_state.get("messages", []))
    return history

def process_pdf(uploaded_file) -> list[str]:
    """Extract text chunks from uploaded PDF."""
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    # Simple fixed-size chunking
    chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
    return chunks


def store_pdf_in_qdrant(file_name: str, chunks: list[str]):
    """Embed and store PDF chunks in Qdrant."""
    embeddings = embedder.encode(chunks).tolist()
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=emb,
            payload={"text": chunk, "source": file_name},
        )
        for emb, chunk in zip(embeddings, chunks)
    ]
    qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points)


def retrieve_relevant_context(query: str, top_k: int = 3) -> str:
    """Retrieve top relevant chunks for a given query."""
    query_emb = embedder.encode(query).flatten().tolist()
    search_result = qdrant.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=query_emb,
        limit=top_k,
    )
    docs = [hit.payload["text"] for hit in search_result if "text" in hit.payload]
    return "\n\n".join(docs)


def main() -> None:
    st.set_page_config(page_title=PAGE_TITLE, page_icon="🏠", layout="wide")

    if "messages" not in st.session_state:
        st.session_state["messages"] = []


    with st.sidebar:
        st.header("Assistant Settings")
        st.write(
            "Connecting to your local Ollama server at "
            f"`{OLLAMA_URL}` using model `{MODEL_NAME}`."
        )
        if st.button("Clear conversation", use_container_width=True):
            st.session_state["messages"] = []
            st.experimental_rerun()

        st.subheader("Tips")
        st.caption(
            "Keep your questions focused on Dutch real estate to get actionable insights. "
            f"If the assistant seems slow, confirm that `ollama run {MODEL_NAME}` is active."
        )

        st.subheader("Knowledge Upload")
        uploaded_pdf = st.file_uploader("Upload property or mortgage PDFs", type=["pdf"])

        if uploaded_pdf is not None:
           with st.spinner("Processing and embedding your PDF..."):
            chunks = process_pdf(uploaded_pdf)
            store_pdf_in_qdrant(uploaded_pdf.name, chunks)
           st.success(f"Stored {len(chunks)} chunks from {uploaded_pdf.name} in Qdrant.")


    render_hero_section()

    for message in st.session_state["messages"]:
        st.chat_message(message["role"]).write(message["content"])

    # if prompt := st.chat_input("Ask about Dutch property buying, financing, or neighborhoods..."):
    #     st.chat_message("user").write(prompt)

    #     # placeholder = st.chat_message("assistant")
    #     # response_container = placeholder.empty()
    #     # generated_text = ""

    #     # Retrieve relevant context from Qdrant
    #     context = retrieve_relevant_context(prompt)
    #     if context:
    #         augmented_prompt = (
    #             f"Use the following context extracted from uploaded documents to answer accurately:\n\n"
    #             f"{context}\n\n"
    #             f"User question: {prompt}"
    #         )
    #     else:
    #         augmented_prompt = prompt

    #     st.session_state["messages"].append({"role": "user", "content": augmented_prompt})
        

    #     try:
    #         for chunk in stream_ollama_response(build_history(), MODEL_NAME):
    #             generated_text += chunk
    #             response_container.markdown(generated_text)
    #     except requests.exceptions.RequestException as exc:
    #         error_msg = (
    #             "Could not reach the Ollama server. Make sure it is running on your machine "
    #             f"and accessible at `{OLLAMA_URL}`. Details: {exc}"
    #         )
    #         response_container.error(error_msg)
    #         st.session_state["messages"].pop()
    #         return
    #     except RuntimeError as exc:  # raised when Ollama returns an error payload
    #         response_container.error(f"Ollama returned an error: {exc}")
    #         st.session_state["messages"].pop()
    #         return

    #     st.session_state["messages"].append({"role": "assistant", "content": generated_text})

    if prompt := st.chat_input("Ask about Dutch property buying, financing, or neighborhoods..."):
        st.chat_message("user").write(prompt)

        # Retrieve relevant context from Qdrant
        context = retrieve_relevant_context(prompt)
        if context:
            augmented_prompt = (
                f"Use the following context extracted from uploaded documents to answer accurately:\n\n"
                f"{context}\n\n"
                f"User question: {prompt}"
            )
        else:
            augmented_prompt = prompt

        # Add augmented prompt to conversation
        st.session_state["messages"].append({"role": "user", "content": augmented_prompt})

        # Initialize UI placeholders
        placeholder = st.chat_message("assistant")
        response_container = placeholder.empty()
        generated_text = ""  # ✅ Initialize early!

        try:
            for chunk in stream_ollama_response(build_history(), MODEL_NAME):
                generated_text += chunk
                response_container.markdown(generated_text)
        except requests.exceptions.RequestException as exc:
            error_msg = (
                "Could not reach the Ollama server. Make sure it is running on your machine "
                f"and accessible at `{OLLAMA_URL}`. Details: {exc}"
            )
            response_container.error(error_msg)
            st.session_state["messages"].pop()
            return
        except RuntimeError as exc:
            response_container.error(f"Ollama returned an error: {exc}")
            st.session_state["messages"].pop()
            return

        # ✅ Always safe to reference now
        st.session_state["messages"].append({"role": "assistant", "content": generated_text})


if __name__ == "__main__":
    main()
