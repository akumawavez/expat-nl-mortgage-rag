# Expat NL Mortgage RAG – Four-Phase Implementation Plan and Completion Tests

This document defines the **four-phase implementation plan** and **concrete tests** (with commands and success criteria) to prove each phase is completed. Each phase delivers a shippable increment. The more complex items (multi-agent, A2A, A2UI, MCP, continuous drift monitoring) are scheduled for later phases.

---

## Overview

| Phase | Name | Summary |
|-------|------|---------|
| **1** | Foundation (MVP) | Single app entry point, RAG + citations, web search toggle, hybrid search + RRF, mortgage calculator, observability tab, tests, CI/CD, deployment. |
| **2** | Location & property intelligence | Map-based nearby search (Nominatim/Overpass), OSRM enrichment, safety (CBS), Knowledge Graph tab (PyVis), optional A2UI (calculator/map directives). |
| **3** | Advanced UX & continuous monitoring | Sun-orientation SVG, retrieval/response quality & drift (RAGAS/Langfuse), RAG evals pipeline, Prometheus + Grafana. |
| **4** | Multi-agent, A2A, A2UI, MCP | Specialist agents + orchestrator (A2A), full A2UI schema & renderer, MCP servers for tools, optional eval smoke in CI. |

### Quick test reference

| Phase | Key tests / proof |
|-------|-------------------|
| **1** | `python scripts/ingest_docs.py` → `python scripts/test_ingestion.py` (RESULT: PASS). Single app `streamlit run app.py`: chat, citations, web search toggle, hybrid retrieval, mortgage calculator tab, observability tab. `pytest` and CI workflow pass. `DEPLOYMENT.md` and `.env.example` exist. |
| **2** | `python scripts/test_phase2.py --check-neo4j`. App: nearby_places (map), OSRM commute/proximity, area_safety, KG tab (PyVis). Optional: agent “show calculator” / “show map” renders widgets. |
| **3** | Sun-orientation widget in app. Observability: “Retrieval quality”, “Response quality”, “Drift indicators”. RAGAS evals run; Prometheus `/metrics` and Grafana dashboard documented. |
| **4** | Multi-agent routing (LangGraph/LangChain), A2UI directives (calculator, map, sun, citations, safety) rendered from agent output, MCP client + tools. Optional: RAGAS subset in CI. |

Details and success criteria for each phase are below.

---

## Phase 1 – Foundation (MVP, fast value)

**Outcome:** Single app with RAG, citations, web search toggle, hybrid retrieval, mortgage calculator, basic observability (tokens/cost), tests, and deployment docs.

### Scope (section refs)

- **Consolidate app to one entry point** (e.g. `app.py`) and **tool-usage visibility** in the chat (section 1).
- **Flexible LLM provider and model in sidebar**: sidebar shows **provider** (OpenAI, OpenRouter, Ollama) and **model** dropdown; only providers with API key or URL set in `.env` are shown; model list per provider comes from `.env` (e.g. `LLM_MODELS_OPENAI`, `LLM_MODELS_OPENROUTER`, `OLLAMA_MODELS`, comma-separated) or built-in defaults. Chat uses the selected provider and model.
- **Interactive citations** (section 4c): store and display sources per turn; expandable source panel and optional inline markers.
- **Web search toggle** (section 1b): sidebar toggle, Tavily tool when enabled, `TAVILY_API_KEY` in `.env.example`.
- **Hybrid search + RRF** (section 2): retrieval module, `hybrid_retrieve` tool.
- **Mortgage calculator** (section 4d): ING-style widget – bid, eigen inleg, type woning, energielabel dropdown (A++++ met EPG … G, geen label mogelijk/bekend), Bruto maandlasten, Hypotheek, Kosten koper; new tab or sidebar section.
- **Observability tab** (sections 4.1–4.5): Langfuse callback, token consumption and price estimation KPIs and charts, links to Langfuse.
- **Tests** (section 7): unit tests for retrieval, PDF, calculator; pytest + config.
- **CI/CD** (section 8): `.github/workflows/ci.yml` – lint and test.
- **Deployment** (section 6): `DEPLOYMENT.md`, `.env.example`, platform notes for Streamlit Cloud, HF Spaces, Render.

