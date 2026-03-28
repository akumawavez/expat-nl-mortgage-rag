# Plan: Build, Test, Monitor, and Deploy AI Agents (LangGraph, RAG, MLflow, FastAPI)

This document summarizes **what the [expat-nl-mortgage-rag](..) repository already provides**, **what is partial or disconnected**, and a **concrete roadmap** to deliver LangGraph-based agents, RAG, MLflow lifecycle/tracking, and a FastAPI service end to end—including test, monitor, and deploy steps.

**Related repo docs:** [PHASES.md](../PHASES.md), [CODE_TODO.md](../CODE_TODO.md), [codedocs/agentic_frameworks_langgraph_plan.md](../codedocs/agentic_frameworks_langgraph_plan.md), [codedocs/api_development_and_integration_plan.md](../codedocs/api_development_and_integration_plan.md), [codedocs/MONITORING_AND_EVALUATION.md](../codedocs/MONITORING_AND_EVALUATION.md), [codedocs/monitoring.md](../codedocs/monitoring.md), [codedocs/DEPLOYMENT.md](../codedocs/DEPLOYMENT.md).

---

## 1. Target architecture (outcome)

| Layer | Technology | Role |
|-------|------------|------|
| Agent orchestration | **LangGraph** | Stateful graph: router → specialist nodes (RAG, location, calculator) → aggregate; optional human-in-the-loop later. |
| Knowledge | **RAG** | Qdrant + embeddings + hybrid retrieval (`lib/retrieval.py`, ingestion in `scripts/ingest_docs.py`). |
| Experiment & model tracking | **MLflow** | Trace runs, log params/metrics/artifacts for retrieval configs, prompts, eval scores, and (if used) fine-tuned or hosted model metadata. |
| Serving | **FastAPI** | REST contract for chat/RAG turns (and optionally separate `/metrics` or proxy to Prometheus). |
| UI (optional) | Streamlit | Current `app.py`; can call FastAPI backend or share `lib/` package. |

---

## 2. Repository inventory (March 2026)

### 2.1 Completed or largely in place

| Area | Evidence | Notes |
|------|----------|--------|
| **RAG pipeline** | `lib/retrieval.py`, `lib/chunking.py`, `lib/documents.py`, `scripts/ingest_docs.py`, Qdrant in `docker-compose.yml` | Vector + hybrid (RRF), chunk metadata, ingestion scripts. |
| **LLM / embeddings** | `lib/provider.py` | OpenAI, OpenRouter, Ollama; optional **Langfuse** wrapper when env vars are set. |
| **Multi-agent (non-LangGraph)** | `lib/agents.py` | Keyword `route_query` + `run_orchestrator` calling retrieval/location/calculator hooks; returns context, `tool_calls`, A2UI directives. |
| **Streamlit app** | `app.py` | Chat with citations, Phase 4 agents toggle, calculator/KG/location/sun tabs, **Observability** tab. |
| **A2UI / MCP** | `lib/a2ui.py`, `lib/mcp_client.py` | Phase 4 UI directives and MCP tool registry. |
| **Knowledge graph (Phase 2)** | `lib/graph_kg.py` | Neo4j-oriented; **compose service for Neo4j is commented out**—enable when using KG in deployment. |
| **Unit / integration tests** | `tests/test_retrieval.py`, `tests/test_chunking.py`, `tests/test_calculator.py` | Pytest against real Qdrant in CI. |
| **CI** | `.github/workflows/ci.yml` | Python 3.11, `ruff`, `pytest`, Qdrant service; **only `main`/`master` branches** on push/PR. |
| **Prometheus metrics (server)** | `scripts/metrics_server.py` | FastAPI (or WSGI fallback): **`GET /metrics`**, **`GET /health`**; defines `Counter`/`Histogram` for RAG. |
| **Drift / quality store (library)** | `monitoring/drift_detection.py` | JSON-backed rolling stats; functions `record_*`, `get_quality_summary`, `get_drift_indicators`. |
| **RAG eval script (baseline)** | `scripts/run_ragas.py` | Heuristic faithfulness/relevancy; can run without full LLM; writes scores for monitoring. |
| **Container image** | `Dockerfile` | Streamlit on 8501, healthcheck on `/_stcore/health`; copies `lib/`, `scripts/`, `monitoring/`, `data/`. |

### 2.2 Partially done or documented only

