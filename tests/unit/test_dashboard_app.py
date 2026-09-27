"""Smoke tests for the Streamlit dashboard script (T015c).

``streamlit.testing.v1.AppTest`` executes ``apps/dashboard/app.py`` headlessly,
so a typo or bad API shape fails here instead of in the browser.  The API is
pointed at an unreachable host so the client uses its deterministic in-process
fallback — no infrastructure required.
"""

from __future__ import annotations

import os

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")

PAGES = (
    "📈 Tổng quan",
    "🔍 Bộ lọc",
    "🏆 Xếp hạng",
    "🧭 Chi tiết mã",
    "🧪 Backtest",
    "📰 Tin tức & RAG",
    "🩺 Sức khỏe",
)


@pytest.fixture()
def app_test(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    # Unreachable API → deterministic fixture fallback inside the client.
    monkeypatch.setenv("API_HOST", "http://127.0.0.1:9")
    app_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "apps",
        "dashboard",
        "app.py",
    )
    return streamlit_testing.AppTest.from_file(app_file, default_timeout=30)


def test_dashboard_boots_without_exception(app_test) -> None:  # type: ignore[no-untyped-def]
    app_test.run()
    assert not app_test.exception, [str(e) for e in app_test.exception]


def test_every_navigation_page_renders(app_test) -> None:  # type: ignore[no-untyped-def]
    """Each sidebar entry must render without raising."""
    for name in PAGES:
        app_test.run()
        app_test.sidebar.radio[0].set_value(name).run()
        assert not app_test.exception, f"{name}: {[str(e) for e in app_test.exception]}"


def test_market_overview_exposes_decision_table(app_test) -> None:  # type: ignore[no-untyped-def]
    app_test.run()
    assert app_test.sidebar.radio[0].value == "📈 Tổng quan"
    headers = [h.value for h in app_test.subheader]
    assert any("Đánh giá & dự đoán" in h for h in headers)
    assert app_test.metric  # KPI row present


def test_sidebar_shows_login_form_when_logged_out(app_test) -> None:  # type: ignore[no-untyped-def]
    """T016: an unauthenticated sidebar renders the email/password login form."""
    app_test.run()
    assert not app_test.exception, [str(e) for e in app_test.exception]
    labels = [f.label for f in app_test.sidebar.text_input]
    assert "Email" in labels
    assert "Mật khẩu" in labels
    assert any(b.label == "Đăng nhập" for b in app_test.sidebar.button)


def test_overview_renders_index_chart_and_movers_sections(app_test) -> None:  # type: ignore[no-untyped-def]
    """T016: Overview has the VNINDEX candlestick and MA20/MA50 movers blocks."""
    app_test.run()
    assert not app_test.exception, [str(e) for e in app_test.exception]
    headers = [h.value for h in app_test.subheader]
    assert any("VNINDEX" in h for h in headers)
    assert any("MA20" in h for h in headers)
    # Universe selector for the gainers/decliners tables.
    assert any(
        "Universe" in s.label for s in app_test.selectbox
    )
