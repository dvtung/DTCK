"""Notification service: DB persistence and report dispatcher."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.db import session_factory
from apps.api.services.market_source import MarketSource

if TYPE_CHECKING:
    from apps.api.services.strategy_service import StrategySource
from src.common.models.notifications import (
    EmailRecipient,
    EmailScheduleConfig,
    EmailSendLog,
    EmailSmtpConfig,
)
from src.notifications.report_generator import generate_market_overview_html
from src.notifications.smtp_mailer import SmtpMailer

logger = logging.getLogger("dtck.notifications.service")

#: Schedule used when no row exists yet — the three documented report windows
#: (Asia/Ho_Chi_Minh, Mon–Fri): 08:00 previous-session summary, 12:30 morning
#: session, 16:30 afternoon session.  Kept as a module constant so the API,
#: dashboard fallback and worker scheduler can never drift apart.
DEFAULT_EMAIL_SCHEDULE: dict[str, Any] = {
    "morning_hour": 8,
    "morning_minute": 0,
    "noon_hour": 12,
    "noon_minute": 30,
    "afternoon_hour": 16,
    "afternoon_minute": 30,
    "days_of_week": "mon-fri",
    "is_enabled": True,
}

#: Ordered ``(period_key, label, hour_field, minute_field)`` report windows.
#: ``period_key`` travels into the subject line; ``label`` is the Vietnamese
#: session name rendered in the email subject.
REPORT_WINDOWS: tuple[tuple[str, str, str, str], ...] = (
    ("morning", "sáng", "morning_hour", "morning_minute"),
    ("noon", "trưa", "noon_hour", "noon_minute"),
    ("afternoon", "chiều", "afternoon_hour", "afternoon_minute"),
)


class NotificationService:
    """Manages email recipients, SMTP configs, schedules, and report dispatching."""

    def __init__(self, session_maker: Callable[[], Session] | None = None) -> None:
        self._session_maker = session_maker or session_factory

    def get_recipients(self, active_only: bool = False) -> list[dict[str, Any]]:
        with self._session_maker() as session:
            stmt = select(EmailRecipient).order_by(EmailRecipient.created_at.desc())
            if active_only:
                stmt = stmt.where(EmailRecipient.is_active.is_(True))
            rows = session.scalars(stmt).all()
            return [
                {
                    "id": str(r.id),
                    "email": r.email,
                    "name": r.name,
                    "is_active": r.is_active,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]

    def add_recipient(self, email: str, name: str | None = None) -> dict[str, Any]:
        email_clean = email.strip().lower()
        with self._session_maker() as session:
            existing = session.scalar(
                select(EmailRecipient).where(EmailRecipient.email == email_clean)
            )
            if existing:
                existing.is_active = True
                if name:
                    existing.name = name
                session.commit()
                return {
                    "id": str(existing.id),
                    "email": existing.email,
                    "name": existing.name,
                    "is_active": True,
                }
            rec = EmailRecipient(email=email_clean, name=name, is_active=True)
            session.add(rec)
            session.commit()
            return {"id": str(rec.id), "email": rec.email, "name": rec.name, "is_active": True}

    def update_recipient(self, recipient_id: str, is_active: bool) -> bool:
        with self._session_maker() as session:
            rec = session.get(EmailRecipient, UUID(recipient_id))
            if not rec:
                return False
            rec.is_active = is_active
            session.commit()
            return True

    def delete_recipient(self, recipient_id: str) -> bool:
        with self._session_maker() as session:
            rec = session.get(EmailRecipient, UUID(recipient_id))
            if not rec:
                return False
            session.delete(rec)
            session.commit()
            return True

    def get_smtp_config(self) -> dict[str, Any]:
        with self._session_maker() as session:
            row = session.scalar(
                select(EmailSmtpConfig).order_by(EmailSmtpConfig.id.desc()).limit(1)
            )
            if not row:
                return {
                    "smtp_server": "smtp.gmail.com",
                    "smtp_port": 587,
                    "sender_email": "",
                    "sender_name": "DTCK Market Intel",
                    "use_tls": True,
                    "use_ssl": False,
                    "is_active": False,
                    "is_configured": False,
                }
            return {
                "id": row.id,
                "smtp_server": row.smtp_server,
                "smtp_port": row.smtp_port,
                "sender_email": row.sender_email,
                "sender_name": row.sender_name,
                "use_tls": row.use_tls,
                "use_ssl": row.use_ssl,
                "is_active": row.is_active,
                "is_configured": bool(row.sender_email and row.sender_password),
            }

    def save_smtp_config(
        self,
        *,
        smtp_server: str = "smtp.gmail.com",
        smtp_port: int = 587,
        sender_email: str,
        sender_password: str,
        sender_name: str = "DTCK Market Intel",
        use_tls: bool = True,
        use_ssl: bool = False,
    ) -> dict[str, Any]:
        with self._session_maker() as session:
            row = session.scalar(
                select(EmailSmtpConfig).order_by(EmailSmtpConfig.id.desc()).limit(1)
            )
            if not row:
                row = EmailSmtpConfig(
                    smtp_server=smtp_server.strip(),
                    smtp_port=int(smtp_port),
                    sender_email=sender_email.strip(),
                    sender_password=sender_password.strip(),
                    sender_name=sender_name.strip(),
                    use_tls=use_tls,
                    use_ssl=use_ssl,
                    is_active=True,
                )
                session.add(row)
            else:
                row.smtp_server = smtp_server.strip()
                row.smtp_port = int(smtp_port)
                row.sender_email = sender_email.strip()
                if sender_password.strip():
                    row.sender_password = sender_password.strip()
                row.sender_name = sender_name.strip()
                row.use_tls = use_tls
                row.use_ssl = use_ssl
                row.is_active = True
            session.commit()
            result: dict[str, Any] = {"success": True, "sender_email": row.sender_email}
            # Gmail only accepts 16-char App Passwords over SMTP; anything else is
            # guaranteed to fail with 535 — surface that before the user test-sends.
            if row.smtp_server.endswith("gmail.com") and len(
                row.sender_password.replace(" ", "")
            ) != 16:
                result["warning"] = (
                    "Mật khẩu hiện tại không phải App Password (16 ký tự) nên Google sẽ "
                    "từ chối khi gửi. Hãy tạo Mật khẩu ứng dụng tại "
                    "myaccount.google.com/apppasswords (cần bật Xác thực 2 bước) rồi lưu lại."
                )
            return result

    def get_schedule_config(self) -> dict[str, Any]:
        with self._session_maker() as session:
            row = session.scalar(
                select(EmailScheduleConfig).order_by(EmailScheduleConfig.id.desc()).limit(1)
            )
            if not row:
                return dict(DEFAULT_EMAIL_SCHEDULE)
            return {
                "morning_hour": row.morning_hour,
                "morning_minute": row.morning_minute,
                "noon_hour": row.noon_hour,
                "noon_minute": row.noon_minute,
                "afternoon_hour": row.afternoon_hour,
                "afternoon_minute": row.afternoon_minute,
                "days_of_week": row.days_of_week,
                "is_enabled": row.is_enabled,
            }

    def save_schedule_config(
        self,
        *,
        morning_hour: int = 8,
        morning_minute: int = 0,
        noon_hour: int = 12,
        noon_minute: int = 30,
        afternoon_hour: int = 16,
        afternoon_minute: int = 30,
        days_of_week: str = "mon-fri",
        is_enabled: bool = True,
    ) -> dict[str, Any]:
        with self._session_maker() as session:
            row = session.scalar(
                select(EmailScheduleConfig).order_by(EmailScheduleConfig.id.desc()).limit(1)
            )
            if not row:
                row = EmailScheduleConfig(
                    morning_hour=morning_hour,
                    morning_minute=morning_minute,
                    noon_hour=noon_hour,
                    noon_minute=noon_minute,
                    afternoon_hour=afternoon_hour,
                    afternoon_minute=afternoon_minute,
                    days_of_week=days_of_week,
                    is_enabled=is_enabled,
                )
                session.add(row)
            else:
                row.morning_hour = morning_hour
                row.morning_minute = morning_minute
                row.noon_hour = noon_hour
                row.noon_minute = noon_minute
                row.afternoon_hour = afternoon_hour
                row.afternoon_minute = afternoon_minute
                row.days_of_week = days_of_week
                row.is_enabled = is_enabled
            session.commit()
            return {"success": True}

    def get_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._session_maker() as session:
            stmt = select(EmailSendLog).order_by(EmailSendLog.sent_at.desc()).limit(limit)
            rows = session.scalars(stmt).all()
            return [
                {
                    "id": str(r.id),
                    "recipient_email": r.recipient_email,
                    "subject": r.subject,
                    "status": r.status,
                    "error_message": r.error_message,
                    "sent_at": r.sent_at.isoformat() if r.sent_at else None,
                }
                for r in rows
            ]

    def _log_send(
        self, recipient: str, subject: str, status: str, error: str | None = None
    ) -> None:
        try:
            with self._session_maker() as session:
                log_entry = EmailSendLog(
                    recipient_email=recipient,
                    subject=subject,
                    status=status,
                    error_message=error,
                    sent_at=datetime.now(UTC),
                )
                session.add(log_entry)
                session.commit()
        except Exception as exc:
            logger.warning("Failed to record email send log: %s", exc)

    def get_mailer(self) -> SmtpMailer | None:
        with self._session_maker() as session:
            row = session.scalar(
                select(EmailSmtpConfig).order_by(EmailSmtpConfig.id.desc()).limit(1)
            )
            if not row or not row.sender_email or not row.sender_password:
                return None
            return SmtpMailer(
                smtp_server=row.smtp_server,
                smtp_port=row.smtp_port,
                sender_email=row.sender_email,
                sender_password=row.sender_password,
                sender_name=row.sender_name,
                use_tls=row.use_tls,
                use_ssl=row.use_ssl,
            )

    def build_current_overview_html(
        self,
        market_service: MarketSource,
        strategy_service: StrategySource | None = None,
    ) -> str:
        indices = market_service.list_indices()
        breadth = market_service.get_breadth()
        regime = market_service.get_regime()
        ranked = market_service.get_ranked()
        movers = market_service.get_movers(universe="VN100", limit=10)

        strat_rankings: dict[str, list[dict[str, Any]]] = {}
        if strategy_service is None:
            try:
                from apps.api.dependencies import get_strategy_service

                strategy_service = get_strategy_service()
            except Exception:
                strategy_service = None

        if strategy_service is not None:
            for profile_name in ("short", "mid", "long"):
                try:
                    strat_rankings[profile_name] = strategy_service.rankings(
                        profile_name, universe="vn30"
                    )[:10]
                except Exception as exc:
                    logger.debug(
                        "Failed to fetch strategy rankings for %s: %s", profile_name, exc
                    )
                    strat_rankings[profile_name] = []

        preds: dict[str, dict[str, Any]] = {}
        try:
            from apps.api.routers.predictions import get_prediction_service

            pred_svc = get_prediction_service()
            for r in ranked[:15]:
                sym = str(r.get("symbol", ""))
                try:
                    p = pred_svc.predict(sym)
                    if isinstance(p, dict) and p.get("available"):
                        preds[sym] = {
                            "probability_positive": p.get("probability_positive"),
                            "expected_return": p.get("expected_return"),
                        }
                except Exception:
                    pass
        except Exception:
            pass

        return generate_market_overview_html(
            indices=indices,
            breadth=breadth,
            regime=regime,
            ranked=ranked,
            predictions=preds,
            movers=movers,
            strategy_rankings=strat_rankings,
        )

    def dispatch_report(
        self,
        market_service: MarketSource,
        recipients: list[str] | None = None,
        subject: str | None = None,
        strategy_service: StrategySource | None = None,
    ) -> dict[str, Any]:
        mailer = self.get_mailer()
        if not mailer:
            return {
                "success": False,
                "error": "Chưa cấu hình tài khoản gửi Gmail SMTP. Vui lòng vào Cài đặt Email.",
            }

        target_emails = recipients
        if target_emails is None:
            active_recs = self.get_recipients(active_only=True)
            target_emails = [r["email"] for r in active_recs]

        if not target_emails:
            return {"success": False, "error": "Danh sách người nhận đang trống."}

        html = self.build_current_overview_html(
            market_service, strategy_service=strategy_service
        )
        subj = (
            subject
            or f"[DTCK] Báo Cáo Tổng Quan Thị Trường — {datetime.now(UTC).strftime('%d/%m/%Y')}"
        )

        results = []
        for em in target_emails:
            res = mailer.send_email(to_email=em, subject=subj, html_content=html)
            status = "SUCCESS" if res.get("success") else "FAILED"
            err = res.get("error")
            self._log_send(em, subj, status, err)
            results.append({"email": em, "status": status, "error": err})

        success_count = sum(1 for r in results if r["status"] == "SUCCESS")
        return {
            "success": success_count > 0,
            "total": len(target_emails),
            "sent": success_count,
            "details": results,
            "html_preview": html,
        }
