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
import plotly.io as pio
import streamlit as st
from plotly.subplots import make_subplots

from apps.dashboard import theme
from apps.dashboard.client import DEFAULT_BASE, MarketClient
from apps.dashboard.components import (
    contribution_rows,
    evidence_rows,
    format_date,
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

try:
    from src.quant.strategy.recommend import DISCLAIMER as STRATEGY_DISCLAIMER
except ImportError:
    STRATEGY_DISCLAIMER = (
        "Hệ thống DTCK hỗ trợ nghiên cứu và ra quyết định đầu tư (§3). "
        "Không cam kết lợi nhuận, không tự động giao dịch."
    )

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
st.set_page_config(page_title="DTCK — AI Investment Platform", page_icon="📊", layout="wide")

# --- Design system (T019) -------------------------------------------------
# Registered once per rerun: the Plotly template keeps every chart on one
# typography/grid/colour scale; the stylesheet styles Streamlit's own widgets.
pio.templates["dtck"] = go.layout.Template(theme.PLOTLY_TEMPLATE)
pio.templates.default = "dtck"
st.markdown(theme.inject_css(), unsafe_allow_html=True)

APP_VERSION = "0.1.0"

# Page registry — order defines the sidebar navigation (T015b: one radio nav
# instead of the old radio + three context checkboxes).
PAGE_NAMES = (
    "Tổng quan",
    "Bộ lọc cổ phiếu",
    "Xếp hạng",
    "Chấm điểm chiến lược",
    "Chi tiết mã",
    "Backtest",
    "Tin tức & RAG",
    "Quản lý Email",
    "Sức khỏe hệ thống",
    "Lịch sử Worker",
)

#: Page label → icon name in ``theme.ICON_PATHS`` (no emoji as icons).
PAGE_ICONS: dict[str, str] = {
    "Tổng quan": "grid",
    "Bộ lọc cổ phiếu": "filter",
    "Xếp hạng": "trophy",
    "Chấm điểm chiến lược": "bars",
    "Chi tiết mã": "compass",
    "Backtest": "flask",
    "Tin tức & RAG": "news",
    "Quản lý Email": "mail",
    "Sức khỏe hệ thống": "pulse",
    "Lịch sử Worker": "clock",
}

with st.sidebar:
    st.markdown(
        theme.brand_html("DTCK", f"v{APP_VERSION}", "Nghiên cứu & Hỗ trợ Quyết định Đầu tư"),
        unsafe_allow_html=True,
    )
    st.markdown(theme.nav_title("Điều hướng"), unsafe_allow_html=True)
    page = st.radio("Điều hướng", PAGE_NAMES, key="nav_page", label_visibility="collapsed")

    st.divider()
    st.markdown(theme.nav_title("Nguồn dữ liệu"), unsafe_allow_html=True)
    # Default comes from the environment (compose sets API_HOST=http://api:8000);
    # hardcoding localhost here used to make the container call itself, fail, and
    # silently render the in-memory fixture — the "fake data" bug (T015b).
    # JWT session (T016): keep the access token in session_state across reruns.
    if "auth_token" not in st.session_state:
        st.session_state["auth_token"] = ""
    if "auth_email" not in st.session_state:
        st.session_state["auth_email"] = ""
    api_host = st.text_input("API host", value=DEFAULT_BASE, key="api_host")
    client = MarketClient(base_url=api_host, token=st.session_state["auth_token"] or None)
    ready = client.probe()
    kind, detail = client.source_badge()
    market_source = str(ready.get("market_source", "?"))
    if kind == "api":
        st.markdown(
            theme.side_card("Chế độ đọc", f"DỮ LIỆU THẬT · {market_source}", tone="up")
            + f'<div class="dtck-brand__sub">{detail}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            theme.side_card("Chế độ đọc", "DỮ LIỆU MÔ PHỎNG · API offline", tone="down")
            + f'<div class="dtck-brand__sub">{detail}</div>',
            unsafe_allow_html=True,
        )
    if st.button("Làm mới dữ liệu", type="primary", icon=":material/refresh:", width="stretch"):
        st.cache_data.clear()
        st.rerun()

    # --- Login (T016): JWT via POST /api/v1/auth/login ----------------------
    st.divider()
    st.markdown(theme.nav_title("Tài khoản"), unsafe_allow_html=True)
    if st.session_state["auth_token"]:
        st.markdown(
            theme.side_card("Đang đăng nhập", str(st.session_state["auth_email"]), tone="brand"),
            unsafe_allow_html=True,
        )
        if st.button("Đăng xuất", key="logout", icon=":material/logout:", width="stretch"):
            st.session_state["auth_token"] = ""
            st.session_state["auth_email"] = ""
            st.rerun()
    else:
        st.caption("Đăng nhập để chạy Phân tích AI & Backtest (JWT)")
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email", value="admin@dtck.local", key="login_email")
            password = st.text_input(
                "Mật khẩu", value="admin123", type="password", key="login_password"
            )
            submitted = st.form_submit_button(
                "Đăng nhập", type="primary", icon=":material/login:", width="stretch"
            )
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
    st.caption("Tài liệu: `docs/DEPLOYMENT_vi.md` · `docs/api.html`")


# ---------------------------------------------------------------------------
# App bar (T019) — brand, live data mode and serving dependencies
# ---------------------------------------------------------------------------
deps: dict[str, Any] = ready.get("dependencies", {}) if isinstance(ready, dict) else {}
mode_chip = (
    theme.chip(f"DỮ LIỆU THẬT · {market_source}", "up", icon="check")
    if kind == "api"
    else theme.chip("DỮ LIỆU MÔ PHỎNG · API offline", "down", icon="alert")
)
st.markdown(
    theme.app_bar(
        "DTCK — Nền tảng Nghiên cứu & Hỗ trợ Quyết định Đầu tư",
        "Thị trường Việt Nam (HOSE/HNX/UPCOM) · định lượng → dự đoán ML → luận giải AI "
        "→ con người quyết định",
        APP_VERSION,
        chips=(
            mode_chip,
            theme.chip(f"Model: {deps.get('models', '?')}", "neutral", icon="layers"),
            theme.chip(f"Tác tử: {deps.get('agents', '?')}", "neutral", icon="sparkle"),
        ),
    ),
    unsafe_allow_html=True,
)


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
    st.markdown(
        theme.page_header(
            "Tổng quan thị trường & dự đoán VN30",
            "Đánh giá định lượng (§12), dự đoán ML (§26) và mức độ bằng chứng dữ liệu (§39).",
            icon=PAGE_ICONS["Tổng quan"],
            eyebrow="Bảng điều khiển trung tâm",
            meta=(
                theme.chip(f"Chế độ đọc: {market_source}", "neutral", icon="database"),
                theme.chip(f"Model: {deps.get('models', '?')}", "neutral", icon="layers"),
            ),
        ),
        unsafe_allow_html=True,
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
            code = str(ix.get("index_code", "VN30"))
            close = float(str(ix.get("close", 0)))
            change = ix.get("change")
            if change is not None:
                delta_str = f"{float(change):+.2f} điểm"
            else:
                p_bars = c.get_index_prices(code)
                if p_bars and len(p_bars) >= 2:
                    p1 = float(p_bars[-1].get("close", close))
                    p2 = float(p_bars[-2].get("close", close))
                    diff = p1 - p2
                    delta_str = f"{diff:+.2f} điểm"
                else:
                    base = float(str(ix.get("open", close))) or close
                    delta_str = f"{close - base:+.2f} điểm"
            st.metric(
                code,
                format_price(close),
                delta_str,
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
    ix_bars = c.get_index_prices("VNINDEX")
    if ix_bars:
        idx = pd.DataFrame(price_dataframe(ix_bars))
        idx["MA20"] = idx["close"].rolling(20).mean()
        idx["MA50"] = idx["close"].rolling(50).mean()

        timeframe_options = [
            "Tất cả",
            "3 năm",
            "2 năm",
            "1 năm",
            "6 tháng",
            "3 tháng",
            "1 tháng",
            "2 tuần",
            "1 tuần",
        ]
        timeframe_bars = {
            "3 năm": 756,
            "2 năm": 504,
            "1 năm": 252,
            "6 tháng": 126,
            "3 tháng": 63,
            "1 tháng": 22,
            "2 tuần": 10,
            "1 tuần": 5,
        }
        window = st.radio(
            "Khoảng thời gian",
            options=timeframe_options,
            index=2,
            horizontal=True,
            key="vnindex_timeframe",
        )
        bars = timeframe_bars.get(window)
        view = idx.tail(bars) if bars else idx

        st.subheader(f"VNINDEX — nến ngày ({window})")
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            row_heights=[0.72, 0.28],
            vertical_spacing=0.04,
            subplot_titles=(f"VNINDEX — nến ngày ({window})", "Khối lượng"),
        )
        fig.add_trace(
            go.Candlestick(
                x=view["date"],
                open=view["open"],
                high=view["high"],
                low=view["low"],
                close=view["close"],
                name="VNINDEX",
                increasing_line_color=theme.COLORS["up"],
                decreasing_line_color=theme.COLORS["down"],
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=view["date"],
                y=view["MA20"],
                name="MA20",
                line=dict(color=theme.CHART_MA20_COLOR, width=1.6),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=view["date"],
                y=view["MA50"],
                name="MA50",
                line=dict(color=theme.CHART_MA50_COLOR, width=1.6),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Bar(
                x=view["date"],
                y=view["volume"],
                name="KL",
                marker_color=theme.CHART_VOLUME_COLOR,
            ),
            row=2,
            col=1,
        )
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
        fig.update_layout(**theme.chart_layout(520, xaxis_rangeslider_visible=False))
        st.plotly_chart(fig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)
        last_ix = idx.iloc[-1]
        diff_vnindex = (
            float(last_ix["close"]) - float(idx.iloc[-2]["close"])
            if len(idx) >= 2
            else None
        )
        d_ix = st.columns(4)
        d_ix[0].metric(
            "VNINDEX",
            format_price(last_ix["close"]),
            f"{diff_vnindex:+.2f} điểm" if diff_vnindex is not None else None,
        )
        d_ix[1].metric("MA20", format_price(float(last_ix["MA20"])))
        d_ix[2].metric("MA50", format_price(float(last_ix["MA50"])))
        d_ix[3].metric("Ngày", format_date(last_ix["date"]))
    else:
        st.info("Chưa có dữ liệu VNINDEX — chạy `ingest --dataset index_prices`.")
    st.divider()

    # --- Top gainers / decliners with MA20 & MA50 (T016) --------------------
    st.subheader("Tăng / giảm mạnh — so với MA20 & MA50")
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
            st.markdown(
                theme.section_label("Top 10 tăng", "up", icon="check"), unsafe_allow_html=True
            )
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
            st.markdown(
                theme.section_label("Top 10 giảm", "down", icon="alert"), unsafe_allow_html=True
            )
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
    st.subheader("Đánh giá & dự đoán VN30")
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
        with st.expander("Cách đọc bảng này"):
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
            idx_rows = []
            for ix in indices:
                chg = ix.get("change")
                chg_str = f"{float(chg):+.2f}" if chg is not None else "—"
                idx_rows.append(
                    {
                        "Mã": ix.get("index_code"),
                        "Đóng cửa": format_price(ix.get("close")),
                        "+/- điểm": chg_str,
                        "KL": f"{float(str(ix.get('volume', 0))):,.0f}",
                        "Ngày": format_date(ix.get("trade_date")),
                    }
                )
            st.dataframe(pd.DataFrame(idx_rows), hide_index=True, width="stretch")
        else:
            st.info("Chưa có dữ liệu chỉ số.")
    with col_right:
        st.subheader("Top 10 điểm tổng hợp")
        top = [r for r in ranked if r.get("overall_score") is not None][:10]
        if top:
            colors = [theme.signal_hex(str(r.get("signal") or "")) for r in top]
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
                **theme.chart_layout(340, yaxis_title="Điểm tổng hợp (0–100)", showlegend=False)
            )
            st.plotly_chart(fig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)
        else:
            st.info("Chưa có bảng xếp hạng — hãy chạy `compute-scores`.")


# ---------------------------------------------------------------------------
# Page 2 — Stock Screener
# ---------------------------------------------------------------------------
def page_screener() -> None:
    st.markdown(
        theme.page_header(
            "Bộ lọc cổ phiếu",
            "Toàn bộ universe trong CSDL (VN30/VN100/HNX/UPCOM), kèm tìm kiếm và sắp xếp.",
            icon=PAGE_ICONS["Bộ lọc cổ phiếu"],
            eyebrow="Vũ trụ đầu tư",
        ),
        unsafe_allow_html=True,
    )
    c = client
    stocks = c.list_stocks(limit=500)
    if not stocks:
        st.info("Chưa có dữ liệu mã — kiểm tra ingest và seed.")
        return

    c1, c2 = st.columns([2, 1])
    with c1:
        query = (
            st.text_input("Tìm theo mã / tên công ty", value="", key="screener_query")
            .strip()
            .upper()
        )
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
    st.markdown(
        theme.page_header(
            "Xếp hạng cổ phiếu",
            "Điểm đa yếu tố (§12) kèm tín hiệu và độ tin cậy — dữ liệu từ API.",
            icon=PAGE_ICONS["Xếp hạng"],
            eyebrow="Điểm & tín hiệu",
        ),
        unsafe_allow_html=True,
    )
    c = client
    ranked = c.get_ranked()
    rows = ranking_rows(ranked)
    if not rows:
        st.info("Chưa có xếp hạng — chạy `compute-scores` trước.")
        return

    if any(r.get("price") is None for r in rows):
        try:
            movers = c.get_movers(universe="ALL", limit=200)
            all_movers = (movers.get("gainers") or []) + (movers.get("decliners") or [])
            movers_by_sym = {m["symbol"]: m for m in all_movers if "symbol" in m}
            for r in rows:
                sym = r.get("symbol")
                if sym in movers_by_sym:
                    m = movers_by_sym[sym]
                    if r.get("price") is None and m.get("close") is not None:
                        r["price"] = round(float(m["close"]), 2)
                    if (
                        r.get("change") is None
                        and m.get("close") is not None
                        and m.get("change_pct") is not None
                    ):
                        pct = float(m["change_pct"])
                        close = float(m["close"])
                        prev = close / (1.0 + pct / 100.0)
                        r["change"] = round(close - prev, 2)
                    if r.get("price_vs_sma20") is None and m.get("price_vs_sma20") is not None:
                        r["price_vs_sma20"] = round(float(m["price_vs_sma20"]), 2)
                    if r.get("price_vs_sma50") is None and m.get("price_vs_sma50") is not None:
                        r["price_vs_sma50"] = round(float(m["price_vs_sma50"]), 2)
        except Exception:
            pass

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
                    marker_color=[theme.signal_hex(str(r.get("signal") or "")) for r in top],
                    text=[f"{float(r['overall_score'] or 0):.1f}" for r in top],
                    textposition="outside",
                )
            )
            fig.update_layout(
                **theme.chart_layout(420, yaxis_title="Điểm tổng hợp", xaxis_tickangle=-45)
            )
            st.plotly_chart(fig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)
            st.caption("30 mã xếp hạng cao nhất — nhãn = điểm tổng hợp, trục X = mã.")
    with col_stat:
        by_signal = pd.Series([str(r.get("signal") or "NEUTRAL") for r in filtered])
        st.metric("Số mã hiển thị", str(len(filtered)))
        counts = by_signal.value_counts().to_dict()
        st.write(
            {signal_label(k): int(v) for k, v in sorted(counts.items(), key=lambda kv: -kv[1])}
        )

    cols = [
        "rank",
        "symbol",
        "price",
        "change",
        "overall_score",
        "signal",
        "price_vs_sma20",
        "price_vs_sma50",
        "confidence",
    ]
    st.dataframe(
        pd.DataFrame(filtered),
        column_order=cols,
        column_config={
            "rank": st.column_config.NumberColumn("Hạng", width="small"),
            "symbol": st.column_config.TextColumn("Mã", width="small"),
            "price": st.column_config.NumberColumn("Giá hiện tại", format="%,.1f"),
            "change": st.column_config.NumberColumn("+/- Phiên", format="%+.2f"),
            "overall_score": st.column_config.NumberColumn("Điểm", format="%.1f"),
            "signal": st.column_config.TextColumn("Tín hiệu"),
            "price_vs_sma20": st.column_config.NumberColumn("vs MA20 %", format="%+.2f"),
            "price_vs_sma50": st.column_config.NumberColumn("vs MA50 %", format="%+.2f"),
            "confidence": st.column_config.NumberColumn("Độ tin cậy", format="%.0%"),
        },
        hide_index=True,
        width="stretch",
    )


