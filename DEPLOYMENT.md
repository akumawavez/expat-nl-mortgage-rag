# Expat NL Mortgage RAG – Deployment

## Quick run (local)

1. Copy `.env.example` to `.env` and set at least:
   - `QDRANT_URL`, `QDRANT_COLLECTION`
   - `OPENAI_API_KEY` (or `OPENROUTER_API_KEY`) and `LLM_PROVIDER` / `EMBEDDING_PROVIDER`
2. Install: `pip install -r requirements.txt`
3. Start Qdrant (e.g. Docker): `docker run -p 6333:6333 qdrant/qdrant`
4. Ingest: `python scripts/ingest_docs.py`
5. Run app: `streamlit run app.py`

## Environment variables

See `.env.example` for all options. Required for Phase 1:

- **Qdrant:** `QDRANT_URL`, `QDRANT_COLLECTION`
- **LLM/embeddings:** `LLM_PROVIDER` (openai | openrouter | ollama), `EMBEDDING_PROVIDER`, and the matching API key (`OPENAI_API_KEY`, `OPENROUTER_API_KEY`, or `OLLAMA_URL` for Ollama)
- Optional: `TAVILY_API_KEY` (web search), `LANGFUSE_HOST` (observability)

## Platform notes

### Streamlit Community Cloud

- Connect repo; set **Secrets** from `.env.example` (no quotes needed in the UI).
- Add Qdrant: use a hosted Qdrant (e.g. [qdrant.cloud](https://qdrant.cloud)) and set `QDRANT_URL` and `QDRANT_API_KEY` if required.
- Build command: `pip install -r requirements.txt`
- Run: `streamlit run app.py --server.port 8501`

### Hugging Face Spaces

- Create a Space with **Streamlit** SDK.
- Add secrets in **Settings → Variables and secrets** (e.g. `OPENAI_API_KEY`, `QDRANT_URL`).
- Use a hosted Qdrant or run Qdrant in a separate Space/container and set `QDRANT_URL`.

### Render

- New **Web Service**; connect repo.
- Build: `pip install -r requirements.txt`
- Start: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
- Add **Environment** variables from `.env.example`.

## Phase 2+

- For Neo4j (Knowledge Graph): set `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` and ensure Neo4j is reachable.
- For OSRM / Nominatim: set base URLs if using self-hosted instances.
