# Docker containerization: plan and documentation

This document is a **plan and documentation** only—no code is executed. It (1) explains **containerization concepts** relevant to this project, (2) summarizes the **current state** of Docker usage in the repo, and (3) gives a **concrete plan** to add a Dockerfile and Docker Compose so the app and its dependencies can run in containers.

**Related docs:** [deploy_plans.md](deploy_plans.md) (dev/staging deployment), [DEPLOYMENT.md](DEPLOYMENT.md) (quick run, platforms), [azure_platform_plan.md](azure_platform_plan.md) (ACR, Container Apps).

---

## 1. Scope and objectives

| Objective | Description |
|-----------|-------------|
| **Concepts** | Document what containerization with Docker means for this app: images, Dockerfile, Compose, env, volumes, networking. |
| **Current state** | Record what exists today (Qdrant via `docker run`; no app image or compose). |
| **Plan** | Define how to add a Dockerfile and docker-compose so the RAG app and backing services run in containers for dev and as a base for staging/production. |

---

## 2. Containerization concepts (Docker)

### 2.1 Why containerize?

- **Reproducibility:** The same image runs the same way on any host (dev laptop, CI, cloud). No “works on my machine” from differing Python versions or system libs.
- **Isolation:** App and dependencies run in a container; the host stays clean. Multiple services (app, Qdrant, Neo4j) can run in separate containers and be composed together.
- **Deployment:** Images can be pushed to a registry (Docker Hub, GitHub Container Registry, Azure ACR) and pulled on staging or production; orchestration (e.g. Kubernetes, Azure Container Apps) runs containers from those images.

### 2.2 Core concepts

- **Image:** A read-only snapshot of filesystem + metadata (entrypoint, env defaults, etc.). Built from a **Dockerfile** (or from another image). Identified by name and tag (e.g. `expat-rag:latest`, `expat-rag:staging-abc123`).
- **Container:** A runnable instance of an image. Has its own filesystem, network, and process space; it can be started, stopped, and removed.
- **Dockerfile:** Recipe to build an image: base image (e.g. `python:3.11-slim`), install deps, copy app code, set working directory and command. Each instruction adds a layer; order matters for cache and image size.
- **Docker Compose:** Defines a **stack** of services (e.g. app, Qdrant, Neo4j) in a YAML file. Each service has an image (or build context), env, ports, volumes, and dependencies. One command (`docker compose up`) starts the whole stack with correct networking so containers can reach each other by service name.

### 2.3 Environment and secrets

- **Environment variables:** Containers receive env vars from the Compose file (`environment` or `env_file`), from the host, or from a secret store at runtime. The app already reads config from env (see `.env.example`); the same vars should be passed into the container. **Never** bake secrets into the image (no `.env` or API keys in the Dockerfile or in committed files).
- **env_file:** Compose can point to `.env` (or a staging env file) so all vars are injected; `.env` should be in `.gitignore` and not committed.

### 2.4 Volumes and persistence

- **Volume:** A named or host-mounted store that outlives the container. Use a volume for Qdrant data so that restarting the Qdrant container does not lose the vector index. Example: `qdrant_data` volume mapped to Qdrant’s data path.
- **Bind mount (dev):** Optionally mount the source code into the container so code changes are reflected without rebuilding; useful for fast iteration. Production images typically copy code at build time (no bind mount).

### 2.5 Networking

- **Compose default network:** All services in the same Compose file join a default network and can reach each other by **service name** (e.g. `qdrant` → `http://qdrant:6333`). So from the app container, `QDRANT_URL=http://qdrant:6333` is correct; from the host browser, the app is reached via `localhost:8501` (published port).

### 2.6 Build and run lifecycle

- **Build:** `docker build -t expat-rag:latest .` (or `docker compose build`) produces the app image from the Dockerfile. Use `.dockerignore` to exclude `.git`, `venv`, `__pycache__`, `.env`, and large or irrelevant files so the build context is small and secure.
- **Run:** `docker run ...` or `docker compose up`. The app container’s command is typically `streamlit run app.py --server.port 8501 --server.address 0.0.0.0` so Streamlit listens on all interfaces inside the container and the published port is reachable from the host.
- **One-off jobs:** Ingest is not part of the long-running app; run it as a one-off: `docker compose run --rm app python scripts/ingest_docs.py` (or from the host with `QDRANT_URL=http://localhost:6333` after the stack is up).

