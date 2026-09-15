"""DTCK Dashboard — Streamlit web UI (T011).

Pages/tabs:
  1. Market Overview  — indices, regime, breadth
  2. Stock Screener   — filtered stock list
  3. Rankings         — score rankings with explainability
  4. Stock Detail     — prices, indicators, valuation, decomposition
  5. Backtests        — list runs, metrics, trades
  6. System Health    — API/readiness probes

Run:
    streamlit run apps/dashboard/app.py
    # or in Docker Compose: docker compose up dashboard  (port 8501)
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from apps.dashboard.client import MarketClient
from apps.dashboard.components import (
    contribution_rows,
    format_date,
    format_percent,
    format_price,
    indicator_dict,
    metric_rows,
    price_dataframe,
    quality_bar_labels,
    ranking_rows,
    signal_label,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
st.set_page_config(page_title="DTCK — AI Investment Platform", layout="wide")

with st.sidebar:
    st.title("⚙️ DTCK")
    api_host = st.text_input("API host", value="http://localhost:8000", key="api_host")
    st.caption("Đặt `API_HOST` môi trường để thay đổi mặc định.")
    if st.button("🔄 Làm mới", type="primary"):
        st.cache_data.clear()
    st.divider()
    st.caption("Tài liệu: docs/DEPLOYMENT.md · docs/htmldocs/api.html")


def _fetch() -> MarketClient:
    return MarketClient(base_url=api_host)


# ---------------------------------------------------------------------------
# Page 1 — Market Overview
# ---------------------------------------------------------------------------
def page_market_overview() -> None:
    st.header("📈 Tổng quan thị trường")
    c = _fetch()
    col_idx, col_reg, col_br = st.columns(3)
    with col_idx:
        st.subheader("Chỉ số")
        indices = c.get_indices()
        for ix in indices:
            change = float(str(ix.get("close", 0))) - float(str(ix.get("open", 0)))
            base = float(str(ix.get("open", 1))) or 1.0
            pct = change / base
            code = ix.get("index_code", "?")
            close = format_price(ix.get("close"))
            chg = format_percent(pct, signed=True)
            st.metric(code, close, chg)
    with col_reg:
        st.subheader("Chế độ thị trường")
        regime = c.get_regime()
        conf = regime.get("confidence", 0)
        st.markdown(
            f"**{regime.get('regime', 'N/A')}** — độ tin cậy {conf:.0%}"
        )
    with col_br:
        st.subheader("Độ rộng")
        breadth = c.get_breadth()
        st.metric("Tăng", f"{breadth.get('advancers', 0)}")
        st.metric("Giảm", f"{breadth.get('decliners', 0)}")
        st.caption(f"Ngày giao dịch: {format_date(breadth.get('trade_date'))}")


# ---------------------------------------------------------------------------
# Page 2 — Stock Screener
# ---------------------------------------------------------------------------
def page_screener() -> None:
    st.header("🔍 Bộ lọc cổ phiếu")
    c = _fetch()
    stocks = c.list_stocks()
    df = pd.DataFrame(stocks)
    st.data_editor(
        df,
        column_config={
            "symbol": st.column_config.TextColumn("Mã"),
            "price": st.column_config.NumberColumn("Giá", format="%.1f"),
            "sector": st.column_config.TextColumn("Ngành"),
            "is_vn30": st.column_config.CheckboxColumn("VN30"),
        },
        hide_index=True,
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# Page 3 — Rankings
# ---------------------------------------------------------------------------
def page_rankings() -> None:
    st.header("🏆 Xếp hạng cổ phiếu")
    c = _fetch()
    ranked = c.get_ranked()
    rows = ranking_rows(ranked)
    df = pd.DataFrame(rows)
    st.data_editor(
        df,
        column_config={
            "rank": st.column_config.NumberColumn("Hạng"),
            "symbol": st.column_config.TextColumn("Mã"),
            "overall_score": st.column_config.NumberColumn("Điểm", format="%.1f"),
            "signal": st.column_config.TextColumn("Tín hiệu"),
            "confidence": st.column_config.NumberColumn("Độ tin cậy", format="%.0%"),
        },
        hide_index=True,
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# Page 4 — Stock Detail
# ---------------------------------------------------------------------------
def page_stock_detail(symbol: str = "FPT") -> None:
    st.header(f"📋 Chi tiết mã {symbol}")
    c = _fetch()
    stock = c.get_stock(symbol)
    if not stock:
        st.error(f"Không tìm thấy mã {symbol}")
        return
    st.subheader(f"{stock.get('company_name', symbol)}")
    st.caption(f"Sàn: {stock.get('exchange')} · Ngành: {stock.get('industry')}")

    # Ranking snapshot
    ranking = c.get_ranking(symbol)
    if ranking:
        cols = st.columns([2, 1, 1])
        with cols[0]:
            st.metric("Điểm tổng", f"{float(ranking.get('overall_score') or 0):.1f}")
        with cols[1]:
            sig = ranking.get("signal", "NEUTRAL")
            st.markdown(f"**Tín hiệu:** {signal_label(sig)}")
        with cols[2]:
            st.metric("Độ tin cậy", f"{float(ranking.get('confidence', 0)):.0%}")
        contribs = contribution_rows(ranking)
        if contribs:
            cdf = pd.DataFrame(contribs)
            fig = go.Figure(
                data=[
                    go.Bar(
                        x=cdf["factor"],
                        y=cdf["weighted"],
                        marker_color="#2563eb",
                    )
                ]
            )
            fig.update_layout(
                title="Đóng góp điểm số",
                xaxis_title="Hệ số",
                yaxis_title="Điểm số",
                height=300,
            )
            st.plotly_chart(fig, use_container_width=True)

    # Price chart
    prices = c.get_prices(symbol)
    if prices:
        pdf = price_dataframe(prices)
        dfp = pd.DataFrame(pdf)
        st.subheader("Biểu đồ giá")
        fig = go.Figure(
            data=[
                go.Candlestick(
                    x=dfp["date"],
                    open=dfp["open"],
                    high=dfp["high"],
                    low=dfp["low"],
                    close=dfp["close"],
                )
            ]
        )
        fig.update_layout(height=350, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

    # Indicators + valuation + quality
    col_ind, col_val, col_qual = st.columns(3)
    with col_ind:
        inds = c.get_indicators(symbol)
        if inds:
            st.subheader("Chỉ báo Kỹ thuật")
            for k, v in indicator_dict(inds).items():
                st.metric(k.upper(), f"{v:.4f}" if v is not None else "—")
    with col_val:
        val = c.get_valuation(symbol)
        if val:
            st.subheader("Định giá")
            for k in ("pe", "pb", "ev_ebitda", "dividend_yield", "peg"):
                v = val.get(k)
                st.metric(k.upper(), f"{v:.2f}" if v is not None else "—")
    with col_qual:
        q = c.get_quality(symbol)
        if q:
            st.subheader("Chất lượng dữ liệu")
            st.metric("Điểm tổng", f"{float(q.get('overall_score', 0)):.0f}/100")
            if q.get("below_threshold"):
                st.warning("Dưới ngưỡng chất lượng")
            dims = quality_bar_labels(q)
            if dims:
                dfig = go.Figure(data=[go.Bar(x=list(dims.keys()), y=list(dims.values()))])
                dfig.update_layout(height=200, title="6 chiều chất lượng", showlegend=False)
                st.plotly_chart(dfig, use_container_width=True)


# ---------------------------------------------------------------------------
# Page 5 — Backtests
# ---------------------------------------------------------------------------
def page_backtests() -> None:
    st.header("🧪 Backtest")
    c = _fetch()
    backtests = c.get_backtests()
    if not backtests:
        st.info("Chưa có backtest nào được lưu.")
        return
    ids = [b["id"] for b in backtests]
    selected = st.selectbox("Chọn backtest", options=ids,
                            format_func=lambda x: x)
    detail = c.get_backtest(selected)
    if detail:
        st.subheader(detail.get("strategy_name", "Chiến lược"))
        run_type = detail.get("run_type")
        capital = format_price(detail.get("initial_capital", 0))
        st.caption(f"Loại: {run_type} · Vốn: {capital}")
        st.subheader("Chỉ số đo")
        metrics = c.get_backtest_metrics(selected)
        mrows = metric_rows(metrics)
        if mrows:
            cols = st.columns(len(mrows))
            for col, m in zip(cols, mrows, strict=True):
                col.metric(m["metric"], f"{m['value']:.2%}")
        st.subheader("Giao dịch")
        trades = c.get_backtest_trades(selected)
        if trades:
            tdf = pd.DataFrame(trades)
            st.data_editor(tdf, hide_index=True, use_container_width=True)


# ---------------------------------------------------------------------------
# Page 6 — System Health
# ---------------------------------------------------------------------------
def page_health() -> None:
    st.header("🩺 Sức khỏe hệ thống")
    c = _fetch()
    st.json(c.get_health())
    st.json(c._get("/readyz"))  # noqa: SLF001


# ---------------------------------------------------------------------------
# Navigation (sidebar radio + context toggles)
# ---------------------------------------------------------------------------
PAGES: dict[str, object] = {
    "📈 Tổng quan": page_market_overview,
    "🔍 Bộ lọc": page_screener,
    "🏆 Xếp hạng": page_rankings,
}

page = st.sidebar.radio("Điều hướng", list(PAGES.keys()))
PAGES[page]()  # type: ignore[operator]

st.sidebar.markdown("---")
if st.sidebar.checkbox("Chi tiết mã"):
    symbol = st.sidebar.text_input("Mã CK", value="FPT", key="detail_symbol")
    page_stock_detail(symbol)
if st.sidebar.checkbox("Backtests"):
    page_backtests()
if st.sidebar.checkbox("Sức khỏe"):
    page_health()
