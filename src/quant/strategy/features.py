"""Multi-strategy feature registry (GĐ 3) — pure, deterministic, testable.

Every feature is a pure function over a :class:`FeatureSnapshot`; the registry
declares its **group**, its **direction** (does a higher number mean a better
company?) and whether it only applies to certain industries. Nothing here
touches the database — the engine (``feature_engine.py``) builds snapshots
as-of a date and persists the result.

VAS line-item codes used (verified against the live CafeF payload,
2026-10-03 — see the code inventory in ``memory-bank/active-task_vi.md``):

==================  ==========================  ==================
code                meaning                     statement
==================  ==========================  ==================
``10``              net revenue                 INCOME
``20``              gross profit                INCOME
``60``              net profit after tax        INCOME
``70``              EPS (VND/share)             INCOME
``100``             current assets              BALANCE
``110``             cash & equivalents          BALANCE
``270``             total assets                BALANCE
``300``             liabilities                 BALANCE
``310``             current liabilities         BALANCE
``400``             owners' equity              BALANCE
``HDKD_20``         net operating cash flow     CASHFLOW
==================  ==========================  ==================
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date

from src.quant.strategy.groups import (
    GROUP_TECHNICAL,
    GROUPS,
)
from src.quant.strategy.redflags import RedFlagResult

__all__ = [
    "FeatureSnapshot",
    "FeatureSpec",
    "FEATURES",
    "compute_raw_features",
    "financial_value",
    "latest_period",
    "periods_sorted",
]

#: VAS line-item codes (see the module docstring).
C_REVENUE = "10"
C_GROSS_PROFIT = "20"
C_NET_PROFIT = "60"
C_EPS = "70"
C_CURRENT_ASSETS = "100"
C_CASH = "110"
C_TOTAL_ASSETS = "270"
C_LIABILITIES = "300"
C_CURRENT_LIABILITIES = "310"
C_EQUITY = "400"
C_OPERATING_CF = "HDKD_20"


@dataclass(frozen=True)
class PeriodValues:
    """One reporting period's line items (keyed by VAS code)."""

    period_type: str  # QUARTER | YEAR
    fiscal_year: int
    fiscal_period: int
    report_date: date
    values: dict[str, float] = field(default_factory=dict)
    #: ``None`` when the vendor publishes no filing date (then the engine
    #: derives an as-of date from ``report_date`` + the configured legal lag).
    published_at: date | None = None


@dataclass(frozen=True)
class FeatureSnapshot:
    """Everything one feature function may look at, already as-of filtered."""

    symbol: str
    as_of: date
    industry: str | None = None
    closes: tuple[float, ...] = ()
    volumes: tuple[float, ...] = ()
    values: tuple[float, ...] = ()  # matched traded value (VND)
    index_closes: tuple[float, ...] = ()
    financials: tuple[PeriodValues, ...] = ()  # ascending by report_date
    dividend_amount_ttm: float | None = None
    red_flags: RedFlagResult | None = None

    # ------------------------------------------------------------- helpers
    def latest(self) -> PeriodValues | None:
        return self.financials[-1] if self.financials else None

    def year_ago(self) -> PeriodValues | None:
        """Same fiscal quarter one year earlier (YoY comparison base)."""
        latest = self.latest()
        if latest is None:
            return None
        for period in reversed(self.financials[:-1]):
            if (
                period.period_type == latest.period_type
                and period.fiscal_period == latest.fiscal_period
                and period.fiscal_year == latest.fiscal_year - 1
            ):
                return period
        return None

    def last_n_quarters(self, n: int) -> list[PeriodValues]:
        quarters = [p for p in self.financials if p.period_type == "QUARTER"]
        return quarters[-n:]

    def last_n_years(self, n: int) -> list[PeriodValues]:
        years = [p for p in self.financials if p.period_type == "YEAR"]
        return years[-n:]

    def close(self) -> float | None:
        return self.closes[-1] if self.closes else None


def financial_value(period: PeriodValues | None, code: str) -> float | None:
    """Line-item value, ``None`` when absent (never zero-filled)."""
    if period is None:
        return None
    return period.values.get(code)


def latest_period(periods: list[PeriodValues], period_type: str) -> PeriodValues | None:
    matching = [p for p in periods if p.period_type == period_type]
    return max(matching, key=lambda p: p.report_date) if matching else None


def periods_sorted(periods: list[PeriodValues]) -> tuple[PeriodValues, ...]:
    return tuple(sorted(periods, key=lambda p: p.report_date))


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous)


