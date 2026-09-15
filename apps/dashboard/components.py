"""Pure-Python UI helpers for the Streamlit dashboard (T011).

All functions here are independent of Streamlit so they can be unit-tested
without a running display.  They take raw API response dicts and return
presentation-ready structures (lists, dicts, formatted strings).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

SIGNAL_LABELS: dict[str, str] = {
    "POSITIVE": "🟢 Tích cực",
    "NEUTRAL": "🟡 Trung tính",
    "NEGATIVE": "🔴 Tiêu cực",
}

SIGNAL_COLORS: dict[str, str] = {
    "POSITIVE": "green",
    "NEUTRAL": "orange",
    "NEGATIVE": "red",
}


def signal_label(signal: str) -> str:
    """Map a raw signal enum to a human-readable Vietnamese label."""
    return SIGNAL_LABELS.get(signal.upper(), signal)


def signal_color(signal: str) -> str:
    """Map a raw signal enum to a display color."""
    return SIGNAL_COLORS.get(signal.upper(), "gray")


def format_price(value: float | int | str | None) -> str:
    """Format a price as ``1 234.5`` with a leading non-breaking space."""
    if value is None:
        return "—"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{f:,.1f}".replace(",", "\xa0")


def format_percent(value: float | int | None, signed: bool = False) -> str:
    """Format a fraction as a percentage string."""
    if value is None:
        return "—"
    sign = "+" if signed and value >= 0 else ""
    return f"{sign}{value * 100:.1f}%"


def format_date(d: str | date | datetime | None) -> str:
    """Format a date/datetime as ``DD/MM/YYYY``."""
    if d is None:
        return "—"
    if isinstance(d, datetime):
        d = d.date()
    if isinstance(d, date):
        return d.strftime("%d/%m/%Y")
    if isinstance(d, str):
        try:
            return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            return d
    return str(d)


# ---------------------------------------------------------------------------
# Response → presentation transforms
# ---------------------------------------------------------------------------

def ranking_rows(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten ranking API responses into table rows."""
    rows: list[dict[str, Any]] = []
    for r in ranked:
        rows.append(
            {
                "rank": r.get("rank", 0),
                "symbol": r.get("symbol", ""),
                "overall_score": round(float(r.get("overall_score") or 0), 2),
                "signal": r.get("signal", "NEUTRAL"),
                "confidence": float(r.get("confidence", 0)),
            }
        )
    return rows


def contribution_rows(ranking: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract per-factor contribution rows from a single stock's ranking."""
    contribs: list[dict[str, Any]] = []
    for c in ranking.get("contributions", []):
        contribs.append(
            {
                "factor": c.get("factor", ""),
                "score": float(c.get("score") or 0),
                "weight": float(c.get("weight") or 0),
                "weighted": float(c.get("weighted_score") or 0),
                "share": c.get("contribution_pct"),
            }
        )
    return contribs


def price_dataframe(prices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return OHLCV rows ready for a dataframe / chart."""
    out: list[dict[str, Any]] = []
    for p in prices:
        out.append(
            {
                "date": format_date(p.get("trade_date")),
                "open": float(p.get("open") or 0),
                "high": float(p.get("high") or 0),
                "low": float(p.get("low") or 0),
                "close": float(p.get("close") or 0),
                "volume": int(p.get("volume") or 0),
            }
        )
    return out


def indicator_dict(indicators: dict[str, Any]) -> dict[str, float | None]:
    """Flatten an indicator response's 'series' sub-dict into scalars."""
    return {k: float(v) if v is not None else None for k, v in indicators.get("series", {}).items()}


def quality_bar_labels(quality: dict[str, Any]) -> dict[str, float]:
    """Return dimension → score mapping for a bar chart."""
    dims = quality.get("dimensions", {})
    return {k: float(v or 0) for k, v in dims.items()}


def metric_rows(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert a metrics list into table rows."""
    rows = []
    for m in metrics:
        rows.append({"metric": m.get("metric_name", ""),
                     "value": float(m.get("value") or 0)})
    return rows


def news_rows(news: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    """Format a news list into preview rows."""
    out: list[dict[str, Any]] = []
    for n in news[:limit]:
        out.append(
            {
                "title": n.get("title", ""),
                "source": n.get("source", ""),
                "published": format_date(n.get("published_at")),
            }
        )
    return out


__all__ = [
    "signal_label",
    "signal_color",
    "format_price",
    "format_percent",
    "format_date",
    "SIGNAL_LABELS",
    "SIGNAL_COLORS",
    "ranking_rows",
    "contribution_rows",
    "price_dataframe",
    "indicator_dict",
    "quality_bar_labels",
    "metric_rows",
    "news_rows",
]
