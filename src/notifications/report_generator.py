"""HTML report generator for Market Overview (Tổng quan thị trường)."""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.dashboard.components import format_date, format_percent, format_price, signal_label


def generate_market_overview_html(
    *,
    indices: list[dict[str, Any]],
    breadth: dict[str, Any],
    regime: dict[str, Any],
    ranked: list[dict[str, Any]],
    predictions: dict[str, dict[str, Any]] | None = None,
    movers: dict[str, Any] | None = None,
    trade_date: str | date | None = None,
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
        o_val = float(str(headline.get("open", 1))) or 1.0
        index_close = format_price(c_val)
        index_change = format_percent((c_val - o_val) / o_val, signed=True)

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
        for g in (movers.get("gainers") or [])[:5]:
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
        for d in (movers.get("decliners") or [])[:5]:
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
        or '<tr><td colspan="7" style="padding:12px;text-align:center;">Chưa có dữ liệu</td></tr>'
    )

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
    )


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
) -> str:
    chg_color = "#15803d" if "+" in idx_change else "#b91c1c"
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
                <tr><th style="padding:4px;">Top Tăng</th><th style="padding:4px;text-align:right;">Giá</th><th style="padding:4px;text-align:right;">%1D</th><th style="padding:4px;text-align:right;">vs MA20</th></tr>
              </thead>
              <tbody>{gainers}</tbody>
            </table>
          </td>
          <td style="width:2%;"></td>
          <td style="width:49%;vertical-align:top;">
            <table style="width:100%;border-collapse:collapse;border:1px solid #e2e8f0;">
              <thead style="background:#fef2f2;font-size:11px;color:#991b1b;">
                <tr><th style="padding:4px;">Top Giảm</th><th style="padding:4px;text-align:right;">Giá</th><th style="padding:4px;text-align:right;">%1D</th><th style="padding:4px;text-align:right;">vs MA20</th></tr>
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
            <th style="padding:6px 8px;text-align:right;">Điểm §12</th>
            <th style="padding:6px 8px;text-align:center;">Tín hiệu</th>
            <th style="padding:6px 8px;text-align:right;">P(tăng 5D)</th>
            <th style="padding:6px 8px;text-align:right;">LN kỳ vọng</th>
            <th style="padding:6px 8px;text-align:center;">Gợi ý</th>
          </tr>
        </thead>
        <tbody>{ranked}</tbody>
      </table>

      <div style="background:#f8fafc;border:1px dashed #cbd5e1;border-radius:6px;padding:10px;font-size:11px;color:#64748b;">
        <b>📌 Chú thích:</b> Điểm §12 tất định 0–100 · P(tăng 5D) từ ML XGBoost · Bản tin tự động hỗ trợ quyết định, không phải khuyến nghị đầu tư (§3).
      </div>
    </div>
    <div style="background:#f1f5f9;padding:10px;text-align:center;font-size:11px;color:#94a3b8;border-top:1px solid #e2e8f0;">
      DTCK System · Tự động gửi lúc 08:00 &amp; 15:30 (Thứ 2 - Thứ 6)
    </div>
  </div>
</body>
</html>"""
