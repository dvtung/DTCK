"""Ingestion pipelines (T004): collect → validate → normalize → upsert → quality.

Runs inside the worker (APScheduler jobs) or one-off via the worker CLI. Every
batch records provenance (``source`` + ``ingested_at``), is scored by the T005
quality framework, and reports whether the quality gate (§39) passed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, cast

from sqlalchemy import Connection, Engine, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.data.collectors import (
    collect_eod,
    collect_events,
    collect_financials,
    collect_index,
    collect_macro,
    collect_news,
)
from src.data.normalizers import (
    normalize_eod,
    normalize_events,
    normalize_financials,
    normalize_index,
    normalize_macro,
    normalize_news,
    resolve_stock_ids,
)
from src.data.providers.base import DataProvider
from src.data.quality import QualityScore, compute_quality, persist_quality
from src.data.records import EODBar, IndexBar, NewsItem
from src.data.validators import (
    ValidationIssue,
    corrupt_financial_keys,
    corrupt_keys,
    eod_key,
    financial_key,
    index_key,
    validate_eod,
    validate_events,
    validate_financials,
    validate_index,
    validate_macro,
    validate_news,
)


@dataclass(slots=True)
class IngestResult:
    """Outcome of one pipeline run (logged by the worker / CLI)."""

    dataset: str
    source: str
    rows_fetched: int = 0
    rows_written: int = 0
    rows_skipped: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)
    quality: QualityScore | None = None

    @property
    def quality_passed(self) -> bool:
        """§39 gate: True when scored above threshold (or nothing was scoreable)."""
        return self.quality is None or not self.quality.below_threshold

    def summary(self) -> str:
        score = self.quality.overall_score if self.quality else None
        flagged = " [BELOW THRESHOLD]" if self.quality and self.quality.below_threshold else ""
        return (
            f"{self.dataset} source={self.source} fetched={self.rows_fetched} "
            f"written={self.rows_written} skipped={self.rows_skipped} "
            f"issues={len(self.issues)} quality={score}{flagged}"
        )


def _now() -> datetime:
    return datetime.now(tz=UTC)


# Postgres caps a statement at 65,535 bind parameters; a full VN30 × 2y batch
# (14k+ rows × 10 columns) used to blow past it and abort the whole ingest.
# 1,000 rows × 10 columns = 10k parameters — safely under the limit.
_UPSERT_CHUNK = 1000


def _weekdays(start: date, end: date) -> list[date]:
    """Approximation of trading days for the completeness denominator (§39)."""
    days: list[date] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:  # Mon–Fri; holidays come from the scheduler later
            days.append(cursor)
        cursor = date.fromordinal(cursor.toordinal() + 1)
    return days


def _threshold(value: float | None) -> float:
    if value is not None:
        return value
    from src.data.quality import DEFAULT_THRESHOLD

    try:
        from apps.api.config import settings

        return float(settings.data_quality_threshold)
    except Exception:  # pragma: no cover - settings unavailable outside the app
        return DEFAULT_THRESHOLD


def _score_and_persist(
    conn: Connection,
    *,
    dataset: str,
    rows_total: int,
    issues: list[ValidationIssue],
    end: date,
    latest_date: date | None,
    expected_keys: int | None,
    present_keys: int | None,
    threshold: float | None,
) -> QualityScore | None:
    """Score + persist a batch; ``None`` when the batch is empty (nothing to score).

    An empty batch is reported via ``IngestResult.rows_fetched == 0`` rather than
    a synthetic zero score — there are no dimensions to compute (§39 denominators
    are all zero).
    """
    if rows_total <= 0:
        return None
    quality = compute_quality(
        dataset=dataset,
        as_of_date=end,
        rows_total=rows_total,
        issues=issues,
        expected_keys=expected_keys,
        present_keys=present_keys,
        latest_date=latest_date,
        threshold=_threshold(threshold),
    )
    persist_quality(conn, quality)
    return quality


def ingest_eod(
    engine: Engine,
    provider: DataProvider,
    symbols: list[str],
    *,
    start: date,
    end: date,
    source: str | None = None,
    threshold: float | None = None,
) -> IngestResult:
    """Ingest raw EOD OHLCV for ``symbols`` into ``prices`` and score the batch."""
    from src.common.models.market import Price

    src = source or provider.id
    bars: list[EODBar] = collect_eod(provider, symbols, start, end)
    issues = validate_eod(bars, start=start, end=end)
    result = IngestResult(dataset="prices", source=src, rows_fetched=len(bars), issues=issues)

    if not bars:
        # Nothing to persist/score — an empty batch is reported as fetched=0 and
        # never opens a transaction (§39 has no denominators for it).
        return result

    # Drop bars that violate the OHLC/volume invariants (§39): they stay in
    # `issues` so the quality score still penalises the batch, but corrupt rows
    # must never be persisted (live finding: Yahoo returned `high < low` on TPB).
    bad_keys = corrupt_keys(issues)
    kept_bars = bars
    if bad_keys:
        kept_bars = [b for b in bars if eod_key(b.symbol, b.trade_date) not in bad_keys]

    with engine.begin() as conn:
        stock_ids = resolve_stock_ids(conn, symbols)
        rows, normalize_issues = normalize_eod(kept_bars, stock_ids, source=src, ingested_at=_now())
        result.issues.extend(normalize_issues)
        result.rows_skipped = (len(bars) - len(kept_bars)) + (len(kept_bars) - len(rows))

        if rows:
            # Chunked upsert: one statement per _UPSERT_CHUNK rows so a 2-year
            # backfill never exceeds Postgres' 65,535-parameter limit.
            for chunk_start in range(0, len(rows), _UPSERT_CHUNK):
                stmt = pg_insert(Price).values(rows[chunk_start : chunk_start + _UPSERT_CHUNK])
                stmt = stmt.on_conflict_do_update(
                    index_elements=[Price.stock_id, Price.trade_date],
                    set_={
                        "open": stmt.excluded.open,
                        "high": stmt.excluded.high,
                        "low": stmt.excluded.low,
                        "close": stmt.excluded.close,
                        "volume": stmt.excluded.volume,
                        "trading_value": stmt.excluded.trading_value,
                        "source": stmt.excluded.source,
                        "ingested_at": stmt.excluded.ingested_at,
                    },
                )
                conn.execute(stmt)
            result.rows_written = len(rows)

        result.quality = _score_and_persist(
            conn,
            dataset="prices",
            rows_total=len(bars),
            issues=result.issues,
            end=end,
            latest_date=max((bar.trade_date for bar in bars), default=None),
            expected_keys=len({s.upper() for s in symbols}) * len(_weekdays(start, end)),
            present_keys=len({(bar.symbol, bar.trade_date) for bar in kept_bars}),
            threshold=threshold,
        )
    return result


def ingest_index(
    engine: Engine,
    provider: DataProvider,
    index_codes: list[str],
    *,
    start: date,
    end: date,
    source: str | None = None,
    threshold: float | None = None,
) -> IngestResult:
    """Ingest index OHLCV into ``index_prices`` and score the batch."""
    from src.common.models.market import IndexPrice

    src = source or provider.id
    bars: list[IndexBar] = collect_index(provider, index_codes, start, end)
    issues = validate_index(bars, start=start, end=end)
    result = IngestResult(dataset="index_prices", source=src, rows_fetched=len(bars), issues=issues)

    if not bars:
        return result

    # Same corrupt-row guard as ``ingest_eod`` (§39).
    bad_index_keys = corrupt_keys(issues)
    kept_bars = bars
    if bad_index_keys:
        kept_bars = [
            b for b in bars if index_key(b.index_code, b.trade_date) not in bad_index_keys
        ]
    rows = normalize_index(kept_bars, source=src, ingested_at=_now())

    with engine.begin() as conn:
        result.rows_skipped = len(bars) - len(kept_bars)
        if rows:
            for chunk_start in range(0, len(rows), _UPSERT_CHUNK):
                stmt = pg_insert(IndexPrice).values(rows[chunk_start : chunk_start + _UPSERT_CHUNK])
                stmt = stmt.on_conflict_do_update(
                    index_elements=[IndexPrice.index_code, IndexPrice.trade_date],
                    set_={
                        "open": stmt.excluded.open,
                        "high": stmt.excluded.high,
                        "low": stmt.excluded.low,
                        "close": stmt.excluded.close,
                        "volume": stmt.excluded.volume,
                        "trading_value": stmt.excluded.trading_value,
                    },
                )
                conn.execute(stmt)
            # See ingest_eod: multi-row upserts report rowcount=-1 under psycopg.
            result.rows_written = len(rows)

        result.quality = _score_and_persist(
            conn,
            dataset="index_prices",
            rows_total=len(bars),
            issues=issues,
            end=end,
            latest_date=max((bar.trade_date for bar in bars), default=None),
            expected_keys=len({c.upper() for c in index_codes}) * len(_weekdays(start, end)),
            present_keys=len({(bar.index_code, bar.trade_date) for bar in kept_bars}),
            threshold=threshold,
        )
    return result


def ingest_news(
    engine: Engine,
    provider: DataProvider,
    *,
    since: datetime,
    threshold: float | None = None,
) -> IngestResult:
    """Ingest news items into ``news``/``news_symbols`` (dedup on ``(source, title)``).

    Deduplication is application-level: the ``news`` table has no natural unique
    key, so existing ``(source, title)`` pairs are looked up before insert —
    re-runs are idempotent without extra schema.
    """
    from src.common.models.events import News, NewsSymbol

    items: list[NewsItem] = collect_news(provider, since)
    issues = validate_news(items)
    result = IngestResult(
        dataset="news", source=provider.id, rows_fetched=len(items), issues=issues
    )

    if not items:
        return result

    with engine.begin() as conn:
        stock_ids = resolve_stock_ids(conn, [s for item in items for s in item.symbols])
        news_rows, links_per_row, normalize_issues = normalize_news(
            items, stock_ids, ingested_at=_now()
        )
        result.issues.extend(normalize_issues)

        # Only look up (source, title) pairs that this batch may insert — the
        # lookup stays bounded by the batch size instead of the whole table.
        candidate_titles = [str(row["title"]) for row in news_rows]
        existing_titles: set[tuple[str, str]] = set()
        if candidate_titles:
            for chunk_start in range(0, len(candidate_titles), 500):
                chunk = candidate_titles[chunk_start : chunk_start + 500]
                rows = conn.execute(
                    select(News.source, News.title).where(News.title.in_(chunk))
                ).fetchall()
                existing_titles.update((source, title) for source, title in rows)

        inserted = 0
        for row, row_stock_ids in zip(news_rows, links_per_row, strict=True):
            key = (str(row["source"]), str(row["title"]))
            if key in existing_titles:
                continue
            news_id = conn.execute(insert(News).values(**row).returning(News.id)).scalar_one()
            for stock_id in row_stock_ids:
                conn.execute(
                    insert(NewsSymbol.__table__).values(news_id=news_id, stock_id=stock_id)  # type: ignore[arg-type]
                )
            inserted += 1
        result.rows_written = inserted
        result.rows_skipped = len(news_rows) - inserted

        result.quality = _score_and_persist(
            conn,
            dataset="news",
            rows_total=len(items),
            issues=result.issues,
            end=_now().date(),
            latest_date=max((item.published_at.date() for item in items), default=None),
            expected_keys=None,
            present_keys=None,
            threshold=threshold,
        )
    return result


def ingest_financials(
    engine: Engine,
    provider: DataProvider,
    symbols: list[str],
    *,
    period_types: tuple[str, ...] = ("QUARTER", "YEAR"),
    source: str | None = None,
    threshold: float | None = None,
) -> IngestResult:
    """Ingest financial-statement line items into ``financial_statements`` (§5.1).

    Bitemporal upsert keyed on the model's unique constraint
    ``(stock_id, period_type, fiscal_year, fiscal_period, statement_type,
    line_item, valid_from)``. ``published_at`` is stored exactly as reported
    (NULL when the vendor did not disclose it) — the look-ahead guard for every
    fundamental feature built on this table.
    """
    from src.common.models.fundamental import FinancialStatement

    src = source or provider.id
    rows = collect_financials(provider, symbols, period_types=period_types)
    issues = validate_financials(rows)
    result = IngestResult(dataset="financials", source=src, rows_fetched=len(rows), issues=issues)
    if not rows:
        return result

    # Same guard as EOD bars: rows whose value cannot fit the column are
    # flagged (so the quality score penalises the batch) and dropped, never
    # rescaled or truncated (live finding: CafeF cash-flow outliers).
    bad_keys = corrupt_financial_keys(issues)
    kept_rows = rows
    if bad_keys:
        kept_rows = [r for r in rows if financial_key(r) not in bad_keys]

    with engine.begin() as conn:
        stock_ids = resolve_stock_ids(conn, [row.symbol for row in kept_rows])
        normalized, normalize_issues = normalize_financials(kept_rows, stock_ids, source=src)
        result.issues.extend(normalize_issues)
        result.rows_skipped = (len(rows) - len(kept_rows)) + (len(kept_rows) - len(normalized))

        if normalized:
            # Bitemporal snapshot-diff (memory-bank decision 2026-09-13): a
            # changed restatement CLOSES the open row (valid_to) and opens a new
            # one; an unchanged restatement is a no-op. Inserting every run
            # without closing would duplicate rows, because valid_from is part
            # of the unique key.
            stock_id_list = sorted({cast(int, r["stock_id"]) for r in normalized})
            open_maps = conn.execute(
                select(
                    FinancialStatement.id,
                    FinancialStatement.stock_id,
                    FinancialStatement.period_type,
                    FinancialStatement.fiscal_year,
                    FinancialStatement.fiscal_period,
                    FinancialStatement.statement_type,
                    FinancialStatement.line_item,
                    FinancialStatement.value,
                    FinancialStatement.published_at,
                ).where(
                    FinancialStatement.stock_id.in_(stock_id_list),
                    FinancialStatement.valid_to.is_(None),
                )
            ).mappings().all()
            open_by_key: dict[tuple[int, str, int, int, str, str], tuple[int, Any, Any]] = {
                (
                    m["stock_id"],
                    m["period_type"],
                    m["fiscal_year"],
                    m["fiscal_period"],
                    m["statement_type"],
                    m["line_item"],
                ): (m["id"], m["value"], m["published_at"])
                for m in open_maps
            }

            now = datetime.now().astimezone()
            written = 0
            for row in normalized:
                key = (
                    cast(int, row["stock_id"]),
                    cast(str, row["period_type"]),
                    cast(int, row["fiscal_year"]),
                    cast(int, row["fiscal_period"]),
                    cast(str, row["statement_type"]),
                    cast(str, row["line_item"]),
                )
                previous = open_by_key.get(key)
                if previous is not None:
                    previous_id, previous_value, previous_published = previous
                    if previous_value == row["value"]:
                        if previous_published != row["published_at"]:
                            # Publication timestamp corrected without a
                            # restatement: metadata fix in place, no new version.
                            conn.execute(
                                update(FinancialStatement)
                                .where(FinancialStatement.id == previous_id)
                                .values(published_at=row["published_at"], source=src)
                            )
                        continue
                    conn.execute(
                        update(FinancialStatement)
                        .where(FinancialStatement.id == previous_id)
                        .values(valid_to=now)
                    )
                conn.execute(insert(FinancialStatement).values(**row))
                written += 1
            result.rows_written = written
            result.rows_skipped += len(normalized) - written

        result.quality = _score_and_persist(
            conn,
            dataset="financials",
            rows_total=len(rows),
            issues=result.issues,
            end=max((row.report_date for row in rows), default=_now().date()),
            latest_date=max((row.report_date for row in rows), default=None),
            expected_keys=None,
            present_keys=None,
            threshold=threshold,
        )
    return result


def ingest_events(
    engine: Engine,
    provider: DataProvider,
    symbols: list[str],
    *,
    since: date,
    source: str | None = None,
    threshold: float | None = None,
) -> IngestResult:
    """Ingest corporate events into ``corporate_events`` (§7.1).

    ``corporate_events`` has no natural unique key, so deduplication is
    application-level on ``(stock_id, event_type, event_date)`` — re-runs stay
    idempotent without a schema change (mirrors ``ingest_news``).
    """
    from src.common.models.events import CorporateEvent

    src = source or provider.id
    rows = collect_events(provider, symbols, since=since)
    issues = validate_events(rows, since=since)
    result = IngestResult(dataset="events", source=src, rows_fetched=len(rows), issues=issues)
    if not rows:
        return result

    with engine.begin() as conn:
        stock_ids = resolve_stock_ids(conn, [row.symbol for row in rows])
        normalized, normalize_issues = normalize_events(rows, stock_ids, source=src)
        result.issues.extend(normalize_issues)
        result.rows_skipped = len(rows) - len(normalized)

        existing: set[tuple[int, str, date]] = set()
        if normalized:
            stock_id_list = [cast(int, r["stock_id"]) for r in normalized]
            for chunk_start in range(0, len(stock_id_list), 500):
                chunk = stock_id_list[chunk_start : chunk_start + 500]
                found = conn.execute(
                    select(
                        CorporateEvent.stock_id,
                        CorporateEvent.event_type,
                        CorporateEvent.event_date,
                    ).where(CorporateEvent.stock_id.in_(chunk))
                ).fetchall()
                existing.update((int(a), str(b), c) for a, b, c in found)

        inserted = 0
        for row in normalized:
            key = (
                cast(int, row["stock_id"]),
                cast(str, row["event_type"]),
                cast(date, row["event_date"]),
            )
            if key in existing:
                continue
            conn.execute(insert(CorporateEvent).values(**row))
            inserted += 1
        result.rows_written = inserted
        result.rows_skipped += len(normalized) - inserted

    return result


def ingest_macro(
    engine: Engine,
    provider: DataProvider,
    indicators: list[str],
    *,
    start: date,
    end: date,
    source: str | None = None,
    threshold: float | None = None,
) -> IngestResult:
    """Ingest macro series observations into ``macro_indicators`` (§8.1).

    Upsert on the table's ``(indicator_code, period_date)`` primary key, so a
    refreshed vintage of the same year overwrites the previous value.
    """
    from src.common.models.macro import MacroIndicator

    src = source or provider.id
    rows = collect_macro(provider, indicators, start=start, end=end)
    issues = validate_macro(rows, start=start, end=end)
    result = IngestResult(dataset="macro", source=src, rows_fetched=len(rows), issues=issues)
    if not rows:
        return result

    normalized = normalize_macro(rows, source=src)

    with engine.begin() as conn:
        for chunk_start in range(0, len(normalized), _UPSERT_CHUNK):
            chunk = normalized[chunk_start : chunk_start + _UPSERT_CHUNK]
            stmt = pg_insert(MacroIndicator).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=[MacroIndicator.indicator_code, MacroIndicator.period_date],
                set_={
                    "value": stmt.excluded.value,
                    "unit": stmt.excluded.unit,
                    "source": stmt.excluded.source,
                },
            )
            conn.execute(stmt)
        result.rows_written = len(normalized)

        result.quality = _score_and_persist(
            conn,
            dataset="macro",
            rows_total=len(rows),
            issues=issues,
            end=max((row.period_date for row in rows), default=end),
            latest_date=max((row.period_date for row in rows), default=None),
            expected_keys=None,
            present_keys=None,
            threshold=threshold,
        )
    return result


__all__ = [
    "IngestResult",
    "ingest_eod",
    "ingest_events",
    "ingest_financials",
    "ingest_index",
    "ingest_macro",
    "ingest_news",
]
