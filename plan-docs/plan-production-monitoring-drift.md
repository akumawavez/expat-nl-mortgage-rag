# Plan: Monitor model performance in production, investigate drift, and iterate

**Scope:** Define how to observe RAG/LLM quality and input/output drift in this repo, how to investigate regressions, and how to close the loop with evaluation metrics. **Implementation and tests are deferred.**

**Related:** [codedocs/MONITORING_AND_EVALUATION.md](../codedocs/MONITORING_AND_EVALUATION.md) (if present), [langgraph-rag-mlflow-fastapi-build-test-monitor-deploy.md](langgraph-rag-mlflow-fastapi-build-test-monitor-deploy.md), [plan-ab-testing-validation.md](plan-ab-testing-validation.md), [plan-reproducible-model-documentation.md](plan-reproducible-model-documentation.md).

---

## 1. Goals and success criteria

| Goal | Success criterion |
|------|-------------------|
| **Operational** health | Dashboards for latency, errors, token/cost proxies, dependency failures |
| **Quality** signals | Rolling faithfulness/relevancy or user-feedback proxies; alerts on thresholds |
| **Drift** detection | Statistical or rule-based alerts on query length, language mix, retrieval score distribution, empty-hit rate |
| **Iteration loop** | Weekly or per-release review: metric trend → hypothesis → experiment → deploy |

---

## 2. Inventory in this repository (baseline)

Align plans with existing pieces:

- **`monitoring/drift_detection.py`** — Rolling stats and drift-style indicators; needs **live path instrumentation** to populate data consistently.
- **`scripts/metrics_server.py`** — Prometheus `/metrics`; **wire** the same counters/histograms from the chat/RAG execution path ([CODE_TODO.md](../CODE_TODO.md) §2).
- **`scripts/run_ragas.py`** — Offline/heuristic eval; use as **batch** quality signal and optionally schedule post-deploy.
- **`app.py` Observability tab** — Surface drift summary when data exists; document expected JSON layout for operators.

---

## 3. Metric layers (what to monitor)

### 3.1 System and API

- Request rate, latency histograms (end-to-end and per-stage: embed, retrieve, LLM)
- Error counts by class (provider, Qdrant, timeout)
- Saturation: queue depth if you add workers later

### 3.2 Retrieval and RAG-specific

- Hit rate (non-empty context), average similarity / hybrid score, RRF rank stats
- Chunk source distribution (domain drift if ingestion changes)
- Citation rate (answers with vs without citations)

### 3.3 “Model” and content drift (inputs/outputs)

- Query length distribution, language detection counts (expat use case)
- Embedding norm or cluster centroid distance (optional advanced)
- Output length, refusal rate, tool-call rate (if agents)

### 3.4 Human and LLM-as-judge (offline or sampled)

- Golden-set scores from RAGAS or custom rubric
- Spot-check labels stored with trace id for audit

---

## 4. Phased plan (plan → implement → test)

### Phase A — Instrument the live path

- From the single code path used in production (Streamlit and/or FastAPI), call `record_*` in `monitoring/drift_detection.py` with minimal PII (hashed user id optional).
- Increment Prometheus metrics in-process or via push gateway (choose one model; avoid duplicate series).

**Test:** Local chat generates non-empty drift store; Grafana/Prometheus scrape shows non-zero rates.

### Phase B — Dashboards and alerts

- Grafana panels: latency p95, error rate, retrieval hit rate, drift indicator flags.
- Alert rules: sustained error spike, p95 latency, sudden drop in avg retrieval score.

**Test:** Synthetic fault injection (bad Qdrant URL) triggers alert in staging.

### Phase C — Drift investigation playbook

1. Confirm data pipeline (ingest) unchanged; check collection counts in Qdrant.
2. Compare query distribution vs last week (saved aggregates).
3. Run `run_ragas.py` on golden set with **pinned** model and prompt version.
4. Diff prompt or retrieval params vs last MLflow run (when MLflow exists).

**Test:** Tabletop exercise with saved snapshots; document RCA template in runbook.

### Phase D — Iteration tied to metrics

- Define **guardrail metrics** (must not regress) vs **optimization metrics** (improve over time).
- Every change: MLflow experiment (or ADR) + before/after golden scores.

**Test:** CI fails if golden score drops below threshold (when you add the gate).

---

## 5. Deliverables (when implementing)

- Runbook: “Drift alert fired → steps”
- Dashboard JSON or provisioning notes
- Optional: scheduled job (cron/Airflow) for nightly eval batch ([plan-databricks-airflow-dbt-powerbi.md](plan-databricks-airflow-dbt-powerbi.md))

---

## 6. Privacy and compliance (mortgage/expat context)

- Avoid logging raw PII in metrics; prefer aggregates and hashed identifiers.
- Retention policy for traces (Langfuse/Prometheus) documented alongside this plan.
