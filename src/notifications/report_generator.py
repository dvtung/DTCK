"""HTML report generator for Market Overview (Tổng quan thị trường)."""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.dashboard.components import format_date, format_price, signal_label


def generate_market_overview_html(
    *,
    indices: list[dict[str, Any]],
    breadth: dict[str, Any],
    regime: dict[str, Any],
    ranked: list[dict[str, Any]],
    predictions: dict[str, dict[str, Any]] | None = None,
    movers: dict[str, Any] | None = None,
    trade_date: str | date | None = None,
    strategy_rankings: dict[str, list[dict[str, Any]]] | None = None,
) -> str:
    """Generate a clean, modern, responsive HTML email for the daily market overview."""
    preds = predictions or {}
    t_date_str = format_date(trade_date or breadth.get("trade_date") or date.today())

    # 1. KPI cards — prefer VNINDEX as the headline index when available.
    index_name = "VNINDEX"
    index_close = "—"
    index_change = ""
    headline = None
    for ix in indices:
        if str(ix.get("index_code", "")).upper() == "VNINDEX":
            headline = ix
            break
    if headline is None and indices:
        headline = indices[0]
    if headline is not None:
        index_name = str(headline.get("index_code", "VNINDEX"))
        c_val = float(str(headline.get("close", 0)))
        index_close = format_price(c_val)
        chg = headline.get("change")
        if chg is not None:
            diff = float(chg)
        else:
            o_val = float(str(headline.get("open", c_val))) or c_val
            diff = c_val - o_val
        index_change = f"{diff:+.2f} điểm"

    advancers = int(breadth.get("advancers", 0))
    decliners = int(breadth.get("decliners", 0))
    regime_name = str(regime.get("regime", "N/A"))
    confidence = float(regime.get("confidence", 0))
    ranked_count = len(ranked)

    # 2. VN30 / Ranked Rows
    ranked_rows = []
    for r in ranked[:15]:
        sym = str(r.get("symbol", ""))
        p_data = preds.get(sym, {})
        prob = p_data.get("probability_positive")
        prob_str = f"{float(prob):.1%}" if prob is not None else "—"
        exp_ret = p_data.get("expected_return")
        exp_ret_str = f"{float(exp_ret):+.2%}" if exp_ret is not None else "—"
        c_price = r.get("current_price") or r.get("price")
        c_price_str = format_price(c_price)

        sig = str(r.get("signal", "NEUTRAL"))
        sig_viet = signal_label(sig)
        sig_color = (
            "#15803d" if sig == "POSITIVE" else "#b91c1c" if sig == "NEGATIVE" else "#64748b"
        )

        prob_val = float(prob) if prob is not None else 0.5
        if sig == "POSITIVE" and prob_val >= 0.55:
            hint = "🟢 Tích cực"
        elif sig == "NEGATIVE" or prob_val < 0.45:
            hint = "🔴 Thận trọng"
        else:
            hint = "🟡 Theo dõi"

        ranked_rows.append(
            f'<tr style="border-bottom:1px solid #e2e8f0;font-size:13px;">'
            f'<td style="padding:6px 10px;font-weight:bold;">#{r.get("rank", "—")}</td>'
            f'<td style="padding:6px 10px;font-weight:bold;color:#1d4ed8;">{sym}</td>'
            f'<td style="padding:6px 10px;text-align:right;font-weight:600;color:#0f172a;">{c_price_str}</td>'
            f'<td style="padding:6px 10px;text-align:right;">{float(r.get("overall_score") or 0):.1f}</td>'
            f'<td style="padding:6px 10px;text-align:center;color:{sig_color};font-weight:600;">{sig_viet}</td>'
            f'<td style="padding:6px 10px;text-align:right;font-weight:600;">{prob_str}</td>'
            f'<td style="padding:6px 10px;text-align:right;">{exp_ret_str}</td>'
            f'<td style="padding:6px 10px;text-align:center;">{hint}</td>'
            f"</tr>"
        )

    # 3. Movers
    gainers_rows = []
    decliners_rows = []
    if movers:
        for g in (movers.get("gainers") or [])[:10]:
            chg = float(g.get("change_pct", 0))
            vs_ma = g.get("price_vs_sma20")
            vs_ma_str = f"{float(vs_ma):+.1f}%" if vs_ma is not None else "—"
            gainers_rows.append(
                f'<tr style="border-bottom:1px solid #e2e8f0;font-size:12px;">'
                f'<td style="padding:5px;font-weight:bold;color:#15803d;">{g.get("symbol")}</td>'
                f'<td style="padding:5px;text-align:right;">{format_price(g.get("close"))}</td>'
                f'<td style="padding:5px;text-align:right;color:#15803d;font-weight:bold;">{chg:+.2f}%</td>'
                f'<td style="padding:5px;text-align:right;">{vs_ma_str}</td></tr>'
            )
        for d in (movers.get("decliners") or [])[:10]:
            chg = float(d.get("change_pct", 0))
            vs_ma = d.get("price_vs_sma20")
            vs_ma_str = f"{float(vs_ma):+.1f}%" if vs_ma is not None else "—"
            decliners_rows.append(
                f'<tr style="border-bottom:1px solid #e2e8f0;font-size:12px;">'
                f'<td style="padding:5px;font-weight:bold;color:#b91c1c;">{d.get("symbol")}</td>'
                f'<td style="padding:5px;text-align:right;">{format_price(d.get("close"))}</td>'
                f'<td style="padding:5px;text-align:right;color:#b91c1c;font-weight:bold;">{chg:+.2f}%</td>'
                f'<td style="padding:5px;text-align:right;">{vs_ma_str}</td></tr>'
            )

    gain_tb = (
        "".join(gainers_rows)
        or '<tr><td colspan="4" style="padding:8px;text-align:center;">Chưa có dữ liệu</td></tr>'
    )
    decl_tb = (
        "".join(decliners_rows)
        or '<tr><td colspan="4" style="padding:8px;text-align:center;">Chưa có dữ liệu</td></tr>'
    )
    rank_tb = (
        "".join(ranked_rows)
        or '<tr><td colspan="8" style="padding:12px;text-align:center;">Chưa có dữ liệu</td></tr>'
    )
    strat_section = _render_strategy_sections(strategy_rankings)

    return _render_template(
        date_str=t_date_str,
        idx_name=index_name,
        idx_close=index_close,
        idx_change=index_change,
        adv=advancers,
        dec=decliners,
        regime=regime_name,
        confidence=confidence,
        count=ranked_count,
        gainers=gain_tb,
        decliners=decl_tb,
        ranked=rank_tb,
        strategy_section=strat_section,
    )


