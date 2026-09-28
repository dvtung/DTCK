"""Unit tests for the dashboard design system (apps/dashboard/theme.py).

Validates tokens, contrast ratios, CSS injection, HTML builders, Plotly template,
and SVG icon mappings independently of browser rendering.
"""

from __future__ import annotations

from apps.dashboard import theme


class TestThemeTokens:
    def test_colors_dict_has_required_keys(self) -> None:
        required = {"brand", "up", "down", "warn", "info", "neutral", "surface", "ink"}
        assert required.issubset(theme.COLORS.keys())

    def test_signal_colors_distinguishable(self) -> None:
        assert theme.COLORS["up"] != theme.COLORS["down"]
        assert theme.COLORS["up"] != theme.COLORS["neutral"]

    def test_signal_hex_lookup(self) -> None:
        assert theme.signal_hex("POSITIVE") == theme.COLORS["up"]
        assert theme.signal_hex("NEGATIVE") == theme.COLORS["down"]
        assert theme.signal_hex("NEUTRAL") == theme.COLORS["neutral"]
        assert theme.signal_hex("UNKNOWN") == theme.COLORS["neutral"]
        assert theme.signal_hex(None) == theme.COLORS["neutral"]


class TestSvgIcons:
    def test_registered_icons_render_svg_markup(self) -> None:
        for name in ("grid", "filter", "trophy", "compass", "flask", "news", "mail", "pulse"):
            svg = theme.svg_icon(name)
            assert svg.startswith("<svg") and svg.endswith("</svg>")
            assert 'class="dtck-icon"' in svg
            assert 'aria-hidden="true"' in svg

    def test_unknown_icon_returns_empty_string(self) -> None:
        assert theme.svg_icon("nonexistent_icon_xyz") == ""

    def test_custom_size_and_stroke(self) -> None:
        svg = theme.svg_icon("grid", size=24, stroke_width=2.0)
        assert 'width="24"' in svg
        assert 'height="24"' in svg
        assert 'stroke-width="2.0"' in svg


class TestHtmlBuilders:
    def test_page_header_contains_title_and_eyebrow(self) -> None:
        html = theme.page_header(
            title="Tổng quan thị trường",
            subtitle="Mô tả kiểm thử",
            icon="grid",
            eyebrow="Bảng điều khiển",
        )
        assert "Tổng quan thị trường" in html
        assert "Mô tả kiểm thử" in html
        assert "Bảng điều khiển" in html
        assert 'class="dtck-hero"' in html
        assert 'class="dtck-hero__icon"' in html
        assert "<svg" in html

    def test_page_header_escapes_unsafe_characters(self) -> None:
        html = theme.page_header(
            title="<script>alert(1)</script>",
            subtitle="A & B",
            eyebrow="<b>Tag</b>",
        )
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
        assert "A &amp; B" in html
        assert "&lt;b&gt;Tag&lt;/b&gt;" in html

    def test_chip_builder(self) -> None:
        chip = theme.chip("Tích cực", "up", icon="check")
        assert 'class="dtck-chip dtck-chip--up"' in chip
        assert "Tích cực" in chip
        assert "<svg" in chip

    def test_brand_html(self) -> None:
        brand = theme.brand_html("DTCK", "v1.2.3", "Phân tích định lượng")
        assert "DTCK" in brand
        assert "v1.2.3" in brand
        assert "Phân tích định lượng" in brand
        assert 'class="dtck-brand"' in brand
        assert "<svg" in brand

    def test_side_card(self) -> None:
        card = theme.side_card("Chế độ đọc", "DỮ LIỆU THẬT", tone="up", mono=True)
        assert "dtck-sidecard--up" in card
        assert "dtck-sidecard__v--mono" in card
        assert "Chế độ đọc" in card
        assert "DỮ LIỆU THẬT" in card

    def test_section_label(self) -> None:
        label = theme.section_label("Top 10 tăng", tone="up", icon="check")
        assert 'class="dtck-label dtck-label--up"' in label
        assert "Top 10 tăng" in label
        assert "<svg" in label

    def test_app_bar(self) -> None:
        bar = theme.app_bar("DTCK", "Hệ thống hỗ trợ đầu tư", "0.1.0", (theme.chip("Prod", "up"),))
        assert 'class="dtck-appbar"' in bar
        assert "DTCK" in bar
        assert "Hệ thống hỗ trợ đầu tư" in bar
        assert "v0.1.0" in bar

    def test_footer(self) -> None:
        foot = theme.footer(
            items=(("Nguồn", "Vietcap"), ("CSDL", "TimescaleDB")),
            disclaimer="Không phải lời khuyên tài chính.",
        )
        assert 'class="dtck-foot"' in foot
        assert "Vietcap" in foot
        assert "TimescaleDB" in foot
        assert "Không phải lời khuyên tài chính." in foot


