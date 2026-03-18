# Code To-Do List

This file lists **code and refactoring tasks** that are **not** done in the current “documentation-only” pass. Use it for implementation planning and tracking. Do not run or modify existing code as part of the documentation task; this file only records what remains.

---

## 1. Refactor: frontend and backend folder (NotesToImprove §7)

**Goal**: Separate frontend and backend so the codebase is easier to maintain and deploy as a service.

**Tasks**:
- [ ] Introduce a `frontend/` folder (e.g. Streamlit app, or a minimal web UI) and a `backend/` folder (or `api/`) for core logic and optional REST API.
- [ ] Move shared logic (retrieval, provider, chunking, agents, location, graph_kg, documents) into a package usable by both (e.g. `backend/` or keep `lib/` and have both frontend and backend depend on it).
- [ ] If adding a REST API: expose a small FastAPI (or similar) service for “chat turn” (query → answer + sources + tools_used) so non-Streamlit clients can call the RAG pipeline.
- [ ] Update README and DEPLOYMENT.md to describe the new layout and how to run frontend vs backend.
- [ ] Ensure tests and CI still run (pytest, lint) after refactor.

**Reference**: NotesToImprove.txt item 7; [ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## 2. Instrumentation: wire app to Prometheus and drift module (NotesToImprove §10)

**Goal**: Latency, request counts, and tool usage are recorded so monitoring and evaluation metrics are meaningful.

**Tasks**:
- [ ] In the chat path (after retrieval and after LLM call), record latency (e.g. time from request start to response end) and call `REQUEST_LATENCY.labels(tool="vector_search" or "hybrid_retrieve").observe(duration)` and `REQUEST_COUNT.labels(tool=...).inc()`. Use the same metric names as in `scripts/metrics_server.py` (Prometheus client must be importable in the app, or use a small HTTP push to the metrics server if preferred).
- [ ] On retrieval/LLM failure, call `ERROR_COUNT.labels(tool=...).inc()`.
- [ ] Optionally call `record_latency_ms(ms)`, `record_tool_use(tool_name)`, and `record_retrieval_score(score)` from `monitoring/drift_detection.py` so the Observability tab and drift indicators reflect real usage.
- [ ] Document in [MONITORING_AND_EVALUATION.md](docs/MONITORING_AND_EVALUATION.md) that the app is now instrumented (after implementation).

**Reference**: NotesToImprove §10; [MONITORING_AND_EVALUATION.md](docs/MONITORING_AND_EVALUATION.md); [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) §9.

---

## 3. RAG evals: run real pipeline and log quality (NotesToImprove §10)

**Goal**: Evaluation measures the live retrieval + LLM pipeline, not only heuristics on reference data.

**Tasks**:
- [ ] Extend `scripts/run_ragas.py` (or a new script) to: load golden set; for each question, call the same retrieval (vector or hybrid) and LLM as the app; compute faithfulness/relevancy (e.g. with RAGAS library or existing heuristics) against reference; write per-question and summary scores to file.
- [ ] Optionally expose a summary metric (e.g. `rag_retrieval_quality`) for Prometheus/Grafana.
- [ ] Document how to run evals and where results are stored in [MONITORING_AND_EVALUATION.md](docs/MONITORING_AND_EVALUATION.md).
- [ ] Optional: add a small eval subset to CI and fail on regression (e.g. mean score below threshold).

**Reference**: [MONITORING_AND_EVALUATION.md](docs/MONITORING_AND_EVALUATION.md); [scripts/run_ragas.py](scripts/run_ragas.py).

---

## 4. Prompt injection: detection and handling (NotesToImprove §19)

**Goal**: Reduce risk of prompt injection by detecting likely injection attempts and handling them safely.

**Tasks**:
- [ ] Add input validation: maximum length for user message (e.g. 2K–4K characters); reject or truncate with a clear message.
- [ ] Implement a simple heuristic detector (e.g. blocklist of phrases: “ignore previous instructions”, “system:”, “you are now”, “disregard”, etc.). If match, do not call RAG/LLM; return a fixed safe message (e.g. “I can only answer questions about Dutch mortgages and property. Please rephrase.”) and log (without logging full user content in production if PII is a concern).
- [ ] Optionally add an LLM-based or classifier-based “injection score” and throttle or block when above threshold.
- [ ] Strengthen system prompt to explicitly refuse to follow instructions embedded in the user message.
- [ ] On detection, increment an error or “injection” metric if you have one (e.g. `rag_errors_total{reason="prompt_injection"}`).
- [ ] Document in [SECURITY_AND_ERROR_HANDLING.md](docs/SECURITY_AND_ERROR_HANDLING.md) that implementation is done and where it lives in code.

**Reference**: NotesToImprove §19; [SECURITY_AND_ERROR_HANDLING.md](docs/SECURITY_AND_ERROR_HANDLING.md).

---

## 5. General error handling and robustness

**Tasks**:
- [ ] Differentiate “retrieval error” (e.g. Qdrant down) from “no results” in the UI and in logs; show a user-friendly message on error and do not treat errors as empty context.
- [ ] Wrap LLM (OpenAI and Ollama) calls in try/except; on timeout or API error, show a short safe message and log; do not expose stack traces to the user.
- [ ] Consider a small set of error types (ValidationError, RetrievalError, LLMError) and map them to user-facing messages and optional metrics.

**Reference**: [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md); [SECURITY_AND_ERROR_HANDLING.md](docs/SECURITY_AND_ERROR_HANDLING.md).

---

## 6. Optional / later

- [ ] **Rate limiting**: Per-IP or per-session rate limit for chat (e.g. at reverse proxy or in app).
- [ ] **PII in logs**: Redact or avoid logging full prompts and user content in production.
- [ ] **Content safety**: Output filter or provider-level content policy for harmful model output.
- [ ] **Auth**: If the app is extended with user accounts, add authentication and authorization; document in deployment and security docs.

---

## Summary table

| # | Area | Priority | Notes |
|---|------|----------|--------|
| 1 | Frontend/backend refactor | Medium | Improves maintainability and enables API |
| 2 | Prometheus + drift instrumentation | High | Required for real latency and usage metrics |
| 3 | RAG evals (live pipeline) | High | Required for quality tracking and regression |
| 4 | Prompt injection handling | High | Security and safety |
| 5 | Error handling and UX | Medium | Better UX and ops |
| 6 | Rate limit, PII, auth | Low / later | As needed for production |

All of the above are **code changes**; documentation for behavior and design is already in the referenced docs.
