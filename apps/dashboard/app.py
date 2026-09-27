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

from collections.abc import Callable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from apps.dashboard.client import DEFAULT_BASE, MarketClient
from apps.dashboard.components import (
    contribution_rows,
    evidence_rows,
    format_date,
    format_percent,
    format_price,
    indicator_dict,
    metric_rows,
    news_rows,
    price_dataframe,
    quality_bar_labels,
    rag_doc_rows,
    ranking_rows,
    signal_label,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="DTCK — AI Investment Platform", page_icon="📊", layout="wide"
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.6rem; padding-bottom: 2rem;}
      div[data-testid="stMetric"] {
          background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px;
          padding: 12px 14px;
      }
      div[data-testid="stMetricValue"] {font-size: 1.45rem;}
      .dtck-badge {
          display:inline-block; padding:4px 10px; border-radius:999px;
          font-size:0.82rem; font-weight:600; margin-bottom:6px;
      }
      .dtck-badge-real {background:#dcfce7; color:#166534;}
      .dtck-badge-demo {background:#fee2e2; color:#991b1b;}
      .dtck-sub {color:#475569; font-size:0.85rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

# Page registry — order defines the sidebar navigation (T015b: one radio nav
# instead of the old radio + three context checkboxes).
PAGE_NAMES = (
    "📈 Tổng quan",
    "🔍 Bộ lọc",
    "🏆 Xếp hạng",
    "🧭 Chi tiết mã",
    "🧪 Backtest",
    "📰 Tin tức & RAG",
    "🩺 Sức khỏe",
)

with st.sidebar:
    st.title("📊 DTCK")
    # Default comes from the environment (compose sets API_HOST=http://api:8000);
    # hardcoding localhost here used to make the container call itself, fail, and
    # silently render the in-memory fixture — the "fake data" bug (T015b).
    api_host = st.text_input("API host", value=DEFAULT_BASE, key="api_host")
    client = MarketClient(base_url=api_host)
    ready = client.probe()
    kind, detail = client.source_badge()
    if kind == "api":
        market_source = str(ready.get("market_source", "?"))
        st.markdown(
            f'<span class="dtck-badge dtck-badge-real">● DỮ LIỆU THẬT — {market_source}</span>'
            f'<div class="dtck-sub">{detail}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="dtck-badge dtck-badge-demo">▲ DỮ LIỆU MÔ PHỎNG (API offline)</span>'
            f'<div class="dtck-sub">{detail}</div>',
            unsafe_allow_html=True,
        )
    if st.button("🔄 Làm mới dữ liệu", type="primary"):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    page = st.radio("Điều hướng", PAGE_NAMES)
    st.divider()
    st.caption("Tài liệu: `docs/DEPLOYMENT_vi.md` · `docs/api.html`")


# ---------------------------------------------------------------------------
# Page 1 — Market Overview
# ---------------------------------------------------------------------------
def page_market_overview() -> None:
    st.header("📈 Tổng quan thị trường")
    st.caption("Chỉ số, chế độ thị trường, độ rộng và xếp hạng mới nhất từ API.")
    c = client
    indices = c.get_indices()
    breadth = c.get_breadth()
    regime = c.get_regime()
    ranked = c.get_ranked()

    # --- KPI row -----------------------------------------------------------
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        if indices:
            ix = indices[0]
            base = float(str(ix.get("open", 1))) or 1.0
            close = float(str(ix.get("close", 0)))
            st.metric(
                str(ix.get("index_code", "Chỉ số")),
                format_price(close),
                format_percent((close - base) / base, signed=True),
            )
        else:
            st.metric("Chỉ số", "—")
    with k2:
        st.metric(
            "Độ rộng (tăng/giảm)",
            f"{breadth.get('advancers', 0)} / {breadth.get('decliners', 0)}",
            f"{int(breadth.get('advancers', 0)) - int(breadth.get('decliners', 0)):+d}",
        )
    with k3:
        st.metric(
            "Chế độ thị trường",
            str(regime.get("regime", "N/A")),
            f"tin cậy {float(regime.get('confidence', 0)):.0%}",
        )
    with k4:
        scored_symbols = len(ranked)
        st.metric("Mã đã chấm điểm", f"{scored_symbols}")
    st.caption(
        f"Ngày dữ liệu: {format_date(breadth.get('trade_date'))} · "
        f"nguồn đọc: {ready.get('market_source', '?')} · "
        f"model: {ready.get('dependencies', {}).get('models', '?')}"
    )
    st.divider()

    # --- Index table + top scores -------------------------------------------
    col_left, col_right = st.columns([1, 2])
    with col_left:
        st.subheader("Chỉ số")
        if indices:
            idx_rows = [
                {
                    "Mã": ix.get("index_code"),
                    "Đóng cửa": format_price(ix.get("close")),
                    "KL": f"{float(str(ix.get('volume', 0))):,.0f}",
                    "Ngày": format_date(ix.get("trade_date")),
                }
                for ix in indices
            ]
            st.dataframe(pd.DataFrame(idx_rows), hide_index=True, width="stretch")
        else:
            st.info("Chưa có dữ liệu chỉ số.")
    with col_right:
        st.subheader("Top 10 điểm tổng hợp")
        top = [r for r in ranked if r.get("overall_score") is not None][:10]
        if top:
            colors = [
                "#16a34a" if r.get("signal") == "POSITIVE"
                else "#dc2626" if r.get("signal") == "NEGATIVE"
                else "#64748b"
                for r in top
            ]
            fig = go.Figure(
                go.Bar(
                    x=[r.get("symbol") for r in top],
                    y=[float(r.get("overall_score") or 0) for r in top],
                    marker_color=colors,
                    text=[signal_label(r.get("signal", "")) for r in top],
                    textposition="outside",
                )
            )
            fig.update_layout(
                height=340,
                yaxis_title="Điểm tổng hợp (0–100)",
                margin=dict(t=30, b=10),
                showlegend=False,
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Chưa có bảng xếp hạng — hãy chạy `compute-scores`.")


# ---------------------------------------------------------------------------
# Page 2 — Stock Screener
# ---------------------------------------------------------------------------
def page_screener() -> None:
    st.header("🔍 Bộ lọc cổ phiếu")
    c = client
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
        width="stretch",
    )


# ---------------------------------------------------------------------------
# Page 3 — Rankings
# ---------------------------------------------------------------------------
def page_rankings() -> None:
    st.header("🏆 Xếp hạng cổ phiếu")
    st.caption("Điểm đa yếu tố (§12) kèm tín hiệu và độ tin cậy — dữ liệu từ API.")
    c = client
    ranked = c.get_ranked()
    rows = ranking_rows(ranked)
    if not rows:
        st.info("Chưa có xếp hạng — chạy `compute-scores` trước.")
        return

    signals = sorted({str(r.get("signal") or "NEUTRAL") for r in rows})
    chosen = st.multiselect("Lọc theo tín hiệu", options=signals, default=signals)
    filtered = [r for r in rows if str(r.get("signal") or "NEUTRAL") in chosen]

    col_chart, col_stat = st.columns([3, 2])
    with col_chart:
        top = [r for r in filtered if r.get("overall_score") is not None][:15]
        if top:
            fig = go.Figure(
                go.Bar(
                    x=[r["symbol"] for r in top],
                    y=[float(r["overall_score"] or 0) for r in top],
                    marker_color=[
                        "#16a34a" if r.get("signal") == "POSITIVE"
                        else "#dc2626" if r.get("signal") == "NEGATIVE"
                        else "#64748b"
                        for r in top
                    ],
                )
            )
            fig.update_layout(
                height=360, yaxis_title="Điểm tổng hợp", margin=dict(t=20, b=10)
            )
            st.plotly_chart(fig, width="stretch")
    with col_stat:
        by_signal = pd.Series([str(r.get("signal") or "NEUTRAL") for r in filtered])
        st.metric("Số mã hiển thị", str(len(filtered)))
        counts = by_signal.value_counts().to_dict()
        st.write(
            {
                signal_label(k): int(v)
                for k, v in sorted(counts.items(), key=lambda kv: -kv[1])
            }
        )

    st.dataframe(
        pd.DataFrame(filtered),
        column_config={
            "rank": st.column_config.NumberColumn("Hạng", width="small"),
            "symbol": st.column_config.TextColumn("Mã", width="small"),
            "overall_score": st.column_config.NumberColumn("Điểm", format="%.1f"),
            "signal": st.column_config.TextColumn("Tín hiệu"),
            "confidence": st.column_config.NumberColumn("Độ tin cậy", format="%.0%"),
        },
        hide_index=True,
        width="stretch",
    )


# ---------------------------------------------------------------------------
# Page 4 — Stock Detail
# ---------------------------------------------------------------------------
def page_stock_detail(symbol: str = "FPT") -> None:
    st.header(f"📋 Chi tiết mã {symbol}")
    c = client
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
            st.plotly_chart(fig, width="stretch")

    # Price chart
    prices = c.get_prices(symbol)
    if prices:
        pdf = price_dataframe(prices)
        dfp = pd.DataFrame(pdf)
        dfp["MA20"] = dfp["close"].rolling(20).mean()
        dfp["MA50"] = dfp["close"].rolling(50).mean()
        st.subheader("Biểu đồ giá & khối lượng")
        window = st.radio(
            "Khoảng thời gian",
            options=["6 tháng", "1 năm", "Toàn bộ (2 năm)"],
            index=1,
            horizontal=True,
            key=f"range_{symbol}",
        )
        bars = {"6 tháng": 126, "1 năm": 252}.get(window)
        view = dfp.tail(bars) if bars else dfp
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            row_heights=[0.72, 0.28],
            vertical_spacing=0.04,
            subplot_titles=(f"{symbol} — nến ngày", "Khối lượng"),
        )
        fig.add_trace(
            go.Candlestick(
                x=view["date"],
                open=view["open"],
                high=view["high"],
                low=view["low"],
                close=view["close"],
                name=symbol,
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=view["date"], y=view["MA20"], name="MA20", line=dict(color="#2563eb")),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=view["date"], y=view["MA50"], name="MA50", line=dict(color="#f59e0b")),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Bar(x=view["date"], y=view["volume"], name="KL", marker_color="#94a3b8"),
            row=2,
            col=1,
        )
        fig.update_layout(
            height=560,
            xaxis_rangeslider_visible=False,
            margin=dict(t=50, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, width="stretch")
        last = view.iloc[-1]
        d1 = st.columns(4)
        d1[0].metric("Giá đóng cửa", format_price(last["close"]))
        d1[1].metric("Cao / Thấp", f"{float(last['high']):,.0f} / {float(last['low']):,.0f}")
        d1[2].metric("Khối lượng", f"{float(last['volume']):,.0f}")
        d1[3].metric("Ngày", format_date(last["date"]))

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
                st.plotly_chart(dfig, width="stretch")


# ---------------------------------------------------------------------------
# Page 5 — Backtests
# ---------------------------------------------------------------------------
def _format_metric(name: str, value: float) -> str:
    """Render a §16 metric with the unit that actually fits it.

    The old page printed every metric as a percentage (``{value:.2%}``), which
    turned Sharpe 1.2 into "120%".
    """
    percent_like = (
        "return",
        "volatility",
        "drawdown",
        "win_rate",
        "turnover",
        "cost",
        "cagr",
    )
    if any(token in name for token in percent_like):
        return f"{value:.2%}"
    return f"{value:,.3f}"


def page_backtests() -> None:
    st.header("🧪 Backtest")
    st.caption("Lượt chạy đã lưu trong CSDL, chỉ số §16 và nhật ký lệnh.")
    c = client
    backtests = c.get_backtests()
    if not backtests:
        st.info(
            "Chưa có backtest nào trong CSDL. Tạo lượt chạy bằng "
            "`POST /api/v1/backtests` (chế độ DB)."
        )
        return
    ids = [str(b["id"]) for b in backtests]
    labels = {
        str(b["id"]): f"{b.get('strategy_name', '?')} · {b.get('start_date')} → {b.get('end_date')}"
        for b in backtests
    }
    selected = st.selectbox(
        "Chọn lượt chạy", options=ids, format_func=lambda x: labels.get(x, x)
    )
    detail = c.get_backtest(selected)
    if detail:
        st.subheader(str(detail.get("strategy_name", "Chiến lược")))
        st.caption(
            f"Loại: {detail.get('run_type')} · Vũ trụ: {detail.get('universe')} · "
            f"Chi phí: {detail.get('transaction_cost_bps')} bps + "
            f"{detail.get('slippage_bps')} bps"
        )
        metrics = c.get_backtest_metrics(selected)
        mrows = metric_rows(metrics)
        if mrows:
            st.subheader("Chỉ số đo (§16)")
            cols = st.columns(min(len(mrows), 4))
            for i, m in enumerate(mrows):
                cols[i % len(cols)].metric(
                    m["metric"], _format_metric(str(m["metric"]), float(m["value"]))
                )
        else:
            st.info("Lượt chạy này chưa có chỉ số (engine chưa ghi).")
        st.subheader("Giao dịch")
        trades = c.get_backtest_trades(selected)
        if trades:
            st.dataframe(pd.DataFrame(trades), hide_index=True, width="stretch")
        else:
            st.info("Chưa có giao dịch nào được ghi cho lượt chạy này.")


# ---------------------------------------------------------------------------
# Page 6 — News & RAG Evidence
# ---------------------------------------------------------------------------
def page_news_rag() -> None:
    st.header("📰 Tin tức & Bằng chứng RAG")
    c = client

    tab_news, tab_rag, tab_status = st.tabs(
        ["Tin tức thị trường", "Truy vấn bằng chứng RAG", "Trạng thái RAG"]
    )

    with tab_news:
        st.subheader("Dòng tin tức tài chính đã thu thập")
        col_sym, col_src, col_lim = st.columns([1, 1, 1])
        with col_sym:
            filter_sym = st.text_input(
                "Lọc theo mã (ví dụ: FPT)", value="", key="news_filter_sym"
            ).strip().upper()
        with col_src:
            filter_src = st.selectbox(
                "Nguồn tin",
                options=["Tất cả", "cafef", "fixture"],
                index=0,
                key="news_filter_src",
            )
        with col_lim:
            limit_val = st.slider(
                "Số lượng tin",
                min_value=5,
                max_value=100,
                value=20,
                step=5,
                key="news_limit",
            )

        src_arg = None if filter_src == "Tất cả" else filter_src
        sym_arg = filter_sym or None
        news_items = c.get_news(symbol=sym_arg, source=src_arg, limit=limit_val)
        if news_items:
            rows = news_rows(news_items, limit=limit_val)
            ndf = pd.DataFrame(rows)
            st.dataframe(
                ndf,
                column_config={
                    "title": st.column_config.TextColumn("Tiêu đề", width="medium"),
                    "symbols": st.column_config.TextColumn("Mã liên quan"),
                    "source": st.column_config.TextColumn("Nguồn"),
                    "published": st.column_config.TextColumn("Ngày đăng"),
                    "url": st.column_config.LinkColumn("Link gốc"),
                },
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("Chưa có tin tức nào phù hợp.")

    with tab_rag:
        st.subheader("Tìm kiếm ngữ nghĩa & Trích xuất bằng chứng")
        col_q, col_qsym = st.columns([3, 1])
        with col_q:
            query = st.text_input(
                "Truy vấn ngữ nghĩa", value="lợi nhuận tăng trưởng", key="rag_query"
            )
        with col_qsym:
            rag_symbol = st.text_input(
                "Mã CK (tùy chọn)", value="", key="rag_symbol"
            ).strip().upper()

        if st.button("🔎 Tìm kiếm bằng chứng", key="btn_rag_search"):
            st.markdown("### Kết quả bằng chứng (§19 Evidence)")
            ev_items = c.get_evidence(query=query, symbol=rag_symbol or None, top_k=5)
            if ev_items:
                erows = evidence_rows(ev_items)
                st.dataframe(
                    pd.DataFrame(erows),
                    column_config={
                        "symbol": st.column_config.TextColumn("Mã"),
                        "confidence": st.column_config.NumberColumn("Độ tin cậy", format="%.2f"),
                        "source": st.column_config.TextColumn("Nguồn"),
                        "published": st.column_config.TextColumn("Ngày đăng"),
                        "snippet": st.column_config.TextColumn(
                            "Đoạn trích chứng cứ", width="large"
                        ),
                        "chunk_id": st.column_config.TextColumn("Chunk ID"),
                    },
                    hide_index=True,
                    width="stretch",
                )
            else:
                st.info("Không tìm thấy bằng chứng nào liên quan.")

            st.markdown("### Tài liệu liên quan (Hybrid Search)")
            rag_res = c.search_rag(query=query, symbol=rag_symbol or None, top_k=5)
            doc_items = rag_res.get("items", [])
            if doc_items:
                drows = rag_doc_rows(doc_items)
                st.dataframe(
                    pd.DataFrame(drows),
                    column_config={
                        "symbol": st.column_config.TextColumn("Mã"),
                        "score": st.column_config.NumberColumn("Điểm khớp", format="%.4f"),
                        "source": st.column_config.TextColumn("Nguồn"),
                        "published": st.column_config.TextColumn("Ngày đăng"),
                        "content": st.column_config.TextColumn("Nội dung", width="large"),
                    },
                    hide_index=True,
                    width="stretch",
                )

    with tab_status:
        st.subheader("Trạng thái RAG Engine")
        st.json(c.get_rag_status())


# ---------------------------------------------------------------------------
# Page 7 — System Health
# ---------------------------------------------------------------------------
def page_health() -> None:
    st.header("🩺 Sức khỏe hệ thống")
    st.caption("Trạng thái phụ thuộc trực tiếp từ `/healthz` và `/readyz`.")
    c = client
    ready = c.probe()
    health = c.get_health()

    ok = bool(health.get("status") == "ok") and bool(ready.get("status") == "ready")
    if ok:
        st.success("Hệ thống sẵn sàng (liveness + readiness đều OK).")
    else:
        st.error("Hệ thống chưa sẵn sàng — xem chi tiết bên dưới.")

    k1, k2, k3 = st.columns(3)
    k1.metric("/healthz", str(health.get("status", "?")))
    k2.metric("/readyz", str(ready.get("status", "?")))
    k3.metric("Nguồn dữ liệu đọc", str(ready.get("market_source", "?")))

    deps = ready.get("dependencies", {}) if isinstance(ready, dict) else {}
    if deps:
        st.subheader("Phụ thuộc")
        dependency_rows = [
            {
                "Thành phần": name,
                "Trạng thái": str(state),
                "Đánh giá": "🟢 OK"
                if str(state)
                not in ("unreachable", "unavailable", "offline-index-ready", "stub")
                else "🟡 dự phòng",
            }
            for name, state in deps.items()
        ]
        st.dataframe(pd.DataFrame(dependency_rows), hide_index=True, width="stretch")

    st.subheader("Số liệu vận hành (/metrics)")
    metrics_text = c.get_metrics_text()
    if not metrics_text:
        st.info(
            "Không đọc được `/metrics` (có thể đang bật `API_AUTH_KEY` nên endpoint "
            "yêu cầu Bearer). Scrape trực tiếp bằng Prometheus/cron kèm header."
        )
    else:
        requests = [
            line
            for line in metrics_text.splitlines()
            if line.startswith("dtck_http_requests_total")
        ]
        agent_runs = [
            line
            for line in metrics_text.splitlines()
            if line.startswith("dtck_agent_runs_total{")
        ]
        if requests:
            rows = []
            for line in requests:
                try:
                    labels, value = line.rsplit(" ", 1)
                    route = labels.split('route="')[1].split('"')[0]
                    status = labels.split('status="')[1].split('"')[0]
                    rows.append({"Route": route, "HTTP": status, "Số lượt": int(float(value))})
                except (IndexError, ValueError):
                    continue
            if rows:
                st.dataframe(
                    pd.DataFrame(rows).sort_values("Số lượt", ascending=False),
                    hide_index=True,
                    width="stretch",
                )
        if agent_runs:
            st.caption("Lượt chạy tác tử: " + " · ".join(agent_runs))
        with st.expander("Nội dung /metrics thô"):
            st.code(metrics_text, language="text")

    with st.expander("JSON gốc"):
        st.json(health)
        st.json(ready)


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
PAGES: dict[str, Callable[[], None]] = {
    "📈 Tổng quan": page_market_overview,
    "🔍 Bộ lọc": page_screener,
    "🏆 Xếp hạng": page_rankings,
    "🧭 Chi tiết mã": lambda: page_stock_detail(
        st.text_input("Mã cổ phiếu", value="FPT", key="detail_symbol").strip().upper()
    ),
    "🧪 Backtest": page_backtests,
    "📰 Tin tức & RAG": page_news_rag,
    "🩺 Sức khỏe": page_health,
}

PAGES[page]()
