"""In-process request/agent metrics with Prometheus text exposition (spec §46).

Stdlib-only by design — the project dependency policy requires explicit
approval for third-party packages, so this hand-rolls the exposition format
instead of pulling in ``prometheus_client``.

Thread-safe: FastAPI serves requests from a thread pool and the async
analysis runs in background tasks.
"""

from __future__ import annotations

import threading
from collections import defaultdict

# Fixed histogram buckets (seconds) covering sub-ms health probes up to slow
# LLM-backed agent runs (§45 latency budget).
BUCKETS: tuple[float, ...] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)

_lock = threading.Lock()
_requests: dict[tuple[str, str, str], int] = defaultdict(int)  # (method, route, status)
_http_hist: dict[str, list[float]] = {}  # route -> [bucket counts..., sum, count]
_agent_runs: dict[tuple[str, str], int] = defaultdict(int)  # (task, status)
_agent_hist: dict[str, list[float]] = {}  # task -> [bucket counts..., sum, count]


def _observe(hist: dict[str, list[float]], key: str, seconds: float) -> None:
    row = hist.get(key)
    if row is None:
        row = [0.0] * (len(BUCKETS) + 2)  # buckets + sum + count
        hist[key] = row
    for i, bound in enumerate(BUCKETS):
        if seconds <= bound:
            row[i] += 1.0
    row[-2] += seconds
    row[-1] += 1.0


def record_request(method: str, route: str, status: int, duration_seconds: float) -> None:
    """Record one completed HTTP request (``route`` is the path template)."""
    with _lock:
        _requests[(method, route, str(status))] += 1
        _observe(_http_hist, route, duration_seconds)


def record_agent_run(task: str, status: str, duration_seconds: float) -> None:
    """Record one agent execution (sync runs + async background executions)."""
    with _lock:
        _agent_runs[(task, status)] += 1
        _observe(_agent_hist, task, duration_seconds)


def reset() -> None:
    """Clear every metric (tests only)."""
    with _lock:
        _requests.clear()
        _http_hist.clear()
        _agent_runs.clear()
        _agent_hist.clear()


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _render_counter(
    name: str, help_text: str, rows: list[tuple[dict[str, str], int]]
) -> list[str]:
    lines = [f"# HELP {name} {help_text}", f"# TYPE {name} counter"]
    for labels, value in rows:
        label_str = ",".join(f'{k}="{_escape(v)}"' for k, v in sorted(labels.items()))
        lines.append(f"{name}{{{label_str}}} {value}")
    return lines


def _render_histogram(
    name: str, help_text: str, hist: dict[str, list[float]], label_key: str
) -> list[str]:
    lines = [f"# HELP {name} {help_text}", f"# TYPE {name} histogram"]
    for key in sorted(hist):
        row = hist[key]
        base = f'{label_key}="{_escape(key)}"'
        for i, bound in enumerate(BUCKETS):
            lines.append(f'{name}_bucket{{{base},le="{bound}"}} {row[i]:g}')
        lines.append(f'{name}_bucket{{{base},le="+Inf"}} {row[-1]:g}')
        lines.append(f"{name}_sum{{{base}}} {row[-2]:g}")
        lines.append(f"{name}_count{{{base}}} {row[-1]:g}")
    return lines


def render() -> str:
    """Render every metric in Prometheus text exposition format (0.0.4)."""
    with _lock:
        request_rows = [
            ({"method": m, "route": r, "status": s}, n)
            for (m, r, s), n in sorted(_requests.items())
        ]
        agent_rows = [
            ({"task": t, "status": st}, n) for (t, st), n in sorted(_agent_runs.items())
        ]
        http_hist = {k: list(v) for k, v in _http_hist.items()}
        agent_hist = {k: list(v) for k, v in _agent_hist.items()}

    lines: list[str] = []
    lines += _render_counter(
        "dtck_http_requests_total",
        "HTTP requests handled by the API, by method, route and status.",
        request_rows,
    )
    lines += _render_histogram(
        "dtck_http_request_duration_seconds",
        "HTTP request latency in seconds, by route.",
        http_hist,
        "route",
    )
    lines += _render_counter(
        "dtck_agent_runs_total",
        "Agent executions, by task and final status.",
        agent_rows,
    )
    lines += _render_histogram(
        "dtck_agent_duration_seconds",
        "Agent execution latency in seconds, by task.",
        agent_hist,
        "task",
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "BUCKETS",
    "record_agent_run",
    "record_request",
    "render",
    "reset",
]
