# Plan: Reproducible, versioned documentation of modeling, experiments, and results

**Scope:** Establish how development choices, experiments, and outcomes are captured so you—or a teammate—can replay and audit them. **Implementation is deferred** (this file is the planning artifact).

**Related:** [plan-reports-presentations.md](plan-reports-presentations.md), [langgraph-rag-mlflow-fastapi-build-test-monitor-deploy.md](langgraph-rag-mlflow-fastapi-build-test-monitor-deploy.md), [PHASES.md](../PHASES.md), [CODE_TODO.md](../CODE_TODO.md).

---

## 1. Goals

| Goal | Outcome |
|------|---------|
| **Reproducibility** | Given a git tag + MLflow run id + data snapshot id, recreate eval numbers |
| **Traceability** | Every prompt/retrieval change links to rationale and measured effect |
| **Onboarding** | New contributor reads docs and runs one command to reproduce baseline eval |

---

## 2. Versioned artifacts (what to track)

| Artifact | Where / how |
|----------|-------------|
| Source code | Git tags per release; `requirements.txt` pins (consider lockfile) |
| **Data** | Ingested corpus version: commit hash of `data/` or manifest (file hashes); Qdrant collection name + point count |
| **Embeddings / models** | Provider + model id in env or config; log on startup |
| **Prompts** | Versioned templates in repo or MLflow params; avoid only-UI edits for production |
| **Experiments** | MLflow: params, metrics, artifacts (eval CSV, confusion-style tables if classifiers exist) |
| **Infra** | `docker-compose.yml` image digests in release notes |

---

## 3. Documentation structure (suggested)

Keep **plan-docs** for roadmaps; add or extend **codedocs** for deep technical references:

1. **`codedocs/experiments/`** (optional folder) — One short markdown per major experiment: hypothesis, config diff, results table, link to MLflow.
2. **`ADR/` or `docs/adr/`** (optional) — Architecture Decision Records: “Why Qdrant,” “Why hybrid RRF,” “LangGraph vs custom orchestrator.”
3. **Root README** — “Reproduce baseline eval” section: env vars, `ingest_docs.py`, `run_ragas.py`, expected score range.
4. **CHANGELOG.md** — User-visible and model-visible changes per version.

---

## 4. Phased plan (plan → implement → test)

### Phase A — Baseline manifest

- Create a **data manifest** (JSON/YAML): list of source files, sha256, ingestion date.
- Script or makefile target: `reproduce-baseline` that runs ingest + eval with pinned env.

**Test:** Clean clone + documented steps → scores within documented tolerance.

### Phase B — MLflow (or equivalent) adoption

- One **experiment** per concern: `retrieval`, `prompts`, `agents`, `eval`.
- Log: `git_sha`, `qdrant_collection`, `embedding_model`, `prompt_version`, golden-set path.
- Store eval outputs as artifacts.

**Test:** `mlflow ui` shows runs; another machine reproduces metric from logged params.

### Phase C — Continuous documentation

- PR template checkbox: “Updated experiment log / ADR if behavior changed.”
- Release: attach eval summary snippet to tag notes.

**Test:** Review last 3 PRs for doc completeness (process audit).

---

## 5. MLflow ↔ this repo (mapping)

When MLflow is added:

- **Params:** chunk size, overlap, hybrid weights, top_k, temperature, router keywords.
- **Metrics:** RAGAS aggregates, latency from batch eval, drift indicator snapshots.
- **Artifacts:** `golden_questions.jsonl`, eval reports, sample bad traces (redacted).

---

## 6. What not to do

- Do not rely on “we changed the prompt in Streamlit session state” as the source of truth.
- Do not store secrets in experiment params; use references to secret names only.
