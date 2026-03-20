# Expat NL Mortgage Assistant – Dashboard Features & UI Guide

This document describes the features implemented in the **Expat NL Mortgage Assistant** web dashboard and the options available to users. The app is a single Streamlit entry point (`streamlit run app.py`) with a dark theme, red accents, and multiple tabs for chat, tools, and monitoring.

---

## 1. Overview

- **Title:** Expat NL Mortgage Assistant (Phase 1)
- **Purpose:** Help expats and international buyers with Dutch mortgages, property, tax, and housing in the Netherlands.
- **Theme:** Dark mode with high-contrast text and red navigation highlights.
- **Layout:** Top tab bar for main views; left sidebar for configuration and session controls.

---

## 2. Navigation Bar (Top Tabs)

Users can switch between these views via the top navigation:

| Tab | Description |
|-----|-------------|
| **Chat** | Main AI chat with RAG, tool usage, and citations. |
| **Mortgage Calculator** | ING-style calculator for bid, down payment, and monthly costs. |
| **Map** | Nearby facilities (POIs) around an address with routes and travel times. |
| **Documents** | List of ingested documents and upload of new PDFs to the vector store. |
| **Knowledge Graph** | Build and visualize entities/relations from text (PyVis). |
| **Location** | Geocoding, nearby places, OSRM commute, and area safety. |
| **Sun** | Sun path vs apartment orientation by date. |
| **Observability** | Token/price, Langfuse, retrieval/response quality, drift. |
| **Agents (P4)** | Phase 4 multi-agent info and MCP tools. |

---

## 3. Sidebar (Settings)

The **left sidebar** configures backend behavior and session:

### LLM configuration
- **Provider:** Dropdown (e.g. OpenAI, OpenRouter, Ollama) – only providers with API key/URL set in `.env` are shown.
- **Model:** Dropdown for the selected provider (e.g. `nvidia/nemotron-3-su...` for OpenRouter).

### Search & retrieval
- **Use hybrid search (RRF):** Checkbox to combine vector and keyword search with Reciprocal Rank Fusion.
- **Retrieval chunks:** Slider (e.g. 3–20) for number of document chunks retrieved.
- **Web search (Tavily):** Checkbox to enable real-time web search via Tavily API when answering.

### Agent settings
- **Use Phase 4 agents (orchestrator):** Checkbox to route queries through the orchestrator and specialist agents (retrieval, location, calculator).

### Session
- **Clear conversation:** Button to reset chat history.

---

## 4. Chat Tab

- **Header:** Project title and short instruction: *“Ask about Dutch mortgages, tax, housing. Tools Used and sources are shown per turn.”*
- **Flow:** User asks in the chat; the assistant may call retrieval, web search, or agents. Each turn shows:
  - **Tools Used:** List of tools invoked (e.g. `hybrid_retrieve`, `retrieval_agent`) with parameters.
  - **Assistant reply:** Structured text (bold headers, bullets, code blocks when relevant).
  - **Sources:** Expandable panel with document/chunk sources used for the answer.
- **Behavior:**
  - RAG uses the vector store (Qdrant); hybrid search and optional Tavily improve answers.
  - If Phase 4 agents are enabled, the orchestrator can route to specialists and emit A2UI directives (e.g. show calculator, show map).
- **Errors:** Backend errors (e.g. Qdrant client issues) can appear in the chat for debugging.

**Example:** Ask “what is NHG” to get an explanation of Nationale Hypotheek Garantie with purpose, eligibility, costs, and benefits; the UI shows which tools were used.

---

## 5. Mortgage Calculator Tab

- **Title:** Mortgage calculator (ING-style).
- **Disclaimer:** Values are placeholder estimates (~0.45% monthly interest, ~6% costs); not for real financial decisions.
- **Logic:** Bid, eigen inleg, type woning, energielabel → Bruto maandlasten, Hypotheek, Kosten koper.

**Inputs:**
- **Bod / aankoopprijs (€):** Purchase price (e.g. 350,000), with −/+ controls.
- **Eigen inleg (€):** Down payment (e.g. 35,000).
- **Type woning:** Dropdown (e.g. Bestaande koopwoning, Nieuwbouw, Bouwkavel).
- **Energielabel:** Dropdown (A++++ (met EPG) down to G, “Geen label mogelijk/bekend”).

**Outputs (indicative):**
- **Hypotheek:** Mortgage amount (e.g. € 315,000).
- **Bruto maandlasten (indicatief):** Gross monthly costs (e.g. € 1,417.50).
- **Kosten koper (indicatief):** Buyer’s costs (e.g. € 21,000).

---

## 6. Map Tab

- **Title:** Map – nearby facilities.
- **Description:** POIs around an address with route distance and duration; transport mode affects routing.

**Inputs:**
- **Address:** Text field (e.g. “Assebalpad 210, 3816 SV Amersfoort”).
- **Facility categories:** Multi-select (e.g. School, Grocery, Health, Gym, Restaurant, Bank).
- **Route by:** Car, Walk, or Bike (public OSRM often supports only car; walk/bike may use straight-line).

**Actions:** “Show map” runs geocoding and POI search, then shows:
- **Map:** Interactive map with markers (e.g. colored dots for facilities, red for the address).
- **Table:** Name, category, distance (km), duration (min) for each POI.

**Status:** Green bar, e.g. “Found 25 places near &lt;address&gt;.”

