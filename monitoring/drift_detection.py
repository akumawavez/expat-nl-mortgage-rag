"""
Phase 3: Simple drift detection – track input/output stats and flag significant changes.

Optional: use with Observability tab to show drift indicators.
Scores can be stored in a JSON file or in-memory for demo.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Default path for persistence (optional)
METRICS_FILE = Path(__file__).resolve().parent.parent / "data" / "rag_metrics.json"


def load_metrics() -> dict[str, Any]:
    if METRICS_FILE.exists():
        try:
            return json.loads(METRICS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "retrieval_scores": [],
        "response_scores": [],
        "request_latencies_ms": [],
        "tool_usage_counts": {},
    }


def save_metrics(metrics: dict[str, Any]) -> None:
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    METRICS_FILE.write_text(json.dumps(metrics, indent=2), encoding="utf-8")


def record_retrieval_score(score: float) -> None:
    m = load_metrics()
    m["retrieval_scores"] = (m.get("retrieval_scores") or [])[-99:] + [score]
    save_metrics(m)


def record_response_score(score: float) -> None:
    m = load_metrics()
    m["response_scores"] = (m.get("response_scores") or [])[-99:] + [score]
    save_metrics(m)


def record_latency_ms(ms: float) -> None:
    m = load_metrics()
    m["request_latencies_ms"] = (m.get("request_latencies_ms") or [])[-199:] + [ms]
    save_metrics(m)


def record_tool_use(tool_name: str) -> None:
    m = load_metrics()
    counts = m.get("tool_usage_counts") or {}
    counts[tool_name] = counts.get(tool_name, 0) + 1
    m["tool_usage_counts"] = counts
    save_metrics(m)


def get_drift_indicators() -> dict[str, Any]:
    """Return simple drift indicators: mean of recent vs older scores (if enough data)."""
    m = load_metrics()
    out = {"has_data": False, "retrieval_trend": None, "response_trend": None}
    rs = m.get("retrieval_scores") or []
    rps = m.get("response_scores") or []
    if len(rs) >= 10:
        out["has_data"] = True
        mid = len(rs) // 2
        out["retrieval_trend"] = "up" if sum(rs[mid:]) / len(rs[mid:]) > sum(rs[:mid]) / mid else "stable_or_down"
    if len(rps) >= 10:
        out["has_data"] = True
        mid = len(rps) // 2
        out["response_trend"] = "up" if sum(rps[mid:]) / len(rps[mid:]) > sum(rps[:mid]) / mid else "stable_or_down"
    return out


def get_quality_summary() -> dict[str, Any]:
    m = load_metrics()
    rs = m.get("retrieval_scores") or []
    rps = m.get("response_scores") or []
    lat = m.get("request_latencies_ms") or []
    return {
        "retrieval_quality_mean": sum(rs) / len(rs) if rs else None,
        "response_quality_mean": sum(rps) / len(rps) if rps else None,
        "latency_p50_ms": sorted(lat)[len(lat) // 2] if lat else None,
        "tool_usage": m.get("tool_usage_counts") or {},
    }