| Area | Status | Gap |
|------|--------|-----|
| **LangGraph** | **Not implemented** | `langgraph` is **commented out** in `requirements.txt`. Design lives in `codedocs/agentic_frameworks_langgraph_plan.md`. |
| **FastAPI “product API”** | **Metrics only** | No `POST /chat` (or equivalent) exposing the full RAG+agent pipeline. Planned in `codedocs/api_development_and_integration_plan.md` and [CODE_TODO.md](../CODE_TODO.md) §1. |
| **MLflow** | **Absent** | No `mlflow` dependency, no tracking calls, no MLflow server in compose—**greenfield** for this stack. |
| **Prometheus ↔ app** | **Metrics defined, not wired** | [CODE_TODO.md](../CODE_TODO.md) §2: chat path does not increment `REQUEST_COUNT` / `REQUEST_LATENCY` / `ERROR_COUNT` in the running process that exposes `/metrics` (or push gateway). |
| **Drift / observability UI** | **Displays if data exists** | `app.py` Observability tab reads `monitoring.drift_detection`; **recording from the live chat path is listed as TODO**—tab often shows “No data” until scripts populate or instrumentation lands. |
| **RAGAS / full pipeline evals** | **Heuristic / stub path** | `run_ragas.py` does not drive the **same** retrieval+LLM as production by default; CI does not run RAGAS regression ([CODE_TODO.md](../CODE_TODO.md) §3). |
| **Feature branches in CI** | **May not run** | Workflow triggers only `main`/`master`; branch `feature/monitoring` (and similar) won’t hit CI unless workflow is extended or PR targets `main`. |

### 2.3 What is working vs not working (practical)

**Working (when env and services are correct):**

- Local/dev: Qdrant + ingest + Streamlit chat, hybrid retrieval, citations, Tools Used, optional web search (Tavily), Phase 4 orchestrator path in `app.py`.
- Langfuse: works **if** keys/host configured (`lib/provider.py`, Observability tab link).
- Standalone: `python scripts/metrics_server.py` exposes `/metrics` and `/health`.
- Tests: `pytest` with `QDRANT_URL` (as in CI).

**Not working or misleading without follow-up:**

- **LangGraph**: no graph execution; only custom Python orchestrator.
- **MLflow**: nothing to connect to; no experiment lineage for prompts or evals.
- **End-to-end API**: no FastAPI service for programmatic agents/RAG (only metrics server).
- **Production-grade monitoring**: Prometheus counters/histograms are **not** fed from Streamlit chat turns; Grafana dashboards would show zeros or stale series unless wired ([CODE_TODO.md](../CODE_TODO.md) §2).
- **Eval as quality gate**: golden set + `run_ragas.py` exist, but **live pipeline eval** and **CI threshold** are not implemented.

---

## 3. Roadmap: build → test → monitor → deploy

Phases below assume you keep **one shared library package** (`lib/` today) consumed by Streamlit and FastAPI, and add **optional** LangGraph behind a feature flag.

### Phase A — Build (LangGraph + RAG core)

1. **Uncomment and pin `langgraph`** in `requirements.txt` (and resolve any `langchain-*` version alignment).
2. **State schema**: define a `TypedDict` or Pydantic model for graph state (`query`, `messages`, `context`, `tool_calls`, `a2ui_directives`, `specialists_invoked`, …) matching current `run_orchestrator` outputs ([codedocs/agentic_frameworks_langgraph_plan.md](../codedocs/agentic_frameworks_langgraph_plan.md) §5.2).
3. **Implement graph** in a dedicated module (e.g. `lib/agents_graph.py`): nodes for router, retrieval, location, calculator, merge; reuse existing callables from `app.py` / `lib/`.
4. **Wrapper** `run_orchestrator_langgraph(...)` returning the same tuple shape as `run_orchestrator` so `app.py` can switch via sidebar or env flag.
5. **MLflow — tracking SDK**
   - Add `mlflow` to dependencies.
   - At minimum: `mlflow.set_experiment(...)`, `with mlflow.start_run():` log **params** (collection name, top_k, hybrid on/off, model id), **metrics** (latency, chunk count, token usage if available), **tags** (git commit, branch).
   - Optional: log **prompts** and **retrieved contexts** as artifacts (mind PII; redact per [CODE_TODO.md](../CODE_TODO.md) §6).

### Phase B — FastAPI service