@dataclass(frozen=True)
class FeatureSpec:
    """One registered feature: how to compute it and how to read it."""

    name: str
    group: str
    #: +1 → higher is better; -1 → lower is better (used by the ranker).
    direction: int
    fn: Callable[[FeatureSnapshot], float | None]
    #: ``None`` = every industry; otherwise only these industries.
    industries: tuple[str, ...] | None = None
    #: Industries where the ratio is meaningless (e.g. D/E for banks) — a
    #: generic leverage ratio must never be applied to a bank (§industry rules).
    exclude_industries: tuple[str, ...] | None = None

    def applies_to(self, industry: str | None) -> bool:
        if self.industries is not None and industry not in self.industries:
            return False
        if self.exclude_industries is not None and industry in self.exclude_industries:
            return False
        return True


#: Industries that must not be scored with the generic leverage/valuation set.
NOT_GENERIC_LEVERAGE = ("banking", "securities", "insurance")
NOT_GENERIC_VALUATION = ("banking",)


FEATURES: tuple[FeatureSpec, ...] = ()


# ---------------------------------------------------------------- technical
def _price_vs_sma(snapshot: FeatureSnapshot, period: int) -> float | None:
    if len(snapshot.closes) < period:
        return None
    sma = sum(snapshot.closes[-period:]) / period
    return _pct_change(snapshot.close(), sma)


def _return_over(snapshot: FeatureSnapshot, days: int) -> float | None:
    if len(snapshot.closes) <= days:
        return None
    return _pct_change(snapshot.closes[-1], snapshot.closes[-1 - days])


def _rs_over_index(snapshot: FeatureSnapshot, days: int) -> float | None:
    own = _return_over(snapshot, days)
    if own is None or len(snapshot.index_closes) <= days:
        return None
    benchmark = _pct_change(snapshot.index_closes[-1], snapshot.index_closes[-1 - days])
    if benchmark is None:
        return None
    return own - benchmark


def _atr_pct(snapshot: FeatureSnapshot, period: int = 20) -> float | None:
    closes = snapshot.closes
    if len(closes) < period + 1:
        return None
    window = closes[-(period + 1) :]
    true_ranges = [abs(window[i] - window[i - 1]) for i in range(1, len(window))]
    atr = sum(true_ranges) / len(true_ranges)
    price = window[-1]
    return None if price <= 0 else atr / price


def _macd_hist_pct(snapshot: FeatureSnapshot) -> float | None:
    closes = snapshot.closes
    if len(closes) < 35:
        return None
    ema_fast = _ema(closes, 12)
    ema_slow = _ema(closes, 26)
    if ema_fast is None or ema_slow is None:
        return None
    # The two EMAs start at different offsets — align them from the end.
    shared = min(len(ema_fast), len(ema_slow))
    macd_line = [f - s for f, s in zip(ema_fast[-shared:], ema_slow[-shared:], strict=True)]
    signal = _ema(macd_line, 9)
    if signal is None:
        return None
    hist = macd_line[-1] - signal[-1]
    return None if closes[-1] <= 0 else hist / closes[-1]


def _ema(values: Sequence[float], period: int) -> list[float] | None:
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1)
    out = [sum(values[:period]) / period]
    for value in values[period:]:
        out.append(alpha * value + (1 - alpha) * out[-1])
    return out


# ------------------------------------------------------------------ growth
def _revenue_yoy(snapshot: FeatureSnapshot) -> float | None:
    return _pct_change(
        financial_value(snapshot.latest(), C_REVENUE),
        financial_value(snapshot.year_ago(), C_REVENUE),
    )


def _net_profit_yoy(snapshot: FeatureSnapshot) -> float | None:
    return _pct_change(
        financial_value(snapshot.latest(), C_NET_PROFIT),
        financial_value(snapshot.year_ago(), C_NET_PROFIT),
    )


def _revenue_cagr_3y(snapshot: FeatureSnapshot) -> float | None:
    years = snapshot.last_n_years(4)
    if len(years) < 4:
        return None
    start = financial_value(years[0], C_REVENUE)
    end = financial_value(years[-1], C_REVENUE)
    if start is None or start == 0 or end is None or start < 0:
        return None
    return float((end / start) ** (1.0 / 3.0) - 1.0)