def _fmt_strat_price(val: float | int | None) -> str:
    if val is None:
        return "—"
    try:
        f = float(val)
        return format_price(round(f)) if f >= 100 else format_price(f)
    except (TypeError, ValueError):
        return "—"


def _grade_badge(grade: str | None) -> str:
    g = (grade or "—").strip().upper()
    colors = {
        "A": ("#15803d", "#dcfce7"),  # dark green on light green
        "B": ("#1d4ed8", "#dbeafe"),  # dark blue on light blue
        "C": ("#b45309", "#fef3c7"),  # amber on light amber
        "D": ("#b91c1c", "#fee2e2"),  # red on light red
    }
    color, bg = colors.get(g, ("#64748b", "#f1f5f9"))
    return (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
        f'font-weight:700;font-size:11px;background-color:{bg};color:{color};">{g}</span>'
    )


def _render_strategy_table(
    items: list[dict[str, Any]],
    title: str,
    subtitle: str,
    header_color: str,
    header_bg: str,
) -> str:
    rows = []
    for idx, r in enumerate(items[:10], start=1):
        sym = str(r.get("symbol", ""))
        c_price = r.get("current_price") or r.get("price")
        price_str = _fmt_strat_price(c_price)
        score = float(r.get("overall_score") or 0)
        grade_html = _grade_badge(r.get("grade"))
        low = r.get("buy_zone_low")
        high = r.get("buy_zone_high")
        if low is not None and high is not None:
            buy_zone = f"{_fmt_strat_price(low)} – {_fmt_strat_price(high)}"
        else:
            buy_zone = "—"
        stop_loss = _fmt_strat_price(r.get("stop_loss"))
        target = _fmt_strat_price(r.get("target_price"))
        conf = r.get("confidence")
        conf_str = f"{float(conf):.0%}" if conf is not None else "—"

        bg_row = "#ffffff" if idx % 2 != 0 else "#f8fafc"
        rows.append(
            f'<tr style="border-bottom:1px solid #f1f5f9;background-color:{bg_row};">'
            f'<td style="padding:6px 8px;text-align:center;font-weight:600;color:#64748b;">#{idx}</td>'
            f'<td style="padding:6px 8px;font-weight:700;color:#1d4ed8;">{sym}</td>'
            f'<td style="padding:6px 8px;text-align:right;font-weight:600;color:#0f172a;">{price_str}</td>'
            f'<td style="padding:6px 8px;text-align:right;font-weight:700;color:#0f172a;">{score:.1f}</td>'
            f'<td style="padding:6px 8px;text-align:center;">{grade_html}</td>'
            f'<td style="padding:6px 8px;text-align:center;color:#0f172a;font-size:11px;">{buy_zone}</td>'
            f'<td style="padding:6px 8px;text-align:right;color:#b91c1c;font-weight:600;">{stop_loss}</td>'
            f'<td style="padding:6px 8px;text-align:right;color:#15803d;font-weight:600;">{target}</td>'
            f'<td style="padding:6px 8px;text-align:center;color:#475569;">{conf_str}</td>'
            f'</tr>'
        )

    tbody = (
        "".join(rows)
        or '<tr><td colspan="9" style="padding:10px;text-align:center;color:#64748b;font-size:12px;">Chưa có dữ liệu chấm điểm cho hồ sơ này</td></tr>'
    )

    return f"""
    <div style="margin-bottom:16px;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
      <div style="background-color:{header_bg};padding:10px 14px;border-bottom:1px solid #e2e8f0;">
        <div style="font-size:13px;font-weight:700;color:{header_color};">{title}</div>
        <div style="font-size:11px;color:#64748b;margin-top:2px;">{subtitle}</div>
      </div>
      <table style="width:100%;border-collapse:collapse;font-size:12px;">
        <thead style="background:#f8fafc;font-size:11px;color:#64748b;border-bottom:1px solid #e2e8f0;">
          <tr>
            <th style="padding:6px 8px;text-align:center;width:35px;">Hạng</th>
            <th style="padding:6px 8px;text-align:left;width:50px;">Mã</th>
            <th style="padding:6px 8px;text-align:right;width:65px;">Giá hiện tại</th>
            <th style="padding:6px 8px;text-align:right;width:50px;">Điểm</th>
            <th style="padding:6px 8px;text-align:center;width:60px;">Xếp hạng</th>
            <th style="padding:6px 8px;text-align:center;width:140px;">Vùng mua (thấp – cao)</th>
            <th style="padding:6px 8px;text-align:right;width:65px;">Cắt lỗ</th>
            <th style="padding:6px 8px;text-align:right;width:65px;">Mục tiêu</th>
            <th style="padding:6px 8px;text-align:center;width:55px;">Độ tin cậy</th>
          </tr>
        </thead>
        <tbody>
          {tbody}
        </tbody>
      </table>
    </div>"""


