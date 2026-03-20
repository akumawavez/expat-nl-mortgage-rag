# Architecture & End-to-End Workflow

This document describes the high-level architecture, main components, and end-to-end data flow of the Expat NL Mortgage RAG system. For deployment and operations, see [DEPLOYMENT.md](../DEPLOYMENT.md) and [docs/monitoring.md](monitoring.md).

---

## System overview

```mermaid
flowchart TB
    subgraph UI["Frontend (Streamlit)"]
        Chat[Chat tab]
        Calc[Mortgage Calculator]
        Map[Map tab]
        Docs[Documents tab]
        KG[Knowledge Graph tab]
        Obs[Observability tab]
    end

    subgraph Core["Core services / lib"]
        Retrieval[lib/retrieval]
        Provider[lib/provider]
        Chunking[lib/chunking]
        Agents[lib/agents]
        Location[lib/location]
        GraphKG[lib/graph_kg]
    end

    subgraph Data["Data & external"]
        Qdrant[(Qdrant)]
        PDFs[PDF documents]
        OSRM[OSRM / Nominatim]
    end

    Chat --> Retrieval
    Chat --> Provider
    Chat --> Agents
    Docs --> Chunking
    Retrieval --> Qdrant
    Provider --> Qdrant
    Map --> Location
    Location --> OSRM
    KG --> GraphKG
    Docs --> Qdrant
    PDFs --> Chunking
    Chunking --> Qdrant
```

---

## Component diagram

```mermaid
flowchart LR
    subgraph App["app.py"]
        Sidebar[Sidebar: provider, model, toggles]
        Tabs[Tabs: Chat, Calculator, Map, Documents, KG, Observability, Agents]
    end

    subgraph Lib["lib/"]
        retrieval[retrieval.py: vector_search, hybrid_retrieve]
        provider[provider.py: LLM + embedding clients]
        chunking[chunking.py: chunk_text]
        agents[agents.py: orchestrator, route_query]
        location[location.py: nearby_places, osrm_commute, area_safety]
        graph_kg[graph_kg.py: build_kg_from_text]
        documents[documents.py: list_documents_in_store, upsert_pdf_to_qdrant]
    end

    subgraph Scripts["scripts/"]
        ingest[ingest_docs.py]
        test_ingest[test_ingestion.py]
        run_ragas[run_ragas.py]
        metrics_srv[metrics_server.py]
    end

    App --> Lib
    ingest --> chunking
    ingest --> provider
    ingest --> Qdrant[(Qdrant)]
    retrieval --> Qdrant
```

---

## End-to-end workflow: Chat (RAG)

```mermaid
sequenceDiagram
    participant User
    participant App
    participant Retrieval
    participant Qdrant
    participant LLM

    User->>App: Ask question (Chat tab)
    App->>App: Resolve provider/model from sidebar
    App->>Retrieval: vector_search or hybrid_retrieve(query)
    Retrieval->>Qdrant: search(collection, query_vector)
    Qdrant-->>Retrieval: chunks (text, source, score)
    Retrieval-->>App: chunks + tool_calls
    opt Web search on
        App->>App: Tavily search
        App->>App: Append web context
    end
    App->>App: Build context string from chunks (+ web)
    App->>LLM: chat.completions.create(system, context, question)
    LLM-->>App: streamed answer
    App->>App: Store message + sources + tools_used
    App->>User: Show answer, Tools Used, Source tracing
```

---

## End-to-end workflow: Document ingestion

```mermaid
flowchart TD
    A[PDFs in gov docs/ or project root] --> B[ingest_docs.py]
    B --> C[extract_text_from_pdf]
    C --> D[chunk_text - simple or semantic]
    D --> E[get_embedding_client]
    E --> F[embed_texts batch]
    F --> G[Qdrant upsert]
    G --> H[Collection: property_docs]
    H --> I[Chat retrieval uses same collection]
```

---

## End-to-end workflow: Phase 4 agents (optional)

When “Use Phase 4 agents” is enabled in the sidebar:

```mermaid
flowchart TD
    Q[User query] --> R[route_query]
    R --> S1[retrieval_agent]
    R --> S2[location_agent]
    R --> S3[calculator_agent]
    S1 --> T1[retrieval_fn: vector/hybrid]
    S2 --> T2[location_fn: nearby_places]
    S3 --> T3[calculator_fn: pointer to tab]
    T1 --> AGG[Aggregate context]
    T2 --> AGG
    T3 --> AGG
    AGG --> LLM[LLM with combined context]
    LLM --> OUT[Answer + tool_calls + A2UI directives]
```

---

## Data flow summary

| Flow | Input | Output |
|------|--------|--------|
| **Ingestion** | PDF paths, `.env` (Qdrant, embedding API) | Chunks in Qdrant with `payload.text`, `payload.source` |
| **Chat (RAG)** | User message, sidebar settings | Answer, sources (document + chunk), tools_used |
| **Documents tab** | List: scroll Qdrant. Upload: PDF file | List of sources + chunk counts; new chunks upserted |
| **Observability** | Langfuse (if configured), drift_detection.json | Token/cost, quality/drift indicators in UI |
| **Metrics server** | Separate process: `scripts/metrics_server.py` | Prometheus `/metrics` (counters, latency histograms) |

---

## Key configuration

- **Single entry point**: `app.py` (Streamlit).
- **Vector store**: Qdrant; collection name and dimension from `.env` (`QDRANT_COLLECTION`, `VECTOR_DIMENSION`).
- **LLM/embeddings**: `lib/provider.py`; provider and model from sidebar (driven by `.env` keys and `LLM_MODELS_*` / `OLLAMA_MODELS`).
- **Chunking**: `lib/chunking.py`; ingestion uses `scripts/ingest_docs.py` (simple or `--semantic`); Documents tab upload uses `lib/documents.chunk_text_simple`.

See [DEPLOYMENT.md](../DEPLOYMENT.md) for environment variables and platform notes.
