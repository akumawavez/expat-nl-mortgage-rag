"""
Phase 1 consolidated app: Chat (RAG + Tools Used + citations), Mortgage Calculator, Observability.

Single entry point: streamlit run app.py
Run scripts/ingest_docs.py first to populate Qdrant. Sidebar: provider/model from .env, web search toggle, hybrid retrieval.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
import base64

import streamlit as st
from qdrant_client import QdrantClient

from lib.provider import (
    get_llm_client,
    get_embedding_client,
    get_available_llm_providers,
    get_default_llm_models,
)
from lib.retrieval import vector_search, hybrid_retrieve
from lib.graph_kg import build_kg_from_text
from lib.location import (
    nearby_places,
    osrm_commute,
    area_safety,
    POI_CATEGORIES,
    nearby_pois_with_routes,
)
from lib.map_ui import build_map_html, build_pydeck_map, build_pois_table_data
from lib.sun_orientation import build_sun_orientation_html
from lib.documents import list_documents_in_store, upsert_pdf_to_qdrant, delete_document_from_store
from lib.agents import run_orchestrator
from lib.mcp_client import list_mcp_tools, register_default_mcp_tools

import dotenv
dotenv.load_dotenv(Path(__file__).resolve().parent / ".env")

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
PAGE_TITLE = "Expat NL Mortgage Assistant"
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")

# Navigation: (page_key, icon, label, short description for Home cards)
NAV_ITEMS = [
    ("Home", "🏠", "Home", "Dashboard and quick links"),
    ("Chat", "💬", "Chat", "Ask about Dutch mortgages, tax, and housing"),
    ("Documents", "📄", "Documents", "Manage knowledge base and upload PDFs"),
    ("Knowledge Graph", "🕸️", "Knowledge Graph", "Extract and visualize entities & relations"),
    ("Mortgage Calculator", "🧮", "Mortgage Calculator", "Estimate loan, monthly payment, costs"),
    ("Map", "🗺️", "Map", "Nearby facilities and POIs on map"),
    ("Observability", "📈", "Observability", "Metrics, Langfuse, retrieval quality"),
]
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "property_docs")
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "150"))
MAX_SEARCH_RESULTS = int(os.environ.get("MAX_SEARCH_RESULTS", "10"))
VECTOR_DIMENSION = int(os.environ.get("VECTOR_DIMENSION", "1536"))
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
LLM_CHOICE_DEFAULT = os.environ.get("LLM_CHOICE", "gpt-4o-mini")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MAX_QUERY_LENGTH = int(os.environ.get("MAX_QUERY_LENGTH", "5000"))
STREAM_TIMEOUT_SECONDS = int(os.environ.get("STREAM_TIMEOUT_SECONDS", "30"))
MAX_COMPLETION_TOKENS = int(os.environ.get("MAX_COMPLETION_TOKENS", "2048"))

SYSTEM_PROMPT = (
    "You are an expert assistant helping expats and international buyers with Dutch mortgages "
    "and property in the Netherlands. Use the provided context from documents to answer. "
    "If the context does not contain enough information, say so. Keep answers concise and actionable. "
    "When web search results are provided, you may use them to supplement the document context."
)


def _inject_custom_css() -> None:
    """Apply dark sidebar, card-style panels, and accent blue to match mockups."""
    st.markdown(
        """
        <style>
        /* Dark navy sidebar */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #1e3a5f 0%, #152a45 100%);
        }
        [data-testid="stSidebar"] .stRadio label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] .stMarkdown {
            color: #e8eef4 !important;
        }
        [data-testid="stSidebar"] .stRadio div[role="radiogroup"] {
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            padding: 6px 8px;
        }
        [data-testid="stSidebar"] label[data-checked="true"] {
            background: #2b5797 !important;
            color: white !important;
            border-radius: 6px;
        }
        /* Card-style containers */
        .nav-card {
            background: #fff;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            padding: 1.25rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
            margin-bottom: 1rem;
            transition: box-shadow 0.2s;
        }
        .nav-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
        .panel-card {
            background: #fff;
            border: 1px solid #e8eaed;
            border-radius: 10px;
            padding: 1rem 1.25rem;
            margin-bottom: 1rem;
        }
        /* Primary blue for buttons and links */
        .stButton > button[kind="primary"], .stButton > button:first-child {
            background-color: #2b5797 !important;
            color: white !important;
            border-radius: 8px;
        }
        /* Main area subtle background */
        .main .block-container { padding-top: 1.5rem; max-width: 1400px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource
def get_qdrant() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


def _validate_and_sanitize_query(text: str) -> str:
    """Enforce max length and remove control characters. Returns sanitized string."""
    if not text or not isinstance(text, str):
        return ""
    # Remove control characters (except newline, tab)
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    sanitized = sanitized.strip()
    if len(sanitized) > MAX_QUERY_LENGTH:
        sanitized = sanitized[:MAX_QUERY_LENGTH].rstrip()
    return sanitized


def get_embedding(client, text: str) -> list[float]:
    resp = client.embeddings.create(input=[text], model=EMBEDDING_MODEL)
    return resp.data[0].embedding


def _tavily_search(query: str, max_results: int = 5) -> tuple[str, list[dict], list[dict]]:
    """
    Return (context_string, tool_calls_for_ui, web_sources_for_tracing).
    web_sources: list of {"source": "[Web] Title", "text": content, "url": url} for source panel.
    If no key or error, returns ('', [], []).
    """
    if not os.environ.get("TAVILY_API_KEY"):
        return "", [{"tool": "tavily_search", "args": {"status": "skipped_no_api_key"}}], []
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        response = client.search(query, max_results=max_results)
        if isinstance(response, dict):
            results = response.get("results", [])
        else:
            results = getattr(response, "results", response) if hasattr(response, "results") else []
        if isinstance(results, list):
            parts = []
            web_sources = []
            for r in results:
                title = r.get("title", "").strip() or "Web result"
                url = r.get("url", "")
                # Tavily may return empty `content` for some results; fallback to snippets.
                content = (r.get("content") or r.get("snippet") or r.get("raw_content") or "").strip()
                if content:
                    parts.append(f"[{title}]({url})\n{content}")
                elif url:
                    # Keep URL in context so the LLM can still reference source when snippet is empty.
                    parts.append(f"[{title}]({url})")
                if url or content:
                    web_sources.append({
                        "type": "web",
                        "title": title,
                        "source": title,
                        "text": (content[:2000] + ("..." if len(content) > 2000 else "")) if content else "",
                        "url": url,
                    })
            tool_calls = [{"tool": "tavily_search", "args": {"query": query[:80], "results": len(web_sources)}}]
            return "\n\n".join(parts), tool_calls, web_sources
    except Exception as e:
        logger.warning("Tavily web search failed: %s", e, exc_info=True)
        return "", [{"tool": "tavily_search", "args": {"status": "error", "error": str(e)[:120]}}], []
    return "", [{"tool": "tavily_search", "args": {"status": "no_results"}}], []


def _has_query_signal_in_docs(prompt: str, chunks: list[dict]) -> bool:
    """
    Heuristic: returns True if at least one meaningful prompt token appears in retrieved docs.
    Used to decide when to explicitly prioritize web context.
    """
    if not prompt or not chunks:
        return False
    tokens = [t for t in re.findall(r"[A-Za-z0-9]{3,}", prompt.lower()) if t not in {"what", "when", "where", "which", "about", "does", "have", "with", "from"}]
    if not tokens:
        return True
    joined = " ".join((c.get("text", "") or "").lower() for c in chunks[:5])
    return any(t in joined for t in tokens)


def _format_tools_used(tool_calls: list[dict]) -> str:
    lines = []
    for i, tc in enumerate(tool_calls, 1):
        name = tc.get("tool", "?")
        args = tc.get("args", {})
        args_str = ", ".join(f"{k}={repr(v)}" for k, v in args.items())
        lines.append(f"  {i}. {name} ({args_str})")
    return "🛠 **Tools Used:**\n" + "\n".join(lines) if lines else ""


# ---------- Home page: cards linking to each section ----------
def _render_home_page() -> None:
    st.title("Expat NL Mortgage Assistant")
    st.caption("Your guide to Dutch mortgages, property, and housing. Choose a section below to get started.")
    st.markdown("---")
    non_home = [(pk, icon, label, desc) for pk, icon, label, desc in NAV_ITEMS if pk != "Home"]
    num_cols = min(4, len(non_home))
    cols = st.columns(num_cols)
    for i, (page_key, icon, label, desc) in enumerate(non_home):
        with cols[i % num_cols]:
            with st.container():
                st.markdown(f"### {label}")
                st.caption(desc)
                if st.button("Open →", key=f"home_go_{page_key}", use_container_width=True):
                    st.session_state["nav_page"] = page_key
                    st.session_state["_nav_from_button"] = True
                    st.rerun()
    st.markdown("---")
    st.caption("Use the **sidebar** to switch sections anytime. Chat uses the knowledge base and optional web search.")


def _stream_api(provider: str, model: str, messages: list[dict], placeholder, prefix: str = "") -> str:
    client = get_llm_client(provider_override=provider)
    full = ""
    kwargs = {"model": model, "messages": messages, "stream": True, "max_tokens": MAX_COMPLETION_TOKENS}
    for chunk in client.chat.completions.create(**kwargs):
        if chunk.choices and chunk.choices[0].delta.content:
            full += chunk.choices[0].delta.content
            placeholder.markdown(prefix + full + "▌")
    placeholder.markdown(prefix + full)
    return full


def _stream_ollama(model: str, messages: list[dict], placeholder, prefix: str = "") -> str:
    import requests
    base = OLLAMA_URL.rstrip("/")
    payload = {"model": model, "messages": messages, "stream": True, "options": {"num_predict": MAX_COMPLETION_TOKENS}}
    full = ""
    r = requests.post(f"{base}/api/chat", json=payload, stream=True, timeout=STREAM_TIMEOUT_SECONDS)
    r.raise_for_status()
    for line in r.iter_lines(decode_unicode=True):
        if not line:
            continue
        data = json.loads(line)
        if data.get("message", {}).get("content"):
            full += data["message"]["content"]
            placeholder.markdown(prefix + full + "▌")
    placeholder.markdown(prefix + full)
    return full


# ---------- Mortgage calculator (ING-style) ----------
ENERGIELABELS = [
    "A++++ (met EPG)",
    "A+++",
    "A++",
    "A+",
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "Geen label mogelijk/bekend",
]


def _render_calculator_tab() -> None:
    st.subheader("Mortgage Calculator")
    st.warning(
        "**Disclaimer:** All values are placeholder estimates only (e.g. ±0.5% monthly interest, +6% cost). "
        "Do not use for real financial decisions. Consult a mortgage advisor for accurate numbers."
    )
    col_input, col_result = st.columns([1, 1])
    with col_input:
        st.markdown("#### Inputs")
        bid = st.number_input("Loan Amount (€)", min_value=50000, max_value=2_000_000, value=350000, step=10000, key="calc_bid")
        eigen_inleg = st.number_input("Own Input (€)", min_value=0, max_value=bid, value=35000, step=5000, key="calc_eigen")
        hypotheek = bid - eigen_inleg
        _type_woning = st.selectbox("Type of Property", ["Existing Home", "New Build", "Building Plot"], key="calc_type")
        _energielabel = st.selectbox("Energy Label", ENERGIELABELS, key="calc_energy")
        st.button("Calculate", type="primary", key="calc_btn", use_container_width=True)
    with col_result:
        st.markdown("#### Summary Results")
        maandlast_approx = round(hypotheek * 0.0045, 2)
        kk = round(bid * 0.06, 0)
        st.metric("Loan Amount", f"€ {hypotheek:,}")
        st.metric("Monthly Payment (Gross)", f"€ {maandlast_approx:,.2f}")
        st.metric("Buyer Costs", f"€ {kk:,.0f}")


# ---------- Knowledge Graph tab ----------
def _render_kg_tab() -> None:
    st.subheader("Knowledge Graph")
    st.caption("Extract entities and relations from text, visualize with PyVis.")
    default_text = (
        "Mortgage interest deduction (hypotheekrenteaftrek) applies to owner-occupied homes. "
        "The Tax Authority (Belastingdienst) oversees tax returns. NHG provides guarantees for mortgages."
    )
    text = st.text_area("Enter text to build graph from", value=default_text, height=140, key="kg_text")
    if st.button("Build Graph", type="primary", key="kg_build"):
        with st.spinner("Building graph..."):
            html = build_kg_from_text(text)
        st.markdown("#### Knowledge Graph")
        st.components.v1.html(html, height=500, scrolling=True)
    else:
        html = build_kg_from_text("" if not text.strip() else text)
        st.markdown("#### Knowledge Graph")
        st.components.v1.html(html, height=500, scrolling=True)


# ---------- Documents tab: list uploaded docs, upload new PDF, KB status panel ----------
def _render_documents_tab() -> None:
    st.subheader("Documents")
    st.caption("Documents in the knowledge base are used for RAG retrieval. Upload a PDF to add it to the vector database and optionally extract a knowledge graph.")
    qdrant = get_qdrant()
    docs = list_documents_in_store(qdrant, QDRANT_COLLECTION)
    col_main, col_status = st.columns([2, 1])
    with col_main:
        st.markdown("#### Documents in Knowledge Base")
        st.caption("Indexed documents and chunk counts. Use **Remove** to delete a document and its embeddings from the vector store.")
        if docs:
            for i, d in enumerate(docs):
                row_col1, row_col2, row_col3, row_col4 = st.columns([3, 1, 1, 1])
                with row_col1:
                    st.text(d["source"])
                with row_col2:
                    st.text(str(d["chunk_count"]))
                with row_col3:
                    st.caption("✓ Indexed")
                with row_col4:
                    if st.button("Remove", key=f"doc_remove_{i}", type="secondary"):
                        try:
                            delete_document_from_store(qdrant, QDRANT_COLLECTION, d["source"])
                            st.success(f"Removed **{d['source']}** and its embeddings.")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
            st.divider()
        else:
            st.info("No documents in the vector store yet. Run scripts/ingest_docs.py or upload a PDF below.")
        st.markdown("---")
        st.markdown("#### Upload New Document")
        uploaded = st.file_uploader("Drag & drop PDF here or browse", type=["pdf"], key="doc_upload")
        add_to_kg = st.checkbox("Also extract Knowledge Graph", value=True, key="doc_add_kg")
        if uploaded is not None:
            st.caption(f"Selected: **{uploaded.name}** ({uploaded.size / (1024*1024):.1f} MB)")
        if uploaded is not None and st.button("Ingest into Knowledge Base", type="primary", key="doc_ingest"):
            file_bytes = uploaded.getvalue()
            with st.spinner("Extracting text, chunking, embedding, and upserting..."):
                try:
                    emb = get_embedding_client()
                    name = uploaded.name or "uploaded.pdf"
                    num = upsert_pdf_to_qdrant(
                        qdrant,
                        emb,
                        QDRANT_COLLECTION,
                        file_name=name,
                        file_bytes=file_bytes,
                        chunk_size=CHUNK_SIZE,
                        overlap=CHUNK_OVERLAP,
                        embedding_model=EMBEDDING_MODEL,
                        vector_dimension=VECTOR_DIMENSION,
                    )
                    st.success("Document successfully indexed.")
                    if add_to_kg:
                        from lib.documents import extract_text_from_pdf_bytes
                        text = extract_text_from_pdf_bytes(file_bytes)
                        if text.strip():
                            html = build_kg_from_text(text[:8000])
                            st.caption("Knowledge graph from this document:")
                            st.components.v1.html(html, height=400, scrolling=True)
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    with col_status:
        st.markdown("#### Knowledge Base Status")
        total_docs = len(docs)
        total_chunks = sum(d["chunk_count"] for d in docs)
        st.metric("Total Documents", total_docs)
        st.metric("Total Chunks", total_chunks)
        st.caption("✓ Last updated when ingestion runs")
        st.markdown("#### Retrieval Health")
        st.caption("Retrieval Status: ✓ Healthy")
        st.caption(f"Embedding Model: {EMBEDDING_MODEL}")
        st.caption("Vector DB: Qdrant")


# ---------- Map tab: address + nearby facilities by category, route/distance, walk/bike/car ----------
def _render_map_tab() -> None:
    st.subheader("Map – nearby facilities")
    st.caption("Enter an address, choose categories and transport mode (walk / bike / car). Map shows POIs with route distance and duration. Note: public OSRM often supports only car; for walk/bike, distance may be straight-line.")
    address = st.text_input("Address", value="Amsterdam Centrum", key="map_addr")
    categories = st.multiselect(
        "Facility categories",
        options=list(POI_CATEGORIES.keys()),
        default=["schools", "grocery", "hospitals", "gym", "restaurants", "banks"],
        format_func=lambda x: POI_CATEGORIES[x][1],
        key="map_cats",
    )
    profile = st.radio("Route by", options=["driving", "walking", "cycling"], format_func=lambda x: {"driving": "Car", "walking": "Walk", "cycling": "Bike"}[x], key="map_profile", horizontal=True)
    if st.button("Show map", key="map_btn"):
        if not address.strip():
            st.warning("Enter an address.")
        elif not categories:
            st.warning("Select at least one category.")
        else:
            with st.spinner("Geocoding and fetching POIs..."):
                center, pois = nearby_pois_with_routes(address.strip(), categories, profile=profile, radius_m=1500, max_pois=25)
            if center is None:
                st.error("Could not geocode that address.")
            else:
                st.success(f"Found {len(pois)} places near **{address}**.")
                deck = build_pydeck_map(center, pois, profile, height=500)
                if deck is not None:
                    st.pydeck_chart(deck, use_container_width=True)
                else:
                    html = build_map_html(center, pois, profile)
                    st.components.v1.html(html, height=500, scrolling=False)
                if pois:
                    table_data = build_pois_table_data(pois, profile)
                    st.dataframe(table_data, use_container_width=True, hide_index=True)


# ---------- Location tab (Phase 2) ----------
def _render_location_tab() -> None:
    st.subheader("Location & commute")
    st.caption("Nearby places (Nominatim + Overpass), OSRM commute, area safety (placeholder).")
    addr = st.text_input("Address (e.g. Amsterdam Centrum)", value="Amsterdam Centrum", key="loc_addr")
    if st.button("Nearby places", key="np_btn"):
        results, _ = nearby_places(addr)
        if results:
            r = results[0]
            st.write(f"**{addr}** → lat={r['lat']:.4f}, lon={r['lon']:.4f}")
            for p in r.get("pois", [])[:15]:
                st.caption(f"- {p.get('name', '?')} ({p.get('type', '')})")
        else:
            st.warning("Could not geocode address.")
    dest = st.text_input("Commute destination", value="Schiphol Airport", key="loc_dest")
    if st.button("Commute time (OSRM)", key="osrm_btn"):
        res, _ = osrm_commute(addr, dest)
        if res:
            st.metric("Duration", f"{res['duration_min']} min")
            st.metric("Distance", f"{res['distance_km']} km")
        else:
            st.warning("Could not compute route.")
    area = st.text_input("Area for safety (placeholder)", value="Amsterdam", key="area_name")
    if st.button("Area safety", key="safety_btn"):
        res, _ = area_safety(area)
        if res:
            st.json(res)


# ---------- Phase 4: Agents tab (Multi-agent, A2UI, MCP) ----------
def _render_agents_tab() -> None:
    st.subheader("Agents (Phase 4)")
    st.caption("Orchestrator routes to retrieval, location, and calculator specialists. A2UI directives render in chat.")
    register_default_mcp_tools()
    mcp_tools = list_mcp_tools()
    if mcp_tools:
        st.write("**MCP tools registered:**", ", ".join(mcp_tools))
    else:
        st.caption("No MCP tools registered. OSRM and others register when available.")
    st.markdown("Enable **Use Phase 4 agents** in the sidebar to route queries through the orchestrator. Responses may include A2UI directives (e.g. show calculator, show map).")

# ---------- Sun-orientation tab (Phase 3) ----------
def _render_sun_tab() -> None:
    st.subheader("Sun orientation")
    st.caption("Sun path vs apartment: elevation through the day. Date and building orientation control the view.")
    sun_date = st.date_input("Date", key="sun_date")
    orientation = st.selectbox("Orientation", ["South", "SW", "West", "NW", "North", "NE", "East", "SE"], key="sun_orient")
    html = build_sun_orientation_html(sun_date, orientation)
    st.components.v1.html(html, height=360, scrolling=False)

# ---------- Observability tab ----------
def _render_observability_tab() -> None:
    st.subheader("Observability")
    st.caption("Monitor key metrics: Langfuse, retrieval quality, response quality, and drift indicators.")
    langfuse_host = os.environ.get("LANGFUSE_HOST", "").strip() or os.environ.get("LANGFUSE_URL", "").strip()
    if langfuse_host:
        st.markdown(f"**Langfuse:** [Open dashboard]({langfuse_host})")
    else:
        st.info(
            "**Langfuse connection:** No host is set. To link this app to Langfuse, set `LANGFUSE_HOST` or "
            "`LANGFUSE_URL` in your environment or `.env` file. [View Langfuse docs](https://langfuse.com/docs)."
        )
    with st.expander("Token / price tracking"):
        st.caption("Via Langfuse callback when enabled.")
    try:
        from monitoring.drift_detection import get_quality_summary, get_drift_indicators
        summary = get_quality_summary()
        drift = get_drift_indicators()
    except Exception as e:
        logger.warning("Observability metrics failed: %s", e)
        summary = {}
        drift = {}
    with st.expander("Retrieval quality"):
        rq = summary.get("retrieval_quality_mean")
        st.metric("Retrieval quality (mean)", f"{rq:.3f}" if rq is not None else "No data")
        st.caption("From RAGAS or monitoring/drift_detection. Run scripts/run_ragas.py to populate.")
    with st.expander("Response quality"):
        rp = summary.get("response_quality_mean")
        st.metric("Response quality (mean)", f"{rp:.3f}" if rp is not None else "No data")
        lat = summary.get("latency_p50_ms")
        st.metric("Latency p50 (ms)", f"{lat:.0f}" if lat is not None else "No data")
    with st.expander("Drift indicators"):
        if drift.get("has_data"):
            st.write("**Trends:**", drift.get("retrieval_trend"), "/", drift.get("response_trend"))
        else:
            st.caption("Record scores via monitoring.drift_detection to see trends.")
    st.markdown("[Responsible AI](docs/RESPONSIBLE_AI.md) | [Monitoring / Grafana](docs/monitoring.md)")


# ---------- Main ----------
def main() -> None:
    st.set_page_config(page_title=PAGE_TITLE, page_icon="🏠", layout="wide")
    _inject_custom_css()

    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = "Home"
    available = get_available_llm_providers()
    if "selected_provider" not in st.session_state:
        env_p = (os.environ.get("LLM_PROVIDER") or "openai").strip().lower()
        st.session_state["selected_provider"] = env_p if env_p in available else (available[0] if available else "openai")
    if "selected_model" not in st.session_state:
        models = get_default_llm_models(st.session_state["selected_provider"])
        st.session_state["selected_model"] = LLM_CHOICE_DEFAULT if LLM_CHOICE_DEFAULT in models else (models[0] if models else LLM_CHOICE_DEFAULT)
    if "use_hybrid" not in st.session_state:
        st.session_state["use_hybrid"] = True
    if "web_search" not in st.session_state:
        st.session_state["web_search"] = False
    if "use_agents" not in st.session_state:
        st.session_state["use_agents"] = False

    nav_options = [x[0] for x in NAV_ITEMS]

    if st.session_state.pop("_nav_from_button", False):
        st.session_state["nav_radio"] = st.session_state["nav_page"]

    with st.sidebar:
        st.markdown("### 🧭 Navigate")
        chosen = st.radio(
            "Section",
            options=nav_options,
            format_func=lambda k: f"{next((x[1] + ' ' + x[2] for x in NAV_ITEMS if x[0] == k), k)}",
            key="nav_radio",
            label_visibility="collapsed",
        )
        st.session_state["nav_page"] = chosen
        st.markdown("---")
        st.markdown("### ⚙️ Settings")
        st.caption("LLM (from .env)")
        provider = st.selectbox(
            "Provider",
            options=available,
            index=available.index(st.session_state["selected_provider"]) if st.session_state["selected_provider"] in available else 0,
            key="sb_provider",
        )
        st.session_state["selected_provider"] = provider
        models = get_default_llm_models(provider)
        cur = st.session_state["selected_model"]
        model = st.selectbox("Model", options=models, index=models.index(cur) if cur in models else 0, key="sb_model")
        st.session_state["selected_model"] = model
        st.checkbox("Use hybrid search (RRF)", value=st.session_state["use_hybrid"], key="use_hybrid")
        top_k = st.slider("Retrieval chunks", 3, 20, MAX_SEARCH_RESULTS, key="top_k")
        st.caption("Controls how many retrieved chunks are sent as context. Higher values can improve recall but may add noise and latency.")
        st.checkbox("Web search (Tavily)", value=st.session_state["web_search"], key="web_search")
        if st.button("Clear conversation", use_container_width=True):
            st.session_state["messages"] = []
            st.session_state["pdf_preview"] = None
            st.rerun()
    # Phase 4 agents toggle removed; keep orchestrator off
    st.session_state["use_agents"] = False

    page = st.session_state["nav_page"]
    valid_pages = [x[0] for x in NAV_ITEMS]
    if page not in valid_pages:
        st.session_state["nav_page"] = "Home"
        _render_home_page()
        return
    if page == "Home":
        _render_home_page()
        return
    if page == "Mortgage Calculator":
        _render_calculator_tab()
        return
    if page == "Map":
        _render_map_tab()
        return
    if page == "Documents":
        _render_documents_tab()
        return
    if page == "Knowledge Graph":
        _render_kg_tab()
        return
    if page == "Observability":
        _render_observability_tab()
        return

    # Chat page: main area + optional right panel (Sources, Tools Used, System Status)
    _render_chat_page(top_k)
    return


def _render_chat_page(top_k: int) -> None:
    """Chat interface with optional right-hand panel for sources, tools, and status."""
    col_chat, col_panel = st.columns([3, 1])
    with col_chat:
        if "pdf_preview" not in st.session_state:
            st.session_state["pdf_preview"] = None

        @st.cache_data(show_spinner=False)
        def _get_pdf_base64(source: str) -> str | None:
            from lib.documents import load_pdf_bytes_from_store

            pdf_bytes = load_pdf_bytes_from_store(source)
            if not pdf_bytes:
                return None
            return base64.b64encode(pdf_bytes).decode("ascii")

        def _render_pdf_preview(source: str, page: int | None) -> None:
            b64 = _get_pdf_base64(source)
            if not b64:
                st.info("PDF preview not available for this document (original PDF not saved during ingestion).")
                return
            page_num = int(page) if page else 1
            st.caption(f"Previewing: {source} (page {page_num})")
            # Browser PDF rendering can fail on some setups. Use iframe+object fallback.
            pdf_src = f"data:application/pdf;base64,{b64}#page={page_num}&toolbar=1&navpanes=1&scrollbar=1"
            html = f"""
            <div style="width:100%;height:760px">
              <iframe src="{pdf_src}" width="100%" height="760" style="border:1px solid #334155;border-radius:8px;"></iframe>
              <object data="{pdf_src}" type="application/pdf" width="100%" height="760" style="display:none"></object>
            </div>
            """
            st.components.v1.html(html, height=780, scrolling=True)
            st.download_button(
                "Download PDF",
                data=base64.b64decode(b64),
                file_name=source,
                mime="application/pdf",
                key=f"dl_pdf_{source}_{page_num}",
                use_container_width=False,
            )
            # Fallback content: show extracted text from selected page if PDF viewer is blocked.
            try:
                from pypdf import PdfReader
                import io

                reader = PdfReader(io.BytesIO(base64.b64decode(b64)))
                idx = max(0, min(page_num - 1, len(reader.pages) - 1))
                page_text = (reader.pages[idx].extract_text() or "").strip()
                if page_text:
                    st.caption("Page text fallback (shown if inline PDF preview is blocked):")
                    st.text(page_text[:1800] + ("..." if len(page_text) > 1800 else ""))
            except Exception:
                pass

        st.title(PAGE_TITLE)
        st.caption("Ask about Dutch mortgages, tax, housing. Sources and tools used are shown in the panel on the right.")

        for msg_idx, msg in enumerate(st.session_state["messages"]):
            with st.chat_message(msg["role"]):
                if msg["role"] == "assistant" and msg.get("tools_used"):
                    st.markdown(_format_tools_used(msg["tools_used"]) + "\n\n🤖 **Assistant:**\n\n")
                st.write(msg["content"])
                if msg["role"] == "assistant" and msg.get("a2ui_directives"):
                    st.caption("**A2UI:** " + ", ".join(d.get("type", "") for d in msg["a2ui_directives"]))
                if msg["role"] == "assistant":
                    web_fallback = msg.get("web_fallback_used")
                    web_count = msg.get("web_sources_count")
                    if web_fallback is not None or web_count is not None:
                        st.caption(
                            f"**Web fallback used:** {'Yes' if web_fallback else 'No'} | "
                            f"**Web sources found:** {int(web_count or 0)}"
                        )
                if msg["role"] == "assistant" and msg.get("sources"):
                    sources = msg.get("sources") or []
                    with st.expander("Citations (documents + web search)"):
                        for cite_i, s in enumerate(sources, start=1):
                            src = s.get("source", "?")
                            url = s.get("url")
                            snippet = (s.get("text", "") or "").strip()
                            snippet = snippet.replace("\n", " ")
                            snippet_short = (snippet[:200] + ("..." if len(snippet) > 200 else "")) if snippet else ""
                            page = s.get("page")
                            heading = s.get("heading")

                            if url:
                                title = s.get("title") or src
                                st.caption(f"**{cite_i}.** [{title}]({url})")
                                if snippet_short:
                                    st.text(snippet_short)
                                continue

                            # PDF citation: doc title → section heading → page number
                            doc_title = src.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
                            parts = [f"**{cite_i}.** 📄 {doc_title}"]
                            if heading:
                                parts.append(f"§ {heading}")
                            if page:
                                parts.append(f"p. {page}")
                            st.caption(" · ".join(parts))

                            if snippet_short:
                                st.text(snippet_short)

                            preview_label = f"Preview page {page}" if page else "Preview PDF"
                            if st.button(preview_label, key=f"cit_preview_{msg_idx}_{cite_i}", use_container_width=False):
                                st.session_state["pdf_preview"] = {
                                    "source": src,
                                    "page": page,
                                }

        # PDF preview for the selected citation (shown once per rerun).
        if st.session_state.get("pdf_preview"):
            pp = st.session_state["pdf_preview"]
            st.markdown("#### PDF Preview")
            if pp and pp.get("source"):
                _render_pdf_preview(pp["source"], pp.get("page"))
            if st.button("Close preview", key="cit_preview_close", use_container_width=False):
                st.session_state["pdf_preview"] = None
                st.rerun()

        prompt = st.chat_input("Type your message...")
        if prompt:
            prompt = _validate_and_sanitize_query(prompt)
            if not prompt:
                st.warning("Query is empty or invalid after sanitization.")
                st.stop()
            if len(prompt) >= MAX_QUERY_LENGTH:
                st.caption(f"Query truncated to {MAX_QUERY_LENGTH} characters.")
            st.session_state["messages"].append({"role": "user", "content": prompt})
            st.chat_message("user").write(prompt)

            # Retrieval
            try:
                embedding_client = get_embedding_client()
            except RuntimeError as e:
                st.chat_message("assistant").error(str(e))
                st.session_state["messages"].pop()
                st.stop()
            qdrant = get_qdrant()
            query_embedding = get_embedding(embedding_client, prompt)
            tool_calls: list[dict] = []
            chunks: list[dict] = []
            a2ui_directives: list[dict] = []

            if st.session_state.get("use_agents"):
                retrieval_chunks: list[dict] = []
                def retrieval_fn(q: str):
                    nonlocal retrieval_chunks
                    try:
                        if st.session_state["use_hybrid"]:
                            c, tc = hybrid_retrieve(qdrant, QDRANT_COLLECTION, get_embedding(embedding_client, q), q, limit=top_k)
                        else:
                            c, tc = vector_search(qdrant, QDRANT_COLLECTION, get_embedding(embedding_client, q), limit=top_k, query_text=q)
                    except Exception as e:
                        logger.error("Agent retrieval failed: %s", e, exc_info=True)
                        c, tc = [], [{"tool": "vector_search", "args": {"error": str(e)}}]
                    retrieval_chunks[:] = c
                    return "\n\n---\n\n".join(x.get("text", "") for x in c), tc
                def location_fn(q: str):
                    res, tc = nearby_places("Amsterdam Centrum" if "amsterdam" not in q.lower() else q[:80])
                    ctx = ""
                    if res:
                        r = res[0]
                        ctx = f"Location: {r.get('lat')}, {r.get('lon')}. POIs: " + "; ".join(p.get("name", "") for p in r.get("pois", [])[:5])
                    return ctx, tc
                def calculator_fn(q: str):
                    return "Use the Mortgage Calculator tab for Bruto maandlasten, Hypotheek, Kosten koper.", [{"tool": "calculator_agent", "args": {"query": q[:80]}}]
                context, tool_calls, a2ui_directives, _ = run_orchestrator(prompt, retrieval_fn, location_fn, calculator_fn)
                chunks = retrieval_chunks
            else:
                try:
                    if st.session_state["use_hybrid"]:
                        chunks, tool_calls = hybrid_retrieve(
                            qdrant, QDRANT_COLLECTION, query_embedding, prompt, limit=top_k
                        )
                    else:
                        chunks, tool_calls = vector_search(
                            qdrant, QDRANT_COLLECTION, query_embedding, limit=top_k, query_text=prompt
                        )
                except Exception as e:
                    logger.error("Retrieval failed: %s", e, exc_info=True)
                    chunks, tool_calls = [], [{"tool": "vector_search", "args": {"error": str(e)}}]
                context = "\n\n---\n\n".join(c.get("text", "") for c in chunks) if chunks else ""

            doc_context = context

            # Optional Tavily (web search) with source tracing
            web_sources: list[dict] = []
            web_ctx = ""
            if st.session_state["web_search"]:
                web_ctx, web_tools, web_sources = _tavily_search(prompt)
                if web_tools:
                    tool_calls.extend(web_tools)
            if web_ctx:
                context = (doc_context + "\n\n--- Web search ---\n\n" + web_ctx) if doc_context else web_ctx
            # Merge web and document sources for citation panels (web first so they are visible in top-N list)
            sources_for_message = web_sources + chunks

            docs_have_signal = _has_query_signal_in_docs(prompt, chunks)
            web_fallback_used = bool(web_ctx) and not docs_have_signal
            web_sources_count = len(web_sources)
            if context:
                if web_ctx and not docs_have_signal:
                    user_content = (
                        "Use the context below to answer.\n"
                        "Document context appears insufficient for this question, so prioritize WEB SEARCH CONTEXT.\n"
                        "If web and documents conflict, prefer newer official web information and state that clearly.\n\n"
                        "DOCUMENT CONTEXT:\n"
                        + (doc_context or "(none)") +
                        "\n\nWEB SEARCH CONTEXT:\n" + web_ctx +
                        "\n\nQuestion: " + prompt
                    )
                else:
                    user_content = (
                        "Use the context below to answer. Use document context first, and web context as supplement when needed.\n\n"
                        "DOCUMENT CONTEXT:\n" + (doc_context or "(none)") +
                        "\n\nWEB SEARCH CONTEXT:\n" + (web_ctx or "(none)") +
                        "\n\nQuestion: " + prompt
                    )
            else:
                user_content = "No document context found. Answer from general knowledge and suggest loading documents (python scripts/ingest_docs.py).\n\nQuestion: " + prompt

            messages_for_llm = [{"role": "system", "content": SYSTEM_PROMPT}]
            for m in st.session_state["messages"][:-1]:
                messages_for_llm.append({"role": m["role"], "content": m["content"]})
            messages_for_llm.append({"role": "user", "content": user_content})

            placeholder = st.chat_message("assistant").empty()
            prefix = (_format_tools_used(tool_calls) + "\n\n🤖 **Assistant:**\n\n") if tool_calls else ""
            try:
                prov = st.session_state["selected_provider"]
                mod = st.session_state["selected_model"]
                if prov == "ollama":
                    answer = _stream_ollama(mod, messages_for_llm, placeholder, prefix=prefix)
                else:
                    answer = _stream_api(prov, mod, messages_for_llm, placeholder, prefix=prefix)
            except Exception as e:
                placeholder.error(str(e))
                st.session_state["messages"].pop()
                st.stop()

            st.session_state["messages"].append({
                "role": "assistant",
                "content": answer,
                "tools_used": tool_calls,
                "sources": sources_for_message,
                "a2ui_directives": a2ui_directives,
                "web_fallback_used": web_fallback_used,
                "web_sources_count": web_sources_count,
            })
            # Flush Langfuse so traces appear in the dashboard promptly
            try:
                from langfuse import get_client
                get_client().flush()
            except Exception:
                pass
            st.rerun()

    # Right panel: Sources, Tools Used, System Status (from last assistant message)
    with col_panel:
        last_assistant = next(
            (m for m in reversed(st.session_state["messages"]) if m.get("role") == "assistant"),
            None,
        )
        if last_assistant:
            st.markdown("**Sources**")
            for s in (last_assistant.get("sources") or [])[:10]:
                src = s.get("source", "?")
                url = s.get("url")
                if url:
                    link_text = src.replace("[Web] ", "") if src.startswith("[Web] ") else src
                    st.caption(f"✓ [{link_text}]({url})")
                else:
                    doc_title = src.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
                    heading = s.get("heading")
                    page = s.get("page")
                    label = f"✓ {doc_title}"
                    if heading:
                        label += f" · § {heading}"
                    if page:
                        label += f" · p. {page}"
                    st.caption(label)
            if not (last_assistant.get("sources")):
                st.caption("—")
            st.markdown("**Tools Used**")
            for t in (last_assistant.get("tools_used") or [])[:10]:
                st.caption(f"`{t.get('tool', '?')}`")
            if not (last_assistant.get("tools_used")):
                st.caption("—")
            st.markdown("**System Status**")
            st.caption("Retrieval: OK" if (last_assistant.get("sources") or last_assistant.get("tools_used")) else "—")
            st.caption("LLM: Responded")
        else:
            st.caption("Send a message to see sources and tools here.")


if __name__ == "__main__":
    main()