class TestPlotlyIntegration:
    def test_chart_layout_helper(self) -> None:
        layout = theme.chart_layout(450, title="Biểu đồ thử nghiệm", showlegend=False)
        assert layout["height"] == 450
        assert layout["title"] == "Biểu đồ thử nghiệm"
        assert layout["showlegend"] is False

    def test_plotly_template_registered(self) -> None:
        import plotly.graph_objects as go
        import plotly.io as pio

        pio.templates["dtck"] = go.layout.Template(theme.PLOTLY_TEMPLATE)
        pio.templates.default = "dtck"
        assert "dtck" in pio.templates
        assert pio.templates.default == "dtck"
        assert theme.PLOTLY_TEMPLATE["layout"]["paper_bgcolor"] == "rgba(0,0,0,0)"


class TestContrast:
    """WCAG 2.x relative-luminance checks on the token pairs the sheet relies on.

    The CSS cannot be screenshotted in CI, so the pairs that were *observed* to
    break (form fields and button captions inside the dark sidebar, plus the
    dropdown popovers) are pinned here as numbers instead.
    """

    @staticmethod
    def _luminance(hex_color: str) -> float:
        raw = hex_color.lstrip("#")
        assert len(raw) == 6, f"expected a 6-digit hex colour, got {hex_color!r}"
        channels = []
        for offset in (0, 2, 4):
            value = int(raw[offset : offset + 2], 16) / 255
            channels.append(
                value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
            )
        red, green, blue = channels
        return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)

    def contrast(self, foreground: str, background: str) -> float:
        first = self._luminance(foreground)
        second = self._luminance(background)
        lighter, darker = max(first, second), min(first, second)
        return (lighter + 0.05) / (darker + 0.05)

    def test_helper_matches_known_ratios(self) -> None:
        assert round(self.contrast("#000000", "#ffffff"), 1) == 21.0
        assert round(self.contrast("#ffffff", "#ffffff"), 1) == 1.0

    def test_annotated_text_pairs_meet_wcag_aa(self) -> None:
        pairs = (
            ("ink", "surface"),
            ("ink_2", "surface"),
            ("ink_3", "surface"),
            ("ink", "bg"),
            ("ink_2", "bg"),
            ("surface", "ink"),
            ("on_dark", "chrome"),
            ("chrome_ink", "chrome"),
            ("chrome_ink_2", "chrome"),
            ("field_ink", "field"),
            ("field_ink_dark", "field_dark"),
            ("placeholder", "field"),
            ("placeholder_dark", "field_dark"),
            ("up", "surface"),
            ("down", "surface"),
        )
        for foreground, background in pairs:
            ratio = self.contrast(theme.COLORS[foreground], theme.COLORS[background])
            assert ratio >= 4.5, f"{foreground} on {background} is only {ratio:.2f}:1"

    def test_status_chip_tones_meet_wcag_aa(self) -> None:
        # Chip backgrounds are the opaque soft tokens declared in ``COLORS``.
        chips = (
            ("up", "up_soft", "#14532d"),
            ("down", "down_soft", "#7f1d1d"),
            ("warn", "warn_soft", "#7c2d12"),
            ("info", "info_soft", "#0c4a6e"),
        )
        for _tone, background, ink in chips:
            ratio = self.contrast(ink, theme.COLORS[background])
            assert ratio >= 4.5, f"{ink} on {background} is only {ratio:.2f}:1"


class TestCssContrastContract:
    """The rules that fix the reported light/dark theme defects must ship."""

    def test_sidebar_fields_paint_an_opaque_surface(self) -> None:
        css = theme.GLOBAL_CSS
        assert "background: var(--dtck-field-dark) !important;" in css
        assert "color: var(--dtck-field-ink-dark) !important;" in css
        # Alpha overlays are what let the host theme bleed through.
        assert "background: rgba(255,255,255,.06) !important" not in css

    def test_button_captions_inherit_the_button_colour(self) -> None:
        css = theme.GLOBAL_CSS
        for scope in (
            'section[data-testid="stSidebar"] .stButton > button *',
            "stBaseButton-primary",
        ):
            assert scope in css
        assert "color: inherit !important;" in css

    def test_dropdowns_and_tooltips_have_explicit_surfaces(self) -> None:
        css = theme.GLOBAL_CSS
        assert '[data-baseweb="popover"] [role="option"]' in css
        assert '[data-baseweb="tooltip"]' in css

    def test_native_widgets_are_pinned_to_light(self) -> None:
        assert "color-scheme: light;" in theme.GLOBAL_CSS

    def test_dataframe_canvas_variables_are_pinned(self) -> None:
        css = theme.GLOBAL_CSS
        assert "--gdg-text-dark:" in css
        assert "--gdg-bg-cell:" in css


class TestCssInjection:
    def test_global_css_contains_design_tokens(self) -> None:
        css = theme.GLOBAL_CSS
        assert "--dtck-bg:" in css
        assert "--dtck-brand:" in css
        assert "--dtck-up:" in css
        assert "--dtck-down:" in css
        assert ".dtck-hero" in css
        assert ".dtck-appbar" in css
        assert "@media (prefers-reduced-motion: reduce)" in css
