# How to use ML, statistics, and Databricks/PySpark skills in this project

**Purpose:** Map your strengths—**data manipulation, statistical analysis, classical ML (MLlib, scikit-learn), deep learning stacks, MLflow, Databricks, PySpark**—to the **expat-nl-mortgage-rag** codebase so interview and portfolio stories stay concrete.

**Related:** [plan-databricks-airflow-dbt-powerbi.md](plan-databricks-airflow-dbt-powerbi.md), [plan-reproducible-model-documentation.md](plan-reproducible-model-documentation.md), [langgraph-rag-mlflow-fastapi-build-test-monitor-deploy.md](langgraph-rag-mlflow-fastapi-build-test-monitor-deploy.md).

---

## 1. Where this project is “ML-heavy” today

| Area | Repo touchpoints | Skill angle |
|------|------------------|-------------|
| **Text → vectors** | `lib/provider.py`, embeddings in retrieval | Same as feature extraction; model id is a tracked “model” |
| **Retrieval as scoring** | `lib/retrieval.py` (hybrid, RRF) | Ranking metrics: nDCG@k, MRR on labeled pairs |
| **Quality / drift** | `monitoring/drift_detection.py`, `scripts/run_ragas.py` | Distributional comparisons, control charts, hypothesis tests on eval scores |
| **Orchestration (future)** | MLflow for experiments | Standard experiment tracking you already know from sklearn workflows |

The app is **RAG + LLM-first**, not a tabular classifier—but **your statistical and MLOps habits** still apply to eval, drift, and versioning.

---

## 2. Concrete ways to apply each skill

### 2.1 Data manipulation and statistics

- **Build a labeled eval set:** Query–document relevance labels (binary or graded); summarize with precision@k, recall@k, calibration-style checks on “confidence” scores if you expose them.
- **Drift:** Compare weekly histograms of query length, retrieval score, language; use KS test or simple thresholds in `monitoring/drift_detection.py` (conceptually—implement later).
- **A/B analysis:** Compare variant metrics with confidence intervals ([plan-ab-testing-validation.md](plan-ab-testing-validation.md)).

### 2.2 Scikit-learn

- **Reranking / classification:** Train a lightweight **cross-encoder or logistic** model on hand-labeled (query, chunk) pairs; sklearn for baseline, or export features for a two-stage retrieve-then-rerank pipeline.
- **Clustering / topic drift:** Embed historical queries (batch job), cluster with sklearn, track cluster mass shift over time (offline job).

### 2.3 MLlib (Spark)

- Use when **volume** of logs or training pairs outgrows pandas: distributed feature prep, train/test split at scale, batch scoring of retrieval candidates. Natural home: **Databricks** notebooks reading bronze/silver tables ([plan-databricks-airflow-dbt-powerbi.md](plan-databricks-airflow-dbt-powerbi.md)).

### 2.4 TensorFlow / PyTorch

- Optional **fine-tuned embedding or reranker** for domain-specific mortgage Dutch/English; log checkpoints and metrics to MLflow.
- Keep serving path simple: export model behind a small Python dependency or ONNX if you later split services.

### 2.5 MLflow

- Log **every** retrieval/prompt experiment: params (chunk size, top_k, hybrid weights), metrics (golden-set scores, latency), artifacts (eval tables, prompt files).
- Register a “model” that is really a **bundle**: prompt version + embedding model name + retrieval config (conceptual model flavor for RAG).

### 2.6 Databricks + PySpark

- **Ingestion at scale:** If sources move from flat files to lakehouse, PySpark cleans/normalizes HTML/PDF-derived text before writing to a **staging** table; downstream job writes chunks to Qdrant or exports parquet for batch embed.
- **Batch analytics:** Sessionized chat logs (if exported with governance), aggregations for Power BI or internal dashboards.

---

## 3. Portfolio narrative (one paragraph you can reuse)

> I treated the RAG stack like an ML system: versioned data and prompts, MLflow for experiments, statistical monitoring for query and retrieval drift, and golden-set evaluation with clear metrics. Where tabular or high-volume workloads appear, I use PySpark on Databricks for feature and log processing, and sklearn or MLlib for baselines and rerankers.

---

## 4. Suggested next experiments (priority order)

1. MLflow + golden-set automation ([plan-reproducible-model-documentation.md](plan-reproducible-model-documentation.md)).
2. Labeled retrieval metrics (small hand-set is enough for a portfolio).
3. Optional sklearn reranker on top-k candidates from `lib/retrieval.py`.
4. Databricks notebook that reproduces ingest stats and eval summary from the same git SHA.

---

## 5. Boundaries (be honest in interviews)

- Core **generative** answers are not “a sklearn `.predict` in production”; the **discipline** (eval, drift, versioning) is what transfers.
- Financial advice disclaimers and human oversight remain product requirements, not ML accuracy alone.
