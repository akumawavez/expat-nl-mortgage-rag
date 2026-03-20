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
- Optional: `TAVILY_API_KEY` (web search), `LANGFUSE_HOST` or `LANGFUSE_URL` (observability; see below)

### Langfuse (optional)

To link the **Observability** tab to Langfuse:

1. Sign up at [langfuse.com](https://langfuse.com) and create a project.
2. In Langfuse: **Settings → Project** and note your host (e.g. `https://cloud.langfuse.com`).
3. In your **`.env`** file set **one** of these (no trailing slash):
   - `LANGFUSE_HOST=https://cloud.langfuse.com`
   - or `LANGFUSE_URL=https://cloud.langfuse.com`
4. Restart the app; the Observability tab will show an “Open dashboard” link when set.
5. (Optional) To send traces from the app to Langfuse, also set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` from the same project.

#### Langfuse in Docker (e.g. local-ai-packaged)

If you run Langfuse via Docker (e.g. [local-ai-packaged](https://github.com/coleam00/local-ai-packaged) with Caddy), use the **same URL you use in the browser** to open the Langfuse UI:

- **Same machine as the app:** usually `http://localhost:8007` (default `LANGFUSE_HOSTNAME` in that stack is `:8007`). If you changed the port or use a hostname, use that instead.
- **Different machine or custom domain:** use that host (e.g. `http://192.168.1.10:8007` or `https://langfuse.yourdomain.com`).

In your **app's `.env`** (the one used by `streamlit run app.py`), set for example:

```env
LANGFUSE_HOST=http://localhost:8007
```

or `LANGFUSE_URL=http://localhost:8007`.

To **send traces** from this app to your Dockerized Langfuse:

1. Open your Langfuse UI (e.g. http://localhost:3000), create a project if needed.
2. In Langfuse: **Settings → Project → API keys** and create/copy the **public** and **secret** keys.
3. In your app's `.env` set: `LANGFUSE_HOST` or `LANGFUSE_URL` (dashboard link), `LANGFUSE_BASE_URL` (same URL, for tracing), `LANGFUSE_PUBLIC_KEY`, and `LANGFUSE_SECRET_KEY`.
4. Restart the Streamlit app; chat requests will then appear as traces in Langfuse.

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
