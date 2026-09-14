"""T007 tests (part 1): fundamental, valuation, momentum."""

from __future__ import annotations

from src.market.fundamental import factors as fund
from src.market.momentum import momentum as mom
from src.market.valuation import valuation as val


def _approx(a: float | None, b: float | None, tol: float = 1e-9) -> bool:
    if a is None or b is None:
        return a is b
    return abs(a - b) <= tol


class TestFundamental:
    def test_revenue_growth(self) -> None:
        result = fund.revenue_growth([100.0, 120.0, 132.0])
        assert result[0] is None
        assert _approx(result[1], 0.2)
        assert _approx(result[2], 0.1)

    def test_zero_denominators(self) -> None:
        assert fund.revenue_growth([0.0, 100.0]) == [None, None]
        assert fund.roe(10.0, 0.0) is None
        assert fund.roa(10.0, 0.0) is None
        assert fund.gross_margin(10.0, 0.0) is None
        assert fund.operating_margin(10.0, 0.0) is None
        assert fund.net_margin(10.0, 0.0) is None
        assert fund.debt_to_equity(10.0, 0.0) is None
        assert fund.fcf_margin(10.0, 0.0) is None
        assert fund.earnings_quality(0.0, 100.0) is None

    def test_ratios(self) -> None:
        assert _approx(fund.roe(20.0, 100.0), 0.2)
        assert _approx(fund.roa(20.0, 200.0), 0.1)
        assert _approx(fund.gross_margin(60.0, 100.0), 0.6)
        assert _approx(fund.operating_margin(25.0, 100.0), 0.25)
        assert _approx(fund.net_margin(15.0, 100.0), 0.15)
        assert _approx(fund.debt_to_equity(50.0, 100.0), 0.5)
        assert _approx(fund.interest_coverage(100.0, 20.0), 5.0)
        assert fund.free_cash_flow(80.0, 30.0) == 50.0
        assert _approx(fund.fcf_margin(50.0, 200.0), 0.25)
        assert _approx(fund.earnings_quality(100.0, 120.0), 1.2)


class TestValuation:
    def test_ratios(self) -> None:
        assert _approx(val.pe(100.0, 5.0), 20.0)
        assert _approx(val.forward_pe(100.0, 10.0), 10.0)
        assert _approx(val.pb(50.0, 10.0), 5.0)
        assert _approx(val.ev_ebitda(1000.0, 200.0), 5.0)
        assert _approx(val.ev_sales(1000.0, 500.0), 2.0)
        assert _approx(val.dividend_yield(2.0, 50.0), 0.04)
        assert _approx(val.peg(20.0, 10.0), 2.0)
        assert val.enterprise_value(1000.0, 200.0, 100.0) == 1100.0

    def test_invalid_inputs(self) -> None:
        assert val.pe(100.0, 0.0) is None
        assert val.pe(100.0, -5.0) is None
        assert val.ev_ebitda(1000.0, 0.0) is None
        assert val.dividend_yield(2.0, 0.0) is None
        assert val.peg(20.0, 0.0) is None

    def test_percentiles(self) -> None:
        assert val.percentile_rank(5.0, [1.0, 2.0, 3.0, 4.0, 6.0]) == 80.0
        assert val.percentile_rank(1.0, [1.0, 2.0, 3.0]) == 0.0
        assert val.percentile_rank(5.0, []) is None


class TestMomentum:
    def test_return_n(self) -> None:
        result = mom.return_n([100.0, 110.0, 121.0], 1)
        assert result[0] is None
        assert _approx(result[1], 0.1)
        assert _approx(result[2], 0.1)

    def test_volume_expansion(self) -> None:
        result = mom.volume_expansion([100, 100, 100, 200], 4)
        assert result[:3] == [None, None, None]
        assert _approx(result[3], 1.6)

    def test_relative_momentum(self) -> None:
        stock = [100.0, 110.0, 121.0]
        bench = [100.0, 105.0, 110.25]
        result = mom.relative_momentum(stock, bench, 1)
        assert result[0] is None
        assert _approx(result[1], 2.0)
        assert _approx(result[2], 2.0)
