# Security and monitoring practices for cloud and AI systems: plan and documentation

This document is a **plan and documentation** only—no code is executed. It consolidates **security** and **monitoring** practices relevant to **cloud** and **AI** systems, summarizes what this project already documents or implements, and gives a checklist for gaps.

**Related docs:** [docs/SECURITY_AND_ERROR_HANDLING.md](docs/SECURITY_AND_ERROR_HANDLING.md) (prompt injection, errors), [docs/MONITORING_AND_EVALUATION.md](docs/MONITORING_AND_EVALUATION.md) (metrics, drift, evals), [docs/PRODUCTION_MLOPS_AIOPS.md](docs/PRODUCTION_MLOPS_AIOPS.md) (production, MLOps, AIOps), [docs/RESPONSIBLE_AI.md](docs/RESPONSIBLE_AI.md) (traceability, oversight), [azure_platform_plan.md](azure_platform_plan.md) (Azure security).

---

## 1. Scope and objectives

| Objective | Description |
|-----------|-------------|
| **Security awareness** | Secrets, identity, network, TLS, input validation, prompt injection, data protection, and compliance considerations for cloud and AI. |
| **Monitoring awareness** | Metrics, logs, alerts, health checks, and AI-specific observability (latency, tokens, quality, drift) in cloud and on-prem. |
| **Plan** | Single checklist and pointers so the repo demonstrates awareness and links to existing docs; identify remaining to-dos. |

---

## 2. Security practices

### 2.1 Secrets and configuration

- **Never in code or images:** API keys, database credentials, and tokens must come from environment variables or a **secret store** (e.g. Azure Key Vault, HashiCorp Vault). `.env` is gitignored; `.env.example` documents required vars without values.
- **Cloud:** Use managed identity (e.g. Azure Container App identity) to read secrets from Key Vault so no long-lived keys are stored in env. See [azure_platform_plan.md](azure_platform_plan.md).
- **Rotation:** Document or automate secret rotation; apps should tolerate key rotation without code change (restart or reload env).

### 2.2 Authentication and authorization

- **Application:** This app has no user accounts; it’s a single-tenant UI. For a future REST API or multi-tenant use, define auth (API key, JWT, OAuth) and authorization (who can call which endpoint). See [api_development_and_integration_plan.md](api_development_and_integration_plan.md).
- **Cloud:** Use platform auth (e.g. Azure AD) for CI/CD and for service-to-service calls; least-privilege roles (e.g. Key Vault Secrets User only for the app identity).

### 2.3 Network and transport

- **TLS:** All user-facing and API traffic over HTTPS. In cloud, use platform TLS (e.g. Azure Container Apps default) or a reverse proxy/gateway.
- **Outbound:** App calls LLM APIs, Qdrant, Neo4j, and third-party APIs; ensure outbound connectivity and firewall rules allow only required endpoints. No secrets in URLs or logs.
- **Internal:** In Docker/Kubernetes, service-to-service can use internal DNS and optional mTLS; keep internal ports off the public internet.

### 2.4 Input validation and abuse

- **Validation:** Validate and length-limit user input before retrieval and LLM calls. Reject malformed or oversized requests with a clear, safe message. See [docs/SECURITY_AND_ERROR_HANDLING.md](docs/SECURITY_AND_ERROR_HANDLING.md).
- **Rate limiting:** Protect against abuse and cost spikes (e.g. runaway LLM calls). Implement at the app, reverse proxy, or API gateway. Documented in deploy_plans and PRODUCTION_MLOPS_AIOPS; implementation in CODE_TODO.

### 2.5 Prompt injection and AI-specific security

- **Risk:** User or attacker input can try to override instructions, leak context, or force off-topic/harmful output. See [docs/SECURITY_AND_ERROR_HANDLING.md](docs/SECURITY_AND_ERROR_HANDLING.md).
- **Mitigations (documented):** Fixed system prompt; clear separation of context vs user message; length limits; output instructions (“answer only from context”); detection (heuristics or classifier) and safe response on suspicion; logging without PII.
- **Implementation:** Detection and handling are in CODE_TODO; awareness and design are in SECURITY_AND_ERROR_HANDLING.

### 2.6 Data protection and privacy

- **PII:** Do not log full prompts or user content in production if they may contain PII. Log request_id, tool, latency, and error type only. Redaction and retention policies are recommended for production (CODE_TODO).
- **Data at rest:** Use encrypted storage for Qdrant and any persisted data; cloud storage is typically encrypted by default. Document if you handle sensitive documents (e.g. mortgage data) and any retention or deletion requirements.
- **Compliance:** Be aware of applicable regulations (e.g. GDPR if EU users); document data flows and retention where required. This doc does not provide legal advice.

### 2.7 Dependencies and supply chain

- **Dependencies:** Keep `requirements.txt` (and lockfile if used) up to date; run `pip audit` or similar to check for known vulnerabilities. CI can fail on high/critical CVEs.
- **Images:** Use trusted base images; scan images in CI or in the registry (e.g. Azure Defender, Trivy). See docker_containerization_plan and azure_platform_plan.

