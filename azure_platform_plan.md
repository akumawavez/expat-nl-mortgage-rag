# Azure platform plan: practical experience

This document is a **plan only**—no code is executed. It outlines how to gain practical experience with **Microsoft Azure** in the context of the Expat NL Mortgage RAG project (Generative AI / agentic RAG).

**Related docs:** [deploy_plans.md](deploy_plans.md) (dev/staging deployment), [DEPLOYMENT.md](DEPLOYMENT.md) (quick run), [docs/PRODUCTION_MLOPS_AIOPS.md](docs/PRODUCTION_MLOPS_AIOPS.md) (production, MLOps).

---

## 1. Scope and objectives

| Objective | Description |
|-----------|-------------|
| **Azure fundamentals** | Use Azure Portal, CLI, and resource organization (subscriptions, resource groups, naming). |
| **Containers and compute** | Build, store, and run containerized app and optional backing services on Azure. |
| **Secrets and identity** | Store API keys and credentials in Azure Key Vault; use managed identity where applicable. |
| **Networking and hosting** | Expose the app over HTTPS with minimal configuration. |
| **Observability** | Use Azure Monitor and optional Log Analytics for logs and metrics. |
| **CI/CD** | Build and push images from GitHub Actions; optionally deploy to Azure from the same pipeline. |

**Out of scope for this plan:** Running any Azure commands or deploying resources—this file is planning only.

---

## 2. Azure account and resource organization

### 2.1 Prerequisites (to implement later)

- **Azure subscription:** Create or use an existing subscription (e.g. free tier or Visual Studio benefit). Ensure you have enough quota for the services below.
- **Azure CLI:** Install and run `az login`; use the same identity in local dev and in GitHub Actions (service principal or federated credential).
- **Resource group:** Create one resource group per environment (e.g. `rg-expat-rag-dev`, `rg-expat-rag-staging`) in a single region (e.g. `westeurope`) to keep billing and networking simple.

### 2.2 Naming and tagging

- **Naming convention:** Use a consistent prefix (e.g. `expatrag`) and environment suffix (e.g. `stg`, `prod`). Example: `expatragstg-acr`, `expatragstg-kv`.
- **Tags:** Add tags such as `Project=expat-nl-mortgage-rag`, `Environment=staging`, `ManagedBy=manual` (or `terraform` / `bicep` if you adopt IaC later) for cost and governance.

---

## 3. Azure services to use (by category)

### 3.1 Container registry (Azure Container Registry – ACR)

- **Purpose:** Store Docker images for the RAG app (and optionally for Qdrant/Neo4j if self-hosted on Azure).
- **Plan:** Create an ACR (Basic or Standard SKU); enable admin user or use Azure AD auth for pull. Configure GitHub Actions to build the app image and push to ACR with a tag (e.g. `staging-<git-sha>`).
- **Hands-on:** Create ACR → build image locally or in CI → push → pull from Container Apps / ACI / AKS.

### 3.2 Compute: where to run the app

| Service | Use case | Hands-on focus |
|---------|----------|----------------|
| **Azure Container Apps** | Run the Streamlit RAG app as a container with scaling (0 to N), built-in HTTPS, and easy env/secrets from Key Vault or literal values. | Managed app hosting, revisions, ingress, minimal YAML or Portal. |
| **Azure Container Instances (ACI)** | Single container or container group; good for staging or one-off jobs (e.g. ingest script). | Simple deploy, no orchestration. |
| **Azure App Service (Linux, container)** | Run a single container with custom domain, slots, and App Service auth if needed. | Alternative to Container Apps; more app-centric features. |
| **Azure Kubernetes Service (AKS)** | Run app + Qdrant + optional Neo4j in one cluster; full control over networking and scaling. | Orchestration, Deployments, Services, ConfigMaps, Secrets. |
| **Azure VM** | Run Docker Compose on a Linux VM; full control. | IaaS, SSH, firewall, disk. |

**Suggested path for practical experience:** Start with **Container Apps** (or ACI) for the app; use managed or external Qdrant/Neo4j. Optionally add **AKS** or a **VM** for a second pass.

### 3.3 Secrets: Azure Key Vault

- **Purpose:** Store API keys (OpenAI, OpenRouter, Tavily), Qdrant URL/key, Neo4j credentials, and any other secrets. Avoid storing secrets in repo or in container env as plain text.
- **Plan:** Create a Key Vault per environment (e.g. `expatragstg-kv`). Add secrets for each variable in `.env.example`. Grant the compute identity (Container App managed identity, or AKS pod identity / workload identity) access to read secrets (e.g. `Key Vault Secrets User` or custom role).
- **Hands-on:** Create Key Vault → add secrets → reference them in Container Apps (Key Vault references) or in AKS (CSI driver / external secrets operator, or init container that fetches and exports env). Optionally use Azure CLI or a small script to populate secrets from a local `.env` (never commit `.env`).

### 3.4 Networking (minimal for staging)

- **Container Apps / ACI:** Use default Microsoft-managed ingress and TLS; optional custom domain and DNS (e.g. Azure DNS or external).
- **VM / AKS:** Plan a VNet, subnets, NSG rules (e.g. allow 22 for SSH, 80/443 for app), and optional private endpoints for Key Vault or ACR to reduce exposure.
- **Outbound:** App needs outbound access to LLM APIs, Qdrant, Neo4j; no special config if using public endpoints. If Qdrant/Neo4j are inside Azure, use VNet integration or private endpoints as needed.

