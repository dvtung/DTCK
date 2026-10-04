"""Unit tests for automated email reports (T018): generator, mailer, service, API.

Everything runs offline: SMTP is monkeypatched, and the service is exercised
against the in-memory market fixture — no Gmail credentials are needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from apps.api.services.market_data import MarketService
from apps.dashboard.components import format_price
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
            ranked=[{"symbol": "FPT", "rank": 1, "price": 132000, "overall_score": 85.0}],
        )
        assert "VNINDEX" in html
        assert "+12.00 điểm" in html
        assert "Giá hiện tại" in html
        assert format_price(132000) in html

    def test_empty_data_still_renders_honestly(self) -> None:
        """No data must produce placeholders, never invented numbers."""
        html = generate_market_overview_html(
            indices=[], breadth={}, regime={}, ranked=[], movers=None
        )
        assert "Chưa có dữ liệu" in html
        assert "—" in html

    def test_renders_strategy_rankings_and_explanations(self) -> None:
        strat_rankings = {
            "short": [
                {
                    "symbol": "FPT",
                    "price": 131500,
                    "overall_score": 85.5,
                    "grade": "A",
                    "buy_zone_low": 130000,
                    "buy_zone_high": 133000,
                    "stop_loss": 125000,
                    "target_price": 142000,
                    "confidence": 0.88,
                }
            ],
            "mid": [
                {
                    "symbol": "HDB",
                    "overall_score": 79.2,
                    "grade": "B",
                    "buy_zone_low": 28000,
                    "buy_zone_high": 28500,
                    "stop_loss": 27000,
                    "target_price": 31000,
                    "confidence": 0.75,
                }
            ],
            "long": [
                {
                    "symbol": "VNM",
                    "overall_score": 68.0,
                    "grade": "C",
                    "buy_zone_low": 65000,
                    "buy_zone_high": 66500,
                    "stop_loss": 62000,
                    "target_price": 72000,
                    "confidence": 0.90,
                }
            ],
        }
        html = generate_market_overview_html(
            indices=[],
            breadth={},
            regime={},
            ranked=[],
            strategy_rankings=strat_rankings,
        )
        assert "Chấm Điểm & Gợi Ý 3 Chiến Lược" in html
        assert "Chiến lược Ngắn hạn" in html
        assert "Chiến lược Trung hạn" in html
        assert "Chiến lược Dài hạn" in html
        assert "FPT" in html
        assert "HDB" in html
        assert "VNM" in html
        assert "85.5" in html
        assert "Vùng mua (thấp – cao)" in html
        assert "Cắt lỗ" in html
        assert "Mục tiêu" in html
        assert "Độ tin cậy" in html
        assert "Giải thích các thông tin cơ bản" in html
        assert "Hạng A" in html
        assert "Stop Loss" in html
        assert format_price(131500) in html


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


