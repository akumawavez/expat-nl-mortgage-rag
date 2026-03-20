# API development, integration, and API gateways: plan and documentation

This document is a **plan and documentation** only—no code is executed. It (1) explains **API development** and **API integration** concepts, (2) introduces **API gateways** and when they help, (3) summarizes what this project already does, and (4) gives a plan to strengthen API exposure and optional gateway use.

**Related docs:** [docs/API.md](docs/API.md) (lib and external APIs), [python_automation_api_plan.md](python_automation_api_plan.md) (Python API integration), [CODE_TODO.md](CODE_TODO.md) (REST API to-do).

---

## 1. Scope and objectives

| Objective | Description |
|-----------|-------------|
| **API development** | Designing and exposing APIs (e.g. REST) for your own services: contracts, versioning, auth, errors, and documentation. |
| **API integration** | Consuming external or internal APIs from your app: clients, auth, timeouts, retries, and error handling. |
| **API gateways (plus)** | Understanding what a gateway is, when to use one (routing, rate limiting, auth, observability), and how it could sit in front of this app or a future backend. |

---

## 2. API development: concepts

### 2.1 What we mean by “API”

- **Application Programming Interface:** A defined way for one system to call another. For web apps this is usually **REST** (HTTP, JSON, resource-oriented URLs) or **GraphQL**. This doc focuses on REST.
- **Contract:** The API contract is the set of endpoints, request/response shapes, status codes, and error format. It should be stable and documented so clients can rely on it.

### 2.2 REST API design (concepts)

- **Resources and URLs:** Use nouns and HTTP methods: e.g. `GET /documents`, `POST /chat`, `GET /health`. Version in URL (`/v1/chat`) or header if you expect breaking changes.
- **HTTP methods:** GET (read), POST (create or action), PUT/PATCH (update), DELETE. Use the right method and status codes (200, 201, 400, 401, 404, 500).
- **Request/response:** JSON body for POST; JSON response with consistent shape (e.g. `{ "data": ..., "error": null }` or `{ "answer": ..., "sources": [...] }`). Include `Content-Type: application/json`.
- **Errors:** Return appropriate status code and a body with a clear message or code (e.g. `{ "error": "invalid_query", "message": "..." }`). Avoid leaking internal details in production.
- **Idempotency and safety:** GET should be safe and idempotent; POST for non-idempotent actions. Document which endpoints are idempotent if it matters for retries.

### 2.3 Authentication and authorization

- **Auth:** Who is calling? Common options: API key (header or query), Bearer token (OAuth2/JWT), or mutual TLS. Keys and tokens should not appear in logs or docs.
- **Authorization:** What can they do? Role- or scope-based (e.g. read-only vs write). Enforce at the API layer or at a gateway.
- **This project:** Today the Streamlit app has no API auth (it’s a single-user UI). A future REST backend for “chat turn” would need a defined auth strategy (e.g. API key for internal clients, JWT for frontend).

### 2.4 Documentation and discoverability

- **OpenAPI (Swagger):** Machine-readable spec (YAML/JSON) describing endpoints, request/response schemas, and auth. Tools generate docs and client stubs.
- **Human docs:** A short “API” section in the repo (e.g. docs/API.md) listing endpoints, env vars, and example requests. For a new REST API, add an OpenAPI spec and link to it.

### 2.5 Versioning and compatibility

- **Versioning:** URL path (`/v1/chat`) or header (`Accept-Version: 1`). When you make breaking changes, introduce a new version and deprecate the old one with a timeline.
- **Compatibility:** Add new optional fields rather than removing or renaming existing ones when possible.

---

## 3. API integration: concepts

### 3.1 Consuming external APIs

- **Client:** Use a stable HTTP client (e.g. `requests`, `httpx`) with timeouts and retries. Same patterns as in [python_automation_api_plan.md](python_automation_api_plan.md): base URL and keys from env, no secrets in code.
- **Contract:** Rely on the provider’s docs (and optionally your own response models) so you handle all expected status codes and response shapes. Handle rate limits (429) and server errors (5xx) with backoff or clear errors to the user.
- **Idempotency:** For retries, prefer idempotent operations (GET, or POST with idempotency key if the provider supports it).

### 3.2 Integration styles in this project

