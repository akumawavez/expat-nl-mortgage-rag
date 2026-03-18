# Expat NL Mortgage RAG

RAG-based assistant for Dutch mortgages and property (expat-focused), with knowledge graph (Phase 2), location tools, and a four-phase roadmap (PHASES.md).

## Chat response format

Each turn shows **Tools Used** (e.g. `vector_search`, `hybrid_retrieve`, `tavily_search`) and the **Assistant** reply; **citations** are in an expandable Sources panel. See PHASES.md for the format in Phase 1–4.

## Quick start

From the project root (see **[docs/QUICKSTART.md](docs/QUICKSTART.md)** for a step-by-step guide with diagrams):

```bash
# 1. Environment
cp .env.example .env   # set QDRANT_*, LLM/embedding API keys, optional TAVILY_API_KEY
python -m venv venv
venv\Scripts\activate   # Windows; source venv/bin/activate on Linux/macOS
pip install -r requirements.txt

# 2. Start Qdrant (e.g. Docker), then ingest
python scripts/ingest_docs.py
python scripts/test_ingestion.py   # expect RESULT: PASS

# 3. Run app (single entry point)
streamlit run app.py
```

**app.py** includes: **Chat** (RAG, hybrid retrieval, web search toggle, Tools Used + citations; optional **Phase 4 agents** orchestrator), **Mortgage Calculator**, **Knowledge Graph** (PyVis), **Location** (nearby_places, OSRM, area_safety), **Sun** (Phase 3 sun-path SVG), **Observability** (retrieval/response quality, drift, Langfuse), **Agents** (Phase 4: MCP tools, A2UI directives).

## Run steps per phase

**Full code run steps for each phase (when that phase is completed)** are in **[PHASES.md](PHASES.md)**:

- **Phase 1 completed:** env, install, Qdrant, ingest, test_ingestion, run app, pytest, CI.  
- **Phase 2 completed:** Phase 1 steps + Neo4j, test_phase2, app with KG tab, nearby_places, OSRM, safety.  
- **Phase 3 completed:** Phase 1–2 + observability (quality/drift), sun-orientation, RAG evals, /metrics, Grafana.  
- **Phase 4 completed:** Phase 1–3 + multi-agent app, A2UI, MCP, optional eval smoke in CI.

See **[PHASES.md – Code run steps at end of each phase](PHASES.md#code-run-steps-at-end-of-each-phase-when-phase-is-completed)** for the exact ordered steps (env, install, services, ingest, verify, run app, tests) for each phase.

## Project layout

- **`app.py`** – Single entry point: Chat (RAG, Tools Used, citations), Calculator, KG, Location, Sun, Observability, Agents.
- `app_phase1.py` – Phase 1 RAG chat (alternative; PDF upload in sidebar).
- `scripts/ingest_docs.py` – Ingest PDFs into Qdrant (default: full replace; `--semantic` for agentic chunking).
- `scripts/test_ingestion.py` – Verify Qdrant and retrieval.
- `scripts/test_phase2.py` – Phase 2: Neo4j, graph extraction, PyVis.
- `scripts/run_ragas.py` – Phase 3 RAG evals (stub).
- `lib/retrieval.py` – vector_search, hybrid_retrieve (RRF).
- `lib/chunking.py` – Chunking (simple or semantic).
- `lib/provider.py` – LLM/embedding client (OpenAI, OpenRouter, Ollama).
- `lib/graph_kg.py` – KG extraction and PyVis (Phase 2).
- `lib/location.py` – nearby_places, osrm_commute, area_safety (Phase 2).
- `lib/sun_orientation.py` – Sun-path SVG (Phase 3).
- `lib/agents.py` – Orchestrator + specialists (Phase 4).
- `lib/a2ui.py` – A2UI directive schema and parsing (Phase 4).
- `lib/mcp_client.py` – MCP tool registry (Phase 4).
- `monitoring/drift_detection.py` – Quality/drift metrics (Phase 3).
- `data/golden_rag.json` – Golden dataset for evals; `scripts/run_ragas.py` – RAG evals (Phase 3).
- `scripts/metrics_server.py` – Prometheus /metrics (Phase 3); `docs/monitoring.md`, `docs/RESPONSIBLE_AI.md`.
- `tests/` – pytest (retrieval, calculator, chunking).
- `DEPLOYMENT.md`, `.env.example` – Deployment and env vars.
- **`PHASES.md`** – Four-phase plan, completion tests, and **code run steps at end of each phase**.

## Docs

- **[PHASES.md](PHASES.md)** – Four-phase implementation plan, completion tests, and **run steps when each phase is completed**.
- **[DEPLOYMENT.md](DEPLOYMENT.md)** – Deployment and environment variables.
- **[CODE_TODO.md](CODE_TODO.md)** – Code and refactor to-do list (refactor, instrumentation, prompt injection, evals).

### Documentation (docs/)

| Document | Description |
|----------|-------------|
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | Quick start guide with setup flowchart |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Architecture and end-to-end workflows (with diagrams) |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Usual errors and how to debug |
| [docs/PRD.md](docs/PRD.md) | Product Requirements Document |
| [docs/API.md](docs/API.md) | API and tools documentation (lib, scripts, external services) |
| [docs/MONITORING_AND_EVALUATION.md](docs/MONITORING_AND_EVALUATION.md) | Monitoring, latency, and evaluation metrics |
| [docs/monitoring.md](docs/monitoring.md) | Prometheus /metrics and Grafana |
| [docs/REPORT.md](docs/REPORT.md) | Presentation-style report |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | Branching, PRs, and merge to main |
| [docs/EXECUTION_SUMMARY.md](docs/EXECUTION_SUMMARY.md) | Execution summary, to-do, and completed tracking |
| [docs/DESIGN_AND_VERSION_CONTROL.md](docs/DESIGN_AND_VERSION_CONTROL.md) | Design thinking, system design, version control |
| [docs/PRODUCTION_MLOPS_AIOPS.md](docs/PRODUCTION_MLOPS_AIOPS.md) | Production, MLOps, and AIOps |
| [docs/SECURITY_AND_ERROR_HANDLING.md](docs/SECURITY_AND_ERROR_HANDLING.md) | Security and error handling (including prompt injection) |
| [docs/RESPONSIBLE_AI.md](docs/RESPONSIBLE_AI.md) | Traceability, transparency, and oversight |
