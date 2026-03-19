# Vector databases and RAG patterns: conceptual overview

This document explains **vector databases** and **RAG (Retrieval-Augmented Generation) patterns** at a conceptual level. It is documentation only—no code is executed. Implementation details for this project are in [lib/retrieval.py](lib/retrieval.py), [lib/chunking.py](lib/chunking.py), and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## 1. Why vector databases?

### 1.1 The problem with traditional search

- **Keyword search** (e.g. BM25, SQL `LIKE`, full-text index) matches **lexical overlap**: the query and the document must share words or stems. “Mortgage interest deduction” will not match a paragraph that says “hypotheekrenteaftrek” or “tax relief on loan interest” unless those exact terms appear.
- **Semantic similarity** is different: two phrases that *mean* the same thing should be close even if they use different words. Vector databases are built for this: they store **embeddings** (dense numerical vectors) and retrieve by **similarity in vector space**, not by keywords.

### 1.2 Embeddings

- An **embedding model** maps a piece of text (a sentence, a paragraph, a document) to a fixed-size vector of real numbers (e.g. 384 or 1536 dimensions). Semantically similar texts tend to have vectors that are “close” under a chosen distance measure.
- **Distance measures:** The most common are **cosine similarity** (angle between vectors; invariant to length) and **Euclidean distance** (L2). Many vector DBs use cosine or a variant (e.g. inner product after normalization). Smaller distance or larger similarity ⇒ more relevant.
- **Same space:** For retrieval to work, the **query** and the **documents** must be embedded with the **same model** (or compatible models in the same space). If you re-train or change the embedding model, you typically must re-embed and re-index all documents.

### 1.3 What a vector database does

- **Store:** Each item (e.g. a text chunk) is represented by an **id**, a **vector**, and optional **payload** (metadata: source file, page, raw text, etc.).
- **Index:** The database builds an index over the vectors so that **similarity search** (e.g. “find the k nearest vectors to this query vector”) is fast even with millions of vectors. Common index types include flat (exact search), IVF (inverted file), HNSW (graph-based), or hybrid; the choice trades off build time, memory, and recall/latency.
- **Query:** The client sends a **query vector** and parameters (e.g. top-k, score threshold, optional filters on payload). The DB returns the **nearest** vectors (and their payloads) ranked by similarity score.
- **Why not a regular DB?** Relational or document DBs are not optimized for high-dimensional nearest-neighbor search; vector DBs (and vector extensions in some SQL DBs) are built for it.

### 1.4 Typical use cases

- **Semantic search:** “Find documents about X” where X is expressed in natural language; results are by meaning, not just keywords.
- **RAG:** Retrieve relevant chunks from a vector store, then pass them as context to an LLM so the answer is grounded in those chunks.
- **Recommendations, deduplication, clustering:** Any task that benefits from “find items similar to this one” in embedding space.

---

## 2. RAG patterns at a conceptual level

### 2.1 What is RAG?

- **Retrieval-Augmented Generation** means: (1) **Retrieve** relevant information from a store (often a vector DB) given the user query; (2) **Augment** the prompt to the LLM with that information (e.g. as “context” or “documents”); (3) **Generate** the answer using the LLM. The LLM is encouraged to base its answer on the retrieved context, reducing hallucination and keeping answers tied to your data.

### 2.2 High-level RAG flow

```text
User query  →  Embed query  →  Similarity search in vector DB  →  Top-k chunks (+ payload)
       →  Build context string (e.g. concatenate chunk text)
       →  Prompt = system + context + query  →  LLM  →  Answer
       →  (Optional) Cite which chunks/sources were used
```

- **Single-shot:** One retrieve step, one LLM call. Simple and common.
- **Multi-step:** Retrieve → maybe grade relevance → if insufficient, retrieve again (e.g. with rewritten query) or use different strategy; then generate. This is an “agentic” or iterative RAG pattern.

### 2.3 Chunking: why and how

- **Why chunk?** Documents are often too long to fit in a single embedding or in the LLM context window. We split documents into **chunks** (e.g. paragraphs or fixed-size windows), embed each chunk, and store chunks in the vector DB. At query time we retrieve **chunks**, not whole documents.
- **Chunk size and overlap:**
  - **Larger chunks:** More context per chunk, but fewer chunks; risk of diluting the relevant part with irrelevant text; may exceed embedding model’s optimal length.
  - **Smaller chunks:** Finer-grained retrieval, but may lose coherence or miss context that spans boundaries.
  - **Overlap:** Consecutive chunks share a few sentences so that a concept at the boundary is still fully present in at least one chunk. Reduces “split in the middle of a sentence” issues.
- **Chunking strategies (concepts):**
  - **Fixed-size:** Sliding window with optional overlap; break at sentence or paragraph when possible to avoid mid-sentence cuts.
  - **Structure-based:** Split on headings, sections, lists, or paragraphs so chunks align with document structure. Good for manuals and long PDFs.
  - **Semantic / agentic:** Use structure first; for very long sections, use an LLM or rules to split at semantic boundaries (e.g. “new topic here”). More expensive but can improve retrieval quality.
- **Consistency:** The same chunking and embedding pipeline must be used at **ingestion** and the same embedding model at **query** time; otherwise scores and rankings are not comparable.

### 2.4 Retrieval strategies