# ---------------------------------------------------------------------------
# Page 4 — Stock Detail
# ---------------------------------------------------------------------------
def page_stock_detail(symbol: str = "FPT") -> None:
    st.markdown(
        theme.page_header(
            f"Chi tiết mã {symbol}",
            "Giá & khối lượng, điểm hệ số, dự đoán ML, định giá, chất lượng dữ liệu và bằng chứng.",
            icon=PAGE_ICONS["Chi tiết mã"],
            eyebrow="Hồ sơ doanh nghiệp",
        ),
        unsafe_allow_html=True,
    )
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
                        marker_color=theme.COLORS["brand"],
                    )
                ]
            )
            fig.update_layout(
                **theme.chart_layout(
                    300, title="Đóng góp điểm số", xaxis_title="Hệ số", yaxis_title="Điểm số"
                )
            )
            st.plotly_chart(fig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)

    # --- ML prediction + AI analysis ---------------------------------------
    st.subheader("Dự đoán ML & đánh giá AI")
    pred = c.get_prediction(symbol)
    if pred and pred.get("probability_positive") is not None:
        prob = float(pred["probability_positive"])
        p_cols = st.columns(4)
        p_cols[0].metric("P(tăng 5D)", f"{prob:.3f}")
        p_cols[1].metric("Lợi nhuận kỳ vọng", f"{float(pred.get('expected_return') or 0):.4f}")
        p_cols[2].metric("Độ tin cậy", f"{float(pred.get('confidence') or 0):.0%}")
        p_cols[3].metric("Model", f"{pred.get('model_id')}@{pred.get('model_version')}")
        st.progress(min(max(prob, 0.0), 1.0), text=f"Xác suất tăng: {prob:.1%}")
    else:
        st.info("Chưa có dự đoán ML cho mã này (cần model APPROVED trong registry).")

    if st.button(
        "Chạy phân tích AI (LLM + dữ liệu tool)",
        key=f"ai_{symbol}",
        type="primary",
        icon=":material/psychology:",
    ):
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
                increasing_line_color=theme.COLORS["up"],
                decreasing_line_color=theme.COLORS["down"],
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=view["date"],
                y=view["MA20"],
                name="MA20",
                line=dict(color=theme.CHART_MA20_COLOR, width=1.6),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=view["date"],
                y=view["MA50"],
                name="MA50",
                line=dict(color=theme.CHART_MA50_COLOR, width=1.6),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Bar(
                x=view["date"],
                y=view["volume"],
                name="KL",
                marker_color=theme.CHART_VOLUME_COLOR,
            ),
            row=2,
            col=1,
        )
        fig.update_layout(**theme.chart_layout(560, xaxis_rangeslider_visible=False))
        st.plotly_chart(fig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)
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
                {"Chỉ báo": k.upper(), "Giá trị": v} for k, v in indicator_dict(inds).items()
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
                dfig.update_layout(
                    **theme.chart_layout(200, title="6 chiều chất lượng", showlegend=False)
                )
                st.plotly_chart(dfig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)

    # --- Evidence (§19) -----------------------------------------------------
    st.divider()
    st.subheader("Bằng chứng dữ liệu đáng tin cậy (§19)")
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
    st.markdown(
        theme.page_header(
            "Backtest chiến lược",
            "Tạo lượt chạy mới, xem chỉ số §16 và nhật ký lệnh đã lưu trong CSDL.",
            icon=PAGE_ICONS["Backtest"],
            eyebrow="Kiểm nghiệm chiến lược",
        ),
        unsafe_allow_html=True,
    )
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
        submitted = st.form_submit_button(
            "Tạo lượt chạy", type="primary", icon=":material/play_arrow:"
        )

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
    selected = st.selectbox("Chọn lượt chạy", options=ids, format_func=lambda x: labels.get(x, x))
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
    st.markdown(
        theme.page_header(
            "Tin tức & Bằng chứng RAG",
            "Dòng tin tài chính đã thu thập, tìm kiếm ngữ nghĩa và trích xuất bằng chứng (§19).",
            icon=PAGE_ICONS["Tin tức & RAG"],
            eyebrow="Tri thức & bằng chứng",
        ),
        unsafe_allow_html=True,
    )
    c = client

    tab_news, tab_rag, tab_status = st.tabs(
        ["Tin tức thị trường", "Truy vấn bằng chứng RAG", "Trạng thái RAG"]
    )

    with tab_news:
        st.subheader("Dòng tin tức tài chính đã thu thập")
        col_sym, col_src, col_lim = st.columns([1, 1, 1])
        with col_sym:
            filter_sym = (
                st.text_input("Lọc theo mã (ví dụ: FPT)", value="", key="news_filter_sym")
                .strip()
                .upper()
            )
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
            rag_symbol = (
                st.text_input("Mã CK (tùy chọn)", value="", key="rag_symbol").strip().upper()
            )

        if st.button("Tìm kiếm bằng chứng", key="btn_rag_search", icon=":material/search:"):
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
    st.markdown(
        theme.page_header(
            "Sức khỏe hệ thống",
            "Trạng thái phụ thuộc trực tiếp từ `/healthz` và `/readyz`.",
            icon=PAGE_ICONS["Sức khỏe hệ thống"],
            eyebrow="Vận hành",
        ),
        unsafe_allow_html=True,
    )
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
                if str(state) not in ("unreachable", "unavailable", "offline-index-ready", "stub")
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
            line for line in metrics_text.splitlines() if line.startswith("dtck_agent_runs_total{")
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
# Page 9 — Worker History & Operations
# ---------------------------------------------------------------------------
def page_worker_history() -> None:
    st.markdown(
        theme.page_header(
            "Lịch sử Worker & Tác vụ Định kỳ",
            "Theo dõi lịch trình APScheduler, nhật ký gửi email và hướng dẫn vận hành CLI.",
            icon=PAGE_ICONS["Lịch sử Worker"],
            eyebrow="Vận hành",
        ),
        unsafe_allow_html=True,
    )
    c = client

    tab_jobs, tab_logs, tab_cli = st.tabs(
        ["Lịch trình APScheduler", "Nhật ký gửi Email", "Lệnh vận hành CLI"]
    )

    with tab_jobs:
        st.subheader("Các tác vụ nền đang hoạt động (Worker Scheduler)")
        st.caption("Thời gian chạy theo múi giờ Việt Nam (Asia/Ho_Chi_Minh), Thứ 2 đến Thứ 6.")

        jobs_data = [
            {
                "Job ID": "news_ingestion",
                "Tần suất": "Mỗi 15 phút",
                "Mô tả": "Nạp tin tức thị trường (CaféF RSS) và gắn nhãn mã.",
            },
            {
                "Job ID": "daily_eod_morning",
                "Tần suất": "Thứ 2–6 lúc 11:30",
                "Mô tả": "Nạp giá EOD và chỉ số kết phiên sáng (chuỗi ssix_finipro → yahoo).",
            },
            {
                "Job ID": "daily_eod_afternoon",
                "Tần suất": "Thứ 2–6 lúc 15:30",
                "Mô tả": "Nạp giá EOD và chỉ số kết phiên chiều.",
            },
            {
                "Job ID": "daily_eod_catchup",
                "Tần suất": "Thứ 2–6 lúc 15:50",
                "Mô tả": "Bù giá phiên chiều nếu dữ liệu bị trễ hoặc lỗi vendor (KI-014).",
            },
            {
                "Job ID": "daily_scoring_morning",
                "Tần suất": "Thứ 2–6 lúc 12:00",
                "Mô tả": "Chấm điểm nhân tố và xếp hạng cổ phiếu phiên sáng.",
            },
            {
                "Job ID": "daily_scoring_afternoon",
                "Tần suất": "Thứ 2–6 lúc 16:00",
                "Mô tả": "Chấm điểm nhân tố và xếp hạng cổ phiếu phiên chiều.",
            },
            {
                "Job ID": "email_reports",
                "Tần suất": "Thứ 2–6 lúc 08:00, 12:30, 16:30",
                "Mô tả": "Gửi báo cáo tổng quan thị trường qua email (SMTP Gmail).",
            },
            {
                "Job ID": "daily_strategy_scoring",
                "Tần suất": "Thứ 2–6 lúc 17:00",
                "Mô tả": (
                    "Cập nhật dữ liệu EOD, tính 24 đặc trưng 7 nhóm, chấm điểm 3 chiến lược "
                    "(Ngắn/Trung/Dài hạn) và gửi cảnh báo xếp hạng."
                ),
            },
            {
                "Job ID": "email_schedule_sync",
                "Tần suất": "Mỗi 15 phút",
                "Mô tả": "Đồng bộ lịch gửi email mới từ CSDL vào scheduler.",
            },
        ]
        st.dataframe(pd.DataFrame(jobs_data), hide_index=True, width="stretch")

        st.markdown("### Chuỗi nhà cung cấp dữ liệu thị trường (`market_provider_chain`)")
        st.info(
            "Thứ tự ưu tiên khi nạp dữ liệu: `ssix_finipro` (Chính) → `yahoo` (Dự phòng 1) "
            "→ `vndirect` → `tcbs` → `dsc`."
        )

    with tab_logs:
        st.subheader("Nhật ký gửi Email tự động")
        logs = c.get_email_logs()
        if logs:
            ldf = pd.DataFrame(logs)
            st.dataframe(
                ldf,
                column_config={
                    "recipient_email": st.column_config.TextColumn("Người nhận"),
                    "subject": st.column_config.TextColumn("Tiêu đề"),
                    "status": st.column_config.TextColumn("Trạng thái"),
                    "sent_at": st.column_config.TextColumn("Thời gian gửi"),
                    "error_message": st.column_config.TextColumn("Chi tiết lỗi"),
                },
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("Chưa có lịch sử gửi email nào trong CSDL.")

    with tab_cli:
        st.subheader("Hướng dẫn lệnh vận hành Worker CLI")
        st.markdown(
            "Thực hiện các tác vụ một lần (one-off) trực tiếp qua container worker "
            "hoặc dòng lệnh cục bộ:"
        )

        st.markdown("**1. Nạp giá EOD lịch sử hoặc cập nhật phiên:**")
        st.code(
            "python -m apps.worker.cli ingest --dataset prices --source ssix_finipro "
            "--start 2020-01-01 --end 2026-09-30 --symbols FPT,VCB,HPG",
            language="bash",
        )

        st.markdown("**2. Chấm điểm nhân tố và xếp hạng:**")
        st.code("python -m apps.worker.cli compute-scores", language="bash")

        st.markdown("**3. Chấm điểm chiến lược & cảnh báo xếp hạng (GĐ 4/6):**")
        st.code(
            "# Bước 1: Tính 24 đặc trưng 7 nhóm\n"
            "python -m apps.worker.cli compute-features\n\n"
            "# Bước 2: Chấm điểm 3 chiến lược (ngắn/trung/dài hạn)\n"
            "python -m apps.worker.cli strategy-scores\n\n"
            "# Bước 3: Phát email cảnh báo thay đổi xếp hạng\n"
            "python -m apps.worker.cli notify-strategy-changes",
            language="bash",
        )

        st.markdown("**4. Huấn luyện mô hình ML (XGBoost từ CSDL):**")
        st.code(
            "python -m apps.worker.cli train-model --source db --algorithm xgboost",
            language="bash",
        )

        st.markdown("**5. Chạy tác tử AI (AI Agent):**")
        st.code("python -m apps.worker.cli run-agent --task analyze --symbol FPT", language="bash")


# ---------------------------------------------------------------------------
# Page 8 — Email Notification Management
# ---------------------------------------------------------------------------
#: Minute values offered by the schedule form (kept in sync with the cron jobs).
SCHEDULE_MINUTE_OPTIONS: tuple[int, ...] = (0, 15, 30, 45)


def _sched_int(cfg: dict[str, Any], key: str, default: int) -> int:
    """Read an int from the schedule payload without trusting the API shape."""
    try:
        return int(cfg.get(key, default))
    except (TypeError, ValueError):
        return default


def _minute_selectbox(label: str, cfg: dict[str, Any], key: str, widget_key: str) -> int:
    """Minute dropdown; an off-grid stored value snaps to the nearest option."""
    current = _sched_int(cfg, key, 0)
    nearest = min(SCHEDULE_MINUTE_OPTIONS, key=lambda m: abs(m - current))
    return int(
        st.selectbox(
            label,
            options=list(SCHEDULE_MINUTE_OPTIONS),
            index=list(SCHEDULE_MINUTE_OPTIONS).index(nearest),
            key=widget_key,
        )
    )


def page_email_notifications() -> None:
    st.markdown(
        theme.page_header(
            "Quản lý email báo cáo tự động",
            "Tự động gửi báo cáo thị trường vào 08:00 (tổng kết phiên trước), 12:30 (phiên sáng) "
            "và 16:30 (phiên chiều) Thứ 2 – Thứ 6 qua Gmail SMTP.",
            icon=PAGE_ICONS["Quản lý Email"],
            eyebrow="Thông báo",
        ),
        unsafe_allow_html=True,
    )
    c = client

    tab_send, tab_recipients, tab_smtp, tab_schedule, tab_logs = st.tabs(
        [
            "Gửi thử & Xem trước",
            "Người nhận",
            "Tài khoản Gmail SMTP",
            "Lịch gửi",
            "Nhật ký gửi",
        ]
    )

    with tab_send:
        st.subheader("Gửi Thử Nghiệm Báo Cáo Thị Trường")
        col_t1, col_t2 = st.columns([3, 1])
        with col_t1:
            test_target = st.text_input(
                "Email người nhận thử nghiệm", value="user@example.com", key="test_target_email"
            )
        with col_t2:
            st.write("")
            st.write("")
            btn_send_test = st.button(
                "Gửi thử ngay", type="primary", key="btn_send_test_email", icon=":material/send:"
            )

        if btn_send_test:
            if not test_target or "@" not in test_target:
                st.error("Vui lòng nhập địa chỉ email hợp lệ.")
            else:
                with st.spinner(f"Đang gửi email thử nghiệm đến {test_target} qua SMTP..."):
                    res = c.send_test_email(test_target)
                if res.get("success"):
                    st.success(f"Đã gửi email thành công đến {test_target}.")
                else:
                    st.error(f"Gửi email thất bại: {res.get('error') or res}")

        st.divider()
        st.subheader("Bản xem trước nội dung Email HTML")
        preview_html = c.get_email_preview_html()
        if preview_html:
            with st.expander("Xem trước giao diện email (HTML Preview)", expanded=True):
                st.components.v1.html(preview_html, height=650, scrolling=True)
        else:
            st.info("Chưa tải được bản xem trước.")

    with tab_recipients:
        st.subheader("Danh sách Email Nhận Báo Cáo Hằng Ngày")
        recs = c.get_email_recipients()

        with st.form("add_recipient_form", clear_on_submit=True):
            ar1, ar2, ar3 = st.columns([3, 2, 1])
            with ar1:
                new_em = st.text_input("Địa chỉ email mới", placeholder="investor@example.com")
            with ar2:
                new_nm = st.text_input("Họ tên (tuỳ chọn)", placeholder="Nguyễn Văn A")
            with ar3:
                st.write("")
                st.write("")
                sub_rec = st.form_submit_button("Thêm", type="primary", icon=":material/add:")

            if sub_rec:
                if not new_em or "@" not in new_em:
                    st.error("Email không hợp lệ.")
                else:
                    add_res = c.add_email_recipient(new_em, new_nm or None)
                    if add_res.get("error"):
                        st.error(f"Lỗi thêm email: {add_res['error']}")
                    else:
                        st.success(f"Đã thêm {new_em} vào danh sách nhận báo cáo.")
                        st.rerun()

        if recs:
            st.write(f"Hiện có **{len(recs)}** email trong danh sách:")
            for r in recs:
                rc1, rc2, rc3, rc4 = st.columns([3, 2, 2, 1])
                rc1.write(f"**{r['email']}**")
                rc2.write(r.get("name") or "—")
                rc3.write("Đang nhận" if r.get("is_active") else "Đã tắt")
                if rc4.button("Xóa", key=f"del_{r['id']}", icon=":material/delete:"):
                    c.delete_email_recipient(r["id"])
                    st.rerun()
        else:
            st.info("Chưa có email nào trong danh sách. Hãy thêm email ở trên.")

    with tab_smtp:
        st.subheader("Cấu Hình Tài Khoản Gửi Gmail SMTP")
        st.caption("Khuyên dùng Gmail với Mật khẩu ứng dụng (App Password 16 ký tự).")
        smtp_cfg = c.get_email_smtp()

        with st.form("smtp_config_form"):
            s1, s2 = st.columns(2)
            with s1:
                server = st.text_input(
                    "SMTP Server", value=smtp_cfg.get("smtp_server") or "smtp.gmail.com"
                )
                port = st.number_input(
                    "SMTP Port", value=int(smtp_cfg.get("smtp_port") or 587), step=1
                )
                sender = st.text_input(
                    "Gmail người gửi",
                    value=smtp_cfg.get("sender_email") or "",
                    placeholder="your-email@gmail.com",
                )
            with s2:
                sender_title = st.text_input(
                    "Tên hiển thị người gửi",
                    value=smtp_cfg.get("sender_name") or "DTCK Market Intel",
                )
                pwd = st.text_input(
                    "Mật khẩu ứng dụng Gmail (App Password)",
                    type="password",
                    placeholder="16 ký tự app password",
                )
                tls = st.checkbox(
                    "Sử dụng TLS (STARTTLS port 587)", value=bool(smtp_cfg.get("use_tls", True))
                )

            st.caption("Mật khẩu được mã hóa và lưu trữ an toàn trong PostgreSQL.")
            save_smtp_btn = st.form_submit_button(
                "Lưu Cấu Hình SMTP", type="primary", icon=":material/save:"
            )

            if save_smtp_btn:
                if not sender:
                    st.error("Vui lòng nhập Email người gửi.")
                elif not pwd and not smtp_cfg.get("is_configured"):
                    st.error("Vui lòng nhập mật khẩu ứng dụng Gmail.")
                else:
                    payload = {
                        "smtp_server": server,
                        "smtp_port": int(port),
                        "sender_email": sender,
                        "sender_password": pwd,
                        "sender_name": sender_title,
                        "use_tls": tls,
                        "use_ssl": False,
                    }
                    res_s = c.save_email_smtp(payload)
                    if res_s.get("error"):
                        st.error(f"Lưu thất bại: {res_s['error']}")
                    elif res_s.get("warning"):
                        # No rerun here: the warning must stay visible.
                        st.warning(f"Đã lưu. Lưu ý: {res_s['warning']}")
                    else:
                        st.success("Đã lưu cấu hình tài khoản gửi SMTP thành công.")
                        st.rerun()

    with tab_schedule:
        st.subheader("Cấu Hình Lịch Gửi Tự Động")
        st.caption(
            "3 khung báo cáo mỗi ngày (Thứ 2 – Thứ 6, giờ Việt Nam): **08:00** tổng kết phiên "
            "hôm trước · **12:30** phiên sáng · **16:30** phiên chiều (sau khi chấm điểm xong)."
        )
        sched_cfg = c.get_email_schedule()

        with st.form("schedule_config_form"):
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                st.markdown("**08:00 — Phiên sáng hôm trước**")
                m_h = st.slider(
                    "Giờ gửi sáng",
                    min_value=6,
                    max_value=11,
                    value=_sched_int(sched_cfg, "morning_hour", 8),
                    key="sched_morning_hour",
                )
                m_m = _minute_selectbox(
                    "Phút gửi sáng", sched_cfg, "morning_minute", "sched_morning_min"
                )
            with sc2:
                st.markdown("**12:30 — Phiên sáng (sau 11:30)**")
                n_h = st.slider(
                    "Giờ gửi trưa",
                    min_value=11,
                    max_value=14,
                    value=_sched_int(sched_cfg, "noon_hour", 12),
                    key="sched_noon_hour",
                )
                n_m = _minute_selectbox(
                    "Phút gửi trưa", sched_cfg, "noon_minute", "sched_noon_min"
                )
            with sc3:
                st.markdown("**16:30 — Phiên chiều (sau 15:30)**")
                a_h = st.slider(
                    "Giờ gửi chiều",
                    min_value=15,
                    max_value=18,
                    value=_sched_int(sched_cfg, "afternoon_hour", 16),
                    key="sched_afternoon_hour",
                )
                a_m = _minute_selectbox(
                    "Phút gửi chiều", sched_cfg, "afternoon_minute", "sched_afternoon_min"
                )

            st.divider()
            enable_sched = st.checkbox(
                "Bật tự động gửi báo cáo theo lịch", value=bool(sched_cfg.get("is_enabled", True))
            )
            st.caption(
                "Lịch gửi: Thứ 2 đến Thứ 6 (Mon-Fri) múi giờ Việt Nam (Asia/Ho_Chi_Minh). "
                "Worker tự đọc lại cấu hình này mỗi 15 phút — không cần khởi động lại."
            )
            save_sc_btn = st.form_submit_button(
                "Lưu Lịch Gửi", type="primary", icon=":material/save:"
            )

            if save_sc_btn:
                sc_payload = {
                    "morning_hour": int(m_h),
                    "morning_minute": int(m_m),
                    "noon_hour": int(n_h),
                    "noon_minute": int(n_m),
                    "afternoon_hour": int(a_h),
                    "afternoon_minute": int(a_m),
                    "days_of_week": "mon-fri",
                    "is_enabled": enable_sched,
                }
                sc_res = c.save_email_schedule(sc_payload)
                if sc_res.get("error"):
                    st.error(f"Lưu thất bại: {sc_res['error']}")
                else:
                    st.success("Đã lưu lịch gửi tự động thành công.")
                    st.rerun()

    with tab_logs:
        st.subheader("Nhật Ký Các Lượt Gửi Email")
        logs = c.get_email_logs()
        if logs:
            ldf = pd.DataFrame(logs)
            st.dataframe(
                ldf,
                column_config={
                    "recipient_email": st.column_config.TextColumn("Người nhận"),
                    "subject": st.column_config.TextColumn("Tiêu đề"),
                    "status": st.column_config.TextColumn("Trạng thái"),
                    "sent_at": st.column_config.TextColumn("Thời gian gửi"),
                    "error_message": st.column_config.TextColumn("Chi tiết lỗi"),
                },
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("Chưa có lịch sử gửi email nào.")


# ---------------------------------------------------------------------------
# Page 4b — Strategy scoring (GĐ 6)
# ---------------------------------------------------------------------------
PROFILE_LABELS = {
    "short": "Ngắn hạn / lướt sóng",
    "mid": "Trung hạn",
    "long": "Dài hạn",
}


def page_strategy_scores() -> None:
    st.markdown(
        theme.page_header(
            "Chấm điểm 3 chiến lược",
            "Điểm tổng hợp theo hồ sơ ngắn/trung/dài hạn, vùng mua – cắt lỗ – mục tiêu "
            "và giải thích từng nhóm chỉ số (chỉ mang tính tham khảo, §3).",
            icon=PAGE_ICONS["Chấm điểm chiến lược"],
            eyebrow="Đầu tư có hệ thống",
        ),
        unsafe_allow_html=True,
    )
    c = client

    ctl1, ctl2 = st.columns([1, 1])
    with ctl1:
        profile = st.radio(
            "Hồ sơ chiến lược",
            options=list(PROFILE_LABELS),
            format_func=lambda p: f"{PROFILE_LABELS[p]} ({p})",
            horizontal=True,
            key="strat_profile",
        )
    with ctl2:
        universe = st.selectbox(
            "Vũ trụ",
            options=["", "vn30", "vn100"],
            format_func=lambda u: {"": "Tất cả", "vn30": "VN30", "vn100": "VN100"}[u],
            key="strat_universe",
        )

    page = c.get_strategy_rankings(profile, universe or None, limit=200)
    items = page.get("items") or []
    if not items:
        st.info(
            "Chưa có điểm chiến lược cho phiên gần nhất — chạy "
            "`python -m apps.worker.cli strategy-scores` trước."
        )
        return

    as_of = items[0].get("trade_date")
    st.caption(f"Phiên chấm điểm gần nhất: **{as_of}** · tổng **{page.get('total', 0)}** mã")

    # Distribution of grades (the decision a user actually cares about).
    grades = pd.Series([row.get("grade") or "—" for row in items])
    counts = grades.value_counts().to_dict()
    st.write({g: int(counts[g]) for g in ["A", "B", "C", "D", "—"] if g in counts})

    scored = [r for r in items if r.get("overall_score") is not None]
    if scored:
        top = scored[:30]
        fig = go.Figure(
            go.Bar(
                x=[r["symbol"] for r in top],
                y=[float(r["overall_score"]) for r in top],
                text=[f"{r.get('grade') or '—'}" for r in top],
                textposition="outside",
                marker_color=[theme.signal_hex("POSITIVE" if (r.get("grade") or "") in ("A", "B")
                                               else "NEGATIVE" if (r.get("grade") or "") == "D"
                                               else "NEUTRAL")
                              for r in top],
            )
        )
        fig.update_layout(
            **theme.chart_layout(400, yaxis_title="Điểm tổng hợp", xaxis_tickangle=-45)
        )
        st.plotly_chart(fig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)
        st.caption("30 mã điểm cao nhất — nhãn A–D trên cột; màu xanh = A/B, đỏ = D.")

    if any(r.get("price") is None for r in items):
        try:
            ranked_list = c.get_ranked()
            ranked_by_sym = {x["symbol"]: x for x in ranked_list if "symbol" in x}
            for r in items:
                sym = r.get("symbol")
                if sym in ranked_by_sym:
                    rx = ranked_by_sym[sym]
                    if r.get("price") is None:
                        r["price"] = rx.get("price")
                    if r.get("change") is None:
                        r["change"] = rx.get("change")
        except Exception:
            pass

    table = [
        {
            "Mã": r["symbol"],
            "Tên": (r.get("company_name") or "")[:40],
            "Giá hiện tại": r.get("price"),
            "+/- Phiên": r.get("change"),
            "Điểm": r.get("overall_score"),
            "Xếp hạng": r.get("grade"),
            "Vùng mua (thấp)": r.get("buy_zone_low"),
            "Vùng mua (cao)": r.get("buy_zone_high"),
            "Cắt lỗ": r.get("stop_loss"),
            "Mục tiêu": r.get("target_price"),
            "R/R": r.get("rr_ratio"),
            "Độ tin cậy": r.get("confidence"),
        }
        for r in items
    ]
    st.dataframe(
        pd.DataFrame(table),
        column_config={
            "Mã": st.column_config.TextColumn("Mã", width="small"),
            "Giá hiện tại": st.column_config.NumberColumn("Giá hiện tại", format="%,.1f"),
            "+/- Phiên": st.column_config.NumberColumn("+/- Phiên", format="%+.2f"),
            "Điểm": st.column_config.NumberColumn("Điểm", format="%.1f"),
            "Vùng mua (thấp)": st.column_config.NumberColumn("Vùng mua (thấp)", format="%,.1f"),
            "Vùng mua (cao)": st.column_config.NumberColumn("Vùng mua (cao)", format="%,.1f"),
            "Cắt lỗ": st.column_config.NumberColumn("Cắt lỗ", format="%,.1f"),
            "Mục tiêu": st.column_config.NumberColumn("Mục tiêu", format="%,.1f"),
            "Độ tin cậy": st.column_config.NumberColumn("Độ tin cậy", format="%.0%"),
            "R/R": st.column_config.NumberColumn("R/R", format="%.2f"),
        },
        hide_index=True,
        width="stretch",
    )

    with st.expander("Giải thích nhóm chỉ số + lý do/rủi ro của một mã"):
        symbol = st.text_input("Mã", value=str(items[0]["symbol"]), key="strat_symbol")
        detail = c.get_strategy_symbol(symbol)
        if not detail:
            st.warning("Không có dữ liệu cho mã này.")
            return
        for profile_row in detail["profiles"]:
            label = PROFILE_LABELS.get(profile_row["strategy"], profile_row["strategy"])
            st.markdown(
                f"**{label}** — điểm {profile_row.get('overall_score')} · "
                f"xếp hạng {profile_row.get('grade')}"
            )
            st.write(
                {g: (round(v, 1) if v is not None else None)
                 for g, v in (profile_row.get("group_scores") or {}).items()}
            )
            reasons = profile_row.get("reasons") or []
            risks = profile_row.get("risks") or []
            if reasons:
                st.markdown("**Lý do:**")
                for reason in reasons:
                    st.write(f"- {reason}")
            if risks:
                st.markdown("**Rủi ro:**")
                for risk in risks:
                    st.write(f"- {risk}")
        st.caption(detail.get("disclaimer") or STRATEGY_DISCLAIMER)


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
PAGES: dict[str, Callable[[], None]] = {
    "Tổng quan": page_market_overview,
    "Bộ lọc cổ phiếu": page_screener,
    "Xếp hạng": page_rankings,
    "Chấm điểm chiến lược": page_strategy_scores,
    "Chi tiết mã": lambda: page_stock_detail(
        st.text_input("Mã cổ phiếu", value="FPT", key="detail_symbol").strip().upper()
    ),
    "Backtest": page_backtests,
    "Tin tức & RAG": page_news_rag,
    "Quản lý Email": page_email_notifications,
    "Sức khỏe hệ thống": page_health,
    "Lịch sử Worker": page_worker_history,
}

PAGES[page]()

st.markdown(
    theme.footer(
        (
            ("Nguồn dữ liệu", str(ready.get("market_source", "?"))),
            ("CSDL", str(deps.get("database", "?"))),
            ("Model", str(deps.get("models", "?"))),
            ("Tác tử", str(deps.get("agents", "?"))),
        ),
        "DTCK hỗ trợ quyết định cho con người — không đưa lời khuyên đầu tư (§3). "
        "Số liệu do engine định lượng tất định tính; LLM không sinh số liệu tài chính.",
    ),
    unsafe_allow_html=True,
)