### 3.5 Data and backing services (optional on Azure)

- **Qdrant:** Use [Qdrant Cloud](https://qdrant.cloud) (any cloud) or self-host Qdrant in ACI/AKS/VM with an Azure Disk for persistence. Document backup (snapshots or re-ingestion).
- **Neo4j:** Use Neo4j Aura (managed) or run Neo4j in ACI/AKS/VM with persistent storage.
- **Azure OpenAI (optional):** If you want to use Azure-hosted OpenAI models, create an Azure OpenAI resource, deploy a model, and point the app to that endpoint and key (stored in Key Vault). This gives experience with Azure’s Generative AI offering.

### 3.6 Observability: Azure Monitor and Logs

- **Container Apps / ACI:** Enable Log Analytics (or use the default workspace); view container logs and metrics in the Portal (Log stream, Metrics, Log Analytics queries).
- **App metrics:** If the app exposes Prometheus `/metrics`, optionally scrape via Azure Monitor agent or push to a custom workspace; or keep Prometheus/Grafana on a VM/AKS and use existing `scripts/metrics_server.py`.
- **Alerts:** Define an alert rule (e.g. failed health check or high 5xx rate) in Azure Monitor; send to email or a webhook.
- **Hands-on:** Deploy app → open Log Analytics → run a KQL query on container logs; create one alert rule.

### 3.7 Identity and access (Azure AD / Entra)

- **GitHub Actions:** Use OIDC federated credential (recommended) or a service principal with a secret to authenticate to Azure (ACR push, deploy to Container Apps or AKS). Restrict role assignments (e.g. ACR push, Contributor on one resource group).
- **Managed identity:** Assign a system- or user-assigned managed identity to the Container App (or AKS workload); grant that identity access to Key Vault and optionally ACR so no keys are stored in env.

---

## 4. Implementation order (suggested)

1. **Subscription and CLI:** Create/use subscription; install Azure CLI; create resource group and set default location.
2. **ACR:** Create ACR; build and push app image (local or CI); verify pull.
3. **Key Vault:** Create Key Vault; add secrets for app env vars; note access policy or RBAC for the identity that will run the app.
4. **Compute:** Deploy app to **Azure Container Apps** (or ACI): create Container App environment, create app from ACR image, set env and Key Vault references, configure ingress (HTTPS).
5. **Backing services:** Use existing Qdrant (e.g. cloud) or deploy Qdrant to ACI/VM; set `QDRANT_URL` (and key) in Key Vault and in app env.
6. **Health and smoke test:** Add `/health` (or similar) to the app; set Container App health probe; run a smoke test (curl or browser).
7. **CI/CD:** Add GitHub Actions workflow: build image → push to ACR → optionally deploy to Container Apps (e.g. `az containerapp update` or Bicep/ARM).
8. **Observability:** Enable Log Analytics for Container Apps; run a sample KQL query; add one alert rule.
9. **Optional:** Azure OpenAI resource + Key Vault secret; or AKS/VM path for full-stack on Azure.

---

## 5. Cost and quotas (awareness)

- **Free tier / credits:** Use free-tier limits where possible (e.g. ACR, Container Apps free grant); set budget alerts in Cost Management.
- **Quotas:** Check vCPU/memory quotas for Container Apps, ACI, or AKS in the chosen region; request increase if needed for staging.
- **Clean-up:** Document how to delete the resource group to tear down all resources and avoid ongoing cost.

---

## 6. Security checklist (to implement)

- [ ] All secrets in Key Vault; no secrets in code or in container image.
- [ ] Managed identity for app to read Key Vault (and optionally ACR); minimal RBAC (e.g. Key Vault Secrets User).
- [ ] GitHub Actions uses OIDC or a scoped service principal; no long-lived secrets in repo.
- [ ] Ingress over HTTPS only; optional WAF or rate limiting if the app is public.
- [ ] Network: restrict ACR and Key Vault to private endpoints or firewall rules if required by policy (optional for staging).

---

## 7. Success criteria (practical experience)

- **Portal and CLI:** Create and list resources (resource group, ACR, Key Vault, Container App) via Portal and `az` CLI.
- **Containers:** Build and push the RAG app image to ACR; run it in Container Apps (or ACI) with env from Key Vault.
- **End-to-end:** Open the app URL in a browser; perform a RAG query; confirm logs appear in Azure Monitor.
- **CI/CD:** Push to a branch triggers build and push to ACR; optionally deploy to staging Container App.
- **Documentation:** Short “Azure staging” section in DEPLOYMENT.md or a separate doc with steps (create RG, ACR, KV, Container App, and required secrets).

---

## 8. References (for implementation)

- Azure Container Apps: [Microsoft Learn – Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/)
- Azure Container Registry: [Microsoft Learn – ACR](https://learn.microsoft.com/en-us/azure/container-registry/)
- Key Vault: [Microsoft Learn – Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/)
- GitHub Actions + Azure: [Azure/login](https://github.com/Azure/login) and [Azure/container-apps-deploy-action](https://github.com/Azure/container-apps-deploy-action) (or equivalent).

---

*This plan is for planning only; no Azure resources are created and no code is run as part of this document.*
