"""Normalizers (T004) — map provider-agnostic records into database-ready rows.

Responsibilities (``docs/DATA_ARCHITECTURE.md`` §2): symbol/exchange resolution,
currency/unit sanity, dedup and provenance stamps (``source`` + ``ingested_at``).
Rows are plain ``dict`` objects matching the SQLAlchemy models, so the pipeline
can upsert them idempotently (§2, "ON CONFLICT DO UPDATE where source allows").
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Connection, select

from src.data.records import EODBar, EventRow, FinancialRow, IndexBar, MacroPoint, NewsItem
from src.data.validators import ValidationIssue


def resolve_stock_ids(conn: Connection, symbols: list[str]) -> dict[str, int]:
    """Map ``symbol -> stocks.id`` for ACTIVE stocks in the reference universe."""
    from sqlalchemy import func

    from src.common.models.reference import Stock

    if not symbols:
        return {}
    wanted = {s.upper() for s in symbols}
    rows = conn.execute(
        select(Stock.symbol, Stock.id).where(
            func.upper(Stock.symbol).in_(wanted), Stock.status == "ACTIVE"
        )
    ).fetchall()
    return {symbol.upper(): stock_id for symbol, stock_id in rows}


def normalize_eod(
    bars: list[EODBar],
    stock_ids: dict[str, int],
    *,
    source: str,
    ingested_at: datetime,
) -> tuple[list[dict[str, object]], list[ValidationIssue]]:
    """Convert raw EOD bars to ``prices`` rows; unknown symbols are reported,
    not dropped silently."""

    rows: list[dict[str, object]] = []
    issues: list[ValidationIssue] = []
    for bar in bars:
        stock_id = stock_ids.get(bar.symbol.upper())
        if stock_id is None:
            issues.append(
                ValidationIssue(
                    "prices",
                    f"{bar.symbol}@{bar.trade_date}",
                    "symbol",
                    "not in reference universe (stocks)",
                )
            )
            continue
        rows.append(
            {
                "stock_id": stock_id,
                "trade_date": bar.trade_date,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "trading_value": bar.trading_value,
                "source": source,
                "ingested_at": ingested_at,
            }
        )
    return rows, issues


def normalize_index(
    bars: list[IndexBar], *, source: str, ingested_at: datetime
) -> list[dict[str, object]]:
    """Convert raw index bars to ``index_prices`` rows (no FK resolution needed)."""

    return [
        {
            "index_code": bar.index_code.upper(),
            "trade_date": bar.trade_date,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "trading_value": bar.trading_value,
        }
        for bar in bars
    ]


def normalize_news(
    items: list[NewsItem],
    stock_ids: dict[str, int],
    *,
    ingested_at: datetime,
) -> tuple[list[dict[str, object]], list[list[int]], list[ValidationIssue]]:
    """Convert raw news to ``news`` rows plus per-row stock ids for ``news_symbols``.

    The pipeline inserts the ``news`` rows first (returning generated ids) and then
    pairs each generated id with the stock ids at the same index.
    """
    news_rows: list[dict[str, object]] = []
    links_per_row: list[list[int]] = []
    issues: list[ValidationIssue] = []
    for item in items:
        key = f"{item.source}:{item.title[:60]}"
        news_rows.append(
            {
                "source": item.source,
                "title": item.title,
                "content": item.content,
                "published_at": item.published_at,
                "event_type": item.event_type,
                "sentiment": item.sentiment,
                "importance": item.importance,
                "ingested_at": ingested_at,
            }
        )
        resolved: list[int] = []
        for symbol in item.symbols:
            stock_id = stock_ids.get(symbol.upper())
            if stock_id is None:
                issues.append(
                    ValidationIssue(
                        "news",
                        key,
                        "symbols",
                        f"unknown symbol {symbol} (not in reference universe)",
                    )
                )
                continue
            resolved.append(stock_id)
        links_per_row.append(resolved)
    return news_rows, links_per_row, issues


def expected_eod_keys(symbols: list[str], dates: list[date]) -> set[tuple[str, date]]:
    """Completeness denominator for the T005 scorer (§39)."""
    return {(symbol.upper(), day) for symbol in symbols for day in dates}


def as_decimal(value: Decimal | None) -> Decimal | None:
    """No-op hook kept for symmetry with future unit conversions (VND → bn VND)."""
    return value


def normalize_financials(
    rows: list[FinancialRow],
    stock_ids: dict[str, int],
    *,
    source: str,
) -> tuple[list[dict[str, object]], list[ValidationIssue]]:
    """Convert raw financial rows to ``financial_statements`` rows.

    ``published_at`` is carried through verbatim: when the vendor did not
    disclose it the column stays ``NULL`` — never backfilled with a guess, so
    as-of queries cannot accidentally see a filing before it was public (§31).
    """
    out: list[dict[str, object]] = []
    issues: list[ValidationIssue] = []
    for row in rows:
        stock_id = stock_ids.get(row.symbol.upper())
        if stock_id is None:
            issues.append(
                ValidationIssue(
                    "financials",
                    f"{row.symbol}@{row.report_date}",
                    "symbol",
                    "not in reference universe (stocks)",
                )
            )
            continue
        out.append(
            {
                "stock_id": stock_id,
                "period_type": row.period_type,
                "fiscal_year": row.fiscal_year,
                "fiscal_period": row.fiscal_period,
                "statement_type": row.statement_type,
                "line_item": row.line_item,
                "value": row.value,
                "currency": row.currency,
                "report_date": row.report_date,
                "published_at": row.published_at,
                # Bitemporal validity: a fresh ingestion is valid from now on.
                "valid_from": datetime.now().astimezone(),
                "valid_to": None,
                "source": source,
            }
        )
    return out, issues


def normalize_events(
    rows: list[EventRow],
    stock_ids: dict[str, int],
    *,
    source: str,
) -> tuple[list[dict[str, object]], list[ValidationIssue]]:
    """Convert raw corporate events to ``corporate_events`` rows."""
    out: list[dict[str, object]] = []
    issues: list[ValidationIssue] = []
    for row in rows:
        stock_id = stock_ids.get(row.symbol.upper())
        if stock_id is None:
            issues.append(
                ValidationIssue(
                    "events",
                    f"{row.symbol}@{row.event_date}",
                    "symbol",
                    "not in reference universe (stocks)",
                )
            )
            continue
        out.append(
            {
                "stock_id": stock_id,
                "event_type": row.event_type,
                "event_date": row.event_date,
                "announced_date": row.announced_date,
                # JSONB cannot serialise Decimal — store amounts as numbers.
                "details": (
                    {
                        str(k): (float(v) if isinstance(v, Decimal) else v)
                        for k, v in row.details.items()
                    }
                    if row.details
                    else None
                ),
                "source": source,
            }
        )
    return out, issues


def normalize_macro(rows: list[MacroPoint], *, source: str) -> list[dict[str, object]]:
    """Convert raw macro observations to ``macro_indicators`` rows (no FK)."""
    return [
        {
            "indicator_code": row.indicator_code,
            "period_date": row.period_date,
            "value": row.value,
            "unit": row.unit,
            "source": source,
        }
        for row in rows
    ]


__all__ = [
    "resolve_stock_ids",
    "normalize_eod",
    "normalize_events",
    "normalize_financials",
    "normalize_index",
    "normalize_macro",
    "normalize_news",
    "expected_eod_keys",
    "as_decimal",
]