*(Existing foundation: ingestion `scripts/ingest_docs.py`, chunking `lib/chunking.py`, provider `lib/provider.py`, Qdrant + Phase 1 RAG chat and PDF upload – these remain and are part of Phase 1 evidence.)*

### Deliverables (evidence)

| Deliverable | Location / Evidence |
|-------------|----------------------|
| Single app entry point | `app.py` – one Streamlit app that includes chat, tools, calculator, observability |
| Provider/model in sidebar | Sidebar: Provider and Model selectboxes; options enabled from `.env` (only providers with keys/URL; model lists from `LLM_MODELS_*` / `OLLAMA_MODELS` or defaults) |
| Tool-usage visibility | In chat UI: which tools were used per turn (e.g. `hybrid_retrieve`, Tavily). See *Chat response format* below. |
| Interactive citations | Sources stored per turn; expandable source panel; optional inline markers in message. Citations must be clearly visible. See *Chat response format* below. |
| *Chat response format* | **Tools Used** block then **Assistant** reply; citations clearly shown (see example in Test 1.2). |
| Web search toggle | Sidebar toggle; when on, Tavily tool available; `TAVILY_API_KEY` in `.env.example` |
| Hybrid search + RRF | Retrieval module with `hybrid_retrieve` (vector + keyword/sparse, RRF merge) |
| Mortgage calculator | Tab or sidebar: bid, eigen inleg, type woning, energielabel (A++++ … G, geen label), Bruto maandlasten, Hypotheek, Kosten koper |
| Observability tab | Langfuse callback; token consumption & price KPIs/charts; link(s) to Langfuse |
| Unit tests | `tests/` – retrieval, PDF, calculator; `pytest` + `pytest.ini` or `pyproject.toml` |
| CI/CD | `.github/workflows/ci.yml` – lint (e.g. ruff/black) and `pytest` |
| Deployment docs | `DEPLOYMENT.md`; `.env.example` with all required vars; notes for Streamlit Cloud, HF Spaces, Render |
| Ingestion & RAG (existing) | `scripts/ingest_docs.py`, `lib/chunking.py`, `lib/provider.py`, `app_phase1.py` or merged into `app.py` |

### Prerequisites for Phase 1 tests

- Python env, `requirements.txt`, `.env` (Qdrant, LLM/embedding provider, optional Tavily, optional Langfuse).
- Qdrant running at `QDRANT_URL`.

### Phase 1 completion tests

Run from **project root**.

#### Test 1.1 – Ingestion and vector store

**Command:** `python scripts/ingest_docs.py` then `python scripts/test_ingestion.py`

**Success criteria:**

- Ingest: exit 0; output shows “Found N PDF(s).”, “Upserted M chunks.”, “Done. Total chunks in store: &lt;positive&gt;”.
- Test: exit 0; “OK – Qdrant is reachable.”, “OK – Collection 'property_docs' exists.”, “Points (chunks) = &lt;positive&gt;”, “RESULT: PASS”.

**Proves:** Ingestion pipeline and Qdrant retrieval are working.

---

#### Test 1.2 – Single app entry point and tool-usage visibility

**Command:** `streamlit run app.py`

**Success criteria:**

- App starts without import/config error.
- Chat is the main interface; after a question, response is shown.
- For each turn where tools are used, the UI shows **which tools were used** with a **Tools Used** block (e.g. `vector_search`, `tavily_search` with params) then **Assistant** reply; **citations** clearly shown (expandable sources; see Test 1.3). Example format:
  - **Tools Used:** 1. vector_search (query='...', limit=10)  2. tavily_search (query='...')  **Assistant:** &lt;response&gt;