def _render_strategy_sections(strategy_rankings: dict[str, list[dict[str, Any]]] | None) -> str:
    if strategy_rankings is None:
        return ""

    profiles = [
        (
            "short",
            "⚡ 1. Chiến lược Ngắn hạn (Short-term)",
            "Nắm giữ 1–20 phiên · Trọng số chính: Kỹ thuật (35%) & Dòng tiền (25%) · Cổng xu hướng: Close > MA20 > MA50",
            "#0369a1",
            "#f0f9ff",
        ),
        (
            "mid",
            "📈 2. Chiến lược Trung hạn (Mid-term)",
            "Nắm giữ 1–6 tháng · Trọng số chính: Cân bằng Tăng trưởng (20%), Định giá (20%) & Kỹ thuật (20%)",
            "#1d4ed8",
            "#eff6ff",
        ),
        (
            "long",
            "💎 3. Chiến lược Dài hạn (Long-term)",
            "Nắm giữ 6–36 tháng · Trọng số chính: Cơ bản, Định giá rẻ (25%), Chất lượng tài chính (25%) & Quản trị",
            "#6d28d9",
            "#f5f3ff",
        ),
    ]

    tables_html = "".join(
        _render_strategy_table(
            strategy_rankings.get(key, []),
            title=title,
            subtitle=subtitle,
            header_color=color,
            header_bg=bg,
        )
        for key, title, subtitle, color, bg in profiles
    )

    explanation_box = """
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-left:4px solid #3b82f6;border-radius:6px;padding:12px 14px;margin-bottom:16px;font-size:12px;color:#334155;line-height:1.6;">
      <b style="color:#0f172a;font-size:13px;">📖 Giải thích các thông tin cơ bản:</b>
      <ul style="margin:6px 0 0 0;padding-left:18px;">
        <li style="margin-bottom:4px;"><b>Điểm (Overall Score):</b> Thang điểm 0–100, tổng hợp tất định từ 24 chỉ tiêu định lượng (Kỹ thuật, Dòng tiền, Tăng trưởng, Chất lượng, Định giá, Vĩ mô, Quản trị) theo trọng số cấu hình riêng của từng hồ sơ chiến lược.</li>
        <li style="margin-bottom:4px;"><b>Xếp hạng (Grade):</b> Phân loại chất lượng & cơ hội:
          <span style="color:#15803d;font-weight:700;">Hạng A (≥80)</span> Rất tích cực;
          <span style="color:#1d4ed8;font-weight:700;">Hạng B (≥65)</span> Khả quan;
          <span style="color:#b45309;font-weight:700;">Hạng C (≥50)</span> Trung bình / thăm dò;
          <span style="color:#b91c1c;font-weight:700;">Hạng D (&lt;50)</span> Kém hoặc có cảnh báo rủi ro (Red flag). Hồ sơ ngắn hạn chỉ đạt hạng A/B khi có xác nhận xu hướng giá (Close &gt; MA20 &gt; MA50).</li>
        <li style="margin-bottom:4px;"><b>Vùng mua (thấp – cao):</b> Khung giá tích lũy giải ngân an toàn quanh giá phiên gần nhất, được xác định dựa trên biên độ biến động thực tế (ATR).</li>
        <li style="margin-bottom:4px;"><b>Cắt lỗ (Stop Loss):</b> Ngưỡng giá phòng vệ vốn bắt buộc (thường đặt ở Close − 2×ATR) nhằm bảo toàn vốn khi giá đảo chiều vi phạm kỳ vọng.</li>
        <li style="margin-bottom:4px;"><b>Mục tiêu (Target Price):</b> Mức giá chốt lời kỳ vọng hướng tới tương ứng tỷ lệ Lợi nhuận / Rủi ro chuẩn mực (R/R tối thiểu ~ 1.5).</li>
        <li><b>Độ tin cậy (Confidence):</b> Mức độ đầy đủ và nhất quán của dữ liệu đầu vào (báo cáo tài chính, khối lượng, sự kiện) tại thời điểm chấm điểm (%).</li>
      </ul>
    </div>"""

    return f"""
      <h3 style="font-size:14px;color:#1e293b;border-bottom:2px solid #e2e8f0;padding-bottom:6px;margin:20px 0 12px 0;">🎖️ Chấm Điểm & Gợi Ý 3 Chiến Lược (Top 10 VN30)</h3>
      {tables_html}
      {explanation_box}
    """