- **SDK:** OpenAI/OpenRouter via official client (lib/provider.py); configuration via env.
- **REST (sync):** Nominatim, Overpass, OSRM (lib/location.py); Ollama `/api/chat`, `/api/tags` (app); Tavily (app). All use env for URL and keys; timeouts and error handling as documented in python_automation_api_plan.md.
- **Database/driver:** Qdrant (client library), Neo4j (Bolt). Same idea: config from env, no secrets in code.

---

## 4. API gateways: concepts (exposure is a plus)

### 4.1 What is an API gateway?

- **Definition:** A component that sits **in front** of one or more backend services and acts as a single entry point for API traffic. The client calls the gateway; the gateway routes the request to the appropriate backend (e.g. by path, host, or rule).
- **Typical responsibilities:**
  - **Routing:** Map path or host to backend (e.g. `/api/*` → FastAPI app, `/metrics` → metrics server).
  - **Authentication / authorization:** Validate API keys or JWT at the gateway; reject unauthorized requests before they reach the backend.
  - **Rate limiting:** Throttle by API key, IP, or user to protect backends and enforce quotas.
  - **Caching:** Cache GET responses to reduce load on the backend (e.g. for read-heavy endpoints).
  - **TLS termination:** Gateway handles HTTPS; traffic to backends can be HTTP on an internal network.
  - **Observability:** Centralized logging, metrics, and tracing at the gateway (request count, latency, status codes per route).
  - **Transformation:** Optional request/response rewriting (e.g. add headers, aggregate responses).

### 4.2 When to use a gateway

- **Multiple backends:** One public hostname, multiple services (e.g. Streamlit on one port, FastAPI on another, metrics on another). Gateway routes by path.
- **Production:** You want auth, rate limiting, and TLS in one place instead of reimplementing in every service.
- **Consistency:** Same rate limits, auth, and logging for all API traffic.

### 4.3 Examples of gateways

- **Cloud / managed:** Azure API Management, AWS API Gateway, Google API Gateway. Configure routes, keys, and quotas in the portal or IaC.
- **Self-hosted / OSS:** Kong, Traefik, NGINX (as reverse proxy with rate limiting and auth modules), Envoy. Run in front of your app in Docker or Kubernetes.
- **Minimal:** A reverse proxy (e.g. NGINX or Caddy) with basic routing and TLS is already a simple “gateway”; add rate limiting and auth modules or a separate gateway for full features.

### 4.4 How this project could use a gateway

- **Today:** The app is Streamlit (no REST API for chat). The only HTTP “API” is the metrics server (`/metrics`, `/health`). A gateway could sit in front of both: route `/` to Streamlit and `/metrics` to the metrics server, add TLS and optional rate limiting.
- **After adding a REST backend (see plan below):** Expose a FastAPI (or similar) service for “chat turn” (query → answer + sources). The gateway would: route `/api/*` to FastAPI, optionally `/` to Streamlit, apply API key or JWT auth and rate limits for `/api`, and terminate TLS. This demonstrates “exposure to API gateways” without requiring a specific product—document the pattern and, if desired, one example (e.g. NGINX or Azure API Management).

---

## 5. Current state in this repository

| Area | Status |
|------|--------|
| **API development (exposing)** | No REST API for the main RAG/chat flow. Streamlit is UI-only. **scripts/metrics_server.py** exposes **GET /metrics** (Prometheus) and **GET /health** (FastAPI) when FastAPI is installed. |
| **API documentation** | **docs/API.md** documents Python lib APIs (retrieval, provider, documents, agents, location, graph) and external services; notes that no REST API is exposed by the app (see CODE_TODO). |
| **API integration (consuming)** | Strong: OpenAI/OpenRouter (provider), Nominatim/Overpass/OSRM (location), Ollama (app), Tavily (app), Qdrant, Neo4j. All env-based; timeouts and error handling in place. See python_automation_api_plan.md. |
| **API gateway** | Not used. deploy_plans and PRODUCTION_MLOPS_AIOPS mention “rate limiting at reverse proxy or gateway”; no gateway config or doc in the repo. |

---

## 6. Plan to strengthen API development and gateway exposure (no code run)

### 6.1 Optional REST API for RAG (backend)