**Proves:** One entry point (section 1) and tool-usage visibility (section 1).

---

#### Test 1.3 – Interactive citations

**Command:** Use the app; ask a RAG question.

**Success criteria:**

- **Sources are stored per turn** (e.g. document names or chunk IDs used for the answer).
- **Expandable source panel** (e.g. “Sources” expander or side panel) shows the sources for the current or selected turn.
- Optional: **inline markers** in the message (e.g. [1], [2]) linking to the source list.

**Proves:** Interactive citations (section 4c).

---

#### Test 1.4 – Web search toggle

**Command:** In app sidebar, enable “Web search” (or equivalent); ask a question that benefits from live web (e.g. “current 30-year mortgage rate Netherlands”).

**Success criteria:**

- Sidebar has a **toggle** for web search.
- When **enabled**, Tavily (or configured search) is invoked when appropriate; response can cite web results.
- `.env.example` includes `TAVILY_API_KEY=` (or equivalent) and deployment docs mention it.

**Proves:** Web search toggle (section 1b) and `.env.example` for Tavily.

---

#### Test 1.5 – Hybrid search + RRF

**Command:** Call or trigger retrieval (e.g. via chat) that uses hybrid search.

**Success criteria:**

- A **retrieval module** (or tool) implements **hybrid_retrieve**: combines vector search and keyword/sparse search and merges with **RRF** (Reciprocal Rank Fusion).
- Chat responses that use retrieval can be attributed to this hybrid path (e.g. via tool-usage visibility).

**Proves:** Hybrid search + RRF (section 2).

---

#### Test 1.6 – Mortgage calculator

**Command:** Open the mortgage calculator (tab or sidebar section).

**Success criteria:**

- **ING-style widget** with: bid (purchase price), eigen inleg (down payment), type woning, **energielabel** dropdown: A++++ met EPG … down to G, and “geen label mogelijk/bekend”.
- Output or summary shows: **Bruto maandlasten**, **Hypotheek**, **Kosten koper** (or equivalent Dutch labels).

**Proves:** Mortgage calculator (section 4d).

---

#### Test 1.7 – Observability tab

**Command:** Open the Observability tab in the app.

**Success criteria:**

- Tab or section shows **token consumption** and **price estimation** (KPIs and/or charts).
- **Langfuse** is wired (callback or client); UI includes **link(s) to Langfuse** (e.g. trace URL or dashboard).

**Proves:** Observability tab (sections 4.1–4.5).

---

#### Test 1.8 – Unit tests (pytest)

**Command:** `pytest` (or `pytest tests/`)

**Success criteria:**

- Exit code 0.
- **Retrieval** tests (e.g. hybrid_retrieve, RRF) exist and pass.
- **PDF** tests (e.g. chunking or ingestion helper) exist and pass.
- **Calculator** tests (e.g. monthly payment or cost logic) exist and pass.
- Config: `pytest.ini` or `[tool.pytest]` in `pyproject.toml` present.

**Proves:** Tests (section 7).

---

#### Test 1.9 – CI/CD

**Command:** Lint and test as run in CI (e.g. `ruff check .`, `pytest`), or push and verify workflow.

**Success criteria:**

- `.github/workflows/ci.yml` exists.
- Workflow runs **lint** (e.g. ruff, black) and **test** (pytest).
- On a clean tree, workflow (or same commands locally) **pass**.

**Proves:** CI/CD (section 8).

---

#### Test 1.10 – Deployment documentation

**Evidence:**

- **DEPLOYMENT.md** exists with: how to run the app, env vars, and **platform notes** for at least one of: Streamlit Cloud, Hugging Face Spaces, Render.
- **.env.example** exists with all required variables (no secrets), including optional Tavily and Langfuse.

**Proves:** Deployment (section 6).

---

### Phase 1 sign-off checklist

