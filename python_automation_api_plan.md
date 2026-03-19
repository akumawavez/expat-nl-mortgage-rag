# Python for automation and API integration: plan and documentation

This document is a **plan and documentation** only—no code is executed. It (1) defines what “proficiency in Python for automation and API integration” means in the context of this project, (2) maps existing project artifacts to those competencies, and (3) suggests concrete steps to strengthen or demonstrate them.

**Related docs:** [docs/API.md](docs/API.md) (API and tools reference), [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) (errors and debugging).

---

## 1. Scope and objectives

| Competency | Description |
|------------|-------------|
| **Automation** | Scripts and tooling that run without interactive input: ingestion, tests, metrics, CI. Use of CLI args, env config, logging, error handling, and (where relevant) idempotency and scheduling. |
| **API integration** | Consuming external and internal APIs from Python: REST clients, auth, timeouts, retries, response parsing, and consistent error handling. |

**Goal:** Have a clear plan and documentation that shows where the project already demonstrates these skills and what to add or refine to show proficiency (e.g. in a portfolio or interview).

---

## 2. Automation: what counts as proficiency

### 2.1 Script design and execution

- **CLI interface:** Scripts accept arguments (e.g. `argparse`) for different modes (e.g. `--semantic`, `--no-replace`) so the same script can be used in dev, CI, and scheduled jobs.
- **Environment-based config:** No hardcoded URLs or keys; use `os.environ` and a single `.env.example` so the same script runs in different environments.
- **Project root and imports:** Scripts resolve project root (e.g. from `__file__`), set `sys.path` if needed, load `.env`, and use shared `lib` modules so they are runnable from repo root.
- **Exit codes and output:** Scripts exit with 0 on success and non-zero on failure; CI and schedulers can rely on this. Optional: structured output (e.g. JSON summary) for downstream automation.

### 2.2 Reliability and operations

- **Error handling:** Catch expected failures (missing env, network errors, API errors), log or print clear messages, and exit with a non-zero code. Avoid silent failures.
- **Logging:** Use `logging` (or consistent `print` with levels) so that when run in CI or as a job, logs can be captured and searched.
- **Idempotency:** Where possible (e.g. ingestion with `--no-replace`), running the script multiple times produces a well-defined state without unintended duplication or corruption.
- **Scheduling and CI:** Scripts are suitable for cron, Azure Functions, or GitHub Actions (e.g. ingest on schedule, tests on push). Document the exact command and env vars.

### 2.3 Automation artifacts in this project (evidence)

| Artifact | Automation aspect | Proficiency demonstrated |
|----------|-------------------|---------------------------|
| `scripts/ingest_docs.py` | CLI (`argparse`: `--semantic`, `--no-replace`), env (Qdrant, chunking, embedding model), project root + dotenv, shared `lib.chunking` / `lib.provider` | Configurable, reusable ingestion; ready for CI or scheduled run. |
| `scripts/test_ingestion.py` | Env-based Qdrant URL/collection; exit code and printed result (PASS/FAIL); can be run in CI | Validation script suitable for automation. |
| `scripts/test_phase2.py` | Env for Neo4j; checks Phase 2 dependencies | Environment-parity and dependency checks. |
| `scripts/run_ragas.py` | Loads golden set, runs eval pipeline; can be extended for CI regression | Offline evaluation as an automated step. |
| `scripts/metrics_server.py` | Exposes `/metrics` and `/health`; env for port; can be run as a sidecar or daemon | Operational automation (observability). |
| `.github/workflows/ci.yml` | Runs lint and tests on push/PR; env for Qdrant (test defaults); install from `requirements.txt` | CI automation; Python in a pipeline. |

---

## 3. API integration: what counts as proficiency

### 3.1 Client design and usage

- **HTTP clients:** Use a single, consistent client where possible (e.g. `requests` for sync, or `httpx`). Use `urllib.request` only where no dependency is desired; document the choice.
- **Base URL and config:** Base URLs and API keys come from env (or a config module that reads env); no URLs or keys in source.
- **Timeouts:** Every outbound HTTP call has a timeout to avoid hanging in automation or under load.
- **Retries:** For transient failures (e.g. 429, 5xx, connection errors), use retries with backoff (or document that a specific integration does not retry and why).
- **Response handling:** Parse JSON safely; handle non-2xx and empty or malformed responses; map to clear exceptions or return types.

### 3.2 Auth and security

- **Secrets:** API keys and tokens from env or a secret store; never logged or committed.
- **Headers:** Set `User-Agent` where required by policy (e.g. Nominatim); use auth headers (e.g. `Authorization: Bearer ...`) from env.

### 3.3 Typing and structure

- **Types:** Use type hints for function args and returns (e.g. `list[dict]`, `tuple[float, float] | None`); optional: Pydantic or dataclasses for request/response DTOs.
- **Contracts:** Document expected request/response shape for key integrations (or point to official API docs) so changes are easier to track.

### 3.4 API integration artifacts in this project (evidence)

