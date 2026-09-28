"""Integration tests for email notification persistence (T018).

Skipped when TimescaleDB is unreachable/un-migrated (see ``conftest``).

Every test here writes through ``isolated_session_factory`` — a transaction that
is rolled back at teardown — because ``DATABASE_URL`` points at the developer's
live database (the API/worker use the same one).  See the T018 regression note in
``conftest``: a global ``DELETE`` in this module previously wiped the configured
SMTP account on every test run.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.db import session_factory
from apps.api.services.market_data import MarketService
from src.common.models.notifications import EmailRecipient, EmailSmtpConfig
from src.notifications.service import NotificationService


@pytest.fixture()
def service(isolated_session_factory: Callable[[], Session]) -> NotificationService:
    return NotificationService(session_maker=isolated_session_factory)


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
    # Every window is persisted, including the noon slot added for the 12:30 report.
    service.save_schedule_config(
        morning_hour=8,
        morning_minute=0,
        noon_hour=12,
        noon_minute=30,
        afternoon_hour=16,
        afternoon_minute=30,
        is_enabled=True,
    )
    restored = service.get_schedule_config()
    assert (restored["morning_hour"], restored["morning_minute"]) == (8, 0)
    assert (restored["noon_hour"], restored["noon_minute"]) == (12, 30)
    assert (restored["afternoon_hour"], restored["afternoon_minute"]) == (16, 30)
    assert restored["is_enabled"] is True
    # The API/worker contract exposes all three windows by name.
    from src.notifications.service import DEFAULT_EMAIL_SCHEDULE

    assert {"morning_hour", "noon_hour", "afternoon_hour"} <= DEFAULT_EMAIL_SCHEDULE.keys()


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
    service.save_smtp_config(sender_email="sender@gmail.com", sender_password="pw")
    res = service.dispatch_report(MarketService(), recipients=["dispatch@dtck.local"])
    assert res["success"] is True
    assert res["sent"] == 1
    assert delivered == ["dispatch@dtck.local"]
    logs = service.get_logs(limit=5)
    assert any(
        r["recipient_email"] == "dispatch@dtck.local" and r["status"] == "SUCCESS" for r in logs
    )
    # No cleanup needed: the fake account lives inside the fixture transaction and
    # is rolled back at teardown (a global DELETE here wiped the real config once).


def test_isolated_writes_never_reach_the_shared_database(
    service: NotificationService,
) -> None:
    """Regression (T018): the suite shares the developer's DB.

    A save performed through the isolated fixture must stay invisible to every
    other connection, so no test can overwrite or delete a real SMTP account.
    """
    probe_email = "rollback-probe@dtck.local"
    service.save_smtp_config(sender_email=probe_email, sender_password="pw")
    service.add_recipient(probe_email)
    # Visible inside the fixture transaction…
    assert service.get_smtp_config()["sender_email"] == probe_email

    # …but invisible to an independent connection (the app's real factory).
    with session_factory() as probe:
        smtp_hits = probe.scalar(
            select(func.count())
            .select_from(EmailSmtpConfig)
            .where(EmailSmtpConfig.sender_email == probe_email)
        )
        recipient_hits = probe.scalar(
            select(func.count())
            .select_from(EmailRecipient)
            .where(EmailRecipient.email == probe_email)
        )
    assert smtp_hits == 0
    assert recipient_hits == 0