- **Goal:** Allow non-Streamlit clients (e.g. mobile, another service, or tests) to call the RAG pipeline with a single “chat turn” endpoint.
- **Design (to implement later):** Add a small FastAPI app (e.g. `backend/api.py` or under `scripts/`) with at least:
  - **POST /v1/chat** (or **POST /chat**): Body `{ "query": "...", "options": { "use_hybrid": true, "top_k": 10 } }`. Runs retrieval (vector or hybrid), optional web search, then LLM; returns `{ "answer": "...", "sources": [...], "tools_used": [...] }`. Reuse logic from app.py (import from lib).
  - **GET /health**: Liveness/readiness (and optionally check Qdrant reachability).
  - **GET /metrics**: Optional; or keep metrics in the existing metrics_server and have the backend only implement business endpoints.
- **Auth:** Plan for API key in header (e.g. `X-API-Key`) or Bearer token; validate in a FastAPI dependency. No implementation in this plan; document the choice.
- **Docs:** OpenAPI (FastAPI generates it); link from docs/API.md. Document in this file that the REST API is the “API development” artifact and that the gateway can sit in front of it.

### 6.2 Consolidate and document integration patterns

- **docs/API.md:** Add a short “Integration patterns” subsection: how the app integrates with each external API (SDK vs REST, env vars, timeouts, retries). Point to python_automation_api_plan.md for Python-level details.
- **External APIs table:** Keep the table in API.md (Qdrant, OpenAI, Nominatim, etc.); add a column “Auth” (e.g. API key, none) and “Timeout (if any)” for quick reference.

### 6.3 API gateway: document the pattern and one option

- **In this file:** Keep §4 as the “API gateway concepts” reference. Add a “Gateway option for this project” subsection:
  - **Placement:** Gateway in front of (1) Streamlit app, (2) optional FastAPI backend, (3) metrics server. Single hostname; routes e.g. `/` → Streamlit, `/api` → FastAPI, `/metrics` → metrics (or restrict `/metrics` to internal only).
  - **Features to use:** TLS termination, routing, optional API key or JWT for `/api`, rate limiting per key or IP. Logging and metrics at the gateway for observability.
  - **Example (choose one when implementing):** (A) **NGINX:** config snippet for reverse proxy + optional rate_limit and auth; or (B) **Azure API Management:** link to Azure docs and note “create API with operations for /chat, set backend to FastAPI URL, add subscription key or JWT.”
- **deploy_plans.md / DEPLOYMENT.md:** Add one sentence: “For production, place an API gateway (or reverse proxy with rate limiting) in front of the app and optional REST API; see api_development_and_integration_plan.md.”

### 6.4 Implementation order (suggested)

1. **Documentation:** Finalize this file; add “Gateway option for this project” and “Integration patterns” to docs/API.md.
2. **REST API (optional):** Implement FastAPI with POST /chat and GET /health; document in API.md and add OpenAPI link; add auth plan (e.g. X-API-Key).
3. **Gateway (optional):** Add a minimal NGINX (or similar) config example in a `deploy/` or `docs/` file, or document “use Azure API Management with backend URL = FastAPI”; reference from this file and deploy_plans.

---

## 7. Experience demonstrated (summary)

| Area | How it is shown |
|------|------------------|
| **API development** | Design of a REST contract (POST /chat, GET /health); use of FastAPI for /metrics and /health today; plan for a full chat API with versioning and auth. |
| **API integration** | Multiple external APIs consumed (OpenAI, OpenRouter, Nominatim, Overpass, OSRM, Ollama, Tavily, Qdrant, Neo4j) with env-based config, timeouts, and error handling; documented in API.md and python_automation_api_plan. |
| **API documentation** | docs/API.md for lib and external services; plan for OpenAPI for any new REST API. |
| **API gateways (plus)** | Understanding of gateway role (routing, auth, rate limit, TLS, observability); when to use one; and how this project would place a gateway in front of the app and optional backend; optional example (NGINX or Azure API Management). |

---

## 8. References

- [FastAPI](https://fastapi.tiangolo.com/) – OpenAPI, async, type hints.
- [REST API design](https://restfulapi.net/) – Resources, methods, status codes.
- [Azure API Management](https://learn.microsoft.com/en-us/azure/api-management/) – Managed gateway, policies, developer portal.
- [Kong](https://docs.konghq.com/) – Open-source API gateway.
- [NGINX reverse proxy and rate limiting](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html) – Simple gateway-like setup.

---

*This document is a plan and documentation only; no code has been run or modified as part of this file.*