---

## 3. Current state in this repository

| Item | Status |
|------|--------|
| **Dockerfile** | Not present. deploy_plans.md describes what to add; no file exists. |
| **docker-compose.yml** | Not present. |
| **.dockerignore** | Not present. |
| **Qdrant** | Documented as “run via Docker”: `docker run -p 6333:6333 qdrant/qdrant`. No compose service; no volume for persistence in the docs. |
| **App** | Run locally with `streamlit run app.py` after `pip install -r requirements.txt`; no container image. |
| **Neo4j** | Optional; mentioned in DEPLOYMENT.md and deploy_plans; no Compose service yet. |

So today: **only Qdrant is run in Docker** (ad hoc); the app and optional Neo4j are not containerized in this repo. Experience with containerization is therefore **partial**—adding a Dockerfile and Compose would complete a clear “containerized dev/staging” story.

---

## 4. Plan to add Docker support (no code run)

### 4.1 Dockerfile for the app

- **Base image:** Use `python:3.11-slim` (or similar) so the Python version matches CI and docs.
- **Working directory:** Set `WORKDIR /app` (or `/src`); copy only what’s needed: `requirements.txt`, `app.py`, `lib/`, `scripts/`, `monitoring/`, and any data or config that must be in the image (e.g. default docs path if used). Do **not** copy `.env`, `venv`, or secrets.
- **Install dependencies:** `RUN pip install --no-cache-dir -r requirements.txt` to keep the layer small and reproducible.
- **Expose port:** `EXPOSE 8501` (Streamlit).
- **Default command:** `CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]` so the app listens inside the container and the port can be published to the host.
- **User (optional):** Run as non-root (e.g. add a user and `USER`) for better security; can be added in a later iteration.
- **Multi-stage (optional):** If needed, use a builder stage to compile or prepare assets, then copy only the runtime artifacts into the final image; for a Python-only app, a single stage is often enough.

### 4.2 .dockerignore

- **Add a `.dockerignore`** so that the build context sent to the daemon excludes:
  - `.git`, `.venv`, `venv`, `__pycache__`, `*.pyc`, `.env`, `.pytest_cache`, `*.egg-info`
  - Large or unnecessary files: e.g. `*.pdf` under `data/` if not needed in the image, `final_presentation.pdf`, `code_critique.pdf`
  - Test outputs, IDE config (e.g. `.vscode`) if not needed at runtime
- This speeds up build and avoids accidentally including secrets or huge files.

### 4.3 docker-compose.yml (or docker-compose.dev.yml)

- **Services to define:**
  - **app:** Build from the Dockerfile (context `.`, dockerfile `Dockerfile`). Ports: `8501:8501`. env_file: `.env`. environment: override `QDRANT_URL=http://qdrant:6333` (and optional `NEO4J_URI` if Neo4j service is present). depends_on: qdrant (and optionally neo4j). Restart policy: optional (e.g. `unless-stopped` for dev).
  - **qdrant:** Image `qdrant/qdrant`. Ports: `6333:6333`. Volumes: a named volume (e.g. `qdrant_data:/qdrant/storage`) for persistence. Optional restart policy.
  - **neo4j** (optional): Image `neo4j`. Ports: `7474:7474`, `7687:7687`. Environment: `NEO4J_AUTH=neo4j/<password>`. Volume for data. Only include if Phase 2 is in use.
- **Networking:** Use the default Compose network; no extra config needed for service-name resolution.
- **Note:** If `.env` is not present, Compose will still start but the app may fail without QDRANT_URL and API keys; document “copy `.env.example` to `.env` and set values” in this file and in README.

### 4.4 First-time setup and ingest

- **First run:** User runs `docker compose up --build`. Qdrant starts; app starts but may have no data in the collection.
- **Ingest:** Either (1) run from host: ensure Qdrant is reachable at `localhost:6333`, then `python scripts/ingest_docs.py` (with venv and `.env`), or (2) run inside the app container: `docker compose run --rm app python scripts/ingest_docs.py` with `QDRANT_URL=http://qdrant:6333` (already set via compose env). Document both options.
- **Persistence:** After first ingest, data lives in the Qdrant volume; next `docker compose up` reuses it so ingest is not required every time.

