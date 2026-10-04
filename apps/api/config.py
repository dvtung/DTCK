"""Application settings (pydantic-settings).

Secrets come exclusively from environment variables / .env (see .env.example).
Never hardcode credentials here.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "dtck-api"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    # API-key auth (spec §32, T015): when set, every POST/PUT/PATCH/DELETE
    # under /api/v1/ requires `Authorization: Bearer <key>`. Empty = disabled
    # (offline demos and unit tests); production deployments MUST set it.
    api_auth_key: str = ""

    # User JWT (spec §3/§32, T015b): HMAC-SHA256 secret for access/refresh
    # tokens issued by /api/v1/auth/login. Empty = tokens are demo strings and
    # role checks fall back to the offline ADMIN identity.
    auth_jwt_secret: str = ""
    auth_jwt_ttl_seconds: int = 3600
    auth_refresh_ttl_seconds: int = 604800

    # Database
    database_url: str = "postgresql+psycopg://dtck:change_me@localhost:5432/dtck"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None

    # Market-data source (W1): "memory" (deterministic fixture, default),
    # "db" (TimescaleDB read path) or "auto" (DB when reachable and populated).
    market_data_source: str = "memory"

    # LLM abstraction (ADR-005) — Phase 5
    llm_provider: str = "mock"
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str | None = None
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4096
    llm_timeout_seconds: int = 120
    # Hybrid reasoning models (Qwen3.5…) emit a long thinking block before the
    # answer; disabling it keeps agent runs inside the §45 latency budget (§47).
    llm_think: bool = False

    # Embeddings — Phase 4
    embedding_provider: str = "sentence-transformers"
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384

    # Scoring baseline (§12)
    scoring_version: str = "baseline_1.0"

    # Worker / Scheduler settings
    scheduler_news_interval_minutes: int = 15
    # Two sessions per VN trading day (Asia/Ho_Chi_Minh): the morning session
    # closes at 11:30, the afternoon at 15:00 — ingest right after each close and
    # score 30 minutes later so ranking always reflects the freshest bars.
    scheduler_scoring_cron_hours: str = "12,16"
    scheduler_scoring_cron_minute: int = 0
    # Strategy-profile scoring (GĐ 4): 3 profiles (short/mid/long) + A–D
    # recommendations. Runs at 17:00 daily (Mon–Fri) after EOD market close and
    # updates related data before scoring.
    scheduler_strategy_hour: int = 17
    scheduler_strategy_minute: int = 0
    scheduler_news_source: str = "cafef"
    # Daily EOD price ingestion (feeds the scoring jobs with same-session bars).
    # Primary source only — the job walks `fallback_chains.market` (Yahoo, …)
    # from `configs/sources.yaml` when the primary fails or returns no rows.
    scheduler_eod_source: str = "ssix_finipro"
    scheduler_eod_cron_hours: str = "11,15"
    scheduler_eod_cron_minute: int = 30
    scheduler_eod_lookback_days: int = 7  # idempotent window: re-fetches recent bars
    # Index codes ingested by the same EOD job (SSI `Market/DailyIndex`). Without
    # this the index chart/regime inputs lag the stock universe (KI-014: they were
    # frozen 2026-09-25 → 09-29). Comma/semicolon separated; empty disables it.
    scheduler_eod_indices: str = "VNINDEX,VN30"
    # The morning run stores the current session's snapshot (it powers the 12:30
    # report) and the close run overwrites it. Set false to only ever ingest
    # sessions that have already closed, at the cost of a live noon report.
    scheduler_eod_include_intraday_session: bool = True
    # Retry window: when `prices`/`index_prices` are still behind the last closed
    # session here, the EOD ingestion runs again — a transient vendor outage (SSI
    # 502 on 2026-09-29) must not lose the close of day before scoring/email.
    scheduler_eod_catchup_hour: int = 15
    scheduler_eod_catchup_minute: int = 50
    # ICT cutoff marking the afternoon session as closed (ATC ends 14:45; vendor
    # EOD data settles a little later). Drives both the catch-up window and the
    # "provisional scores" warning in the scoring job.
    scheduler_session_close_hour: int = 15
    scheduler_session_close_minute: int = 15
    # How often the worker re-reads `email_schedule_configs` so a schedule saved
    # on the dashboard is applied without restarting the container.
    scheduler_email_sync_minutes: int = 15
    scheduler_jobs_enabled: bool = True

    # Data quality gate (§39, T005) — datasets below this overall score are not
    # used downstream (features/signals/backtests).
    data_quality_threshold: float = 80.0

    # CORS
    cors_origins: list[str] = ["http://localhost:8501"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def parse_cron_hours(raw: str, fallback: tuple[int, ...]) -> tuple[int, ...]:
    """Parse a ``"11,15"``-style hour list into a sorted, de-duplicated tuple.

    Environment variables must stay simple strings (pydantic-settings would try
    to JSON-decode a list), so the scheduler accepts a comma/semicolon separated
    hour list here.  Out-of-range or unparsable entries are dropped; an empty
    result falls back to the documented default.
    """
    hours: set[int] = set()
    for part in str(raw or "").replace(";", ",").split(","):
        token = part.strip()
        if token.isdigit() and 0 <= int(token) <= 23:
            hours.add(int(token))
    return tuple(sorted(hours)) or fallback


def parse_codes(raw: str) -> tuple[str, ...]:
    """Parse a ``"VNINDEX,VN30"``-style code list for the scheduler.

    Upper-cased, whitespace-stripped, de-duplicated and order-preserving (the
    vendor expects codes in the order it was given). Blank input yields an empty
    tuple, which callers treat as "this dataset is not scheduled".
    """
    codes: list[str] = []
    for part in str(raw or "").replace(";", ",").split(","):
        token = part.strip().upper()
        if token and token not in codes:
            codes.append(token)
    return tuple(codes)


settings = get_settings()
