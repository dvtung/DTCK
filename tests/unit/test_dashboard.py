"""Unit tests for T011 dashboard components and data client (apps/dashboard).

These tests do NOT require a running Streamlit server or display — they cover
the pure-Python formatting logic and the client's in-process fallback.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from apps.dashboard import components as c
from apps.dashboard.client import MarketClient

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


class TestSignalFormatting:
    def test_label_positive(self) -> None:
        assert c.signal_label("positive") == "🟢 Tích cực"

    def test_label_neutral(self) -> None:
        assert c.signal_label("neutral") == "🟡 Trung tính"

    def test_label_negative(self) -> None:
        assert c.signal_label("NEGATIVE") == "🔴 Tiêu cực"

    def test_label_unknown(self) -> None:
        assert c.signal_label("BOGUS") == "BOGUS"

    def test_color(self) -> None:
        assert c.signal_color("POSITIVE") == "green"
        assert c.signal_color("negative") == "red"


class TestPriceFormat:
    def test_basic(self) -> None:
        result = c.format_price(1234.5)
        assert "234.5" in result

    def test_none(self) -> None:
        assert c.format_price(None) == "—"

    def test_decimal_input(self) -> None:
        assert "123.0" in c.format_price(Decimal("123"))


class TestPercentFormat:
    def test_positive_signed(self) -> None:
        assert c.format_percent(0.05, signed=True) == "+5.0%"

    def test_negative(self) -> None:
        assert c.format_percent(-0.12) == "-12.0%"


class TestDateFormat:
    def test_iso_string(self) -> None:
        assert c.format_date("2026-09-15") == "15/09/2026"

    def test_date_object(self) -> None:
        assert c.format_date(date(2026, 1, 5)) == "05/01/2026"

    def test_datetime_object(self) -> None:
        from datetime import datetime

        assert c.format_date(datetime(2026, 6, 1, 14, 30)) == "01/06/2026"

    def test_none(self) -> None:
        assert c.format_date(None) == "—"


# ---------------------------------------------------------------------------
# Response transforms
# ---------------------------------------------------------------------------


class TestRankingRows:
    def test_basic(self) -> None:
        ranked = [
            {"rank": 1, "symbol": "FPT", "overall_score": 72.5,
             "signal": "POSITIVE", "confidence": 0.88},
            {"rank": 2, "symbol": "VCB", "overall_score": 66.0,
             "signal": "NEUTRAL", "confidence": 0.72},
        ]
        rows = c.ranking_rows(ranked)
        assert rows[0]["symbol"] == "FPT"
        assert rows[0]["overall_score"] == 72.5
        assert rows[1]["rank"] == 2

    def test_missing_score(self) -> None:
        rows = c.ranking_rows([{"symbol": "X", "overall_score": None}])
        assert rows[0]["overall_score"] == 0.0

    def test_empty(self) -> None:
        assert c.ranking_rows([]) == []


class TestContributionRows:
    def test_basic(self) -> None:
        ranking = {
            "symbol": "FPT",
            "contributions": [
                {"factor": "fundamental", "score": 80.0,
                 "weight": 0.3, "weighted_score": 24.0,
                 "contribution_pct": 0.40},
                {"factor": "technical", "score": 60.0,
                 "weight": 0.2, "weighted_score": 12.0,
                 "contribution_pct": 0.20},
            ],
        }
        rows = c.contribution_rows(ranking)
        assert len(rows) == 2
        assert rows[0]["factor"] == "fundamental"
        assert rows[0]["weighted"] == 24.0
        assert rows[1]["share"] == 0.20

    def test_empty(self) -> None:
        assert c.contribution_rows({"symbol": "X", "contributions": []}) == []


class TestPriceDataframe:
    def test_basic(self) -> None:
        prices = [
            {"trade_date": "2026-09-01", "open": 100,
             "high": 105, "low": 98, "close": 102,
             "volume": 1000000},
            {"trade_date": "2026-09-02", "open": 102,
             "high": 103, "low": 100, "close": 101,
             "volume": 1200000}
        ]
        rows = c.price_dataframe(prices)
        assert rows[0]["date"] == "01/09/2026"
        assert rows[0]["close"] == 102.0
        assert rows[1]["volume"] == 1200000

    def test_empty(self) -> None:
        assert c.price_dataframe([]) == []


class TestIndicatorDict:
    def test_basic(self) -> None:
        ind = {"symbol": "FPT", "series": {"sma20": 102.5, "rsi14": 45.3}}
        d = c.indicator_dict(ind)
        assert d["sma20"] == 102.5
        assert d["rsi14"] == 45.3

    def test_none_value(self) -> None:
        ind = {"series": {"sma20": None}}
        assert c.indicator_dict(ind)["sma20"] is None


class TestQualityBarLabels:
    def test_basic(self) -> None:
        q = {"overall_score": 92.0, "below_threshold": False,
             "dimensions": {"completeness": 95, "validity": 90}}
        labels = c.quality_bar_labels(q)
        assert labels["completeness"] == 95.0
        assert labels["validity"] == 90.0

    def test_empty(self) -> None:
        assert c.quality_bar_labels({}) == {}


class TestMetricRows:
    def test_basic(self) -> None:
        metrics = [
            {"metric_name": "cagr", "value": 0.141},
            {"metric_name": "sharpe_ratio", "value": 1.32}
        ]
        rows = c.metric_rows(metrics)
        assert rows[0]["metric"] == "cagr"
        assert rows[0]["value"] == 0.141


class TestNewsRows:
    def test_basic(self) -> None:
        from datetime import datetime

        news = [{"title": "Tin A", "source": "cafef", "published_at": datetime(2026, 9, 3, 8, 0)}]
        rows = c.news_rows(news, limit=5)
        assert rows[0]["title"] == "Tin A"
        assert rows[0]["source"] == "cafef"
        assert rows[0]["published"] == "03/09/2026"

    def test_limit(self) -> None:
        news = [{"title": f"Tin {i}", "source": "s", "published_at": None} for i in range(20)]
        assert len(c.news_rows(news, limit=5)) == 5


# ---------------------------------------------------------------------------
# MarketClient (in-process fallback, no HTTP needed)
# ---------------------------------------------------------------------------


class TestMarketClient:
    def test_client_initializes(self) -> None:
        client = MarketClient(base_url="http://nonexistent:9999")
        assert client.base_url == "http://nonexistent:9999"

    def test_get_indices_fallback(self) -> None:
        client = MarketClient(base_url="http://nonexistent:9999")
        indices = client.get_indices()
        assert len(indices) >= 2
        codes = {i["index_code"] for i in indices}
        assert "VNINDEX" in codes

    def test_get_regime_fallback(self) -> None:
        client = MarketClient(base_url="http://nonexistent:9999")
        regime = client.get_regime()
        assert "regime" in regime
        assert regime["regime"] in {"BULL", "BEAR", "SIDEWAYS", "VOLATILE"}

    def test_get_ranked_fallback(self) -> None:
        client = MarketClient(base_url="http://nonexistent:9999")
        ranked = client.get_ranked()
        assert len(ranked) >= 2
        assert ranked[0]["rank"] == 1

    def test_get_stock_fallback(self) -> None:
        client = MarketClient(base_url="http://nonexistent:9999")
        stock = client.get_stock("FPT")
        assert stock["symbol"] == "FPT"

    def test_get_metrics_fallback(self) -> None:
        client = MarketClient(base_url="http://nonexistent:9999")
        metrics = client.get_backtest_metrics("bt-001")
        assert len(metrics) >= 1
        assert metrics[0]["metric_name"] == "total_return"