- [ ] Test 1.1 – Ingestion and test_ingestion.py PASS.
- [ ] Test 1.2 – Single app (`app.py`) and tool-usage visibility.
- [ ] Test 1.3 – Interactive citations (stored sources, expandable panel, optional inline markers).
- [ ] Test 1.4 – Web search toggle and TAVILY_API_KEY in .env.example.
- [ ] Test 1.5 – Hybrid search + RRF (hybrid_retrieve).
- [ ] Test 1.6 – Mortgage calculator (ING-style, energielabel, Bruto maandlasten, Hypotheek, Kosten koper).
- [ ] Test 1.7 – Observability tab (tokens, price, Langfuse link).
- [ ] Test 1.8 – pytest (retrieval, PDF, calculator).
- [ ] Test 1.9 – CI workflow (lint + test).
- [ ] Test 1.10 – DEPLOYMENT.md and .env.example with platform notes.

**Phase 1 is complete when all items above are checked and the corresponding tests meet the success criteria.**

---

## Phase 2 – Location & property intelligence

**Outcome:** Location-aware recommendations (nearby POIs, commute, proximity, safety), KG tab, and optional A2UI for calculator/map.

### Scope (section refs)

- **Map-based nearby search** (section 4b): Nominatim + Overpass, `nearby_places` tool (grocery, school, church, hospital, dentist, gym, etc.).
- **OSRM enrichment** (section 4g): commute time (property ↔ workplace), proximity scoring to amenities (schools, transit, hospitals), neighborhood accessibility; enrich property recommendations and optional “Property insights” card.
- **Safety information** (section 4f): crime records by area (CBS / data.overheid.nl by wijk/buurt); `area_safety` tool and optional Safety card.
- **Knowledge Graph tab** (section 3): text → graph extraction (e.g. LLMGraphTransformer), PyVis visualization in a tab.
- **A2UI (first widgets)** (optional): agent can return “show calculator” or “show map” directives; Streamlit renders mortgage calculator (prefilled from context) or map with POIs when the agent requests it.

### Deliverables (evidence)

| Deliverable | Location / Evidence |
|-------------|----------------------|
| nearby_places tool | Uses Nominatim + Overpass; returns POIs by category (grocery, school, etc.) |
| OSRM enrichment | Commute time property ↔ workplace; proximity to amenities; optional Property insights card |
| area_safety tool | Uses CBS / data.overheid.nl (wijk/buurt); optional Safety card in UI |
| Knowledge Graph tab | Extraction (e.g. LLMGraphTransformer) → Neo4j or in-memory; PyVis visualization in app tab |
| A2UI (optional) | Agent directives “show calculator” / “show map”; Streamlit renders calculator or map with POIs |

| Chat response format | Tools Used block lists tools (e.g. vector_search, graph_search, nearby_places); citations remain clear. Same pattern as Phase 1. |

### Prerequisites for Phase 2 tests

- Neo4j running if KG is persisted; otherwise in-memory graph + PyVis is acceptable for the tab.
- Phase 1 app running; optional: OSRM instance or public OSRM API, Nominatim/Overpass access.

### Phase 2 completion tests

#### Test 2.1 – Neo4j connectivity (if KG persisted)

**Command:** `python scripts/test_phase2.py --check-neo4j`

**Success criteria:** Exit code 0; output “OK – Neo4j is reachable and credentials work.”

**Proves:** Neo4j is available for KG storage when used.

---

#### Test 2.2 – Graph extraction and KG tab

**Command:** Run app; open Knowledge Graph tab; trigger extraction (e.g. from current doc or sample).

**Success criteria:**

- **Graph extraction** runs (e.g. LLMGraphTransformer or equivalent) on text and produces nodes/edges.
- **PyVis** (or equivalent) visualization is shown in the tab with nodes and edges.
- If Neo4j is used: `python scripts/test_phase2.py --check-graph-write` passes (extraction + write).

**Proves:** Knowledge Graph tab (section 3).

---

#### Test 2.3 – nearby_places (map-based search)

**Command:** In app, use a flow that calls `nearby_places` (e.g. “What’s near [address]?” or dedicated UI).

