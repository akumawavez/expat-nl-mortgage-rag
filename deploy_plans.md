# Deployment plan: AI workloads (Generative AI / agentic RAG) in dev and staging

This document is a **plan only**—no code is executed. It outlines how to get hands-on experience deploying the Expat NL Mortgage RAG (and its agentic/Generative AI components) in **development** and **staging** environments.

**Related docs:** [DEPLOYMENT.md](DEPLOYMENT.md) (quick run, platforms), [docs/PRODUCTION_MLOPS_AIOPS.md](docs/PRODUCTION_MLOPS_AIOPS.md) (production, MLOps, AIOps).

---

## 1. Scope and objectives

| Objective | Description |
|-----------|-------------|
| **Dev** | Run the full stack (RAG, optional KG, agents, observability) locally or in a dev container with minimal setup and fast iteration. |
| **Staging** | Deploy the same workload in a cloud/staging environment (e.g. Azure Container Apps, or Docker on a VM) with env parity, health checks, and optional CI/CD. |
| **AI workload focus** | Generative AI (LLM + embeddings), agentic RAG (tools, citations, optional Phase 4 agents), and optional Knowledge Graph (Neo4j). |

**Out of scope for this plan:** Production hardening (see PRODUCTION_MLOPS_AIOPS.md), running any scripts or builds—this file is planning only.

---

## 2. Prerequisites (to implement later)

- **Secrets and env:** All keys (Qdrant, OpenAI/OpenRouter/Ollama, optional Tavily, Neo4j, Langfuse) via environment or secret store; never in code. Use `.env.example` as the single source of required variables.
- **Python:** Pin version (e.g. 3.11) in CI and in any Dockerfile; use `requirements.txt` (and optionally a lockfile) for reproducible installs.
- **Services the app depends on:**
  - **Qdrant** (required): vector store for RAG.
  - **Neo4j** (optional, Phase 2): Knowledge Graph.
  - **LLM/embedding APIs:** OpenAI, OpenRouter, or Ollama—configured via env.

---

## 3. Development environment plan

### 3.1 Local without Docker

- Use a virtualenv; install from `requirements.txt`.
- Run Qdrant via Docker: `docker run -p 6333:6333 qdrant/qdrant` (see DEPLOYMENT.md).
- If using Phase 2: run Neo4j (Docker or desktop) and set `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`.
- Ingest: `python scripts/ingest_docs.py`.
- Run app: `streamlit run app.py`.
- **Goal:** Fast feedback; no containerization of the app itself.

### 3.2 Development with Docker Compose (recommended for “deploy-like” dev)

- **Add a `Dockerfile`** (multi-stage optional): base image with Python 3.11, `requirements.txt`, copy app and `lib/`, `scripts/`, expose Streamlit port (e.g. 8501), default command `streamlit run app.py --server.port 8501 --server.address 0.0.0.0`.
- **Add a `docker-compose.yml`** (or `docker-compose.dev.yml`) that defines:
  - **app:** build from Dockerfile, env_file `.env`, ports 8501:8501, depends_on Qdrant (and optionally Neo4j).
  - **qdrant:** image `qdrant/qdrant`, port 6333:6333, optional volume for persistence.
  - **neo4j** (optional): image `neo4j`, ports 7474/7687, env for password; only if Phase 2 is in use.
- **Usage:** `docker compose up --build` (or `docker-compose -f docker-compose.dev.yml up --build`). First run: exec into app container or run ingest from host against `QDRANT_URL=http://localhost:6333`.
- **Goal:** One-command dev stack that mirrors staging (same app in a container, same backing services).

### 3.3 Environment parity

- Keep a single `.env.example` listing all variables for Chat/RAG, KG, agents, observability, and optional tools (Tavily, OSRM, etc.).
- Dev and staging should use the same variable names; staging can override with different values (e.g. managed Qdrant URL, API keys from a secret manager).

---

## 4. Staging environment plan

### 4.1 Build and image

- **Build:** Use the same Dockerfile as in dev. Tag images with a version or git SHA (e.g. `expat-rag:staging-$(git rev-parse --short HEAD)`).
- **Registry:** Push to a container registry (e.g. Docker Hub, GitHub Container Registry, or Azure ACR) so staging can pull the image.

### 4.2 Staging deployment options (choose one or more for hands-on)

