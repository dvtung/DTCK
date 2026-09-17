"""Backtesting execution engine (SYSTEM_SPECIFICATION §16, BACKTESTING.md §2/§6).

Pipeline: signal at close of day t → trade executed at open of day t+1
(next-bar-open fill). This removes look-ahead bias by construction. Position
sizing follows target weights produced by a user strategy; the remainder stays
in cash (short selling is out of MVP scope).

Accounting contract:
* every fill pays ``commission_bps + slippage_bps``; the engine is the source of
  truth for the charged cost and the traded notional (reported through
  ``compute_metrics`` overrides so metrics never re-derive them from the trade
  log),
* the equity curve is marked to market at each close, and the final point is
  re-marked **after** the end-of-window liquidation so ``final_equity()``
  includes its cost,
* rebalances smaller than ``MIN_REBALANCE_PCT`` of portfolio value are left
  alone (a no-trade band: chasing sub-0.5% drift just burns commission).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from src.backtesting.metrics import compute_metrics
from src.backtesting.models import BacktestConfig, BacktestData, BacktestResult, EquityPoint, Trade

__all__ = [
    "run_backtest",
    "Strategy",
    "select_window",
    "MIN_REBALANCE_PCT",
]

# A strategy maps (data, index i) -> target weight per symbol (fraction of equity,
# 0..1). It may read only data up to and including close of day i. Returns dict
# of symbol -> weight. Sum may be < 1 (cash remainder).
Strategy = Callable[[BacktestData, int, dict[str, object]], dict[str, float]]

# Rebalance band: |target - current| notional below this share of portfolio value
# is not traded (deterministic, documented, keeps the trade log economically clean).
MIN_REBALANCE_PCT = 0.005


@dataclass
class _ExecutionLedger:
    """Actual fills charged by the engine (exact cost + traded notional)."""

    traded_notional: float = 0.0
    cost_total: float = 0.0

    def fill(self, notional: float, cost_bps: float) -> None:
        cost = abs(notional) * cost_bps
        self.traded_notional += abs(notional)
        self.cost_total += cost


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
    ledger = _ExecutionLedger()

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
                data, i, pending_targets, cash, shares, open_trades, trades, cost_bps, ledger
            )
            pending_targets = {}

        # 2) Ask the strategy for the target portfolio using data up to close i.
        pending_targets = dict(strategy(data, i, ctx) or {})

        # 3) Mark-to-market at close i.
        curve.append(EquityPoint(date=current_date, equity=equity_at_close(i)))

    # 4) Close any open positions at the final close for a clean trade log, then
    #    re-mark the last point: after liquidation the portfolio is pure cash.
    cash, shares, trades, open_trades = _close_all(
        data, end, cash, shares, open_trades, trades, cost_bps, ledger
    )
    if curve:
        curve[-1] = EquityPoint(date=curve[-1].date, equity=cash)

    metrics = compute_metrics(
        curve,
        trades,
        initial_capital=config.initial_capital,
        commission_bps=commission,
        slippage_bps=slippage,
        traded_notional=ledger.traded_notional,
        execution_cost=ledger.cost_total,
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
    ledger: _ExecutionLedger,
) -> tuple[float, dict[str, float], list[Trade], dict[str, dict[str, object]]]:
    """Buy/sell to reach ``target_weights`` at open of bar ``i``.

    Sells are executed before buys so freed cash funds the rebalance (no
    implicit margin). A partial sell closes only the sold quantity and keeps the
    remainder as an open leg with the original entry price/date; adding to a
    position merges into the open leg at the volume-weighted entry price.
    """
    port_value = cash + sum(shares[s] * data.open_at(s, i) for s in data.symbols)
    if port_value <= 0:
        return cash, shares, trades, open_trades

    weight_sum = sum(target_weights.values())
    if weight_sum > 1.0 + 1e-9:
        raise ValueError(f"target weights sum to {weight_sum:.4f} (> 1.0)")
    band = max(1e-12, MIN_REBALANCE_PCT * port_value)

    def _delta(symbol: str) -> float:
        weight = target_weights.get(symbol, 0.0)
        if weight < 0 or weight > 1:
            raise ValueError(f"target weight for {symbol} out of range: {weight}")
        return weight * port_value / data.open_at(symbol, i) - shares[symbol]

    for s in data.symbols:
        delta = _delta(s)
        exec_price = data.open_at(s, i)
        if delta >= 0 or abs(delta) * exec_price < band:
            continue  # buys run in the second pass; sub-band drift is left alone
        notional = delta * exec_price
        cash -= notional
        cash -= abs(notional) * cost_bps
        ledger.fill(notional, cost_bps)
        shares[s] += delta

        leg = open_trades.pop(s, None)
        if leg is not None:
            sold = -delta
            leg_qty = float(str(leg["quantity"]))
            if leg_qty <= sold + 1e-12:
                trades.append(_close_leg(leg, s, i, data.dates[i], exec_price))
            else:
                # Partial close: record only the sold quantity; the remainder
                # stays open with the original entry price/date.
                trades.append(
                    _close_leg(leg, s, i, data.dates[i], exec_price, quantity=sold)
                )
                open_trades[s] = {
                    "entry_date": leg["entry_date"],
                    "entry_price": leg["entry_price"],
                    "quantity": leg_qty - sold,
                }

    for s in data.symbols:
        delta = _delta(s)
        exec_price = data.open_at(s, i)
        if delta <= 0 or delta * exec_price < band:
            continue
        notional = delta * exec_price
        cash -= notional
        cash -= abs(notional) * cost_bps
        ledger.fill(notional, cost_bps)
        shares[s] += delta

        leg = open_trades.get(s)
        if leg is None:
            open_trades[s] = {
                "entry_date": data.dates[i],
                "entry_price": exec_price,
                "quantity": delta,
            }
        else:
            # Average-cost accounting: merge the add into the open leg so the
            # log keeps one position instead of a spurious same-price round trip.
            leg_qty = float(str(leg["quantity"]))
            leg_price = float(str(leg["entry_price"]))
            new_qty = leg_qty + delta
            leg["entry_price"] = (leg_price * leg_qty + exec_price * delta) / new_qty
            leg["quantity"] = new_qty

    return cash, shares, trades, open_trades


def _close_leg(
    leg: dict[str, object],
    symbol: str,
    i: int,
    exit_date: date,
    exit_price: float,
    quantity: float | None = None,
) -> Trade:
    entry_price = float(str(leg["entry_price"]))
    qty = quantity if quantity is not None else float(str(leg["quantity"]))
    pnl = (exit_price - entry_price) * qty
    ret = (exit_price / entry_price - 1.0) if entry_price else 0.0
    return Trade(
        symbol=symbol,
        entry_date=leg["entry_date"],  # type: ignore[arg-type]
        exit_date=exit_date,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=qty,
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
    ledger: _ExecutionLedger,
) -> tuple[float, dict[str, float], list[Trade], dict[str, dict[str, object]]]:
    for s, leg in list(open_trades.items()):
        exec_price = data.close_at(s, i)
        notional = shares[s] * exec_price
        cash += notional
        cash -= notional * cost_bps
        ledger.fill(notional, cost_bps)
        trades.append(_close_leg(leg, s, i, data.dates[i], exec_price))
        shares[s] = 0.0
        del open_trades[s]
    return cash, shares, trades, open_trades
