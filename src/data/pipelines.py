"""Ingestion pipelines (T004): collect → validate → normalize → upsert → quality.

Runs inside the worker (APScheduler jobs) or one-off via the worker CLI. Every
batch records provenance (``source`` + ``ingested_at``), is scored by the T005
quality framework, and reports whether the quality gate (§39) passed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from sqlalchemy import Connection, Engine, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.data.collectors import collect_eod, collect_index, collect_news
from src.data.normalizers import (
    normalize_eod,
    normalize_index,
    normalize_news,
    resolve_stock_ids,
)
from src.data.providers.base import DataProvider
from src.data.quality import QualityScore, compute_quality, persist_quality
from src.data.records import EODBar, IndexBar, NewsItem
from src.data.validators import ValidationIssue, validate_eod, validate_index, validate_news


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

    with engine.begin() as conn:
        stock_ids = resolve_stock_ids(conn, symbols)
        rows, normalize_issues = normalize_eod(bars, stock_ids, source=src, ingested_at=_now())
        result.issues.extend(normalize_issues)
        result.rows_skipped = len(bars) - len(rows)

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
            present_keys=len({(bar.symbol, bar.trade_date) for bar in bars}),
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
    rows = normalize_index(bars, source=src, ingested_at=_now())

    if not bars:
        return result

    with engine.begin() as conn:
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
            present_keys=len({(bar.index_code, bar.trade_date) for bar in bars}),
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


__all__ = ["IngestResult", "ingest_eod", "ingest_index", "ingest_news"]