- **Vector-only (semantic):** Query is embedded; top-k chunks by vector similarity. Good when the user phrase and the document phrase differ in wording but match in meaning.
- **Keyword-only (lexical):** e.g. BM25 or simple term match. Good for exact names, IDs, or rare terms. Often combined with vector in **hybrid**.
- **Hybrid:** Run both vector and keyword (or full-text) retrieval; **merge** the ranked lists (e.g. Reciprocal Rank Fusion – RRF) to get a single ranking. Combines semantic recall with lexical precision. In this project, hybrid = vector search with a larger k, then keyword re-rank over those results, then RRF merge.
- **Reranking (optional):** A second model (cross-encoder or similar) takes query + chunk and outputs a relevance score; used to re-rank the top candidates from first-stage retrieval. Improves precision at extra cost.
- **Filters:** Restrict search by metadata (e.g. source, date, language) before or after similarity; reduces noise and speeds up search.

### 2.5 Context assembly and prompting

- **Context:** The retrieved chunks are usually concatenated (with separators and optional “Source: …” labels) into a single **context string** that is inserted into the prompt (e.g. “Use the following context to answer. Context: …”).
- **Order:** Some systems pass chunks in retrieval order (by score); others reorder (e.g. by document or by position). Consistency helps the LLM and citation.
- **Length:** Stay within the LLM’s context window; if there are many chunks, truncate by score or by total token count.

### 2.6 Citation and traceability

- **Citation:** For each claim or sentence in the answer, the system can associate a **source** (chunk id, document name, page). This is often done by (1) storing source in the chunk payload, (2) returning payload with each retrieved chunk, and (3) showing “Sources” in the UI (e.g. expandable list with document and snippet). Optionally the LLM is prompted to cite (e.g. “[1]”) and the app maps indices to chunks.
- **Traceability:** “Which documents and chunks led to this answer?” is answered by the set of retrieved chunks and their payloads. Logging this set supports debugging, evaluation, and compliance.

### 2.7 Evaluation concepts

- **Relevance (retrieval):** Do the retrieved chunks actually relate to the query? Measured by relevance judgments (human or with a model), or by downstream task success.
- **Faithfulness (generation):** Is the answer supported by the retrieved context? Faithfulness metrics check that the answer does not contradict the context and that claims are grounded in it.
- **Answer relevance:** Is the answer relevant to the user’s question? Can be judged by overlap with a reference answer or by LLM-as-judge.
- **Golden set:** A curated set of (query, reference context, reference answer) used to run offline evals (e.g. RAGAS-style) and track regressions when changing chunking, retrieval, or models.

---

## 3. Summary: key concepts

| Topic | Key idea |
|-------|----------|
| **Vector DB** | Stores vectors (embeddings) and payloads; supports fast similarity search (e.g. top-k by cosine similarity). |
| **Embeddings** | Same model for query and documents; similar meaning ⇒ close vectors. |
| **RAG** | Retrieve relevant chunks → add to prompt as context → LLM generates answer; reduces hallucination and grounds answers in your data. |
| **Chunking** | Split documents into chunks (size, overlap, structure/semantic); embed and index chunks; consistency between ingest and query. |
| **Retrieval** | Vector (semantic), keyword (lexical), or hybrid (merge with RRF); optional rerank and filters. |
| **Citation** | Attach source (document, chunk) to each retrieved item; show in UI and optionally in LLM output for traceability. |
| **Evaluation** | Relevance of retrieval, faithfulness and relevance of the answer; golden set and metrics (e.g. RAGAS) for regression. |

---

## 4. How this project maps to the concepts

This section ties the concepts above to the current codebase (for reference only; no code is run).

| Concept | In this project |
|---------|------------------|
| **Vector database** | **Qdrant.** Collection holds vectors (from embedding model) and payload (`text`, `source`). See [DEPLOYMENT.md](DEPLOYMENT.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). |
| **Embeddings** | **lib/provider.py:** `get_embedding_client()` (OpenAI/OpenRouter). Same model used for ingestion (`scripts/ingest_docs.py`) and for query embedding in the app. Dimension and model name in `.env` (e.g. `VECTOR_DIMENSION`, `EMBEDDING_MODEL`). |
| **Chunking** | **lib/chunking.py:** Fixed-size with overlap (sentence-aware) and optional **semantic/agentic** chunking (structure-based + LLM for long sections). **scripts/ingest_docs.py** uses chunking before embedding and upserting to Qdrant. |
| **Vector search** | **lib/retrieval.py:** `vector_search()` — embed query, call Qdrant `search()`, return chunks with `text`, `source`, `score`. |
| **Hybrid retrieval** | **lib/retrieval.py:** `hybrid_retrieve()` — vector search with larger limit, then keyword re-rank (query terms in chunk text), then **RRF** merge of the two rankings; returns same chunk shape as vector_search. |
| **RAG flow** | **app.py:** User query → (optional agents) → retrieval (vector or hybrid) → context string from chunks → optional web search → prompt with context → LLM → streamed answer; **Tools Used** and **Sources** show retrieval tool and chunk sources. |
| **Citation** | Retrieved chunks include `source` in payload; UI shows expandable Sources; tool_calls list shows which retrieval was used. |
| **Evaluation** | **scripts/run_ragas.py**, **data/golden_rag.json**; **monitoring/drift_detection.py** for quality/drift over time. See [docs/MONITORING_AND_EVALUATION.md](docs/MONITORING_AND_EVALUATION.md). |

---

*This document is conceptual documentation only; no code has been run or modified.*
