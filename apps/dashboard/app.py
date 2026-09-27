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
from datetime import date
from typing import Any

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
      :root {
        --ink:#0f172a; --ink-2:#475569; --line:#e2e8f0; --bg:#ffffff;
        --brand:#1d4ed8; --up:#15803d; --down:#b91c1c; --neutral:#64748b;
      }
      .stApp {background: #f6f8fb;}
      .block-container {padding-top: 1.2rem; padding-bottom: 2.5rem; max-width: 1400px;}
      h1, h2, h3 {color: var(--ink); letter-spacing: -0.01em;}
      section[data-testid="stSidebar"] {
        background: #0f172a; border-right: 1px solid #1e293b;
      }
      section[data-testid="stSidebar"] * {color: #e2e8f0 !important;}
      section[data-testid="stSidebar"] input {
        background: #1e293b !important; color: #f8fafc !important;
      }
      div[data-testid="stMetric"] {
        background: var(--bg); border: 1px solid var(--line);
        border-left: 4px solid var(--brand); border-radius: 12px;
        padding: 14px 16px; box-shadow: 0 1px 2px rgba(15,23,42,.05);
      }
      div[data-testid="stMetricValue"] {font-size: 1.5rem; font-weight: 700;}
      div[data-testid="stMetricLabel"] {color: var(--ink-2); font-weight: 600;}
      .dtck-banner {
        background: linear-gradient(90deg,#0f172a 0%,#1d4ed8 100%);
        color:#fff; border-radius:14px; padding:16px 20px; margin-bottom:14px;
      }
      .dtck-banner h1 {color:#fff; margin:0; font-size:1.35rem;}
      .dtck-banner .sub {color:#c7d2fe; font-size:.85rem; margin-top:4px;}
      .dtck-badge {
        display:inline-block; padding:4px 10px; border-radius:999px;
        font-size:.78rem; font-weight:700; margin-bottom:6px;
      }
      .dtck-badge-real {background:#dcfce7; color:#14532d;}
      .dtck-badge-demo {background:#fee2e2; color:#7f1d1d;}
      .dtck-sub {color:#94a3b8; font-size:.78rem;}
      .dtck-foot {color:var(--ink-2); font-size:.78rem; border-top:1px solid var(--line);
        margin-top:26px; padding-top:10px;}
      div[data-testid="stDataFrame"] {border:1px solid var(--line); border-radius:10px;}
      .stTabs [data-baseweb="tab"] {font-weight:600;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="dtck-banner">
      <h1>📊 DTCK — Nền tảng Nghiên cứu &amp; Hỗ trợ Quyết định Đầu tư</h1>
      <div class="sub">
        Thị trường Việt Nam (HOSE/HNX/UPCOM) · Universe VN30 ·
        Đánh giá định lượng → dự đoán ML → luận điểm AI → con người quyết định
      </div>
    </div>
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
    # JWT session (T016): keep the access token in session_state across reruns.
    if "auth_token" not in st.session_state:
        st.session_state["auth_token"] = ""
    if "auth_email" not in st.session_state:
        st.session_state["auth_email"] = ""
    client = MarketClient(base_url=api_host, token=st.session_state["auth_token"] or None)
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

    # --- Login (T016): JWT via POST /api/v1/auth/login ----------------------
    st.divider()
    if st.session_state["auth_token"]:
        st.markdown(
            f'<span class="dtck-badge dtck-badge-real">● {st.session_state["auth_email"]}</span>',
            unsafe_allow_html=True,
        )
        if st.button("Đăng xuất", key="logout"):
            st.session_state["auth_token"] = ""
            st.session_state["auth_email"] = ""
            st.rerun()
    else:
        with st.form("login_form", clear_on_submit=False):
            st.caption("Đăng nhập để chạy Phân tích AI & Backtest (JWT)")
            email = st.text_input("Email", value="admin@dtck.local", key="login_email")
            password = st.text_input(
                "Mật khẩu", value="admin123", type="password", key="login_password"
            )
            submitted = st.form_submit_button("Đăng nhập", type="primary")
            if submitted:
                result = client.login(email, password)
                if result.get("success"):
                    st.session_state["auth_token"] = client.token or ""
                    st.session_state["auth_email"] = email
                    st.success("Đăng nhập thành công.")
                    st.rerun()
                else:
                    st.error(f"Đăng nhập thất bại: {result.get('error')}")

    st.divider()
    page = st.radio("Điều hướng", PAGE_NAMES)
    st.divider()
    st.caption("Tài liệu: `docs/DEPLOYMENT_vi.md` · `docs/api.html`")


# ---------------------------------------------------------------------------
# Page 1 — Market Overview
# ---------------------------------------------------------------------------
@st.cache_data(ttl=120, show_spinner=False)
def _load_predictions(base_url: str, symbols: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    """Cached ML probability P(return > 0) for the traded universe (§2.8/§26).

    One unavailable symbol must never break the whole overview page.
    """
    api = MarketClient(base_url=base_url)
    out: dict[str, dict[str, Any]] = {}
    for sym in symbols:
        try:
            pred = api.get_prediction(sym)
        except Exception:  # noqa: BLE001 — fallback path may not know the route
            continue
        if pred and pred.get("probability_positive") is not None:
            out[sym] = pred
    return out


def _decision_hint(signal: str, probability: float | None) -> str:
    """Deterministic decision-support label (không phải khuyến nghị đầu tư, §3)."""
    prob = probability if probability is not None else 0.5
    if signal == "POSITIVE" and prob >= 0.55:
        return "🟢 Tín hiệu tích cực"
    if signal == "NEGATIVE" or prob < 0.45:
        return "🔴 Thận trọng"
    return "🟡 Trung tính — theo dõi"


def page_market_overview() -> None:
    st.header("📈 Tổng quan thị trường & dự đoán VN30")
    st.caption(
        "Đánh giá định lượng (§12), dự đoán ML (§26) và mức độ bằng chứng dữ liệu (§39)."
    )
    c = client
    indices = c.get_indices()
    breadth = c.get_breadth()
    regime = c.get_regime()
    ranked = c.get_ranked()

    # --- KPI row -----------------------------------------------------------
    k1, k2, k3, k4, k5 = st.columns(5)
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
            "Độ rộng tăng/giảm",
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
        st.metric("Mã đã chấm điểm", f"{len(ranked)}")
    with k5:
        st.metric("Model phục vụ", str(ready.get("dependencies", {}).get("models", "?")))
    st.caption(
        f"Ngày dữ liệu: {format_date(breadth.get('trade_date'))} · "
        f"chế độ đọc: {ready.get('market_source', '?')} · "
        f"độ rộng tính từ {len(ranked)} mã VN30"
    )
    st.divider()

    # --- VNINDEX candlestick + volume (T016) --------------------------------
    st.subheader("📉 VNINDEX — nến ngày 2 năm")
    ix_bars = c.get_index_prices("VNINDEX")
    if ix_bars:
        idx = pd.DataFrame(price_dataframe(ix_bars))
        idx["MA20"] = idx["close"].rolling(20).mean()
        idx["MA50"] = idx["close"].rolling(50).mean()
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            row_heights=[0.72, 0.28],
            vertical_spacing=0.04,
            subplot_titles=("VNINDEX — nến ngày", "Khối lượng"),
        )
        fig.add_trace(
            go.Candlestick(
                x=idx["date"],
                open=idx["open"],
                high=idx["high"],
                low=idx["low"],
                close=idx["close"],
                name="VNINDEX",
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=idx["date"], y=idx["MA20"], name="MA20", line=dict(color="#2563eb")),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=idx["date"], y=idx["MA50"], name="MA50", line=dict(color="#f59e0b")),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Bar(x=idx["date"], y=idx["volume"], name="KL", marker_color="#94a3b8"),
            row=2,
            col=1,
        )
        fig.update_layout(
            height=520,
            xaxis_rangeslider_visible=False,
            margin=dict(t=40, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, width="stretch")
        last_ix = idx.iloc[-1]
        d_ix = st.columns(4)
        d_ix[0].metric("VNINDEX", format_price(last_ix["close"]))
        d_ix[1].metric("MA20", format_price(float(last_ix["MA20"])))
        d_ix[2].metric("MA50", format_price(float(last_ix["MA50"])))
        d_ix[3].metric("Ngày", format_date(last_ix["date"]))
    else:
        st.info("Chưa có dữ liệu VNINDEX — chạy `ingest --dataset index_prices`.")
    st.divider()

    # --- Top gainers / decliners with MA20 & MA50 (T016) --------------------
    st.subheader("↕️ Tăng / giảm mạnh — so với MA20 & MA50")
    m1, m2 = st.columns([1, 2])
    with m1:
        universe = st.selectbox(
            "Universe",
            options=["VN100", "VN30", "HNX", "UPCOM"],
            index=0,
            key="movers_universe",
        )
    with m2:
        st.caption(
            "Cột MA20/MA50 = khoảng cách giá đóng cửa (%). Chọn universe tương ứng "
            "bộ lọc ở trang Bộ lọc."
        )
    movers = c.get_movers(universe=universe, limit=10)
    gainers = movers.get("gainers") or []
    decliners = movers.get("decliners") or []
    if gainers or decliners:
        def _mover_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [
                {
                    "Mã": it.get("symbol"),
                    "Giá": it.get("close"),
                    "%1D": it.get("change_pct"),
                    "vs MA20 %": it.get("price_vs_sma20"),
                    "vs MA50 %": it.get("price_vs_sma50"),
                }
                for it in items
            ]

        gl, dl = st.columns(2)
        with gl:
            st.markdown("**🟢 Top 10 tăng**")
            st.dataframe(
                pd.DataFrame(_mover_rows(gainers)),
                column_config={
                    "Giá": st.column_config.NumberColumn(format="%,.0f"),
                    "%1D": st.column_config.NumberColumn(format="%+.2f"),
                    "vs MA20 %": st.column_config.NumberColumn(format="%+.2f"),
                    "vs MA50 %": st.column_config.NumberColumn(format="%+.2f"),
                },
                hide_index=True,
                width="stretch",
                height=420,
            )
        with dl:
            st.markdown("**🔴 Top 10 giảm**")
            st.dataframe(
                pd.DataFrame(_mover_rows(decliners)),
                column_config={
                    "Giá": st.column_config.NumberColumn(format="%,.0f"),
                    "%1D": st.column_config.NumberColumn(format="%+.2f"),
                    "vs MA20 %": st.column_config.NumberColumn(format="%+.2f"),
                    "vs MA50 %": st.column_config.NumberColumn(format="%+.2f"),
                },
                hide_index=True,
                width="stretch",
                height=420,
            )
        st.caption(
            f"Ngày dữ liệu: {format_date(movers.get('trade_date'))} · "
            "%1D = thay đổi so với phiên trước · so với MA = giá/MA − 1."
        )
    else:
        st.info("Chưa có dữ liệu giá cho universe này.")
    st.divider()

    # --- Assembly: score + ML prediction per symbol ------------------------
    symbols = tuple(str(r.get("symbol")) for r in ranked if r.get("symbol"))
    predictions = _load_predictions(api_host, symbols) if symbols else {}
    st.subheader("🎯 Đánh giá & dự đoán VN30")
    st.caption(
        "P(tăng 5D) là xác suất mô hình ML dự đoán lợi nhuận 5 phiên tới dương. "
        "Cột Gợi ý chỉ để sàng lọc — hệ thống không đưa lệnh mua/bán (§3)."
    )
    if ranked:
        table = []
        for r in ranked:
            sym = str(r.get("symbol"))
            pred = predictions.get(sym, {})
            prob = pred.get("probability_positive")
            table.append(
                {
                    "Hạng": r.get("rank"),
                    "Mã": sym,
                    "Điểm": r.get("overall_score"),
                    "Tín hiệu": signal_label(str(r.get("signal") or "")),
                    "P(tăng 5D)": round(float(prob), 3) if prob is not None else None,
                    "LN kỳ vọng": pred.get("expected_return"),
                    "Độ tin cậy": r.get("confidence"),
                    "Gợi ý": _decision_hint(str(r.get("signal") or ""), prob),
                }
            )
        st.dataframe(
            pd.DataFrame(table),
            column_config={
                "Hạng": st.column_config.NumberColumn(width="small"),
                "Mã": st.column_config.TextColumn(width="small"),
                "Điểm": st.column_config.NumberColumn(format="%.1f"),
                "P(tăng 5D)": st.column_config.ProgressColumn(
                    "P(tăng 5D)", min_value=0.0, max_value=1.0, format="%.3f"
                ),
                "LN kỳ vọng": st.column_config.NumberColumn(format="%.4f"),
                "Độ tin cậy": st.column_config.NumberColumn(format="%.0%"),
            },
            hide_index=True,
            width="stretch",
            height=430,
        )
        with st.expander("❓ Cách đọc bảng này"):
            st.markdown(
                "- **Điểm**: điểm đa yếu tố 0–100 từ engine định lượng (§12) — tất định, "
                "không do LLM sinh.\n"
                "- **Tín hiệu**: POSITIVE / NEUTRAL / NEGATIVE theo ngưỡng điểm.\n"
                "- **P(tăng 5D)**: xác suất XGBoost + hiệu chuẩn Platt (model đang "
                "phục vụ, xem `/readyz`).\n"
                "- **Gợi ý**: tổ hợp tất định của tín hiệu và xác suất — hỗ trợ sàng lọc, "
                "**không** phải khuyến nghị đầu tư."
            )
    else:
        st.info("Chưa có bảng xếp hạng — chạy `compute-scores` trước.")
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
    st.caption("Toàn bộ universe trong CSDL (VN30/VN100/HNX/UPCOM), kèm tìm kiếm và sắp xếp.")
    c = client
    stocks = c.list_stocks(limit=500)
    if not stocks:
        st.info("Chưa có dữ liệu mã — kiểm tra ingest và seed.")
        return

    c1, c2 = st.columns([2, 1])
    with c1:
        query = st.text_input(
            "Tìm theo mã / tên công ty", value="", key="screener_query"
        ).strip().upper()
    with c2:
        exchanges = sorted({str(s.get("exchange") or "?") for s in stocks})
        picked = st.multiselect("Sàn", options=exchanges, default=exchanges)

    rows = [
        {
            "Mã": s.get("symbol"),
            "Công ty": s.get("company_name"),
            "Sàn": s.get("exchange"),
            "Ngành": s.get("sector") or s.get("industry") or "—",
            "VN30": "✔" if s.get("is_vn30") else "",
            "VN100": "✔" if s.get("is_vn100") else "",
            "Giá": s.get("price"),
        }
        for s in stocks
        if str(s.get("exchange") or "?") in picked
        and (
            not query
            or query in str(s.get("symbol") or "").upper()
            or query in str(s.get("company_name") or "").upper()
        )
    ]
    st.caption(f"{len(rows)}/{len(stocks)} mã hiển thị")
    st.dataframe(
        pd.DataFrame(rows),
        column_config={
            "Giá": st.column_config.NumberColumn(format="%,.0f"),
            "VN30": st.column_config.TextColumn(width="small"),
            "VN100": st.column_config.TextColumn(width="small"),
        },
        hide_index=True,
        width="stretch",
        height=560,
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
        top = [r for r in filtered if r.get("overall_score") is not None][:30]
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
                    text=[
                        f"{float(r['overall_score'] or 0):.1f}" for r in top
                    ],
                    textposition="outside",
                )
            )
            fig.update_layout(
                height=420,
                yaxis_title="Điểm tổng hợp",
                margin=dict(t=30, b=10),
                xaxis_tickangle=-45,
            )
            st.plotly_chart(fig, width="stretch")
            st.caption("30 mã xếp hạng cao nhất — nhãn = điểm tổng hợp, trục X = mã.")
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

    # --- ML prediction + AI analysis ---------------------------------------
    st.subheader("🤖 Dự đoán ML & đánh giá AI")
    pred = c.get_prediction(symbol)
    if pred and pred.get("probability_positive") is not None:
        prob = float(pred["probability_positive"])
        p_cols = st.columns(4)
        p_cols[0].metric("P(tăng 5D)", f"{prob:.3f}")
        p_cols[1].metric(
            "Lợi nhuận kỳ vọng", f"{float(pred.get('expected_return') or 0):.4f}"
        )
        p_cols[2].metric("Độ tin cậy", f"{float(pred.get('confidence') or 0):.0%}")
        p_cols[3].metric(
            "Model", f"{pred.get('model_id')}@{pred.get('model_version')}"
        )
        st.progress(min(max(prob, 0.0), 1.0), text=f"Xác suất tăng: {prob:.1%}")
    else:
        st.info("Chưa có dự đoán ML cho mã này (cần model APPROVED trong registry).")

    if st.button("🧠 Chạy phân tích AI (LLM + dữ liệu tool)", key=f"ai_{symbol}"):
        with st.spinner("Đang tổng hợp luận điểm đầu tư (có thể mất ~15 giây)…"):
            analysis = c.analyze_symbol(symbol)
        if analysis.get("error"):
            st.error(f"Phân tích thất bại: {analysis['error']}")
        else:
            st.markdown("**Luận điểm đầu tư (thesis)**")
            st.info(str(analysis.get("thesis") or "—"))
            a_left, a_right = st.columns(2)
            with a_left:
                st.markdown("**Yếu tố hỗ trợ (catalysts)**")
                for item in analysis.get("catalysts") or []:
                    st.write(f"- {item}")
            with a_right:
                st.markdown("**Rủi ro (risks)**")
                for item in analysis.get("risks") or []:
                    st.write(f"- {item}")
            st.caption(
                f"Model suy luận: {analysis.get('model', '?')} · "
                f"điểm/quant do engine tất định cung cấp, LLM không sửa số liệu."
            )

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
            ind_rows = [
                {"Chỉ báo": k.upper(), "Giá trị": v}
                for k, v in indicator_dict(inds).items()
            ]
            st.dataframe(
                pd.DataFrame(ind_rows),
                column_config={
                    "Giá trị": st.column_config.NumberColumn(format="%.2f"),
                },
                hide_index=True,
                width="stretch",
                height=280,
            )
    with col_val:
        val = c.get_valuation(symbol)
        if val:
            st.subheader("Định giá")
            val_rows = [
                {"Chỉ số": k.upper(), "Giá trị": val.get(k)}
                for k in ("pe", "pb", "ev_ebitda", "dividend_yield", "peg")
            ]
            st.dataframe(
                pd.DataFrame(val_rows),
                column_config={"Giá trị": st.column_config.NumberColumn(format="%.2f")},
                hide_index=True,
                width="stretch",
                height=280,
            )
        else:
            st.caption("Chưa có dữ liệu định giá (cần bảng `valuation_daily`).")
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

    # --- Evidence (§19) -----------------------------------------------------
    st.divider()
    st.subheader("📎 Bằng chứng dữ liệu đáng tin cậy (§19)")
    st.caption(
        "Trích đoạn có nguồn + ngày đăng + độ tin cậy, truy xuất từ chỉ mục RAG "
        "(kho tài liệu tin tức đã thu thập)."
    )
    evidence = c.get_evidence(query=f"{symbol} kết quả kinh doanh", symbol=symbol, top_k=5)
    if evidence:
        st.dataframe(
            pd.DataFrame(evidence_rows(evidence)),
            column_config={
                "confidence": st.column_config.NumberColumn("Tin cậy", format="%.2f"),
                "snippet": st.column_config.TextColumn("Đoạn trích", width="large"),
            },
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("Chưa tìm thấy bằng chứng cho mã này — chạy job tin tức để nạp thêm.")


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
    st.caption("Tạo lượt chạy mới, xem chỉ số §16 và nhật ký lệnh đã lưu trong CSDL.")
    c = client

    with st.form("create_backtest_form"):
        f1, f2, f3 = st.columns(3)
        strategy = f1.selectbox(
            "Chiến lược",
            options=[
                "momentum_breakout_v1",
                "baseline_multi_factor",
                "mean_reversion_v1",
            ],
        )
        universe = f2.selectbox("Vũ trụ", options=["VN30"])
        run_type = f3.selectbox("Loại chạy", options=["walk-forward", "single-run"])
        d1, d2 = st.columns(2)
        start = d1.date_input("Từ ngày", value=date(2025, 1, 1))
        end = d2.date_input("Đến ngày", value=date(2026, 9, 25))
        submitted = st.form_submit_button("▶️ Tạo lượt chạy", type="primary")

    if submitted:
        if end <= start:
            st.error("Ngày kết thúc phải sau ngày bắt đầu.")
        else:
            with st.spinner("Đang gửi yêu cầu tới API…"):
                created = c.create_backtest(
                    strategy_name=strategy,
                    start_date=start.isoformat(),
                    end_date=end.isoformat(),
                    universe=universe,
                    run_type=run_type,
                )
            if created.get("error"):
                st.error(
                    f"Không tạo được lượt chạy: {created['error']}. "
                    "Nếu API bật API_AUTH_KEY/AUTH_JWT_SECRET, dashboard cần kèm "
                    "credential (xem helper/deployment_vi.md)."
                )
            else:
                st.success(f"Đã tạo lượt chạy `{created.get('id')}`.")
                st.cache_data.clear()

    backtests = c.get_backtests()
    if not backtests:
        st.info("Chưa có backtest nào trong CSDL — dùng form phía trên để tạo.")
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

st.markdown(
    '<div class="dtck-foot">'
    f'Nguồn dữ liệu: <b>{ready.get("market_source", "?")}</b>'
    f' · CSDL: <b>{ready.get("dependencies", {}).get("database", "?")}</b>'
    f' · Model: <b>{ready.get("dependencies", {}).get("models", "?")}</b>'
    f' · Tác tử: <b>{ready.get("dependencies", {}).get("agents", "?")}</b>'
    ' · DTCK hỗ trợ quyết định cho con người — không đưa lời khuyên đầu tư (§3).'
    '</div>',
    unsafe_allow_html=True,
)