1. **New app module** (e.g. `api/main.py` or `backend/api.py`): `POST /v1/chat` (or `/chat`) accepting JSON `{ "message": "...", "session_id": "..." }` and returning `{ "answer", "sources", "tool_calls", "a2ui" }` aligned with Streamlit behavior.
2. **Dependency injection**: construct Qdrant client, provider, retrieval fns once at startup (lifespan).
3. **Auth**: API key header (e.g. `X-API-Key`) as dependency—document in OpenAPI.
4. **Wire LangGraph path**: query param or header `X-Orchestrator: langgraph|classic`.
5. **MLflow**: start nested or linked runs per request **or** sample/trace (avoid excessive run creation in high QPS—use batch or async logging strategy).

### Phase C — Test

| Test type | Action |
|-----------|--------|
| **Unit** | Mock LLM/Qdrant; test `route_query`, graph transitions, FastAPI validation and auth rejection. |
| **Integration** | pytest with Qdrant (existing pattern): retrieval + orchestrator (classic and LangGraph) return non-empty context for fixture queries. |
| **API** | `httpx.AsyncClient` tests against FastAPI `TestClient` for `/health` and `/v1/chat` (with test API key). |
| **Eval** | Extend `scripts/run_ragas.py` (or new script) to call **production retrieval + LLM**; write scores; optional **MLflow log_metrics** for mean faithfulness/relevancy. |
| **CI** | Extend `.github/workflows/ci.yml` to run on `feature/*` or all PRs; add job step for eval smoke (threshold) if stable enough. |

### Phase D — Monitor

1. **Wire Prometheus** ([CODE_TODO.md](../CODE_TODO.md) §2): from shared library used by both Streamlit and FastAPI, call `REQUEST_COUNT`, `REQUEST_LATENCY`, `ERROR_COUNT`; ensure the process scraping `/metrics` is the same that handles traffic **or** use Prometheus Pushgateway.
2. **Drift module**: call `record_latency_ms`, `record_retrieval_score`, `record_tool_use` from the chat path so the Observability tab reflects reality.
3. **Langfuse**: keep for trace UX; **MLflow** for experiment comparison and audit; document division of responsibilities in `codedocs/MONITORING_AND_EVALUATION.md`.
4. **MLflow Tracking Server**: optional Docker service in `docker-compose.yml`; set `MLFLOW_TRACKING_URI` in `.env.example`.
5. **Dashboards**: Grafana for Prometheus; MLflow UI for runs—link from Observability tab (mirror Langfuse pattern).

### Phase E — Deploy

1. **Compose / K8s**: add services—**FastAPI** (e.g. port 8000), **metrics** (9090) if not merged into FastAPI, **MLflow** (optional), existing **app** + **Qdrant**.
2. **Reverse proxy**: path routing `/` → Streamlit, `/api` → FastAPI, `/mlflow` or internal-only MLflow ([codedocs/api_development_and_integration_plan.md](../codedocs/api_development_and_integration_plan.md)).
3. **Secrets**: API keys, `MLFLOW_TRACKING_URI`, Langfuse, DB URLs—never in image; use env / vault.
4. **Update** [codedocs/DEPLOYMENT.md](../codedocs/DEPLOYMENT.md) with new ports, health checks, and scaling notes.

---

## 4. Work breakdown summary

| Priority | Task | Owner hint |
|----------|------|------------|
| High | Wire Prometheus + drift recording from real chat/API path | Backend |
| High | FastAPI chat API + shared `lib/` usage | Backend |
| High | MLflow experiment logging for runs and evals | MLOps |
| Medium | Implement LangGraph graph + flag in `app.py` / API | Agents |
| Medium | Live-pipeline RAG eval + optional CI gate | QA / MLOps |
| Medium | CI trigger branches + Docker compose multi-service | DevOps |
| Low | Frontend/backend folder split ([CODE_TODO.md](../CODE_TODO.md) §1) | Refactor |

---

## 5. Definition of done (for this initiative)

- [ ] LangGraph path returns the **same contract** as `run_orchestrator` and is covered by at least one integration test.
- [ ] FastAPI exposes versioned chat endpoint with documented OpenAPI and optional API key auth.
- [ ] MLflow logs identifiable runs for configured experiments; team can compare runs in UI.
- [ ] Prometheus metrics reflect production traffic; Grafana (or doc’d scrape config) validates SLO-style panels.
- [ ] Deploy docs describe multi-container layout and env vars; smoke test: ingest → chat (UI + API) → metric visible → MLflow run created.

---

*Document generated from repository scan; update this file when major components land.*