---

## 7. Documents Tab

- **Title:** Documents in vector store & knowledge base.
- **Purpose:** See what is indexed for RAG and add new PDFs.

**Uploaded documents:**
- List of files already in the store with **chunk count** (e.g. 7, 99, 217 chunks per file).

**Upload new document:**
- **Drag and drop / Browse:** PDF only, up to 200 MB per file.
- **Also run KG extraction and show in Knowledge Graph tab:** Checkbox to run entity/relation extraction and view in the Knowledge Graph tab.
- **Ingest into vector store:** Button to chunk, embed, and upsert the PDF; optional KG extraction runs if checked.

---

## 8. Knowledge Graph Tab

- **Title:** Knowledge Graph.
- **Description:** Extract entities and relations from text; visualize with PyVis.

**Inputs:**
- **Text to build graph from:** Text area (default sample about Dutch mortgages, Belastingdienst, NHG).
- **Build graph:** Button to run extraction and refresh the visualization.

**Output:** Interactive graph (e.g. light blue nodes, directed edges) showing entities (e.g. “The Tax Authority”, “Belastingdienst”, “NHG”, “hypotheekrenteaftrek”) and relationships. Rendered with PyVis in a scrollable area.

---

## 9. Location Tab

- **Title:** Location & commute.
- **Description:** Nearby places (Nominatim + Overpass), OSRM commute, area safety (placeholder).

**Features:**
- **Address:** Input and “Nearby places” to get coordinates and sample POIs.
- **Commute destination:** Input and “Commute time (OSRM)” for duration and distance.
- **Area for safety:** Input and “Area safety” (placeholder) for area-based safety info.

---

## 10. Sun Tab

- **Title:** Sun orientation.
- **Description:** Sun path vs apartment: elevation through the day; date and building orientation control the view.

**Inputs:**
- **Date:** Date picker (e.g. 2026/03/19).
- **Orientation:** Dropdown (South, SW, West, NW, North, NE, East, SE).

**Output:** Chart “Sun path — &lt;date&gt; — facing &lt;orientation&gt;” with sun elevation curve (e.g. orange line/dots), time on X-axis, elevation on Y-axis, and a “Noon” marker (green dashed line).

---

## 11. Observability Tab

- **Title:** Observability.
- **Description:** Token/price, Langfuse, retrieval/response quality, and drift indicators.

**Sections:**
- **Configuration:** If `LANGFUSE_HOST` or `LANGFUSE_URL` is set in `.env`, link to Langfuse dashboard; otherwise an info message to set them.
- **Token / price tracking:** Via Langfuse callback when enabled.
- **Retrieval quality (expandable):** Mean retrieval quality; “No data” until RAGAS or monitoring scripts (e.g. `scripts/run_ragas.py`) populate it.
- **Response quality (expandable):** Response quality (mean) and Latency p50 (ms); same “No data” until populated.
- **Drift indicators (expandable):** Trends from `monitoring.drift_detection` when scores are recorded.

**Links:** Responsible AI doc, Monitoring / Grafana doc.

---

## 12. Agents (P4) Tab

- **Title:** Agents (Phase 4).
- **Description:** Orchestrator routes to retrieval, location, and calculator specialists; A2UI directives render in chat.

**Content:**
- **MCP tools registered:** e.g. `osrm_commute` (and others when available).
- **Instructions:** Enable “Use Phase 4 agents” in the sidebar to use the orchestrator; responses can include A2UI directives (e.g. show calculator, show map).

---

## 13. Summary of Implemented Features

| Area | Features |
|------|----------|
| **RAG** | Vector store (Qdrant), hybrid search + RRF, optional Tavily web search, document ingestion (`ingest_docs.py` or in-app upload). |
| **Chat** | Tools-used visibility, citations/sources per turn, optional Phase 4 orchestrator and A2UI (calculator, map, etc.). |
| **Tools** | Mortgage calculator (ING-style), map with nearby facilities and OSRM routes, Knowledge Graph (PyVis), location/commute/safety. |
| **UX** | Sun orientation by date and orientation; Documents tab for upload and chunk count; dark theme and tab-based navigation. |
| **Observability** | Langfuse (token/price), retrieval/response quality and latency placeholders, drift indicators, links to Responsible AI and Grafana. |
| **Agents** | Phase 4 orchestrator and specialists, MCP tools (e.g. OSRM), A2UI directives in chat. |

---

## 14. Quick Reference for New Users

1. **Ask questions:** Use the **Chat** tab; check **Tools Used** and **Sources** to see how answers are built.
2. **Estimate costs:** Use **Mortgage Calculator** for indicative monthly costs and buyer’s costs.
3. **Explore an area:** Use **Map** (address + categories + transport) or **Location** (nearby + commute).
4. **Inspect or extend knowledge:** Use **Documents** to see/upload PDFs; use **Knowledge Graph** to build graphs from text.
5. **Check light for a property:** Use **Sun** with date and orientation.
6. **Monitor and evaluate:** Use **Observability** (and set Langfuse in `.env`); use **Agents (P4)** to enable the orchestrator and MCP tools.

For setup, run `python scripts/ingest_docs.py` (and optionally upload PDFs in the Documents tab), then `streamlit run app.py`. See [README.md](README.md), [docs/QUICKSTART.md](docs/QUICKSTART.md), and [PHASES.md](PHASES.md) for full run steps and phase details.
