"""Backtesting execution engine (SYSTEM_SPECIFICATION §16, BACKTESTING.md §2/§6).

Pipeline: signal at close of day t → trade executed at open of day t+1
(next-bar-open fill). This removes look-ahead bias by construction. Position
sizing follows target weights produced by a user strategy; the remainder stays
in cash (short selling is out of MVP scope).

Transaction costs (commission + slippage) are deducted from cash on every fill
and summed into ``transaction_cost`` (per BACKTESTING.md §7).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from src.backtesting.metrics import compute_metrics
from src.backtesting.models import BacktestConfig, BacktestData, BacktestResult, EquityPoint, Trade

__all__ = [
    "run_backtest",
    "Strategy",
    "select_window",
]

# A strategy maps (data, index i) -> target weight per symbol (fraction of equity,
# 0..1). It may read only data up to and including close of day i. Returns dict
# of symbol -> weight. Sum may be < 1 (cash remainder).
Strategy = Callable[[BacktestData, int, dict[str, object]], dict[str, float]]


def select_window(
    data: BacktestData,
    start_date: date | None,
    end_date: date | None,
) -> tuple[int, int]:
    """Return inclusive (start, end) index bounds for the requested window.

    Bounds are clamped to the data range; when a bound is None the whole series
    is used. Raises ValueError if the window is empty or index-misaligned.
    """
    n = len(data.dates)
    start = 0
    end = n - 1
    if start_date is not None:
        start = next((i for i, d in enumerate(data.dates) if d >= start_date), end)
    if end_date is not None:
        end = next((i for i in range(n - 1, -1, -1) if data.dates[i] <= end_date), start)
    if start > end:
        raise ValueError("empty backtest window")
    return start, end


def run_backtest(
    data: BacktestData,
    strategy: Strategy,
    config: BacktestConfig,
) -> BacktestResult:
    """Run the engine over ``data`` and return equity curve, trades and metrics."""
    start, end = select_window(data, config.start_date, config.end_date)

    cash = config.initial_capital
    shares: dict[str, float] = {s: 0.0 for s in data.symbols}
    open_trades: dict[str, dict[str, object]] = {}
    trades: list[Trade] = []
    curve: list[EquityPoint] = []
    pending_targets: dict[str, float] = {}
    ctx: dict[str, object] = {}

    commission = config.costs.commission_bps
    slippage = config.costs.slippage_bps
    cost_bps = (commission + slippage) / 10_000.0

    def equity_at_close(i: int) -> float:
        total = cash
        for s in data.symbols:
            total += shares[s] * data.close_at(s, i)
        return total

    for i in range(start, end + 1):
        current_date = data.dates[i]

        # 1) Execute orders decided at close of the previous bar, filled at
        #    today's open (next-bar-open → no look-ahead).
        if pending_targets:
            cash, shares, trades, open_trades = _rebalance(
                data, i, pending_targets, cash, shares, open_trades, trades, cost_bps
            )
            pending_targets = {}

        # 2) Ask the strategy for the target portfolio using data up to close i.
        pending_targets = dict(strategy(data, i, ctx) or {})

        # 3) Mark-to-market at close i.
        curve.append(EquityPoint(date=current_date, equity=equity_at_close(i)))

    # 4) Close any open positions at the final close for a clean trade log.
    cash, shares, trades, open_trades = _close_all(
        data, end, cash, shares, open_trades, trades, cost_bps
    )

    metrics = compute_metrics(
        curve,
        trades,
        initial_capital=config.initial_capital,
        commission_bps=commission,
        slippage_bps=slippage,
    )
    return BacktestResult(
        config=config,
        equity_curve=curve,
        trades=trades,
        metrics=metrics,
    )


def _rebalance(
    data: BacktestData,
    i: int,
    target_weights: dict[str, float],
    cash: float,
    shares: dict[str, float],
    open_trades: dict[str, dict[str, object]],
    trades: list[Trade],
    cost_bps: float,
) -> tuple[float, dict[str, float], list[Trade], dict[str, dict[str, object]]]:
    """Buy/sell to reach ``target_weights`` at open of bar ``i``."""
    port_value = cash + sum(shares[s] * data.open_at(s, i) for s in data.symbols)
    if port_value <= 0:
        return cash, shares, trades, open_trades

    for s in data.symbols:
        weight = target_weights.get(s, 0.0)
        if weight < 0 or weight > 1:
            raise ValueError(f"target weight for {s} out of range: {weight}")
        desired_shares = weight * port_value / data.open_at(s, i)
        delta = desired_shares - shares[s]
        if abs(delta) * data.open_at(s, i) < 1e-9:  # micro-change, skip
            continue
        exec_price = data.open_at(s, i)
        notional = delta * exec_price
        cash -= notional
        cost = abs(notional) * cost_bps
        cash -= cost
        shares[s] += delta

        if open_trades.get(s):
            leg = open_trades.pop(s)
            assert leg is not None
            trades.append(_close_leg(leg, s, i, data.dates[i], exec_price))
        if delta > 0:
            open_trades[s] = {
                "entry_date": data.dates[i],
                "entry_price": exec_price,
                "quantity": delta,
            }

    return cash, shares, trades, open_trades


def _close_leg(
    leg: dict[str, object], symbol: str, i: int, exit_date: date, exit_price: float
) -> Trade:
    entry_price = float(str(leg["entry_price"]))
    quantity = float(str(leg["quantity"]))
    pnl = (exit_price - entry_price) * quantity
    ret = (exit_price / entry_price - 1.0) if entry_price else 0.0
    return Trade(
        symbol=symbol,
        entry_date=leg["entry_date"],  # type: ignore[arg-type]
        exit_date=exit_date,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        pnl=pnl,
        return_pct=ret,
    )


def _close_all(
    data: BacktestData,
    i: int,
    cash: float,
    shares: dict[str, float],
    open_trades: dict[str, dict[str, object]],
    trades: list[Trade],
    cost_bps: float,
) -> tuple[float, dict[str, float], list[Trade], dict[str, dict[str, object]]]:
    for s, leg in list(open_trades.items()):
        exec_price = data.close_at(s, i)
        notional = shares[s] * exec_price
        cash += notional
        cash -= notional * cost_bps
        trades.append(_close_leg(leg, s, i, data.dates[i], exec_price))
        shares[s] = 0.0
        del open_trades[s]
    return cash, shares, trades, open_trades