**Success criteria:**

- **Nominatim** (or similar) used for geocoding; **Overpass** (or similar) for POIs.
- Results include at least one category (e.g. grocery, school, hospital); **map** shows location and POIs (or list with coordinates).

**Proves:** Map-based nearby search (section 4b).

---

#### Test 2.4 – OSRM enrichment

**Command:** Use feature that computes commute or proximity (e.g. property ↔ workplace or amenities).

**Success criteria:**

- **OSRM** (or equivalent) used for **commute time** and/or **proximity** to amenities (schools, transit, hospitals).
- Result visible in **Property insights** card or in chat/tool output (e.g. “Commute: 25 min”, “Schools within 2 km: 3”).

**Proves:** OSRM enrichment (section 4g).

---

#### Test 2.5 – area_safety

**Command:** Use `area_safety` (e.g. “How safe is [wijk/buurt]?” or Safety card).

**Success criteria:**

- **area_safety** tool exists and uses **CBS** or **data.overheid.nl** (wijk/buurt) for crime/safety data.
- Optional **Safety card** in UI shows area safety summary.

**Proves:** Safety information (section 4f).

---

#### Test 2.6 – A2UI (optional): calculator and map directives

**Command:** Trigger agent response that requests “show calculator” or “show map”.

**Success criteria:**

- Agent output includes a **directive** (e.g. structured field or intent) to show calculator or map.
- Streamlit **renders** the mortgage calculator (optionally prefilled) or **map with POIs** according to the directive.

**Proves:** A2UI first widgets (optional).

---

### Phase 2 sign-off checklist

- [ ] Test 2.1 – Neo4j connectivity (if KG in Neo4j).
- [ ] Test 2.2 – Graph extraction + KG tab (PyVis).
- [ ] Test 2.3 – nearby_places (Nominatim + Overpass, map/list).
- [ ] Test 2.4 – OSRM enrichment (commute, proximity, Property insights).
- [ ] Test 2.5 – area_safety (CBS/data.overheid.nl, optional Safety card).
- [ ] Test 2.6 – A2UI calculator/map directives (optional).

**Phase 2 is complete when all implemented items above are checked and tests meet the success criteria.**

---

## Phase 3 – Advanced UX & continuous monitoring

**Outcome:** Sun-orientation widget, production-grade monitoring (retrieval, response, drift), evals pipeline, and Prometheus/Grafana dashboards.

### Scope (section refs)

- **Interactive sun-orientation SVG** (section 4e): tab or section for sun path vs apartment across the year (solar position, orientation, date slider); SVG or embedded HTML/JS.
- **Continuous monitoring & responsible AI** (section 4h): retrieval accuracy and response quality metrics (from RAGAS samples or Langfuse); model behavior drift (input/output distributions, quality trends); responsible AI (traceability, transparency, docs). Observability tab: “Retrieval quality”, “Response quality”, “Drift indicators”; optional `monitoring/drift_detection.py` and `docs/RESPONSIBLE_AI.md`.
- **RAG evals** (section 5): golden dataset, RAGAS script; run periodically and log scores for monitoring.
- **Prometheus + Grafana** (sections 4.2–4.3): `/metrics` endpoint, Grafana dashboard for RAG (latency, tool usage, errors, retrieval quality); document setup.

### Deliverables (evidence)

| Deliverable | Location / Evidence |
|-------------|----------------------|
| Sun-orientation widget | Tab/section: sun path vs apartment; orientation; date slider; SVG or HTML/JS |
| Retrieval quality | Observability: “Retrieval quality” (e.g. from RAGAS or Langfuse) |
| Response quality | Observability: “Response quality” metrics |
| Drift indicators | Observability: “Drift indicators”; optional drift_detection.py |
| Responsible AI docs | docs/RESPONSIBLE_AI.md (traceability, transparency) |
| RAG evals | Golden dataset; RAGAS script; periodic run and logged scores |
| /metrics | Prometheus-compatible endpoint (latency, tool usage, errors, retrieval quality) |
| Grafana | Documented dashboard for RAG (latency, tools, errors, retrieval quality) |
| *Chat response format* | Unchanged: **Tools Used** + **Assistant** + **citations** (Phase 1/2 pattern). Observability tab surfaces quality/drift for retrieval and responses. |

