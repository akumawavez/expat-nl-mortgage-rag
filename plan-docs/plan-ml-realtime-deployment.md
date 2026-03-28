# Plan: Deploy machine learning models for real-time applications

**Scope:** Strategy and steps to put model-backed behavior (retrieval, ranking, LLM routing, eval classifiers) behind a production-style serving path with low-latency contracts. **Implementation and tests are deferred** until you execute the phases below.

**Related:** [langgraph-rag-mlflow-fastapi-build-test-monitor-deploy.md](langgraph-rag-mlflow-fastapi-build-test-monitor-deploy.md), [plan-production-monitoring-drift.md](plan-production-monitoring-drift.md), [plan-event-driven-ml-microservices.md](plan-event-driven-ml-microservices.md).

---

## 1. Goals and success criteria

| Goal | Success criterion |
|------|-------------------|
| Predictable latency | Documented p50/p95 for chat/RAG path; timeouts and fallbacks defined |
| Versioned artifacts | Every deployed build references embedding model, prompt version, optional MLflow run ID |
| Observable serving | Health checks, structured errors, metrics hooks aligned with Prometheus |
| Safe rollout | Canary or shadow traffic plan (see [plan-ab-testing-validation.md](plan-ab-testing-validation.md)) |

---

## 2. Current project fit (expat-nl-mortgage-rag)

**Today:** Streamlit (`app.py`) drives the user path; `scripts/metrics_server.py` exposes `/metrics` but is not the full product API. RAG uses Qdrant + `lib/retrieval.py`; orchestration lives in `lib/agents.py` (and optionally LangGraph in `lib/agents_graph.py`).

**“Models” in this RAG stack include:**

- Embedding model (via `lib/provider.py`)
- Optional reranker or classifier (if you add them later)
- Heuristic or LLM-as-judge eval components (`scripts/run_ragas.py`, monitoring hooks)

**Deployment target options (pick one primary path, document the other as future):**

1. **FastAPI service** — Single process exposing `POST /chat` (or `/v1/rag/query`) calling shared `lib/` code; container via existing `Dockerfile` pattern or a slim API-only image.
2. **Streamlit-only** — Acceptable for demos; not ideal for strict “real-time API” SLAs—still version env, models, and compose services.

---

## 3. Phased plan (plan → implement → test)

### Phase 1 — Define the real-time contract

- Specify API schema (request/response, streaming vs non-streaming, citation format).
- Define SLOs: max latency, error budget, concurrent users (rough).
- Map which components are **stateless** (embed → retrieve → generate) vs **stateful** (conversation memory).

**Test (when implementing):** Contract tests (OpenAPI or pydantic models), load smoke with fixed queries.

### Phase 2 — Package the inference path

- Ensure one importable entrypoint (e.g. `run_turn` or graph invoke) callable from FastAPI without Streamlit.
- Externalize configuration: model names, top-k, temperature, Qdrant URL, feature flags.

**Test:** Integration tests against Qdrant (mirror `tests/test_retrieval.py` patterns); golden-query regression set.

### Phase 3 — Container and runtime

- Production-oriented image: non-root user, health endpoint, `READINESS` vs `LIVENESS`.
- Compose or orchestrator manifests: Qdrant, optional Neo4j, API service, env secrets via `.env` / secret store.

**Test:** `docker compose up` smoke; health checks; cold-start timing.

### Phase 4 — Model and config versioning

- Tie each deploy to: git SHA, dependency lockfile, embedding model id, optional **MLflow** model version or run id for prompts/experiments.
- Document rollback: previous image tag + previous vector collection snapshot (if collection migrations occur).

**Test:** Deploy script prints resolved versions; staging validates same answers on golden set.

### Phase 5 — Production cutover

- DNS / gateway in front of API; TLS termination; rate limits.
- Runbook: scale, restart, drain, incident contacts.

**Test:** Synthetic probes; alert on 5xx/latency (ties to monitoring plan).

---

## 4. Deliverables (documentation and code, when you implement)

- OpenAPI or README section for the real-time API
- CI job that builds the API image and runs pytest + smoke
- Changelog or release notes per deploy with version pins

---

## 5. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| LLM provider outage | Cached responses or graceful degradation message; circuit breaker |
| Vector DB slow | Timeouts, smaller top-k, async batch where possible |
| Prompt drift | Version prompts; compare golden set in staging ([plan-reproducible-model-documentation.md](plan-reproducible-model-documentation.md)) |

---

## 6. Later implementation checklist (no code in this doc)

When you start coding: (1) add FastAPI route module, (2) wire metrics from the same process as `/metrics`, (3) add MLflow logged params on startup or per request (optional), (4) extend `docker-compose.yml` for the API service, (5) add pytest for the HTTP layer.
