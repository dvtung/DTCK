"""Smoke tests for the Streamlit dashboard script (T015c, T019).

``streamlit.testing.v1.AppTest`` executes ``apps/dashboard/app.py`` headlessly,
so a typo or bad API shape fails here instead of in the browser.  The API is
pointed at an unreachable host so the client uses its deterministic in-process
fallback — no infrastructure required.

T019 added the design system (``apps/dashboard/theme.py``): the assertions below
also pin the *visual contract* that must survive a redesign — the stylesheet is
injected, each page renders an SVG-icon hero (no emoji chrome), and the app bar
carries the live data-mode chip.
"""

from __future__ import annotations

import os

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")

PAGES = (
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
    assert app_test.sidebar.radio[0].value == "Tổng quan"
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
    assert any("Universe" in s.label for s in app_test.selectbox)


def test_overview_vnindex_timeframe_selector(app_test) -> None:  # type: ignore[no-untyped-def]
    """VNINDEX candlestick chart allows selecting multiple timeframes."""
    app_test.run()
    assert not app_test.exception, [str(e) for e in app_test.exception]
    tf_radios = [r for r in app_test.radio if r.key == "vnindex_timeframe"]
    assert tf_radios, "vnindex_timeframe radio selector not found"
    tf_radio = tf_radios[0]
    assert tf_radio.value == "2 năm"
    for tf in ("1 tuần", "1 tháng", "6 tháng", "1 năm", "Tất cả"):
        tf_radio.set_value(tf).run()
        assert not app_test.exception, f"Failed on {tf}: {[str(e) for e in app_test.exception]}"


# ---------------------------------------------------------------------------
# T019 — design system contract
# ---------------------------------------------------------------------------


def _markdown_dump(app_test) -> str:  # type: ignore[no-untyped-def]
    """All ``st.markdown`` bodies of the current run, joined for assertions."""
    return "\n".join(str(m.value) for m in app_test.markdown)


def test_design_system_stylesheet_is_injected(app_test) -> None:  # type: ignore[no-untyped-def]
    app_test.run()
    dump = _markdown_dump(app_test)
    assert "--dtck-brand" in dump  # token sheet, not the old inline CSS
    assert ".dtck-hero" in dump and ".dtck-appbar" in dump
    assert "prefers-reduced-motion" in dump  # a11y rule shipped with the theme


def test_overview_renders_svg_hero_and_live_data_chip(app_test) -> None:  # type: ignore[no-untyped-def]
    app_test.run()
    dump = _markdown_dump(app_test)
    assert 'class="dtck-hero__title">Tổng quan thị trường &amp; dự đoán VN30' in dump
    assert "Bảng điều khiển trung tâm" in dump
    assert "<svg" in dump  # icons are inline SVG, never emoji
    assert "dtck-chip--up" in dump or "dtck-chip--down" in dump  # data-mode chip


def test_every_page_renders_a_hero_and_no_emoji_chrome(app_test) -> None:  # type: ignore[no-untyped-def]
    """Every page shows a hero whose title matches the navigation label."""
    for name in PAGES:
        app_test.run()
        app_test.sidebar.radio[0].set_value(name).run()
        assert not app_test.exception, f"{name}: {[str(e) for e in app_test.exception]}"
        dump = _markdown_dump(app_test)
        assert 'class="dtck-hero"' in dump, name
        assert 'class="dtck-hero__icon"' in dump and "<svg" in dump, name
        for emoji in ("📈", "🏆", "🧪", "📧", "🩺", "📰"):
            assert emoji not in dump, f"{name} still renders emoji chrome {emoji}"


def test_footer_lists_runtime_dependencies(app_test) -> None:  # type: ignore[no-untyped-def]
    app_test.run()
    dump = _markdown_dump(app_test)
    assert "dtck-foot" in dump and "không đưa lời khuyên đầu tư" in dump
    assert "Nguồn dữ liệu" in dump


def test_email_page_offers_the_three_report_windows(app_test) -> None:  # type: ignore[no-untyped-def]
    """The schedule tab must expose 08:00 / 12:30 / 16:30 (morning, noon, afternoon)."""
    app_test.run()
    app_test.sidebar.radio[0].set_value("Quản lý Email").run()
    assert not app_test.exception, [str(e) for e in app_test.exception]

    labels = [slider.label for slider in app_test.slider]
    assert "Giờ gửi sáng" in labels
    assert "Giờ gửi trưa" in labels
    assert "Giờ gửi chiều" in labels
    minute_labels = [box.label for box in app_test.selectbox]
    assert {"Phút gửi sáng", "Phút gửi trưa", "Phút gửi chiều"} <= set(minute_labels)

    dump = _markdown_dump(app_test)
    assert "08:00" in dump and "12:30" in dump and "16:30" in dump