### Phase 3 completion tests

#### Test 3.1 – Sun-orientation SVG

**Command:** Open sun-orientation tab/section in the app.

**Success criteria:**

- **Sun path** vs apartment (or building) shown; **orientation** and **date slider** control the view.
- Implemented as **SVG** or embedded **HTML/JS**; updates when date/orientation change.

**Proves:** Interactive sun-orientation (section 4e).

---

#### Test 3.2 – Observability: Retrieval quality, Response quality, Drift indicators

**Command:** Open Observability tab; check for new sections.

**Success criteria:**

- **“Retrieval quality”** section (e.g. from RAGAS or Langfuse).
- **“Response quality”** section with metrics.
- **“Drift indicators”** section (e.g. input/output distributions, quality trends).
- Optional: `monitoring/drift_detection.py` and `docs/RESPONSIBLE_AI.md` exist.

**Proves:** Continuous monitoring & responsible AI (section 4h).

---

#### Test 3.3 – RAG evals pipeline

**Command:** Run RAGAS script on golden dataset (e.g. `python scripts/run_ragas.py`).

**Success criteria:**

- **Golden dataset** exists (e.g. questions + reference answers or context).
- **RAGAS script** runs and produces scores (e.g. faithfulness, answer relevancy); scores **logged** for monitoring (e.g. to Langfuse or file).

**Proves:** RAG evals (section 5).

---

#### Test 3.4 – Prometheus /metrics and Grafana

**Command:** GET `/metrics` (or documented URL); open Grafana (if deployed).

**Success criteria:**

- **/metrics** endpoint returns Prometheus-format metrics (e.g. request latency, tool usage counts, errors, retrieval quality).
- **Grafana** dashboard document (or exported JSON) describes RAG dashboard: latency, tool usage, errors, retrieval quality.
- Setup documented (e.g. in DEPLOYMENT.md or monitoring README).

**Proves:** Prometheus + Grafana (sections 4.2–4.3).

---

### Phase 3 sign-off checklist

- [ ] Test 3.1 – Sun-orientation SVG (date, orientation, sun path).
- [ ] Test 3.2 – Observability: Retrieval quality, Response quality, Drift indicators; optional drift_detection.py and RESPONSIBLE_AI.md.
- [ ] Test 3.3 – RAG evals (golden set, RAGAS, logged scores).
- [ ] Test 3.4 – /metrics endpoint and Grafana RAG dashboard documented.

**Phase 3 is complete when all items above are checked and tests meet the success criteria.**

---

## Phase 4 – Multi-agent, A2A, A2UI, MCP

**Outcome:** Multi-agent architecture with A2A handoffs, rich A2UI-driven widgets, and MCP-based tools; evals in CI where applicable.

### Scope (section refs)

- **Multiple agents (A2A)** (section 4i): specialist agents (e.g. retrieval, location, calculator); orchestrator routes and invokes them (Agent-to-Agent); implement with LangGraph or multi-agent LangChain.
- **A2UI (full)**: Schema for agent-driven UI directives (calculator, map, sun diagram, citation panel, safety card); renderer in Streamlit for each type; agent output parsed and widgets updated accordingly.
- **MCP servers** (section 4i): integrate MCP for selected capabilities (e.g. OSRM, safety API, or search); MCP client in app, tools registered with agent(s).
- **Eval smoke in CI** (section 8): optional workflow to run RAGAS on a small golden subset on schedule or on release.

### Deliverables (evidence)