---

## 3. Monitoring practices

### 3.1 Metrics (operational)

- **What to collect:** Request count and latency by operation (e.g. vector_search, hybrid_retrieve, LLM call); error count by type or tool; optional throughput (requests/sec). See [docs/MONITORING_AND_EVALUATION.md](docs/MONITORING_AND_EVALUATION.md) and [docs/monitoring.md](docs/monitoring.md).
- **Where:** Prometheus-compatible `/metrics` endpoint (e.g. `scripts/metrics_server.py`); scrape with Prometheus or Azure Monitor. The app must be **instrumented** to increment/observe (CODE_TODO).
- **Cloud:** Azure Monitor can scrape metrics or receive push; Container Apps and AKS expose platform metrics (CPU, memory, restarts). Correlate app metrics with platform metrics.

### 3.2 Logging

- **Structured logs:** Emit JSON (or key-value) with `request_id`, `timestamp`, `level`, `message`, `tool`, `latency_ms`, `error` (type only, no stack in prod). Send to a log aggregator (e.g. Azure Log Analytics, ELK, Loki). See PRODUCTION_MLOPS_AIOPS.
- **Sensitive data:** No API keys, full prompts, or PII in logs. Log only IDs and metadata for debugging.
- **Retention:** Define retention and access policy for logs (e.g. 30–90 days); align with compliance if applicable.

### 3.3 Health checks

- **Liveness:** Is the process running? Simple HTTP 200 on `/health` or equivalent.
- **Readiness:** Can the app serve traffic? Optionally check Qdrant (and Neo4j if used) so the orchestrator does not send traffic until dependencies are reachable. Document in deploy_plans and DEPLOYMENT.
- **Cloud:** Configure the platform’s health probe (e.g. Container Apps, AKS) to use `/health`; failed probes trigger restart or removal from load balancer.

### 3.4 Alerting

- **Latency:** Alert if p95 or p99 latency exceeds a threshold (e.g. 10 s for RAG). See PRODUCTION_MLOPS_AIOPS.
- **Errors:** Alert on error rate spike (e.g. `rate(rag_errors_total[5m]) > 0.1`) or consecutive failures.
- **Availability:** Alert if health checks fail (app or Qdrant down).
- **Quality (AI):** Optional alert if retrieval or response quality (drift, RAGAS) drops below a threshold when implemented.
- **Security:** Optional alert on suspected prompt injection or abnormal request volume (when detection is in place).
- **Channels:** Route alerts to email, Slack, PagerDuty, or Azure Action Groups; document in runbooks.

### 3.5 AI-specific observability

- **Token usage and cost:** Track input/output tokens and estimated cost per request (e.g. via Langfuse or provider API). Surfaces runaway usage and supports capacity planning.
- **Quality and drift:** Retrieval quality (e.g. relevance of retrieved chunks) and response quality (faithfulness, answer relevance) over time. Use `monitoring/drift_detection.py` and RAGAS-style evals; see MONITORING_AND_EVALUATION and RESPONSIBLE_AI.
- **Traceability:** Per-request trace (retrieval → context → LLM → answer) for debugging and auditing. Langfuse (when configured) and “Tools Used” + “Sources” in the UI support this. See RESPONSIBLE_AI.
- **Model and config:** Log which model and provider were used per request (or in aggregate) so you can correlate quality or cost with changes.

### 3.6 Incident response and runbooks

- **Runbooks:** Document how to restart the app and Qdrant, how to roll back an ingestion or deployment, how to disable a failing tool (e.g. Tavily) via config, and how to respond to prompt injection or abuse (e.g. block, throttle, log). See PRODUCTION_MLOPS_AIOPS.
- **Traceability:** Use trace IDs (e.g. Langfuse) to debug a specific user report or bad answer.
- **Post-incident:** Optional post-mortem process (what happened, root cause, actions) to improve security and monitoring.

---

## 4. Current state in this repository

| Area | Documented / implemented | Location |
|------|---------------------------|----------|
| **Secrets** | Env-based; no secrets in code; .env gitignored | DEPLOYMENT, .env.example, azure_platform_plan |
| **Prompt injection** | Design and mitigations documented; detection/handling to-do | SECURITY_AND_ERROR_HANDLING, CODE_TODO |
| **Error handling** | General approach and recommendations | SECURITY_AND_ERROR_HANDLING |
| **Input validation / rate limit** | Mentioned; not implemented | CODE_TODO, api_development_and_integration_plan |
| **Metrics** | /metrics and /health (metrics_server); metric names defined | metrics_server.py, MONITORING_AND_EVALUATION, monitoring.md |
| **App instrumentation** | Not wired; counters/latency not incremented by app | CODE_TODO, MONITORING_AND_EVALUATION |
| **Drift / quality** | Module and UI; recording from app optional | drift_detection.py, MONITORING_AND_EVALUATION, RESPONSIBLE_AI |
| **Logging** | Structured logging recommended; not fully implemented | PRODUCTION_MLOPS_AIOPS |
| **Alerts** | Recommended (latency, errors, availability, quality) | PRODUCTION_MLOPS_AIOPS |
| **Health checks** | /health in metrics_server; app health to-do | deploy_plans, DEPLOYMENT |
| **Traceability** | Tools Used, Sources, Langfuse | RESPONSIBLE_AI, app.py |
| **Cloud (Azure)** | Key Vault, managed identity, TLS | azure_platform_plan, deploy_plans |
| **PII / compliance** | Awareness; redaction and retention to-do | This doc §2.6, CODE_TODO |

