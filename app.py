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
from lib.documents import list_documents_in_store, upsert_pdf_to_qdrant
from lib.agents import run_orchestrator
from lib.mcp_client import list_mcp_tools, register_default_mcp_tools

import dotenv
dotenv.load_dotenv(Path(__file__).resolve().parent / ".env")

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
PAGE_TITLE = "Expat NL Mortgage Assistant (Phase 1)"
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
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


def _tavily_search(query: str, max_results: int = 5) -> tuple[str, list[dict]]:
    """Return (context_string, tool_calls_for_ui). If no key or error, returns ('', [])."""
    if not os.environ.get("TAVILY_API_KEY"):
        return "", []
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        response = client.search(query, max_results=max_results)
        results = getattr(response, "results", response) if hasattr(response, "results") else []
        if isinstance(results, list):
            parts = []
            for r in results:
                title = r.get("title", "")
                url = r.get("url", "")
                content = r.get("content", "")
                if content:
                    parts.append(f"[{title}]({url})\n{content}")
            return "\n\n".join(parts), [{"tool": "tavily_search", "args": {"query": query[:80]}}]
    except Exception as e:
        logger.warning("Tavily web search failed: %s", e, exc_info=True)
    return "", []


def _format_tools_used(tool_calls: list[dict]) -> str:
    lines = []
    for i, tc in enumerate(tool_calls, 1):
        name = tc.get("tool", "?")
        args = tc.get("args", {})
        args_str = ", ".join(f"{k}={repr(v)}" for k, v in args.items())
        lines.append(f"  {i}. {name} ({args_str})")
    return "🛠 **Tools Used:**\n" + "\n".join(lines) if lines else ""


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
    st.subheader("Mortgage calculator (ING-style)")
    st.warning(
        "**Disclaimer:** All values are placeholder estimates only (e.g. ~0.45% monthly interest, ~6% costs). "
        "Do not use for real financial decisions. Consult a mortgage advisor for accurate numbers."
    )
    st.caption("Bid, eigen inleg, type woning, energielabel → Bruto maandlasten, Hypotheek, Kosten koper")
    bid = st.number_input("Bod / aankoopprijs (€)", min_value=50000, max_value=2_000_000, value=350000, step=10000)
    eigen_inleg = st.number_input("Eigen inleg (€)", min_value=0, max_value=bid, value=35000, step=5000)
    hypotheek = bid - eigen_inleg
    _type_woning = st.selectbox("Type woning", ["Bestaande koopwoning", "Nieuwbouw", "Bouwkavel"])
    _energielabel = st.selectbox("Energielabel", ENERGIELABELS)
    # Simplified: no real ING formula; show placeholder outputs
    st.divider()
    st.metric("Hypotheek", f"€ {hypotheek:,}")
    # Bruto maandlasten: rough proxy (e.g. ~0.05/12 of hypotheek for interest-only idea; not real)
    maandlast_approx = round(hypotheek * 0.0045, 2)  # placeholder
    st.metric("Bruto maandlasten (indicatief)", f"€ {maandlast_approx:,.2f}")
    kk = round(bid * 0.06, 0)  # ~6% costs koper placeholder
    st.metric("Kosten koper (indicatief)", f"€ {kk:,.0f}")


# ---------- Knowledge Graph tab (Phase 2) ----------
def _render_kg_tab() -> None:
    st.subheader("Knowledge Graph")
    st.caption("Extract entities and relations from text; visualize with PyVis.")
    text = st.text_area("Text to build graph from", value=(
        "Mortgage interest deduction (hypotheekrenteaftrek) applies to owner-occupied homes. "
        "The Tax Authority (Belastingdienst) oversees tax returns. NHG provides guarantees for mortgages."
    ), height=120, key="kg_text")
    if st.button("Build graph", key="kg_build"):
        with st.spinner("Building graph..."):
            html = build_kg_from_text(text)
        st.components.v1.html(html, height=500, scrolling=True)
    else:
        html = build_kg_from_text("")
        st.components.v1.html(html, height=500, scrolling=True)