# ----------------------------------------------------------------- quality
def _ttm_sum(snapshot: FeatureSnapshot, code: str) -> float | None:
    quarters = snapshot.last_n_quarters(4)
    if len(quarters) < 4:
        return None
    total = 0.0
    for period in quarters:
        value = financial_value(period, code)
        if value is None:
            return None
        total += value
    return total


def _roe_ttm(snapshot: FeatureSnapshot) -> float | None:
    profit = _ttm_sum(snapshot, C_NET_PROFIT)
    return _ratio(profit, financial_value(snapshot.latest(), C_EQUITY))


def _roa_ttm(snapshot: FeatureSnapshot) -> float | None:
    profit = _ttm_sum(snapshot, C_NET_PROFIT)
    return _ratio(profit, financial_value(snapshot.latest(), C_TOTAL_ASSETS))


def _net_margin(snapshot: FeatureSnapshot) -> float | None:
    return _ratio(
        financial_value(snapshot.latest(), C_NET_PROFIT),
        financial_value(snapshot.latest(), C_REVENUE),
    )


def _cfo_to_net_profit_ttm(snapshot: FeatureSnapshot) -> float | None:
    return _ratio(_ttm_sum(snapshot, C_OPERATING_CF), _ttm_sum(snapshot, C_NET_PROFIT))


# ------------------------------------------------- financial safety (risk)
def _debt_to_equity(snapshot: FeatureSnapshot) -> float | None:
    return _ratio(
        financial_value(snapshot.latest(), C_LIABILITIES),
        financial_value(snapshot.latest(), C_EQUITY),
    )


def _current_ratio(snapshot: FeatureSnapshot) -> float | None:
    return _ratio(
        financial_value(snapshot.latest(), C_CURRENT_ASSETS),
        financial_value(snapshot.latest(), C_CURRENT_LIABILITIES),
    )


# -------------------------------------------------------------- valuation
def _pe_ttm(snapshot: FeatureSnapshot) -> float | None:
    price = snapshot.close()
    eps = _ttm_sum(snapshot, C_EPS)
    if price is None or eps is None or eps <= 0:
        return None  # a loss-making company has no meaningful P/E
    return price / eps


def _shares_outstanding(snapshot: FeatureSnapshot) -> float | None:
    """Derived: TTM net profit ÷ TTM EPS (documented derivation, not a source).

    No share-count feed is connected yet; deriving it from two real numbers
    keeps P/B computable without inventing a figure. ``None`` when EPS is 0.
    """
    return _ratio(_ttm_sum(snapshot, C_NET_PROFIT), _ttm_sum(snapshot, C_EPS))


def _pb(snapshot: FeatureSnapshot) -> float | None:
    price = snapshot.close()
    equity = financial_value(snapshot.latest(), C_EQUITY)
    book_per_share = _ratio(equity, _shares_outstanding(snapshot))
    if price is None or book_per_share is None or book_per_share <= 0:
        return None
    return price / book_per_share


def _dividend_yield_ttm(snapshot: FeatureSnapshot) -> float | None:
    price = snapshot.close()
    amount = snapshot.dividend_amount_ttm
    if price is None or amount is None or price <= 0:
        return None
    return amount / price


# ------------------------------------------------- liquidity (moneyflow)
def _avg_value_20d(snapshot: FeatureSnapshot) -> float | None:
    if not snapshot.values:
        return None
    window = snapshot.values[-20:]
    return sum(window) / len(window)


def _volume_ratio_20d(snapshot: FeatureSnapshot) -> float | None:
    if len(snapshot.volumes) < 20:
        return None
    recent = sum(snapshot.volumes[-5:]) / 5
    baseline = sum(snapshot.volumes[-20:]) / 20
    return _ratio(recent, baseline)


# ------------------------------------------------ catalyst / events (macro)
def _catalyst_event_ttm(snapshot: FeatureSnapshot) -> float | None:
    """Shareholder-return catalyst: 1.0 if a dividend/split happened in 12m."""
    if snapshot.dividend_amount_ttm is None:
        return None
    return 1.0 if snapshot.dividend_amount_ttm > 0 else 0.0


def _redflag_free(snapshot: FeatureSnapshot) -> float | None:
    """1.0 when the red-flag filter passes, 0.0 when flagged.

    ``None`` when the filter could not be evaluated (missing inputs) — the
    ``unchecked`` report drives confidence instead of a fabricated score.
    """
    if snapshot.red_flags is None or snapshot.red_flags.unchecked:
        return None
    return 0.0 if snapshot.red_flags.flags else 1.0


