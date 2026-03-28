# RAG Monitoring – Prometheus & Grafana

## /metrics endpoint

A separate metrics server exposes Prometheus-format metrics for RAG (request count, latency, errors, tool usage).

### Run the metrics server

```bash
# From project root
pip install prometheus-client fastapi uvicorn
python scripts/metrics_server.py
# Or: uvicorn scripts.metrics_server:app --host 0.0.0.0 --port 9090
```

Default port: **9090**. Override with `METRICS_PORT=9091`.

### Endpoints

- **GET http://localhost:9090/metrics** – Prometheus scrape target
- **GET http://localhost:9090/health** – Health check (when using FastAPI)

### Metrics (examples)

| Metric | Type | Description |
|--------|------|-------------|
| `rag_requests_total` | Counter | Total RAG requests by tool (vector_search, hybrid_retrieve, etc.) |
| `rag_request_latency_seconds` | Histogram | Request latency by tool |
| `rag_errors_total` | Counter | Errors by tool |

The app can increment these via the same names when using the metrics server (e.g. by HTTP calls to a small API or by sharing the same process). For a separate Streamlit app, instrument the app to push metrics to a gateway or run the metrics server in the same process and expose it (e.g. on a different port).

## Prometheus scrape config

Add to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'rag'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 15s
```

## Grafana dashboard

1. Add Prometheus as a data source (URL: `http://localhost:9090` or your Prometheus server).
2. Create a dashboard with panels for:
   - **Latency**: `histogram_quantile(0.5, rate(rag_request_latency_seconds_bucket[5m]))` (p50), same for p95.
   - **Request rate**: `rate(rag_requests_total[5m])` by tool.
   - **Errors**: `rate(rag_errors_total[5m])` by tool.
   - **Retrieval quality**: if you expose a gauge from RAGAS scores (e.g. `rag_retrieval_quality`), add a panel for it.

A JSON export of a minimal dashboard can be stored in `docs/grafana_rag_dashboard.json` for import into Grafana.