---

## 5. Plan and checklist (no code run)

Use this checklist to close gaps and demonstrate awareness. Implementation is separate; this file only plans and documents.

### 5.1 Security

- [ ] **Prompt injection:** Implement detection (heuristics or classifier) and safe response; log suspected attempts; see SECURITY_AND_ERROR_HANDLING and CODE_TODO.
- [ ] **Input validation:** Enforce length limit and basic validation before retrieval/LLM; return clear error message.
- [ ] **Rate limiting:** Add at app layer or at gateway/reverse proxy; document in DEPLOYMENT or api_development_and_integration_plan.
- [ ] **Secrets in cloud:** When deploying to Azure, use Key Vault and managed identity; document in azure_platform_plan (already outlined).
- [ ] **PII in logs:** Ensure no full prompts or PII in production logs; document redaction/retention if required.
- [ ] **Dependencies:** Add `pip audit` or similar to CI; document in CONTRIBUTING or CI workflow.

### 5.2 Monitoring

- [ ] **Instrumentation:** Wire app to Prometheus (REQUEST_COUNT, REQUEST_LATENCY, ERROR_COUNT) and to drift module (record_retrieval_score, record_latency_ms, record_tool_use); see CODE_TODO and MONITORING_AND_EVALUATION.
- [ ] **Structured logging:** Add structured (e.g. JSON) logs with request_id and metadata; document format and destination.
- [ ] **Health endpoint:** Add /health (or /ready) to the main app if it runs separately from metrics_server; check Qdrant (and Neo4j if used) for readiness; see deploy_plans.
- [ ] **Alerts:** Define at least one alert (e.g. error rate or latency) in Prometheus/Grafana or Azure Monitor; document in monitoring.md or PRODUCTION_MLOPS_AIOPS.
- [ ] **Runbooks:** Add a short runbook (restart, rollback, disable tool, respond to abuse) to docs or OPERATIONS.md; link from README.

### 5.3 Documentation

- [ ] **README or OPERATIONS:** Add a “Security and monitoring” subsection that links to this file, SECURITY_AND_ERROR_HANDLING, MONITORING_AND_EVALUATION, and PRODUCTION_MLOPS_AIOPS.
- [ ] **Compliance:** If handling sensitive data, document data flows and retention in a dedicated section or doc; this plan does not implement compliance.

---

## 6. Summary: awareness demonstrated

| Practice | Cloud | AI | In this repo |
|----------|-------|-----|--------------|
| **Secrets management** | Key Vault, managed identity | Env for API keys | Documented; cloud in azure_platform_plan |
| **Auth and network** | TLS, identity, least privilege | — | Documented in deploy/API docs |
| **Prompt injection** | — | Detection, safe response | SECURITY_AND_ERROR_HANDLING; code to-do |
| **Input and rate limit** | Gateway / proxy | Protect LLM cost and abuse | Mentioned; implementation to-do |
| **Metrics and logs** | Azure Monitor, Log Analytics | Token, latency, quality | Metrics server exists; app instrumentation to-do |
| **Health and alerts** | Platform probes, Action Groups | — | Health in metrics_server; alerts documented |
| **Quality and drift** | — | Drift, RAGAS, traceability | drift_detection, RESPONSIBLE_AI, evals |
| **Traceability** | Request ID, logs | Tools Used, Sources, Langfuse | In place in UI and docs |
| **Runbooks and incidents** | Restart, rollback | Abuse, bad answers | Documented in PRODUCTION_MLOPS_AIOPS; runbook to-do |

---

## 7. References

- [docs/SECURITY_AND_ERROR_HANDLING.md](docs/SECURITY_AND_ERROR_HANDLING.md) – Prompt injection, validation, errors.
- [docs/MONITORING_AND_EVALUATION.md](docs/MONITORING_AND_EVALUATION.md) – Metrics, drift, RAGAS, Grafana.
- [docs/PRODUCTION_MLOPS_AIOPS.md](docs/PRODUCTION_MLOPS_AIOPS.md) – Production, MLOps, AIOps, alerts.
- [docs/RESPONSIBLE_AI.md](docs/RESPONSIBLE_AI.md) – Traceability, transparency, oversight.
- [azure_platform_plan.md](azure_platform_plan.md) – Azure security (Key Vault, identity, network).
- [CODE_TODO.md](CODE_TODO.md) – Implementation to-dos for security and instrumentation.

---

*This document is a plan and documentation only; no code has been run or modified as part of this file.*
