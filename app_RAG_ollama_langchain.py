"""
Dutch Real Estate Buyers Assistant – LangChain RAG Version
Uses Qdrant for Knowledge Base Management and LangChain AgentExecutor for chat.
"""

from __future__ import annotations
import os
import json
import uuid
import streamlit as st
from typing import List

from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

# LangChain imports
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_ollama import OllamaEmbeddings
from langchain_ollama import ChatOllama

from fastembed import TextEmbedding

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool


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

# =============================================================================
# --- LangChain RAG Agent Setup ---
# =============================================================================
# llm = init_chat_model(
#     model=CHAT_MODEL,
#     model_provider="ollama",
#     temperature=0,
#     streaming=True,  # 👈 enable token streaming
# )

# llm.invoke("Hello")  # pre-warm

llm = ChatOllama(model="llama3.2", streaming=True)

with st.chat_message("assistant"):
    placeholder = st.empty()
    collected = ""

    for chunk in llm.stream(user_question):
        collected += chunk.content
        placeholder.markdown(collected + "▌")
    placeholder.markdown(collected)


# Prompt Template
prompt = PromptTemplate.from_template("""
You are an expert assistant helping expats navigate the Dutch real estate market.
Use the tool 'retrieve' to get context from uploaded documents.
Answer clearly, concisely, and cite sources when applicable.

The user question:
{input}

Chat history:
{chat_history}

Scratchpad:
{agent_scratchpad}

Return answer as plain text only.
""")

# Tool: retrieve
@tool
def retrieve(query: str):
    """Retrieve relevant information for the user's query from Qdrant."""
    query_emb = embedder.embed_query(query)
    search_result = qdrant.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=query_emb,
        limit=3,
    )

    serialized = ""
    for hit in search_result:
        source = hit.payload.get("source", "unknown")
        content = hit.payload.get("text", "")
        serialized += f"Source: {source}\nContent: {content}\n\n"
    return serialized

tools = [retrieve]

agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False)

# =============================================================================
# --- Streamlit UI ---
# =============================================================================
tab_chat, tab_knowledge = st.tabs(["💬 Assistant", "🧠 Knowledge Base"])

# -------------------------------------------------------------------------
# 💬 CHAT TAB
# -------------------------------------------------------------------------
with tab_chat:
    st.title("💬 Dutch Real Estate Buyers Assistant")

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for msg in st.session_state.messages:
        if isinstance(msg, HumanMessage):
            with st.chat_message("user"):
                st.markdown(msg.content)
        elif isinstance(msg, AIMessage):
            with st.chat_message("assistant"):
                st.markdown(msg.content)

    # Input
    user_question = st.chat_input("Ask about buying property, mortgages, or regulations in the Netherlands...")

    if user_question:
        # Display user input
        with st.chat_message("user"):
            st.markdown(user_question)
        st.session_state.messages.append(HumanMessage(user_question))

        # # Call the LangChain agent
        # result = agent_executor.invoke({
        #     "input": user_question,
        #     "chat_history": st.session_state.messages,
        # })

        # ai_response = result["output"]

        # # Display assistant reply
        # with st.chat_message("assistant"):
        #     st.markdown(ai_response)
        # st.session_state.messages.append(AIMessage(ai_response))

        with st.chat_message("assistant"):
            placeholder = st.empty()
            response = ""

            for event in agent_executor.stream({"input": user_question, "chat_history": st.session_state.messages}):
                if "output" in event:
                    response += event["output"]
                    placeholder.markdown(response + "▌")

            placeholder.markdown(response)
            st.session_state.messages.append(AIMessage(response))



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
