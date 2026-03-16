# Responsible AI – Expat NL Mortgage RAG

This document describes traceability, transparency, and oversight for the RAG assistant.

## Traceability

- **Tools Used** are shown per chat turn (vector_search, hybrid_retrieve, tavily_search, etc.) so users can see which data sources were used.
- **Sources** (citations) are expandable per turn; document and chunk provenance is stored.
- **Observability** tab links to Langfuse (when configured) for full trace and token/cost tracking.
- **RAG evals** (Phase 3) log retrieval and response quality scores for monitoring.

## Transparency

- Model and provider (OpenAI, OpenRouter, Ollama) are selectable in the sidebar and driven by `.env`.
- System prompt and context assembly are explicit in code; no hidden overrides.
- Calculator and location tools use documented formulas or public APIs (OSRM, Nominatim, Overpass).

## Oversight and monitoring

- **Retrieval quality** and **Response quality** sections in Observability surface metrics (from RAGAS/Phoenix or Langfuse when available).
- **Drift indicators** (Phase 3) highlight trends in quality over time; optional `monitoring/drift_detection.py` persists scores.
- **Prometheus /metrics** and Grafana (Phase 3) support operational monitoring (latency, errors, tool usage).

## Limitations

- The assistant is for informational support only; it does not provide legal or financial advice.
- Users are directed to official sources (e.g. Belastingdienst, mortgage advisors) when context is insufficient.
- Web search (Tavily) and document context can be outdated; critical decisions should be verified with up-to-date sources.
