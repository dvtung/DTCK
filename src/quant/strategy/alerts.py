"""Grade-change alerts (GĐ 6) — reuse the existing SMTP notification stack.

Compares the two most recent scored sessions and reports every (symbol,
profile) whose letter grade moved. Only **changes** are reported: a quiet day
sends nothing (no alert fatigue, §4.6 human-in-the-loop).

Email delivery reuses :class:`src.notifications.service.NotificationService`
(Gmail App Password setup done in T018) — no second SMTP path is introduced.
"""

from __future__ import annotations

import html
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import Connection, text

logger = logging.getLogger(__name__)

__all__ = [
    "GradeChange",
    "build_change_email",
    "detect_grade_changes",
    "send_grade_change_alert",
]


@dataclass(frozen=True, slots=True)
class GradeChange:
    """One grade that moved between the previous and the latest session."""

    symbol: str
    strategy: str
    previous_grade: str | None
    new_grade: str | None
    previous_date: date | None
    new_date: date
    overall_score: float | None = None

    @property
    def direction(self) -> str:
        if not self.previous_grade or not self.new_grade:
            return "NEW"
        order = {"A": 4, "B": 3, "C": 2, "D": 1}
        return "UP" if order[self.new_grade] > order.get(self.previous_grade, 0) else "DOWN"

    def subject(self) -> str:
        return (
            f"{self.symbol} ({self.strategy}): "
            f"{self.previous_grade or '—'} → {self.new_grade or '—'} ({self.direction})"
        )


def detect_grade_changes(conn: Connection) -> list[GradeChange]:
    """Grade deltas between the two latest scored sessions.

    Empty when fewer than two sessions exist (nothing to compare yet).
    """
    dates = [
        row[0]
        for row in conn.execute(
            text(
                "select distinct trade_date from strategy_scores "
                "order by trade_date desc limit 2"
            )
        ).all()
    ]
    if len(dates) < 2:
        return []
    latest, previous = dates[0], dates[1]

    def _grades(session_date: date) -> dict[tuple[str, str], str | None]:
        rows = conn.execute(
            text(
                "select sc.strategy, st.symbol, rc.grade "
                "from strategy_scores sc join stocks st on st.id = sc.stock_id "
                "left join strategy_recommendations rc on rc.stock_id = sc.stock_id "
                "and rc.trade_date = sc.trade_date and rc.strategy = sc.strategy "
                "where sc.trade_date = :d"
            ),
            {"d": session_date},
        ).all()
        return {(str(r[0]), str(r[1])): r[2] for r in rows}

    now = _grades(latest)
    before = _grades(previous)
    changes: list[GradeChange] = []
    for (strategy, symbol), new_grade in now.items():
        if (strategy, symbol) not in before:
            continue
        old_grade = before[(strategy, symbol)]
        if old_grade == new_grade:
            continue
        score_rows = conn.execute(
            text(
                "select sc.overall_score from strategy_scores sc "
                "join stocks st on st.id = sc.stock_id "
                "where sc.trade_date = :d and sc.strategy = :s and st.symbol = :sym"
            ),
            {"d": latest, "s": strategy, "sym": symbol},
        ).all()
        overall = float(score_rows[0][0]) if score_rows and score_rows[0][0] is not None else None
        changes.append(
            GradeChange(
                symbol=symbol,
                strategy=strategy,
                previous_grade=old_grade,
                new_grade=new_grade,
                previous_date=previous,
                new_date=latest,
                overall_score=overall,
            )
        )
    changes.sort(key=lambda c: (c.strategy, c.symbol))
    return changes


def send_grade_change_alert(
    conn: Connection,
    *,
    dry_run: bool = False,
    subject: str | None = None,
) -> dict[str, Any]:
    """Detect grade changes and email them through the existing SMTP config.

    Returns ``{"success", "changes", "sent", "error", "html"}``. Nothing is sent
    when there are no changes (quiet days stay quiet) or when no mailer is
    configured — the reason is reported, never silently swallowed.
    """
    changes = detect_grade_changes(conn)
    html_body = build_change_email(changes)
    if not changes:
        return {"success": True, "changes": 0, "sent": 0, "html": html_body}
    if dry_run:
        return {"success": True, "changes": len(changes), "sent": 0, "html": html_body}

    from src.notifications.service import NotificationService

    service = NotificationService()
    mailer = service.get_mailer()
    if mailer is None:
        return {
            "success": False,
            "changes": len(changes),
            "sent": 0,
            "error": "Chưa cấu hình tài khoản gửi Gmail SMTP. Vui lòng vào Cài đặt Email.",
            "html": html_body,
        }
    recipients = [r["email"] for r in service.get_recipients(active_only=True)]
    if not recipients:
        return {
            "success": False,
            "changes": len(changes),
            "sent": 0,
            "error": "Danh sách người nhận đang trống.",
            "html": html_body,
        }

    subj = subject or (
        f"[DTCK] Thay đổi xếp hạng chiến lược — {changes[0].new_date.strftime('%d/%m/%Y')}"
    )
    sent = 0
    errors: list[str] = []
    for email in recipients:
        result = mailer.send_email(to_email=email, subject=subj, html_content=html_body)
        if result.get("success"):
            sent += 1
        else:
            errors.append(f"{email}: {result.get('error')}")
    logger.info(
        "strategy grade-change alert: changes=%d sent=%d/%d",
        len(changes),
        sent,
        len(recipients),
    )
    return {
        "success": sent > 0,
        "changes": len(changes),
        "sent": sent,
        "error": "; ".join(errors) if errors else None,
        "html": html_body,
    }


def build_change_email(changes: Sequence[GradeChange], as_of: date | None = None) -> str:
    """HTML digest of the changes (pure — unit tested without a mailer)."""
    day = (as_of or (changes[0].new_date if changes else datetime.now().date())).isoformat()
    rows = "".join(
        f"<tr><td>{html.escape(c.symbol)}</td>"
        f"<td>{html.escape(c.strategy)}</td>"
        f"<td>{html.escape(c.previous_grade or '—')}</td>"
        f"<td>{html.escape(c.new_grade or '—')}</td>"
        f"<td>{html.escape(c.direction)}</td>"
        f"<td>{'' if c.overall_score is None else f'{c.overall_score:.1f}'}</td></tr>"
        for c in changes
    )
    body = rows or "<tr><td colspan='6'>Không có thay đổi grade.</td></tr>"
    return (
        f"<h2>Thay đổi xếp hạng chiến lược — {day}</h2>"
        "<p>Số mã đổi grade: "
        f"<b>{len(changes)}</b></p>"
        "<table border='1' cellpadding='6' cellspacing='0'>"
        "<tr><th>Mã</th><th>Chiến lược</th><th>Cũ</th><th>Mới</th>"
        "<th>Hướng</th><th>Điểm</th></tr>"
        f"{body}</table>"
        "<p style='color:#666'>Kết quả chỉ mang tính tham khảo, không phải khuyến nghị "
        "đầu tư cá nhân (§3).</p>"
    )