| Option | Description | Hands-on focus |
|--------|-------------|----------------|
| **A. Docker on a VM** | Run `docker compose` on a single VM (e.g. Azure VM, EC2). Use env from a file or a small secret store. | Same compose as dev with different env; learn networking and persistence. |
| **B. Azure Container Apps** | Run the app as a Container App; use Azure Key Vault or Container Apps secrets for env. Optional: run Qdrant/Neo4j as sidecars or separate containers. | Managed scaling, HTTPS, and Azure integration (per NotesToImprove / PHASES). |
| **C. Azure Container Instances (ACI)** | Single container or container group; good for a simple staging slice. | Quick cloud deploy without orchestration. |
| **D. Kubernetes (e.g. AKS, or minikube)** | Deploy app and Qdrant (and optionally Neo4j) as Deployments/Services; ConfigMaps/Secrets for env. | Orchestration, health checks, and rollout patterns. |

### 4.3 Staging checklist (to implement)

- [ ] **Secrets:** All API keys and DB credentials from secret manager or platform secrets (no `.env` in image).
- [ ] **Qdrant:** Use managed Qdrant (e.g. qdrant.cloud) or a dedicated Qdrant instance with persistence and backup.
- [ ] **Neo4j:** If Phase 2 is used, use managed Neo4j or a dedicated container/VM with backups.
- [ ] **Health checks:** Add a small health endpoint (e.g. `/health` or `/ready`) that checks app readiness and optionally Qdrant connectivity; configure the platform’s health probe.
- [ ] **HTTPS:** Use platform TLS or a reverse proxy so staging is served over HTTPS.
- [ ] **Logging:** Emit structured logs (e.g. request_id, tool, latency) to stdout so the platform or a log aggregator can collect them.
- [ ] **Ingestion:** Run `scripts/ingest_docs.py` as a one-off job (e.g. container job or CI step) when documents change, or use a scheduled job; ensure same `QDRANT_COLLECTION` and embedding config as the app.

---

## 5. CI/CD extension plan (optional)

- **Existing:** `.github/workflows/ci.yml` runs lint and tests on push/PR; tests use a dummy Qdrant URL.
- **Add (when implementing):**
  - **Build and push:** On push to `main` (or a `staging` branch), build the Docker image and push to the chosen registry with a tag (e.g. `staging-<sha>`).
  - **Deploy to staging:** Optional job or separate workflow that deploys the new image to the chosen staging platform (e.g. Azure Container Apps, or SSH + `docker compose pull && docker compose up -d` on a VM). Use GitHub Secrets for registry and deployment credentials.
  - **Smoke test:** After deploy, run a minimal smoke test (e.g. curl health endpoint or one RAG query) and fail the workflow if it fails.
- **No run in this plan:** Only define the above as intended steps; implementation is separate.

---

## 6. Observability and operations (dev/staging)

- **Metrics:** Use existing `scripts/metrics_server.py` (Prometheus `/metrics`) in dev/staging if needed; optionally scrape in staging and view in Grafana (see docs/monitoring.md).
- **Tracing/LLM observability:** If `LANGFUSE_HOST` (and key) are set, the app can send traces; enable in staging for debugging and token/latency visibility.
- **Alerts (staging):** Define simple alerts (e.g. health check failing, high error rate) in the staging platform or Prometheus/Grafana; no implementation in this plan.

---

## 7. Rollback and versioning

- **Versioning:** Tag Docker images with git SHA or semantic version; keep a small set of previous tags in the registry.
- **Rollback:** Document the exact command or pipeline step to deploy a previous image (e.g. redeploy with `expat-rag:staging-<previous-sha>`).
- **Data:** For Qdrant/Neo4j, document backup/restore or re-ingestion so a rollback can point to a known-good state if needed.

---

## 8. Implementation order (suggested)

1. **Dev:** Add Dockerfile and docker-compose (app + Qdrant; optional Neo4j); document `docker compose up` and one-time ingest.
2. **Env:** Consolidate and document all variables in `.env.example`; ensure dev and staging use the same names.
3. **Staging:** Choose one target (e.g. Azure Container Apps or Docker on VM); implement deploy and secrets; add health endpoint and wire platform health probe.
4. **CI/CD:** Add build-and-push workflow; optionally add deploy-to-staging and smoke test.
5. **Observability:** Enable Langfuse (or similar) and optional Prometheus scrape in staging; add a short “Staging” section to docs/monitoring.md.

---

## 9. Success criteria (hands-on)

- **Dev:** Any developer can run the full Generative AI / agentic RAG stack with `docker compose up` (and one ingest step) and open the app in a browser.
- **Staging:** The same application runs in a cloud/staging environment with secrets, health checks, and HTTPS; deployments are repeatable (e.g. via CI or documented manual steps).
- **Documentation:** DEPLOYMENT.md and this file (or a short “Staging” doc) describe how to run in dev and how to deploy and roll back in staging.

---

*This plan is for planning only; no code has been run or generated as part of this document.*