### 4.5 Documentation updates (plan)

- **This file:** Keep as the single “Docker plan and concepts” doc; add a short “Quick start with Docker” subsection that lists: copy `.env.example` → `.env`, `docker compose up --build`, run ingest (one of the two ways), open `http://localhost:8501`.
- **README.md:** Add a “Run with Docker” bullet: link to this file and/or DEPLOYMENT.md; one-liner: “With Docker: see docker_containerization_plan.md; run `docker compose up --build` and then ingest.”
- **DEPLOYMENT.md:** Add a “Docker Compose (local)” subsection: same quick steps; note that for production/staging the image can be built and pushed to a registry (see deploy_plans.md, azure_platform_plan.md).
- **.gitignore:** Ensure `.env` is ignored (already is); if any local Compose override or secret file is used, ignore it.

### 4.6 Optional: CI build and push

- **Plan (when implementing):** In GitHub Actions, on push to `main` (or a `staging` branch), build the image, tag with git SHA or `latest`, push to a registry (Docker Hub, GHCR, or ACR). Use secrets for registry login; do not store secrets in the image. See deploy_plans.md and azure_platform_plan.md for ACR and Container Apps.

---

## 5. Implementation order (suggested)

1. **Documentation:** Finalize this plan; add “Quick start with Docker” subsection below.
2. **.dockerignore:** Add file listing exclusions (see §4.2).
3. **Dockerfile:** Add at repo root (see §4.1); verify build locally (`docker build -t expat-rag:test .`).
4. **docker-compose.yml:** Add with app and qdrant services; optional neo4j; document env and volume.
5. **Test:** Run `docker compose up --build`; run ingest (from host or via `docker compose run`); open app in browser and run a RAG query.
6. **Docs:** Update README and DEPLOYMENT.md with Docker instructions and link to this file.
7. **Optional:** CI build/push; staging deploy using the same image (see deploy_plans.md).

---

## 6. Quick start with Docker (after implementation)

*(To be valid once Dockerfile and docker-compose.yml exist.)*

1. Copy `.env.example` to `.env` and set at least `QDRANT_URL` (will be overridden by Compose to `http://qdrant:6333` for the app container), `QDRANT_COLLECTION`, and LLM/embedding API keys.
2. From the project root: `docker compose up --build`.
3. In another terminal (or once the stack is up), run ingest:
   - From host (with venv): `python scripts/ingest_docs.py` (use `QDRANT_URL=http://localhost:6333` in `.env` for this run), or
   - In app container: `docker compose run --rm app python scripts/ingest_docs.py`.
4. Open `http://localhost:8501` in the browser and use the RAG chat.

To stop: `docker compose down`. Data in the Qdrant volume persists; to remove it: `docker compose down -v`.

---

## 7. Experience demonstrated (summary)

| Area | How it is shown |
|------|------------------|
| **Dockerfile** | Writing a Dockerfile that builds a reproducible Python/Streamlit image with correct working dir, deps, and command. |
| **.dockerignore** | Reducing build context and avoiding secrets/large files. |
| **Docker Compose** | Defining a multi-service stack (app + Qdrant [+ optional Neo4j]), env, ports, volumes, and service discovery. |
| **Env and secrets** | Config via env_file and environment; no secrets in the image. |
| **Persistence** | Named volume for Qdrant so data survives container restarts. |
| **One-off jobs** | Ingest as a separate run (compose run) or from host against exposed port. |
| **Docs** | Clear plan and quick start so others can run the stack with Docker. |

---

## 8. References

- [Dockerfile reference](https://docs.docker.com/engine/reference/builder/)
- [Docker Compose file reference](https://docs.docker.com/compose/compose-file/)
- [Streamlit in Docker](https://docs.streamlit.io/knowledge-base/tutorials/deploy/docker) (official guidance)

---

*This document is a plan and documentation only; no code or Docker commands have been executed as part of this file.*