| Artifact | APIs used | Proficiency demonstrated |
|----------|-----------|---------------------------|
| `lib/provider.py` | OpenAI-compatible (OpenAI, OpenRouter); env for base URL and API key; returns typed client | Multi-provider LLM/embedding integration; config from env; no hardcoded keys. |
| `lib/location.py` | **Nominatim** (geocoding): `urllib.request`, GET, User-Agent, timeout 10s, JSON parse. **Overpass** (POIs): POST with form-encoded body, timeout 25s. **OSRM** (routing): GET, timeout 15s, structured response parsing. | Multiple REST APIs; configurable base URLs; timeouts; error handling (try/except); typed helpers. |
| `app.py` / `app_UploadPDF_Chat.py` / `app_wRAG.py` | **Ollama** (local): `requests.post` for `/api/chat`, stream handling, timeout; `requests.get` for `/api/tags`. **Tavily** (search): API key from env, structured results. | Sync REST with streaming; error extraction from response body; env-based keys. |
| Qdrant client (in `lib/retrieval.py`, `scripts/ingest_docs.py`) | Qdrant gRPC/REST via official SDK; URL and optional API key from env | Use of SDK as “API integration”; env-based config. |
| Neo4j (Phase 2) | Bolt driver; URI, user, password from env | Database driver as API; credentials from env. |

---

## 4. Gaps and improvement plan (no code run)

### 4.1 Automation

| Gap | Plan (to implement later) |
|-----|---------------------------|
| **Structured logging** | Replace or wrap key `print` calls in `scripts/ingest_docs.py` and test scripts with `logging`; use a single format (e.g. `%(levelname)s %(message)s`) and optional JSON for log aggregators. |
| **Exit codes** | Ensure all scripts explicitly `sys.exit(0)` or `sys.exit(1)` (or equivalent) so CI and schedulers can detect failure. |
| **Scheduled run** | Document one recommended way to run ingestion on a schedule (e.g. cron, Azure Functions, or GitHub Actions scheduled workflow) with required env vars. |
| **Idempotency** | Document that `ingest_docs.py` with default (full replace) is idempotent, and that `--no-replace` is additive; add a short comment in script docstring. |
| **CI env** | Add to CI (or docs) the exact env vars needed for tests that hit real services (if any); keep unit tests mock-based or using test doubles so CI stays fast and free of secrets. |

### 4.2 API integration

| Gap | Plan (to implement later) |
|-----|---------------------------|
| **Unified HTTP client** | Consider standardizing on `requests` (or `httpx`) for all REST calls; replace `urllib.request` in `lib/location.py` with the chosen client for consistency, timeouts, and easier retries. |
| **Retries** | Add retry logic (e.g. `tenacity` or `urllib3.Retry`) for idempotent GET/POST to external APIs (Nominatim, Overpass, OSRM, LLM) with exponential backoff and max attempts; document in API.md. |
| **Response models** | For critical integrations (e.g. Tavily, OSRM), introduce small Pydantic models or dataclasses for the response shape to validate and document the contract. |
| **Centralized error handling** | Introduce a small helper (e.g. `lib/http_client.py`) that wraps common behavior: timeout, retries, JSON decode, and raising a custom exception (e.g. `APIError`) with status code and message; use it from location, provider, and app code. |
| **API docs** | In docs/API.md, add a short “External APIs” subsection: service, purpose, env vars, timeout/retry policy, and link to official docs. |

### 4.3 Documentation to add or update

- **This file:** Keep as the single “automation and API integration” plan and evidence doc; link to it from README or docs/EXECUTION_SUMMARY.md.
- **docs/API.md:** Add “External APIs” (see above); add one sentence per script in “Scripts” section on how it is intended for automation (CLI, env, exit code).
- **README or QUICKSTART:** Under “Running scripts”, state that scripts expect to be run from project root and that required env vars are in `.env.example`.

---

## 5. Implementation order (suggested)

1. **Documentation only:** Update docs/API.md with External APIs and script-automation notes; add “Automation and API integration” section to README pointing to this file.
2. **Automation:** Add `logging` to at least one script (e.g. `ingest_docs.py`); ensure all scripts use explicit exit codes; document scheduled ingestion in deploy_plans.md or DEPLOYMENT.md.
3. **API integration:** Add a single `lib/http_client.py` (or equivalent) with timeout and optional retries; use it in one integration (e.g. `lib/location.py`) as a pilot; then extend to others and document in API.md.
4. **Optional:** Add Pydantic models for one external API response (e.g. OSRM or Tavily); add retries with backoff for at least one LLM or search API.

---

## 6. How to demonstrate proficiency (portfolio / interview)

- **Automation:** “We have ingestion and test scripts that take CLI args and env config; they’re used in CI and are designed for scheduled runs. Here’s the workflow and the script docstrings.”
- **API integration:** “We integrate several REST APIs (Nominatim, Overpass, OSRM, OpenAI-compatible, Tavily); all use env-based config, timeouts, and consistent error handling. Provider module supports multiple LLM backends. Here’s API.md and the relevant lib modules.”
- **Evidence:** Use this document and the “Evidence” tables in §2 and §3 as a checklist; point to specific files and functions (e.g. `lib/location.py` for geocoding and routing, `scripts/ingest_docs.py` for automation).

---

## 7. Summary

| Area | Current state | Plan |
|------|----------------|------|
| **Automation** | Scripts with CLI and env; CI workflow; metrics server | Add logging and explicit exit codes; document scheduling; document idempotency. |
| **API integration** | Multiple REST and SDK integrations; env-based config; timeouts in place | Unify HTTP client; add retries; optional response models; document in API.md. |
| **Documentation** | API.md and TROUBLESHOOTING exist | Add External APIs and automation notes; link this plan from README. |

---

*This document is for planning and documentation only; no code has been run or modified as part of this file.*
