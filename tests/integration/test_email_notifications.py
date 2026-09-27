"""Integration tests for email notification persistence (T018).

Skipped when TimescaleDB is unreachable/un-migrated (see ``conftest``).
"""

from __future__ import annotations

from typing import Any

import pytest

from apps.api.db import session_factory
from apps.api.services.market_data import MarketService
from src.notifications.service import NotificationService


@pytest.fixture()
def service(db_ready: None) -> NotificationService:
    return NotificationService()


def test_recipient_lifecycle(service: NotificationService) -> None:
    email = "integration-recipient@dtck.local"
    created = service.add_recipient(email, "Integration Test")
    try:
        assert created["email"] == email
        assert email in [r["email"] for r in service.get_recipients()]
        # Duplicate add re-activates the existing row (idempotent, no 500).
        again = service.add_recipient(email)
        assert again["id"] == created["id"]
        assert service.update_recipient(created["id"], is_active=False) is True
        assert email not in [r["email"] for r in service.get_recipients(active_only=True)]
    finally:
        service.delete_recipient(created["id"])
    assert email not in [r["email"] for r in service.get_recipients()]


def test_update_or_delete_unknown_recipient_returns_false(
    service: NotificationService,
) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    assert service.update_recipient(missing, is_active=True) is False
    assert service.delete_recipient(missing) is False


def test_smtp_config_round_trip_never_exposes_password(service: NotificationService) -> None:
    service.save_smtp_config(
        sender_email="sender@gmail.com",
        sender_password="app-password-123",
        sender_name="DTCK Test",
    )
    cfg = service.get_smtp_config()
    assert cfg["sender_email"] == "sender@gmail.com"
    assert cfg["is_configured"] is True
    # The read contract must never leak the credential (SECURITY §32).
    assert "sender_password" not in cfg
    assert service.get_mailer() is not None


def test_schedule_config_round_trip(service: NotificationService) -> None:
    service.save_schedule_config(morning_hour=8, morning_minute=0, is_enabled=False)
    cfg = service.get_schedule_config()
    assert cfg["morning_hour"] == 8
    assert cfg["is_enabled"] is False
    # Restore the documented default (Mon-Fri 08:00 / 15:30, enabled).
    service.save_schedule_config(
        morning_hour=8, morning_minute=0, afternoon_hour=15, afternoon_minute=30, is_enabled=True
    )
    restored = service.get_schedule_config()
    assert (restored["morning_hour"], restored["afternoon_hour"]) == (8, 15)
    assert restored["is_enabled"] is True


def test_dispatch_without_recipients_reports_error(service: NotificationService) -> None:
    res = service.dispatch_report(MarketService(), recipients=[])
    assert res["success"] is False
    assert res["error"]


def test_send_log_is_persisted(service: NotificationService) -> None:
    service._log_send("logged@dtck.local", "unit subject", "SUCCESS", None)  # noqa: SLF001
    logs = service.get_logs(limit=5)
    row = next(r for r in logs if r["recipient_email"] == "logged@dtck.local")
    assert row["status"] == "SUCCESS"
    assert row["sent_at"]


def test_build_overview_html_uses_live_service(service: NotificationService) -> None:
    html = service.build_current_overview_html(MarketService())
    assert "DTCK" in html
    assert len(html) > 1000


def test_dispatch_report_sends_via_mocked_smtp(
    service: NotificationService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end dispatch: report → mailer → log row (SMTP mocked)."""
    delivered: list[str] = []

    class _FakeSMTP:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> _FakeSMTP:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def starttls(self) -> None:
            return None

        def login(self, user: str, password: str) -> None:
            return None

        def send_message(self, msg: Any) -> None:
            delivered.append(str(msg["To"]))

    monkeypatch.setattr("smtplib.SMTP", _FakeSMTP)
    try:
        service.save_smtp_config(sender_email="sender@gmail.com", sender_password="pw")
        res = service.dispatch_report(MarketService(), recipients=["dispatch@dtck.local"])
        assert res["success"] is True
        assert res["sent"] == 1
        assert delivered == ["dispatch@dtck.local"]
        logs = service.get_logs(limit=5)
        assert any(
            r["recipient_email"] == "dispatch@dtck.local" and r["status"] == "SUCCESS"
            for r in logs
        )
    finally:
        # Never leave a fake SMTP account behind: other suites assert the
        # "not configured" path and a leftover row would make them flaky.
        _clear_smtp_configs()


def _clear_smtp_configs() -> None:
    from sqlalchemy import delete

    from src.common.models.notifications import EmailSmtpConfig

    with session_factory() as session:
        session.execute(delete(EmailSmtpConfig))
        session.commit()
