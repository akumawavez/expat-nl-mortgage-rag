# Expat NL Mortgage RAG

RAG-based assistant for Dutch mortgages and property (expat-focused), with optional knowledge graph, location tools, and multi-phase roadmap.

## Quick start (current state – Phase 1 foundation)

From the project root:

```bash
# 1. Environment
cp .env.example .env   # or create .env with QDRANT_*, LLM/embedding API keys
python -m venv venv
venv\Scripts\activate   # Windows; use source venv/bin/activate on Linux/macOS
pip install -r requirements.txt

# 2. Start Qdrant (e.g. Docker), then ingest
python scripts/ingest_docs.py
python scripts/test_ingestion.py   # expect RESULT: PASS

# 3. Run app
streamlit run app_phase1.py
```

Use the chat to ask about Dutch mortgages, tax, or housing; optionally upload PDFs in the sidebar (upsert).

## Run steps per phase

**Full code run steps for each phase (when that phase is completed)** are in **[PHASES.md](PHASES.md)**:

- **Phase 1 completed:** env, install, Qdrant, ingest, test_ingestion, run app, pytest, CI.  
- **Phase 2 completed:** Phase 1 steps + Neo4j, test_phase2, app with KG tab, nearby_places, OSRM, safety.  
- **Phase 3 completed:** Phase 1–2 + observability (quality/drift), sun-orientation, RAG evals, /metrics, Grafana.  
- **Phase 4 completed:** Phase 1–3 + multi-agent app, A2UI, MCP, optional eval smoke in CI.

See **[PHASES.md – Code run steps at end of each phase](PHASES.md#code-run-steps-at-end-of-each-phase-when-phase-is-completed)** for the exact ordered steps (env, install, services, ingest, verify, run app, tests) for each phase.

## Project layout

- `app_phase1.py` – Phase 1 RAG chat (single app entry point may become `app.py` in Phase 1).
- `scripts/ingest_docs.py` – Ingest PDFs into Qdrant (default: full replace; `--semantic` for agentic chunking).
- `scripts/test_ingestion.py` – Verify Qdrant and retrieval (Phase 1).
- `scripts/test_phase2.py` – Phase 2 checks (Neo4j, graph write/content when implemented).
- `lib/chunking.py` – Chunking (simple or semantic).
- `lib/provider.py` – LLM/embedding client (OpenAI, OpenRouter).
- `PHASES.md` – Four-phase plan, completion tests, and **code run steps at end of each phase**.

## Docs

- **[PHASES.md](PHASES.md)** – Four-phase implementation plan, completion tests, and **run steps when each phase is completed**.