def _feature(
    name: str,
    group: str,
    direction: int,
    fn: Callable[[FeatureSnapshot], float | None],
    *,
    exclude_industries: tuple[str, ...] | None = None,
) -> FeatureSpec:
    if group not in GROUPS:
        raise ValueError(
            f"feature {name!r} declares unknown group {group!r} (have {list(GROUPS)})"
        )
    if direction not in (1, -1):
        raise ValueError(f"feature {name!r} direction must be +1 or -1, got {direction}")
    return FeatureSpec(
        name=name,
        group=group,
        direction=direction,
        fn=fn,
        exclude_industries=exclude_industries,
    )


#: Group mapping (documented so the scoring step never guesses):
#: ``technical`` = trend/momentum/volatility · ``moneyflow`` = liquidity ·
#: ``growth``/``quality``/``valuation`` = fundamentals · ``macro`` = catalyst
#: events · ``governance`` = financial safety + red-flag pass.
FEATURES = (
    # -- technical -------------------------------------------------------
    _feature("price_vs_sma20", GROUP_TECHNICAL, 1, lambda s: _price_vs_sma(s, 20)),
    _feature("price_vs_sma50", GROUP_TECHNICAL, 1, lambda s: _price_vs_sma(s, 50)),
    _feature("price_vs_sma200", GROUP_TECHNICAL, 1, lambda s: _price_vs_sma(s, 200)),
    _feature("return_20d", GROUP_TECHNICAL, 1, lambda s: _return_over(s, 20)),
    _feature("return_63d", GROUP_TECHNICAL, 1, lambda s: _return_over(s, 63)),
    _feature("rs_vs_index_63d", GROUP_TECHNICAL, 1, lambda s: _rs_over_index(s, 63)),
    _feature("macd_hist_pct", GROUP_TECHNICAL, 1, _macd_hist_pct),
    _feature("atr20_pct", GROUP_TECHNICAL, -1, _atr_pct),
    # -- moneyflow -------------------------------------------------------
    _feature("avg_value_20d", "moneyflow", 1, _avg_value_20d),
    _feature("volume_ratio_20d", "moneyflow", 1, _volume_ratio_20d),
    # -- growth ----------------------------------------------------------
    _feature("revenue_yoy", "growth", 1, _revenue_yoy),
    _feature("net_profit_yoy", "growth", 1, _net_profit_yoy),
    _feature("revenue_cagr_3y", "growth", 1, _revenue_cagr_3y),
    # -- quality ---------------------------------------------------------
    _feature("roe_ttm", "quality", 1, _roe_ttm),
    _feature("roa_ttm", "quality", 1, _roa_ttm),
    _feature("net_margin", "quality", 1, _net_margin),
    _feature("cfo_to_net_profit_ttm", "quality", 1, _cfo_to_net_profit_ttm),
    # -- valuation (banks have no meaningful P/B from a share count) ------
    _feature(
        "pe_ttm",
        "valuation",
        -1,
        _pe_ttm,
        exclude_industries=NOT_GENERIC_VALUATION,
    ),
    _feature(
        "pb",
        "valuation",
        -1,
        _pb,
        exclude_industries=NOT_GENERIC_VALUATION,
    ),
    _feature("dividend_yield_ttm", "valuation", 1, _dividend_yield_ttm),
    # -- macro / catalyst ------------------------------------------------
    _feature("catalyst_event_ttm", "macro", 1, _catalyst_event_ttm),
    # -- governance (financial safety) -----------------------------------
    _feature(
        "debt_to_equity",
        "governance",
        -1,
        _debt_to_equity,
        exclude_industries=NOT_GENERIC_LEVERAGE,
    ),
    _feature(
        "current_ratio",
        "governance",
        1,
        _current_ratio,
        exclude_industries=NOT_GENERIC_LEVERAGE,
    ),
    _feature("redflag_free", "governance", 1, _redflag_free),
)


def compute_raw_features(snapshot: FeatureSnapshot) -> dict[str, float | None]:
    """Evaluate every registered feature on ``snapshot``.

    Features that do not apply to the snapshot's industry, or that cannot be
    computed from the available data, come back as ``None`` — never as 0.
    """
    industry = snapshot.industry
    out: dict[str, float | None] = {}
    for spec in FEATURES:
        if not spec.applies_to(industry):
            out[spec.name] = None
            continue
        out[spec.name] = spec.fn(snapshot)
    return out