# ---------- Documents tab: list uploaded docs, upload new PDF to vector store (and optional KG) ----------
def _render_documents_tab() -> None:
    st.subheader("Documents in vector store & knowledge base")
    st.caption("Documents listed below are used for RAG retrieval. Upload a PDF to add it to the vector database (and optionally run KG extraction in the Knowledge Graph tab).")
    qdrant = get_qdrant()
    docs = list_documents_in_store(qdrant, QDRANT_COLLECTION)
    if docs:
        st.markdown("**Uploaded documents**")
        for d in docs:
            st.text(f"• {d['source']} — {d['chunk_count']} chunks")
    else:
        st.info("No documents in the vector store yet. Run scripts/ingest_docs.py or upload a PDF below.")
    st.divider()
    st.markdown("**Upload new document**")
    uploaded = st.file_uploader("Choose a PDF", type=["pdf"], key="doc_upload")
    add_to_kg = st.checkbox("Also run KG extraction and show in Knowledge Graph tab", value=False, key="doc_add_kg")
    if uploaded is not None and st.button("Ingest into vector store", key="doc_ingest"):
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
                st.success(f"Inserted {num} chunks for «{name}».")
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

# ---------- Observability tab (Phase 3) ----------
def _render_observability_tab() -> None:
    st.subheader("Observability")
    st.caption("Token/price, Langfuse, retrieval/response quality, and drift indicators.")
    langfuse_host = os.environ.get("LANGFUSE_HOST", "").strip() or os.environ.get("LANGFUSE_URL", "").strip()
    if langfuse_host:
        st.markdown(f"**Langfuse:** [Open dashboard]({langfuse_host})")
    else:
        st.info("Set LANGFUSE_HOST or LANGFUSE_URL in .env to link to Langfuse.")
    st.metric("Token / price tracking", "Via Langfuse callback when enabled")
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
        st.caption("From RAGAS/Phoenix or monitoring/drift_detection. Run scripts/run_ragas.py to populate.")
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

    if "messages" not in st.session_state:
        st.session_state["messages"] = []
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

    with st.sidebar:
        st.header("Settings")
        st.subheader("LLM (from .env)")
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
        st.checkbox("Web search (Tavily)", value=st.session_state["web_search"], key="web_search")
        st.checkbox("Use Phase 4 agents (orchestrator)", value=st.session_state["use_agents"], key="use_agents")
        if st.button("Clear conversation", use_container_width=True):
            st.session_state["messages"] = []
            st.rerun()

    tab_chat, tab_calc, tab_map, tab_docs, tab_kg, tab_loc, tab_sun, tab_obs, tab_agents = st.tabs(
        ["Chat", "Mortgage Calculator", "Map", "Documents", "Knowledge Graph", "Location", "Sun", "Observability", "Agents (P4)"]
    )
    with tab_calc:
        _render_calculator_tab()
    with tab_map:
        _render_map_tab()
    with tab_docs:
        _render_documents_tab()
    with tab_kg:
        _render_kg_tab()
    with tab_loc:
        _render_location_tab()
    with tab_sun:
        _render_sun_tab()
    with tab_obs:
        _render_observability_tab()
    with tab_agents:
        _render_agents_tab()

    with tab_chat:
        st.title(PAGE_TITLE)
        st.caption("Ask about Dutch mortgages, tax, housing. Tools Used and sources are shown per turn.")

        for msg in st.session_state["messages"]:
            with st.chat_message(msg["role"]):
                if msg["role"] == "assistant" and msg.get("tools_used"):
                    st.markdown(_format_tools_used(msg["tools_used"]) + "\n\n🤖 **Assistant:**\n\n")
                st.write(msg["content"])
                if msg["role"] == "assistant" and msg.get("a2ui_directives"):
                    st.caption("**A2UI:** " + ", ".join(d.get("type", "") for d in msg["a2ui_directives"]))
                if msg["role"] == "assistant" and msg.get("sources"):
                    with st.expander("Source tracing (documents used for this answer)"):
                        for s in msg["sources"]:
                            src = s.get("source", "?")
                            st.caption(f"**Document:** {src}")
                            st.text(s.get("text", "")[:500] + ("..." if len(s.get("text", "")) > 500 else ""))

        if prompt := st.chat_input("Ask about Dutch mortgages, tax, or housing..."):
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

            # Optional Tavily
            if st.session_state["web_search"]:
                web_ctx, web_tools = _tavily_search(prompt)
                if web_tools:
                    tool_calls.extend(web_tools)
                if web_ctx:
                    context = (context + "\n\n--- Web search ---\n\n" + web_ctx) if context else web_ctx

            if context:
                user_content = "Use the following context to answer. If not in context, say so.\n\nContext:\n" + context + "\n\nQuestion: " + prompt
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
                "sources": chunks,
                "a2ui_directives": a2ui_directives,
            })
            st.rerun()


if __name__ == "__main__":
    main()