| Deliverable | Location / Evidence |
|-------------|----------------------|
| Specialist agents | E.g. retrieval agent, location agent, calculator agent |
| Orchestrator | Routes queries to specialists; A2A handoffs (LangGraph or multi-agent LangChain) |
| A2UI schema | Documented or code schema for directives: calculator, map, sun, citation panel, safety card |
| A2UI renderer | Streamlit renders each directive type from agent output |
| MCP client | MCP client in app; tools (e.g. OSRM, safety, search) registered with agent(s) |
| Eval smoke in CI | Optional: workflow runs RAGAS on small golden subset (schedule or release) |
| *Chat response format* | **Tools Used** shows which tools/MCP/specialist agents were invoked; **A2UI directives** (calculator, map, sun, citations, safety) rendered from agent output; **citations** remain clear. |

### Phase 4 completion tests

#### Test 4.1 – Multi-agent routing (A2A)

**Command:** Ask questions that require different specialists (retrieval, location, calculator).

**Success criteria:**

- **Orchestrator** routes to **specialist agents** (e.g. retrieval, location, calculator).
- **Agent-to-Agent** handoff is observable (e.g. in traces or tool-usage visibility); response reflects the right specialist(s).

**Proves:** Multiple agents and A2A (section 4i).

---

#### Test 4.2 – A2UI full schema and renderer

**Command:** Trigger agent responses that emit different UI directives.

**Success criteria:**

- **Schema** for directives exists (e.g. calculator, map, sun diagram, citation panel, safety card).
- **Streamlit renderer** updates widgets (calculator, map, sun, citations, safety card) from **parsed agent output** (e.g. structured JSON or intent).

**Proves:** A2UI full (schema + renderer).

---

#### Test 4.3 – MCP integration

**Command:** Use a capability that is provided via MCP (e.g. OSRM, safety API, or search).

**Success criteria:**

- **MCP client** is integrated in the app.
- At least one **MCP server** is used; **tools** from MCP are **registered** with the agent(s) and appear in tool-usage visibility when used.

**Proves:** MCP servers (section 4i).

---

#### Test 4.4 – Eval smoke in CI (optional)

**Command:** Run CI workflow that includes RAGAS (or equivalent) on a small golden subset.

**Success criteria:**

- **Workflow** (e.g. on schedule or on release) runs **RAGAS** (or equivalent) on a **small golden subset**.
- Results are **logged** or **published** (e.g. artifact or status check); pipeline does not block release unless configured to.

**Proves:** Eval smoke in CI (section 8).

---

### Phase 4 sign-off checklist

- [ ] Test 4.1 – Multi-agent routing and A2A handoffs.
- [ ] Test 4.2 – A2UI full (schema + Streamlit renderer for all directive types).
- [ ] Test 4.3 – MCP client + at least one MCP server/tools registered.
- [ ] Test 4.4 – Eval smoke in CI (optional).

**Phase 4 is complete when all implemented items above are checked and tests meet the success criteria.**

---

## Running tests by phase (summary)

### Phase 1

```bash
python scripts/ingest_docs.py
python scripts/test_ingestion.py
streamlit run app.py
pytest
# CI: .github/workflows/ci.yml
# Docs: DEPLOYMENT.md, .env.example
```

### Phase 2

```bash
python scripts/test_phase2.py --check-neo4j
python scripts/test_phase2.py --check-graph-write   # when implemented
# Manual: KG tab, nearby_places, OSRM, area_safety, A2UI
```

### Phase 3

```bash
# Sun-orientation: in-app
# Observability: Retrieval/Response quality, Drift
# RAG evals: scripts/run_ragas.py (or equivalent)
# Prometheus: GET /metrics; Grafana: see docs
```

### Phase 4

```bash
# Multi-agent: in-app (orchestrator + specialists)
# A2UI: in-app (directives + renderer)
# MCP: in-app (client + tools)
# CI: optional RAGAS workflow
```

---

## Code run steps at end of each phase (when phase is completed)

Use these steps to run the project **after** that phase is done. All commands assume you are in the **project root** (`expat-nl-mortgage-rag`).

