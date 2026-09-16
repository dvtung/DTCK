"""Deterministic helpers shared by the agent framework (T013, §21/§24).

Pure functions only — no I/O, no LLM.  Agents may *phrase* numbers, never
compute them (§47): these helpers only round / label / rank values that already
came out of the quant engine or the RAG pipeline through a tool call (§22).
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "IMPORTANT_NEWS_KEYWORDS",
    "SIGNAL_WORDS",
    "bottom_factor",
    "clamp01",
    "round_score",
    "signal_word",
    "top_factor",
]

# §44 signal labels → wording used in theses/alerts.
SIGNAL_WORDS: dict[str, str] = {
    "POSITIVE": "positive",
    "NEUTRAL": "neutral",
    "NEGATIVE": "negative",
}

# Deterministic keyword scan for "important news" (§20.3).  Matching is a text
# lookup, not a numeric judgement on the news content.
IMPORTANT_NEWS_KEYWORDS: tuple[str, ...] = (
    "downgrade",
    "hạ bậc",
    "fraud",
    "gian lận",
    "penalty",
    "xử phạt",
    "vi phạm",
    "cảnh báo",
    "lỗ",
    "sụt giảm",
    "giảm mạnh",
    "từ chức",
    "điều tra",
    "nợ xấu",
    "default",
    "bankruptcy",
    "phá sản",
)


def clamp01(value: float) -> float:
    """Clamp a confidence-like value into [0, 1]."""
    return max(0.0, min(1.0, float(value)))


def round_score(value: Any, digits: int = 2) -> float:
    """Round a tool-provided number; ``None``/unparsable → ``0.0``."""
    if value is None:
        return 0.0
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return 0.0


def signal_word(signal: str) -> str:
    """Map a §44 signal label to its wording (unknown → ``neutral``)."""
    return SIGNAL_WORDS.get(str(signal).upper(), "neutral")


def matches_important_news(text: str) -> bool:
    """True when ``text`` hits the deterministic risk-keyword scan (§20.3)."""
    lowered = (text or "").lower()
    return any(keyword in lowered for keyword in IMPORTANT_NEWS_KEYWORDS)


def _shares(contributions: dict[str, float | None]) -> dict[str, float]:
    """Drop factors with no score — a missing factor is not a weak factor."""
    return {k: float(v) for k, v in contributions.items() if v is not None}


def top_factor(contributions: dict[str, float | None]) -> tuple[str, float]:
    """Factor with the largest contribution share → ``(name, pct)``.

    Returns ``("", 0.0)`` when no factor has a score.  Ties resolve by insertion
    order of ``contributions`` (deterministic).
    """
    available = _shares(contributions)
    if not available:
        return "", 0.0
    factor = max(available, key=lambda k: available[k])
    return factor, round_score(available[factor], 4)


def bottom_factor(contributions: dict[str, float | None]) -> tuple[str, float]:
    """Factor with the smallest contribution share → ``(name, pct)``."""
    available = _shares(contributions)
    if not available:
        return "", 0.0
    factor = min(available, key=lambda k: available[k])
    return factor, round_score(available[factor], 4)
