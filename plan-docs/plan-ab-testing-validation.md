# Plan: A/B testing and validation for model impact and reliability

**Scope:** How to compare two RAG/agent configurations (prompts, retrieval params, models, orchestration) safely, measure impact, and validate reliability before full rollout. **Implementation and tests are deferred.**

**Related:** [plan-ml-realtime-deployment.md](plan-ml-realtime-deployment.md), [plan-production-monitoring-drift.md](plan-production-monitoring-drift.md), [plan-reproducible-model-documentation.md](plan-reproducible-model-documentation.md).

---

## 1. Definitions

| Term | Meaning in this project |
|------|-------------------------|
| **Variant A / B** | Two reproducible configs: e.g. `top_k`, rerank on/off, different system prompt, LangGraph vs legacy orchestrator |
| **Unit of randomization** | Prefer **session** or **anonymous user id** cookie for sticky experience; avoid flipping mid-conversation unless intentional |
| **Primary metric** | Task success: golden-set score, human rating, or “citation present + no error” composite |
| **Guardrail metrics** | Latency p95, error rate, cost per request |

---

## 2. Validation dimensions

1. **Offline validation** — Same golden queries, frozen embeddings collection, compare scores and outputs (cheapest, first gate).
2. **Shadow traffic** — Production requests duplicated to variant B; no user sees B’s answer; log diff metrics (latency, retrieval stats).
3. **User-facing A/B** — Small % traffic to B; monitor business and quality metrics; ethical review if content is regulated.
4. **Canary deploy** — New container version receives 5–10% traffic at gateway; promote or rollback.

---

## 3. Phased plan (plan → implement → test)

### Phase 1 — Experiment design

- Hypothesis template: “Changing X improves Y without hurting Z.”
- Pre-register metrics and minimum detectable effect (even if informal for a learning project).
- Decide exposure: internal only, beta users, or full random sample.

**Test (when implementing):** Design doc peer review (self-review checklist is fine for solo work).

### Phase 2 — Technical plumbing

- **Feature flag** or env-based variant: `EXPERIMENT_VARIANT=a|b` resolved per session.
- Structured logging: `variant`, `trace_id`, `latency_ms`, `retrieval_hits`, `error_code`.
- Optional: expose variant in API response header for debugging (non-production only).

**Test:** Unit test that assignment is sticky for a session id; distribution ~50/50 within tolerance.

### Phase 3 — Analysis

- Aggregate by variant: mean/median metrics, confidence intervals (bootstrap or t-test on golden scores).
- Segment by query type (mortgage vs location vs calculator) if routing exists.

**Test:** Notebook or script reproducible from exported CSV/Parquet; same result on re-run.

### Phase 4 — Decision and rollout

- Promote winner to 100% or iterate; document decision in ADR or experiment log.
- Rollback path: flag off, redeploy previous image.

**Test:** Rollback drill in staging.

---

## 4. Fit with current codebase

- **Orchestrator switch:** Sidebar or env flag already aligns with “variant” concept; formalize session-level assignment in `app.py` or API middleware.
- **Metrics:** Extend Prometheus labels with `variant` (cardinality stays low: `a`, `b`).
- **Quality:** Run `scripts/run_ragas.py` per variant in CI or nightly job; store results for comparison.

---

## 5. Ethics and UX (financial/expat advice context)

- Do not A/B test misleading answers; variants should be “honest” configuration changes.
- Disclose beta or experimental UI if user-facing; prefer shadow/offline first.

---

## 6. Deliverables (when implementing)

- Experiment log template (markdown table: date, hypothesis, variants, metrics, decision)
- Optional: minimal admin page listing active experiments (internal)
