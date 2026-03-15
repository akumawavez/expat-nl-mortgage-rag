## Referring https://github.com/ThomasJanssen-tech/Ollama-Chatbot

"""
Dutch Real Estate Buyers Assistant – LangChain RAG Version
Uses Qdrant for Knowledge Base Management and LangChain AgentExecutor for chat.
"""

from __future__ import annotations
import streamlit as st

## Langchain modules and pdf processing.
from pypdf import PdfReader
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

## For Qdrant
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue



import os
import json
import uuid
from typing import List



# =============================================================================
# --- Configuration ---
# =============================================================================
PAGE_TITLE = "Dutch Real Estate Buyers Assistant"
st.set_page_config(page_title=PAGE_TITLE, page_icon="🏠", layout="wide")

# Environment variables (you can also hardcode if preferred)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = "property_docs"
CHAT_MODEL = os.getenv("CHAT_MODEL", "llama3.2:3b")
EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")


# =============================================================================
# --- Initialize Qdrant and Embeddings ---
# =============================================================================
qdrant = QdrantClient(url=QDRANT_URL)
embedder = OllamaEmbeddings(model=EMBED_MODEL)

# Determine embedding dimension automatically
test_vector = embedder.embed_query("test")
embedding_dim = len(test_vector)

# Ensure collection exists (create with correct size)
existing = [c.name for c in qdrant.get_collections().collections or []]
if QDRANT_COLLECTION not in existing:
    qdrant.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE),
    )

# =============================================================================
# --- Helper functions for PDF and Qdrant ---
# =============================================================================
def process_pdf(uploaded_file) -> list[str]:
    """Extract and chunk text from PDF."""
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    chunks = [text[i:i + 1000] for i in range(0, len(text), 1000)]
    return chunks


def store_pdf_in_qdrant(file_name: str, chunks: list[str]):
    """Embed and store PDF chunks in Qdrant."""
    embeddings = [embedder.embed_query(chunk) for chunk in chunks]
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=emb,
            payload={"text": chunk, "source": file_name},
        )
        for emb, chunk in zip(embeddings, chunks)
    ]
    qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points)



def retrieve_relevant_context(query: str, top_k: int = 1) -> str:
    """Retrieve top relevant text chunks from Qdrant for a given query."""
    # query_emb = list(embedder.embed([query]))[0]  # fastembed returns a generator
    query_emb = embedder.embed_query(query)  ## For using OLLAMA.
    search_result = qdrant.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=query_emb,
        limit=top_k,
    )
    docs = [hit.payload["text"] for hit in search_result if "text" in hit.payload]
    return "\n\n".join(docs)

def list_documents() -> list[str]:
    """List all distinct sources in Qdrant."""
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


def delete_document(file_name: str):
    """Delete all vectors for a document."""
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


# # =============================================================================
# # --- Streamlit UI ---
# # =============================================================================
tab_chat, tab_knowledge = st.tabs(["💬 Assistant", "🧠 Knowledge Base"])


# -------------------------------------------------------------------------
# 💬 CHAT TAB
# -------------------------------------------------------------------------
with tab_chat:
    st.title(PAGE_TITLE)

    # initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

        st.session_state.messages.append(SystemMessage("""
        You are an expert assistant helping international buyers navigate the Dutch 
        real estate market. Provide concise, trustworthy answers, explain regulatory 
        nuances, highlight risks, and suggest practical next steps. If a question is 
        outside property purchasing, politely steer the user back on topic.
                                                    """))

    # display chat messages from history on app rerun
    for message in st.session_state.messages:
        if isinstance(message, HumanMessage):
            with st.chat_message("user"):
                st.markdown(message.content)
        elif isinstance(message, AIMessage):
            with st.chat_message("assistant"):
                st.markdown(message.content)

    bottom_placeholder = st._bottom.empty()

    # create the bar where we can type messages
    prompt = bottom_placeholder.chat_input("What do you want to know about Dutch real estate?")

    # did the user submit a prompt?
    if prompt:

        # add the message from the user (prompt) to the screen with streamlit
        with st.chat_message("user"):
            st.markdown(prompt)

            st.session_state.messages.append(HumanMessage(prompt))

        # create the echo (response) and add it to the screen

        llm = ChatOllama(
            model="llama3.2:3b",
            temperature=0
        )

        context = retrieve_relevant_context(prompt)

        if context:
            augmented_prompt = (
                f"Use the following context extracted from uploaded documents to answer accurately:\n\n"
                f"{context}\n\n"
                f"User question: {prompt}"
            )
        else:
            augmented_prompt = prompt

        # result = llm.invoke(st.session_state.messages).content
        result = llm.invoke(augmented_prompt).content

        with st.chat_message("assistant"):
            st.markdown(result)

            st.session_state.messages.append(AIMessage(result))

            




# -------------------------------------------------------------------------
# 🧠 KNOWLEDGE BASE TAB
# -------------------------------------------------------------------------
with tab_knowledge:
    st.header("Knowledge Base Management")
    st.write("Upload, list, and delete property-related PDFs in your Qdrant vector database.")

    # Upload
    st.subheader("📤 Upload PDF")
    uploaded_pdf = st.file_uploader("Upload a property or mortgage-related PDF", type=["pdf"])

    if uploaded_pdf is not None:
        with st.spinner("Processing and embedding your PDF..."):
            chunks = process_pdf(uploaded_pdf)
            store_pdf_in_qdrant(uploaded_pdf.name, chunks)
        st.success(f"Stored {len(chunks)} chunks from {uploaded_pdf.name} in Qdrant.")

    st.divider()
    st.subheader("📚 Current Documents")

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
