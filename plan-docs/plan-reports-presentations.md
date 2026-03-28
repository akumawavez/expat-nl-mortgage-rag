# Plan: Reports and presentations (methods, findings, recommendations)

**Scope:** How to communicate RAG/agent work to technical and non-technical stakeholders: structure, cadence, and artifacts that map directly to this repository. **No slide deck or code is produced in this step**—this is the plan only.

**Related:** [plan-reproducible-model-documentation.md](plan-reproducible-model-documentation.md), [plan-ab-testing-validation.md](plan-ab-testing-validation.md).

---

## 1. Audiences and formats

| Audience | Format | Emphasis |
|----------|--------|----------|
| Course / hiring panel | 10–15 min deck + 1-pager | Problem, demo, metrics, what you learned |
| Engineering peers | Written report + architecture diagram | APIs, data flow, failure modes, test coverage |
| Product / compliance-minded | FAQ + limitations appendix | Not legal advice, sources, human review |

---

## 2. Core narrative (recommended story arc)

1. **Problem** — Expat mortgage information is fragmented; users need grounded, cited answers.
2. **Approach** — RAG over curated docs, hybrid retrieval, optional KG/agents (`lib/retrieval.py`, `lib/agents.py`, Phase tabs in `app.py`).
3. **Method** — Chunking, embeddings, orchestration; how citations are produced.
4. **Evaluation** — Golden questions, RAGAS/heuristic metrics (`scripts/run_ragas.py`), limitations of automated eval.
5. **Operations** — Monitoring/drift plan ([plan-production-monitoring-drift.md](plan-production-monitoring-drift.md)), deployment sketch ([plan-ml-realtime-deployment.md](plan-ml-realtime-deployment.md)).
6. **Findings** — 3–5 concrete results (e.g. hybrid vs dense-only, prompt change X).
7. **Recommendations** — Next experiments, governance, production hardening.

---

## 3. Artifacts to generate (when you implement this plan)

| Artifact | Purpose |
|----------|---------|
| **Executive summary** (1 page) | Outcomes and risks in plain language |
| **Technical report** (5–15 pages) | Repro steps, architecture, eval tables, references to MLflow runs |
| **Slide deck** | Demo screenshots, one architecture slide, metric trend charts |
| **Demo script** | 5 fixed queries that show citations, edge cases, and failure handling |
| **Appendix** — Limitations | When not to trust the system; escalate to professional advice |

---

## 4. Data visualization checklist

- Latency and error trends (from Prometheus or batch logs).
- Eval score before/after table (from experiment log).
- Simple diagram: User → API/Streamlit → embed → Qdrant → LLM → response + citations.

Use **mermaid** in markdown reports for version-control-friendly diagrams.

---

## 5. Cadence (if the project is ongoing)

- **Weekly (light):** Bullet changelog + one metric snapshot.
- **Per milestone:** Update deck and technical report section.
- **Pre-release:** Refresh limitations and “known issues” from [CODE_TODO.md](../CODE_TODO.md).

---

## 6. Quality bar for claims

- Every quantitative claim ties to a **logged run** or **script output** (path + date).
- Avoid cherry-picking: show one “bad” example and how monitoring would catch it.

---

## 7. Deliverables folder suggestion (optional, when you create content)

- `plan-docs/slides/` or `reports/` — Keep out of repo if large binaries; prefer PDF export linked from README.
