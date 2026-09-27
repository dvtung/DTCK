"""Unit tests for automated email reports (T018): generator, mailer, service, API.

Everything runs offline: SMTP is monkeypatched, and the service is exercised
against the in-memory market fixture — no Gmail credentials are needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from apps.api.services.market_data import MarketService
from src.notifications.report_generator import generate_market_overview_html
from src.notifications.smtp_mailer import SmtpMailer


def _fixture_service() -> MarketService:
    return MarketService()


class TestReportGenerator:
    """HTML email body must carry the Overview figures and the §3 disclaimer."""

    def test_renders_kpi_sections_and_tables(self) -> None:
        svc = _fixture_service()
        html = generate_market_overview_html(
            indices=svc.list_indices(),
            breadth=svc.get_breadth(),
            regime=svc.get_regime(),
            ranked=svc.get_ranked(),
            predictions={"FPT": {"probability_positive": 0.62, "expected_return": 0.012}},
            movers=svc.get_movers(universe="VN30", limit=5),
        )
        assert html.startswith("<!DOCTYPE html>")
        assert "VNINDEX" in html
        assert "Biến Động Nổi Bật" in html
        assert "Đánh Giá" in html
        assert "không phải khuyến nghị" in html  # §3 disclaimer
        assert "62.0%" in html  # prediction rendered
        assert html.count("<tr") > 3

    def test_headline_index_prefers_vnindex(self) -> None:
        html = generate_market_overview_html(
            indices=[
                {"index_code": "VN30", "open": 1300, "close": 1310, "trade_date": "2026-09-25"},
                {"index_code": "VNINDEX", "open": 1200, "close": 1212, "trade_date": "2026-09-25"},
            ],
            breadth={},
            regime={},
            ranked=[],
        )
        assert "VNINDEX" in html

    def test_empty_data_still_renders_honestly(self) -> None:
        """No data must produce placeholders, never invented numbers."""
        html = generate_market_overview_html(
            indices=[], breadth={}, regime={}, ranked=[], movers=None
        )
        assert "Chưa có dữ liệu" in html
        assert "—" in html


class TestSmtpMailer:
    """SMTP transport: STARTTLS + SSL paths, auth errors surfaced (never silent)."""

    def test_missing_credentials_returns_error(self) -> None:
        mailer = SmtpMailer(sender_email="", sender_password="")
        res = mailer.send_email(to_email="a@b.com", subject="s", html_content="<p>x</p>")
        assert res["success"] is False
        assert "chưa được thiết lập" in res["error"]

    def test_starttls_path_sends_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sent: dict[str, Any] = {}

        class _FakeSMTP:
            def __init__(self, host: str, port: int, timeout: float) -> None:
                sent["host"] = host
                sent["port"] = port

            def __enter__(self) -> _FakeSMTP:
                return self

            def __exit__(self, *exc: object) -> None:
                return None

            def starttls(self) -> None:
                sent["tls"] = True

            def login(self, user: str, password: str) -> None:
                sent["login"] = (user, password)

            def send_message(self, msg: Any) -> None:
                sent["subject"] = msg["Subject"]
                sent["to"] = msg["To"]

        monkeypatch.setattr("smtplib.SMTP", _FakeSMTP)
        mailer = SmtpMailer(
            sender_email="sender@gmail.com",
            sender_password="app-password",
            use_tls=True,
        )
        res = mailer.send_email(
            to_email="dest@example.com", subject="Chủ đề", html_content="<p>x</p>"
        )
        assert res["success"] is True
        assert sent["tls"] is True
        assert sent["login"] == ("sender@gmail.com", "app-password")
        assert sent["to"] == "dest@example.com"
        assert sent["subject"] == "Chủ đề"
        assert sent["port"] == 587

    def test_ssl_path_used_for_port_465(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: dict[str, int] = {}

        class _FakeSSL:
            def __init__(self, host: str, port: int, timeout: float) -> None:
                seen["port"] = port

            def __enter__(self) -> _FakeSSL:
                return self

            def __exit__(self, *exc: object) -> None:
                return None

            def login(self, user: str, password: str) -> None:
                return None

            def send_message(self, msg: Any) -> None:
                return None

        monkeypatch.setattr("smtplib.SMTP_SSL", _FakeSSL)
        mailer = SmtpMailer(
            sender_email="s@gmail.com",
            sender_password="pw",
            smtp_port=465,
            use_ssl=True,
        )
        res = mailer.send_email(to_email="d@example.com", subject="s", html_content="<p>x</p>")
        assert res["success"] is True
        assert seen["port"] == 465

    def test_authentication_error_is_reported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import smtplib

        class _FailingSMTP:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

            def __enter__(self) -> _FailingSMTP:
                return self

            def __exit__(self, *exc: object) -> None:
                return None

            def starttls(self) -> None:
                return None

            def login(self, user: str, password: str) -> None:
                raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

            def send_message(self, msg: Any) -> None:
                return None

        monkeypatch.setattr("smtplib.SMTP", _FailingSMTP)
        mailer = SmtpMailer(sender_email="s@gmail.com", sender_password="wrong")
        res = mailer.send_email(to_email="d@example.com", subject="s", html_content="<p>x</p>")
        assert res["success"] is False
        assert "App Password" in res["error"]

    def test_disconnect_during_auth_reports_app_password_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Gmail drops the connection after repeated failed AUTH (T018 live bug)."""
        import smtplib

        class _DroppingSMTP:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

            def __enter__(self) -> _DroppingSMTP:
                return self

            def __exit__(self, *exc: object) -> None:
                return None

            def starttls(self) -> None:
                return None

            def login(self, user: str, password: str) -> None:
                raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")

            def send_message(self, msg: Any) -> None:
                return None

        monkeypatch.setattr("smtplib.SMTP", _DroppingSMTP)
        mailer = SmtpMailer(sender_email="s@gmail.com", sender_password="not-an-app-pw")
        res = mailer.send_email(to_email="d@example.com", subject="s", html_content="<p>x</p>")
        assert res["success"] is False
        assert "App Password" in res["error"]
        assert "đóng kết nối" in res["error"]

    def test_recipients_refused_reports_recipient_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import smtplib

        class _RefusingSMTP:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

            def __enter__(self) -> _RefusingSMTP:
                return self

            def __exit__(self, *exc: object) -> None:
                return None

            def starttls(self) -> None:
                return None

            def login(self, user: str, password: str) -> None:
                return None

            def send_message(self, msg: Any) -> None:
                raise smtplib.SMTPRecipientsRefused(
                    {"bad@example.com": (550, b"no such user")}
                )

        monkeypatch.setattr("smtplib.SMTP", _RefusingSMTP)
        mailer = SmtpMailer(sender_email="s@gmail.com", sender_password="pw")
        res = mailer.send_email(to_email="bad@example.com", subject="s", html_content="<p>x</p>")
        assert res["success"] is False
        assert "người nhận" in res["error"]


