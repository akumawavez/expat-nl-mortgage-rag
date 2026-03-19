"""
Phase 3: Prometheus /metrics endpoint for RAG (latency, tool usage, errors).

Run alongside or separately from Streamlit:
  python scripts/metrics_server.py
  # or: uvicorn scripts.metrics_server:app --host 0.0.0.0 --port 9090

GET http://localhost:9090/metrics returns Prometheus format.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST  # noqa: E402

# Try FastAPI for /metrics; fallback to plain WSGI
try:
    from fastapi import FastAPI
    from fastapi.responses import Response
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# Prometheus metrics
REQUEST_COUNT = Counter("rag_requests_total", "Total RAG requests", ["tool"])
REQUEST_LATENCY = Histogram("rag_request_latency_seconds", "RAG request latency", ["tool"], buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0))
ERROR_COUNT = Counter("rag_errors_total", "Total RAG errors", ["tool"])


def get_metrics_body() -> bytes:
    return generate_latest()


if HAS_FASTAPI:
    app = FastAPI(title="Expat NL Mortgage RAG Metrics")

    @app.get("/metrics")
    def metrics():
        return Response(content=get_metrics_body(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    def main():
        import uvicorn
        port = int(os.environ.get("METRICS_PORT", "9090"))
        uvicorn.run(app, host="0.0.0.0", port=port)
else:
    def main():
        from wsgiref.simple_server import make_server
        def metrics_app(environ, start_response):
            if environ.get("PATH_INFO") == "/metrics":
                start_response("200 OK", [("Content-Type", CONTENT_TYPE_LATEST)])
                return [get_metrics_body()]
            start_response("404 Not Found", [])
            return [b"Not Found"]
        port = int(os.environ.get("METRICS_PORT", "9090"))
        with make_server("", port, metrics_app) as httpd:
            print(f"Metrics at http://localhost:{port}/metrics")
            httpd.serve_forever()


if __name__ == "__main__":
    main()