---

### Run steps – Phase 1 completed

1. **Environment**
   - Copy `.env.example` to `.env` (or ensure `.env` exists).
   - Set at least: `QDRANT_URL`, `QDRANT_COLLECTION`, and for LLM/embeddings either `OPENAI_API_KEY` or `OPENROUTER_API_KEY` (and `LLM_PROVIDER` / `EMBEDDING_PROVIDER`). Optional: `TAVILY_API_KEY`, Langfuse vars.

2. **Install**
   ```bash
   python -m venv venv
   venv\Scripts\activate          # Windows
   # source venv/bin/activate     # Linux/macOS
   pip install -r requirements.txt
   ```

3. **Services**
   - Start **Qdrant** (e.g. Docker) so it is reachable at `QDRANT_URL`.

4. **Ingest documents (first time or after adding PDFs)**
   ```bash
   python scripts/ingest_docs.py
   ```
   Optional semantic chunking: `python scripts/ingest_docs.py --semantic`

5. **Verify ingestion**
   ```bash
   python scripts/test_ingestion.py
   ```
   Expect: `RESULT: PASS`.

6. **Run the app**
   ```bash
   streamlit run app.py
   ```
   (If Phase 1 app is still `app_phase1.py`: `streamlit run app_phase1.py`.)

7. **Run tests**
   ```bash
   pytest
   ```

8. **CI (if workflow exists)**
   - Push and confirm `.github/workflows/ci.yml` passes (lint + test).

---

### Run steps – Phase 2 completed

Do **all Phase 1 steps** first, then:

1. **Environment**
   - Add Neo4j vars if KG is in Neo4j: `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`.
   - Optional: OSRM base URL, Nominatim/Overpass, CBS/data.overheid.nl or safety API keys if required.

2. **Services**
   - Start **Neo4j** (if used) at `NEO4J_URI`.

3. **Verify Neo4j (if used)**
   ```bash
   python scripts/test_phase2.py --check-neo4j
   ```

4. **Run the app**
   ```bash
   streamlit run app.py
   ```
   - Use **Knowledge Graph** tab for graph visualization.
   - Use chat or tools for **nearby_places**, **OSRM** (commute/proximity), **area_safety**; optional A2UI (calculator/map) if implemented.

---

### Run steps – Phase 3 completed

Do **Phase 1 and Phase 2 steps** as needed, then:

1. **Environment**
   - Ensure Langfuse and any eval/monitoring env vars are set if used.

2. **Run the app**
   ```bash
   streamlit run app.py
   ```
   - Open **Observability** tab: Retrieval quality, Response quality, Drift indicators.
   - Open **Sun-orientation** tab/section (date slider, orientation).

3. **RAG evals (when implemented)**
   ```bash
   python scripts/run_ragas.py
   ```

4. **Prometheus / Grafana**
   - If app exposes `/metrics`: GET `http://<app_host>:<port>/metrics` for Prometheus scrape.
   - Use documented Grafana dashboard for RAG (latency, tool usage, errors, retrieval quality).

---

### Run steps – Phase 4 completed

Do **Phase 1–3 steps** as needed, then:

1. **Run the app**
   ```bash
   streamlit run app.py
   ```
   - Multi-agent: orchestrator and specialists (retrieval, location, calculator) used via chat.
   - A2UI: agent directives (calculator, map, sun, citations, safety) render in the UI.
   - MCP: tools from MCP servers appear in tool usage when invoked.

2. **CI (optional eval smoke)**
   - If workflow runs RAGAS on a golden subset: push or trigger workflow and confirm eval step passes or is logged.

---

## Document history

- **Four-phase plan** aligned to sections 1–8 (app, citations, web search, hybrid, calculator, observability, tests, CI, deployment; location/KG; monitoring/evals; multi-agent/A2UI/MCP).
- Each phase has **concrete tests** with **commands** and **success criteria** to prove completion.
- Sign-off **checklists** per phase for formal completion.