def _render_template(
    *,
    date_str: str,
    idx_name: str,
    idx_close: str,
    idx_change: str,
    adv: int,
    dec: int,
    regime: str,
    confidence: float,
    count: int,
    gainers: str,
    decliners: str,
    ranked: str,
    strategy_section: str = "",
) -> str:
    chg_color = (
        "#15803d"
        if idx_change.startswith("+")
        else ("#b91c1c" if idx_change.startswith("-") else "#64748b")
    )
    diff = adv - dec
    return f"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"><title>DTCK - {date_str}</title></head>
<body style="font-family:sans-serif;background-color:#f8fafc;margin:0;padding:16px;color:#0f172a;">
  <div style="max-width:700px;margin:0 auto;background:#fff;border-radius:10px;border:1px solid #e2e8f0;overflow:hidden;">
    <div style="background:linear-gradient(135deg,#1e3a8a 0%,#3b82f6 100%);padding:20px;color:#fff;">
      <h1 style="margin:0 0 4px 0;font-size:20px;">📊 DTCK — Báo Cáo Tổng Quan Thị Trường</h1>
      <p style="margin:0;font-size:13px;opacity:0.9;">Ngày: <b>{date_str}</b> · Nền tảng AI Đầu tư DTCK</p>
    </div>
    <div style="padding:20px;">
      <table style="width:100%;margin-bottom:20px;border-collapse:collapse;">
        <tr>
          <td style="width:24%;padding:8px;background:#f1f5f9;border-radius:6px;text-align:center;">
            <div style="font-size:11px;color:#64748b;">{idx_name}</div>
            <div style="font-size:16px;font-weight:700;color:#0f172a;">{idx_close}</div>
            <div style="font-size:11px;font-weight:600;color:{chg_color};">{idx_change}</div>
          </td>
          <td style="width:1%;"></td>
          <td style="width:24%;padding:8px;background:#f1f5f9;border-radius:6px;text-align:center;">
            <div style="font-size:11px;color:#64748b;">Tăng / Giảm</div>
            <div style="font-size:16px;font-weight:700;color:#0f172a;">{adv} / {dec}</div>
            <div style="font-size:11px;color:#64748b;">{diff:+d}</div>
          </td>
          <td style="width:1%;"></td>
          <td style="width:24%;padding:8px;background:#f1f5f9;border-radius:6px;text-align:center;">
            <div style="font-size:11px;color:#64748b;">Chế độ</div>
            <div style="font-size:16px;font-weight:700;color:#1d4ed8;">{regime}</div>
            <div style="font-size:11px;color:#64748b;">Tin cậy: {confidence:.0%}</div>
          </td>
          <td style="width:1%;"></td>
          <td style="width:24%;padding:8px;background:#f1f5f9;border-radius:6px;text-align:center;">
            <div style="font-size:11px;color:#64748b;">Đã chấm điểm</div>
            <div style="font-size:16px;font-weight:700;color:#0f172a;">{count} mã</div>
            <div style="font-size:11px;color:#15803d;font-weight:600;">Model ML v1.0</div>
          </td>
        </tr>
      </table>

      <h3 style="font-size:14px;color:#1e293b;border-bottom:2px solid #e2e8f0;padding-bottom:6px;margin:16px 0 10px 0;">↕️ Biến Động Nổi Bật (so với MA20)</h3>
      <table style="width:100%;margin-bottom:16px;border-collapse:collapse;">
        <tr>
          <td style="width:49%;vertical-align:top;">
            <table style="width:100%;border-collapse:collapse;border:1px solid #e2e8f0;">
              <thead style="background:#f0fdf4;font-size:11px;color:#166534;">
                <tr><th style="padding:4px;">Top 10 Tăng</th><th style="padding:4px;text-align:right;">Giá</th><th style="padding:4px;text-align:right;">%1D</th><th style="padding:4px;text-align:right;">vs MA20</th></tr>
              </thead>
              <tbody>{gainers}</tbody>
            </table>
          </td>
          <td style="width:2%;"></td>
          <td style="width:49%;vertical-align:top;">
            <table style="width:100%;border-collapse:collapse;border:1px solid #e2e8f0;">
              <thead style="background:#fef2f2;font-size:11px;color:#991b1b;">
                <tr><th style="padding:4px;">Top 10 Giảm</th><th style="padding:4px;text-align:right;">Giá</th><th style="padding:4px;text-align:right;">%1D</th><th style="padding:4px;text-align:right;">vs MA20</th></tr>
              </thead>
              <tbody>{decliners}</tbody>
            </table>
          </td>
        </tr>
      </table>

      <h3 style="font-size:14px;color:#1e293b;border-bottom:2px solid #e2e8f0;padding-bottom:6px;margin:16px 0 10px 0;">🎯 Đánh Giá & Dự Đoán VN30</h3>
      <table style="width:100%;border-collapse:collapse;border:1px solid #e2e8f0;margin-bottom:16px;">
        <thead style="background:#f8fafc;font-size:11px;color:#64748b;">
          <tr>
            <th style="padding:6px 8px;text-align:left;">Hạng</th>
            <th style="padding:6px 8px;text-align:left;">Mã</th>
            <th style="padding:6px 8px;text-align:right;">Giá hiện tại</th>
            <th style="padding:6px 8px;text-align:right;">Điểm §12</th>
            <th style="padding:6px 8px;text-align:center;">Tín hiệu</th>
            <th style="padding:6px 8px;text-align:right;">P(tăng 5D)</th>
            <th style="padding:6px 8px;text-align:right;">LN kỳ vọng</th>
            <th style="padding:6px 8px;text-align:center;">Gợi ý</th>
          </tr>
        </thead>
        <tbody>{ranked}</tbody>
      </table>

      {strategy_section}

      <div style="background:#f8fafc;border:1px dashed #cbd5e1;border-radius:6px;padding:10px;font-size:11px;color:#64748b;">
        <b>📌 Chú thích:</b> Điểm §12 tất định 0–100 · P(tăng 5D) từ ML XGBoost · Bản tin tự động hỗ trợ quyết định, không phải khuyến nghị đầu tư (§3).
      </div>
    </div>
    <div style="background:#f1f5f9;padding:10px;text-align:center;font-size:11px;color:#94a3b8;border-top:1px solid #e2e8f0;">
      DTCK System · Tự động gửi lúc 08:00, 12:30 &amp; 16:30 (Thứ 2 - Thứ 6)
    </div>
  </div>
 </body>
</html>"""
