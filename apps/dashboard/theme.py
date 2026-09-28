"""DTCK dashboard design system (T019) — tokens, CSS and HTML builders.

Visual contract for the Streamlit dashboard: a professional, data-dense
BI/finance surface (dark navy chrome + white cards + signal colours).

Design decisions (from the ``ui-ux-pro-max`` skill catalog):

* Style      : ``data-dense-dashboard`` (BI/Analytics) — KPI row, compact
               cards, 12–14 px data typography, tabular numerals.
* Palette    : ``Banking/Traditional Finance`` (trust navy + neutral greys)
               with semantic up/down/warn/info tokens instead of raw hex.
* Typography : ``Dashboard Data`` pairing — sans UI + tabular numerals
               (no remote webfont: the platform must work offline).
* A11y       : text contrast >= 4.5:1 (guarded by unit tests), visible
               ``:focus-visible`` rings, 44 px touch targets,
               ``prefers-reduced-motion`` honoured.

The module deliberately imports **nothing** from Streamlit/Plotly so the whole
visual contract is unit-testable without a browser:

* ``GLOBAL_CSS``      — one stylesheet, injected once by ``app.py``.
* ``PLOTLY_TEMPLATE`` — registered as the default Plotly template.
* ``page_header`` / ``app_bar`` / ``footer`` / ``chip`` — small HTML builders
  (all user text is escaped).
"""

from __future__ import annotations

from html import escape
from typing import Any, Final

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

#: Semantic colour tokens.  Every foreground/background pair used for text is
#: contrast-checked in ``tests/unit/test_dashboard_theme.py`` (WCAG AA, 4.5:1).
COLORS: Final[dict[str, str]] = {
    # Surfaces
    "bg": "#eef2f8",
    "surface": "#ffffff",
    "surface_2": "#f8fafc",
    "surface_3": "#f1f5f9",
    "line": "#e4e9f2",
    "line_2": "#cfd8e6",
    # Text
    "ink": "#0b1527",
    "ink_2": "#475569",
    "ink_3": "#64748b",
    # Brand
    "brand": "#1d4ed8",
    "brand_2": "#3b82f6",
    "brand_ink": "#1e3a8a",
    # Chrome (sidebar / app bar)
    "chrome": "#0b1527",
    "chrome_2": "#111c33",
    "chrome_ink": "#e6ecf5",
    "chrome_ink_2": "#9fb0c9",
    # Form fields.  Opaque on purpose: an alpha overlay would let Streamlit's own
    # (light *or* dark) theme paint through, which is exactly how "white text on
    # a white input" contrast bugs happen.  Both pairs are contrast-checked.
    "field": "#ffffff",
    "field_ink": "#0b1527",
    "placeholder": "#64748b",
    "field_dark": "#16233f",
    "field_ink_dark": "#f8fafc",
    "placeholder_dark": "#a9bbd4",
    "on_dark": "#ffffff",
    # Semantic (signals, alerts)
    "up": "#15803d",
    "up_soft": "#e7f6ec",
    "down": "#b91c1c",
    "down_soft": "#fdeeee",
    "warn": "#b45309",
    "warn_soft": "#fdf4e3",
    "info": "#0369a1",
    "info_soft": "#e8f3fb",
    "neutral": "#64748b",
}

#: No remote webfonts: offline/air-gapped safety beats brand flourish.
FONTS: Final[dict[str, str]] = {
    "sans": (
        '"Inter", "Fira Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", '
        'Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif'
    ),
    "mono": (
        '"Fira Code", "JetBrains Mono", "SFMono-Regular", Consolas, "Liberation Mono", monospace'
    ),
}

#: Categorical chart colourway (blue → cyan → amber → violet → green …).
CHART_COLORWAY: Final[tuple[str, ...]] = (
    "#1d4ed8",
    "#0e7490",
    "#b45309",
    "#7c3aed",
    "#15803d",
    "#b91c1c",
    "#64748b",
    "#0f766e",
)

#: Volume bars sit under the candlesticks — deliberately low emphasis.
CHART_VOLUME_COLOR: Final[str] = "rgba(100,116,139,0.42)"

#: Moving-average overlays.
CHART_MA20_COLOR: Final[str] = "#2563eb"
CHART_MA50_COLOR: Final[str] = "#b45309"

#: Raw signal enum → hex, so charts and tables never disagree.
SIGNAL_HEX: Final[dict[str, str]] = {
    "POSITIVE": COLORS["up"],
    "NEUTRAL": COLORS["neutral"],
    "NEGATIVE": COLORS["down"],
}


#: Plotly template, registered by ``app.py`` as the default.
PLOTLY_TEMPLATE: Final[dict[str, Any]] = {
    "layout": {
        "font": {"family": FONTS["sans"], "size": 12, "color": COLORS["ink_2"]},
        "title": {"font": {"size": 14, "color": COLORS["ink"]}, "x": 0.005, "xanchor": "left"},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "colorway": list(CHART_COLORWAY),
        "margin": {"l": 52, "r": 20, "t": 44, "b": 40},
        "hoverlabel": {
            "bgcolor": COLORS["chrome"],
            "bordercolor": COLORS["chrome"],
            "font": {"color": "#f8fafc", "size": 12, "family": FONTS["sans"]},
        },
        "hovermode": "x unified",
        "xaxis": {
            "gridcolor": COLORS["line"],
            "zeroline": False,
            "showline": True,
            "linecolor": COLORS["line_2"],
            "ticks": "outside",
            "ticklen": 4,
            "tickcolor": COLORS["line_2"],
            "automargin": True,
        },
        "yaxis": {
            "gridcolor": COLORS["line"],
            "zeroline": False,
            "showline": False,
            "ticks": "outside",
            "ticklen": 4,
            "tickcolor": COLORS["line_2"],
            "automargin": True,
        },
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "x": 0,
            "font": {"size": 11},
            "bgcolor": "rgba(255,255,255,0.7)",
            "bordercolor": COLORS["line"],
            "borderwidth": 1,
        },
        "modebar": {
            "bgcolor": "rgba(0,0,0,0)",
            "color": COLORS["ink_3"],
            "activecolor": COLORS["brand"],
        },
    }
}

#: Passed to ``st.plotly_chart(..., config=...)`` to remove mode-bar clutter.
PLOTLY_CONFIG: Final[dict[str, Any]] = {
    "displaylogo": False,
    "responsive": True,
    "scrollZoom": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d", "toggleSpikelines"],
}


def signal_hex(signal: str | None) -> str:
    """Return the chart colour for a raw signal enum (unknown → neutral)."""
    return SIGNAL_HEX.get(str(signal or "").upper(), COLORS["neutral"])


def chart_layout(height: int, **overrides: Any) -> dict[str, Any]:
    """Layout overrides for one figure, keeping sizing consistent."""
    layout: dict[str, Any] = {"height": height}
    layout.update(overrides)
    return layout


# ---------------------------------------------------------------------------
# Icon set (inline SVG — the skill's pre-delivery rule: never emoji as icons)
# ---------------------------------------------------------------------------

ICON_PATHS: Final[dict[str, str]] = {
    "grid": (
        '<rect x="3" y="3" width="7.5" height="7.5" rx="1.6"/>'
        '<rect x="13.5" y="3" width="7.5" height="7.5" rx="1.6"/>'
        '<rect x="3" y="13.5" width="7.5" height="7.5" rx="1.6"/>'
        '<rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.6"/>'
    ),
    "filter": '<path d="M3 5h18l-7 8.2V20l-4-2.2v-4.6z"/>',
    "trophy": '<circle cx="12" cy="9" r="5"/><path d="M9 13.6 7.6 21l4.4-2.2L16.4 21 15 13.6"/>',
    "compass": ('<circle cx="12" cy="12" r="9"/><path d="M15.6 8.4l-2.1 5.1-5.1 2.1 2.1-5.1z"/>'),
    "flask": (
        '<path d="M9 3h6"/><path d="M10 3v5.2l-4.8 9A2 2 0 0 0 6.9 20h10.2a2 2 0 0 0 1.7-2.8'
        'L14 8.2V3"/><path d="M7.6 15.2h8.8"/>'
    ),
    "news": (
        '<path d="M4 5h11.5v14H5.5A1.5 1.5 0 0 1 4 17.5z"/>'
        '<path d="M15.5 9H20v8a2 2 0 0 1-2 2h-2.5"/>'
        '<path d="M7 8.5h5.5M7 12h5.5M7 15.5h3.5"/>'
    ),
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3.6 6.8 12 13l8.4-6.2"/>',
    "pulse": '<path d="M3 12h3.8l2.2-5.4 3.4 11L15.2 12H21"/>',
    "check": '<path d="M20 6.5 9.2 17.3 4 12.1"/>',
    "alert": '<path d="M12 4.2 21 20H3z"/><path d="M12 10v4.2M12 17h.01"/>',
    "lock": (
        '<path d="M6.5 11V8.2a5.5 5.5 0 0 1 11 0V11"/>'
        '<rect x="4" y="11" width="16" height="9.5" rx="2"/>'
    ),
    "search": '<circle cx="11" cy="11" r="7"/><path d="M16.2 16.2 21 21"/>',
    "refresh": (
        '<path d="M20.5 12a8.5 8.5 0 0 1-14.5 6L4 16"/>'
        '<path d="M3.5 12a8.5 8.5 0 0 1 14.5-6L20 8"/>'
        '<path d="M20 3.5V8h-4.5"/><path d="M4 20.5V16h4.5"/>'
    ),
    "sparkle": (
        '<path d="M11.5 3.5l1.7 4.4 4.4 1.7-4.4 1.7-1.7 4.4L9.8 11.3 5.4 9.6l4.4-1.7z"/>'
        '<path d="M17.8 15.4l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"/>'
    ),
    "bars": (
        '<path d="M3 20.5h18"/>'
        '<rect x="5" y="11" width="4" height="7" rx="1.2"/>'
        '<rect x="10.5" y="6.5" width="4" height="11.5" rx="1.2"/>'
        '<rect x="16" y="14" width="4" height="4" rx="1.2"/>'
    ),
    "layers": (
        '<path d="M12 3.5 20 8l-8 4.5L4 8z"/>'
        '<path d="M4.5 12.5 12 16.7l7.5-4.2"/><path d="M4.5 16.6 12 20.8l7.5-4.2"/>'
    ),
    "file": (
        '<path d="M13.5 3.5H7A1.8 1.8 0 0 0 5.2 5.3v13.4A1.8 1.8 0 0 0 7 20.5h10'
        'a1.8 1.8 0 0 0 1.8-1.8V8.8z"/><path d="M13.5 3.5V9h5.3"/>'
    ),
    "database": (
        '<ellipse cx="12" cy="6" rx="8" ry="3"/>'
        '<path d="M4 6v6c0 1.66 3.58 3 8 3s8-1.34 8-3V6"/>'
        '<path d="M4 12v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6"/>'
    ),
    "shield": (
        '<path d="M12 3l7 3v6c0 4.4-3 7.6-7 9-4-1.4-7-4.6-7-9V6z"/>'
        '<path d="M9.4 12l1.9 1.9 3.4-3.7"/>'
    ),
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7.2V12l3.4 2"/>',
}


def svg_icon(name: str, size: int = 18, stroke_width: float = 1.7) -> str:
    """Inline SVG markup for ``name`` (unknown names return an empty string)."""
    paths = ICON_PATHS.get(name)
    if not paths:
        return ""
    return (
        f'<svg class="dtck-icon" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="currentColor" stroke-width="{stroke_width}" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" '
        f'focusable="false">{paths}</svg>'
    )


# ---------------------------------------------------------------------------
# HTML builders (pure functions — every piece of user text is escaped)
# ---------------------------------------------------------------------------

#: Chip/badge tones → CSS modifiers defined in ``GLOBAL_CSS``.
TONES: Final[tuple[str, ...]] = ("up", "down", "warn", "info", "brand", "neutral")


def chip(text: str, tone: str = "neutral", icon: str | None = None, mono: bool = False) -> str:
    """Return a status chip (pill) with an optional leading SVG icon."""
    tone_class = tone if tone in TONES else "neutral"
    icon_html = svg_icon(icon, size=13) if icon else ""
    mono_class = " dtck-chip--mono" if mono else ""
    return (
        f'<span class="dtck-chip dtck-chip--{tone_class}{mono_class}">'
        f"{icon_html}{escape(text)}</span>"
    )


def app_bar(
    product: str,
    tagline: str,
    version: str,
    chips: tuple[str, ...] = (),
) -> str:
    """Top application bar: brand mark, product name, tagline and status chips."""
    meta = "".join(chips)
    mark = svg_icon("bars", size=20, stroke_width=1.8)
    return (
        '<div class="dtck-appbar" role="banner">'
        '  <div class="dtck-appbar__brand">'
        f'    <span class="dtck-logo" aria-hidden="true">{mark}</span>'
        "    <div>"
        f'      <div class="dtck-appbar__title">{escape(product)}</div>'
        f'      <div class="dtck-appbar__sub">{escape(tagline)}</div>'
        "    </div>"
        "  </div>"
        '  <div class="dtck-appbar__meta">'
        f'    <span class="dtck-chip dtck-chip--onDark dtck-chip--mono">v{escape(version)}</span>'
        f"    {meta}"
        "  </div>"
        "</div>"
    )


def page_header(
    title: str,
    subtitle: str = "",
    icon: str = "grid",
    eyebrow: str = "",
    meta: tuple[str, ...] = (),
) -> str:
    """Page hero: icon chip, eyebrow, title, subtitle and right-aligned meta."""
    icon_html = svg_icon(icon, size=20)
    eyebrow_html = f'<div class="dtck-hero__eyebrow">{escape(eyebrow)}</div>' if eyebrow else ""
    subtitle_html = f'<div class="dtck-hero__sub">{escape(subtitle)}</div>' if subtitle else ""
    meta_html = "".join(meta)
    meta_block = f'<div class="dtck-hero__meta">{meta_html}</div>' if meta else ""
    return (
        '<div class="dtck-hero">'
        f'  <span class="dtck-hero__icon" aria-hidden="true">{icon_html}</span>'
        "  <div>"
        f"    {eyebrow_html}"
        f'    <div class="dtck-hero__title">{escape(title)}</div>'
        f"    {subtitle_html}"
        "  </div>"
        f"  {meta_block}"
        "</div>"
    )


def section_label(text: str, tone: str = "neutral", icon: str | None = None) -> str:
    """Inline section/column label (replaces decorative emoji headings)."""
    tone_class = tone if tone in TONES else "neutral"
    icon_html = f"{svg_icon(icon, size=14)} " if icon else ""
    return f'<div class="dtck-label dtck-label--{tone_class}">{icon_html}{escape(text)}</div>'


def side_card(title: str, value: str, tone: str = "", mono: bool = False) -> str:
    """Compact key/value card used inside the control sidebar."""
    tone_class = f" dtck-sidecard--{tone}" if tone in TONES else ""
    mono_class = " dtck-sidecard__v--mono" if mono else ""
    return (
        f'<div class="dtck-sidecard{tone_class}">'
        f'  <div class="dtck-sidecard__t">{escape(title)}</div>'
        f'  <div class="dtck-sidecard__v{mono_class}">{escape(value)}</div>'
        "</div>"
    )


def brand_html(product: str, product_sub: str, tagline: str) -> str:
    """Sidebar brand block (mark + name + tagline)."""
    mark = svg_icon("bars", size=18, stroke_width=1.9)
    return (
        '<div class="dtck-brand">'
        f'  <span class="dtck-logo dtck-logo--sm" aria-hidden="true">{mark}</span>'
        "  <div>"
        f'    <div class="dtck-brand__name">{escape(product)} '
        f'<span class="dtck-brand__badge">{escape(product_sub)}</span></div>'
        f'    <div class="dtck-brand__sub">{escape(tagline)}</div>'
        "  </div>"
        "</div>"
    )


def nav_title(text: str) -> str:
    """Small uppercase caption above a sidebar group."""
    return f'<div class="dtck-navtitle">{escape(text)}</div>'


def footer(items: tuple[tuple[str, str], ...], disclaimer: str) -> str:
    """Structured footer: key/value chips plus the mandatory §3 disclaimer."""
    chips = "".join(
        f'<span class="dtck-chip dtck-chip--neutral"><strong>{escape(k)}</strong>'
        f'<span class="dtck-chip__mono">{escape(v)}</span></span>'
        for k, v in items
    )
    return (
        '<div class="dtck-foot">'
        f'  <div class="dtck-foot__row" role="contentinfo">{chips}</div>'
        f'  <div class="dtck-foot__note">{escape(disclaimer)}</div>'
        "</div>"
    )


# ---------------------------------------------------------------------------
# Stylesheet (injected once by ``app.py`` via ``st.markdown``)
# ---------------------------------------------------------------------------

GLOBAL_CSS: Final[str] = """
/* ===== Tokens ========================================================== */
:root {
  --dtck-bg: #eef2f8;
  --dtck-surface: #ffffff;
  --dtck-surface-2: #f8fafc;
  --dtck-surface-3: #f1f5f9;
  --dtck-line: #e4e9f2;
  --dtck-line-2: #cfd8e6;
  --dtck-ink: #0b1527;
  --dtck-ink-2: #475569;
  --dtck-ink-3: #64748b;
  --dtck-brand: #1d4ed8;
  --dtck-brand-2: #3b82f6;
  --dtck-brand-ink: #1e3a8a;
  --dtck-chrome: #0b1527;
  --dtck-chrome-2: #111c33;
  --dtck-chrome-ink: #e6ecf5;
  --dtck-chrome-ink-2: #9fb0c9;
  --dtck-up: #15803d;     --dtck-up-soft: #e7f6ec;
  --dtck-down: #b91c1c;   --dtck-down-soft: #fdeeee;
  --dtck-warn: #b45309;   --dtck-warn-soft: #fdf4e3;
  --dtck-info: #0369a1;   --dtck-info-soft: #e8f3fb;
  --dtck-neutral: #64748b;
  --dtck-field: #ffffff;
  --dtck-field-ink: #0b1527;
  --dtck-placeholder: #64748b;
  --dtck-field-dark: #16233f;
  --dtck-field-ink-dark: #f8fafc;
  --dtck-placeholder-dark: #a9bbd4;
  --dtck-on-dark: #ffffff;
  --dtck-font: "Inter", "Fira Sans", -apple-system, BlinkMacSystemFont, "Segoe UI",
    Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif;
  --dtck-mono: "Fira Code", "JetBrains Mono", "SFMono-Regular", Consolas,
    "Liberation Mono", monospace;
  --dtck-radius-sm: 8px;
  --dtck-radius: 12px;
  --dtck-radius-lg: 16px;
  --dtck-shadow-1: 0 1px 2px rgba(11,21,39,.06);
  --dtck-shadow-2: 0 2px 6px rgba(11,21,39,.06), 0 10px 26px -14px rgba(11,21,39,.22);
  --dtck-ring: 0 0 0 3px rgba(59,130,246,.28);
  --dtck-content: 1440px;
  --dtck-tap: 44px;
  --dtck-dur: 170ms;
  /* The design system ships one light surface (dark chrome painted on top), so
     native widgets — scrollbars, checkboxes, dropdown popovers, the date picker
     — must not follow a host dark theme and render unreadable. */
  color-scheme: light;
}

/* ===== Base =========================================================== */
.stApp { background: var(--dtck-bg); font-family: var(--dtck-font); }
[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(1150px 460px at 8% -14%, rgba(29,78,216,.10), transparent 62%),
    radial-gradient(880px 420px at 102% -6%, rgba(14,116,144,.08), transparent 58%),
    var(--dtck-bg);
}
[data-testid="stAppViewContainer"] > .main { background: transparent; }
header[data-testid="stHeader"] { background: transparent; }
[data-testid="stAppDeployButton"] { display: none; }
.block-container { max-width: var(--dtck-content); padding: 1.15rem 1.75rem 3rem; }
h1, h2, h3, h4, h5 { font-family: var(--dtck-font); color: var(--dtck-ink); }
h1 { font-size: 1.55rem; font-weight: 700; letter-spacing: -.018em; margin: .1rem 0 .3rem; }
h2 { font-size: 1.16rem; font-weight: 700; letter-spacing: -.012em; margin: .2rem 0 .15rem; }
h3 { font-size: .98rem; font-weight: 650; letter-spacing: -.008em; }
p, li, span, label, .stMarkdown { font-family: var(--dtck-font); }
p, li { color: var(--dtck-ink-2); }
a { color: var(--dtck-brand); text-decoration: none; }
a:hover { text-decoration: underline; }
code, pre, kbd, samp { font-family: var(--dtck-mono); font-size: .84em; }
[data-testid="stCaptionContainer"] p, .stCaption, small {
  color: var(--dtck-ink-3) !important; font-size: .78rem; line-height: 1.5;
}
hr, [data-testid="stDivider"] { border-color: var(--dtck-line); opacity: 1; margin: 1.05rem 0; }
[data-testid="stWidgetLabel"] p {
  color: var(--dtck-ink-2) !important; font-size: .8rem !important; font-weight: 600;
}

/* ===== Sidebar (chrome) =============================================== */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, var(--dtck-chrome) 0%, var(--dtck-chrome-2) 100%);
  border-right: 1px solid rgba(148,163,184,.16);
}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding: 1rem .85rem 2rem; }
section[data-testid="stSidebar"] * { color: var(--dtck-chrome-ink); }
section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { color: #ffffff; }
section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] small,
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
  color: var(--dtck-chrome-ink-2) !important;
}
section[data-testid="stSidebar"] hr, section[data-testid="stSidebar"] [data-testid="stDivider"] {
  border-color: rgba(148,163,184,.20);
}
section[data-testid="stSidebar"] [data-baseweb="input"],
section[data-testid="stSidebar"] [data-baseweb="input"] > div,
section[data-testid="stSidebar"] [data-baseweb="base-input"],
section[data-testid="stSidebar"] [data-baseweb="select"] > div,
section[data-testid="stSidebar"] input, section[data-testid="stSidebar"] textarea {
  background: var(--dtck-field-dark) !important;
  border-color: rgba(148,163,184,.34) !important;
  border-radius: var(--dtck-radius-sm) !important;
  color: var(--dtck-field-ink-dark) !important;
}
section[data-testid="stSidebar"] input::placeholder,
section[data-testid="stSidebar"] textarea::placeholder {
  color: var(--dtck-placeholder-dark) !important; opacity: 1;
}
/* The generic sidebar `*`/`p` colour rules above would otherwise leak into
   widget internals: a white button with #9fb0c9 label text is ~2.2:1.  Reset
   the label colour to the button's own foreground. */
section[data-testid="stSidebar"] .stButton > button,
section[data-testid="stSidebar"] .stDownloadButton > button,
section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] > button {
  color: var(--dtck-ink) !important;
  background: var(--dtck-field) !important;
  border-color: var(--dtck-line-2) !important;
}
section[data-testid="stSidebar"] .stButton > button *,
section[data-testid="stSidebar"] .stDownloadButton > button *,
section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] > button * {
  color: inherit !important;
}
section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"],
section[data-testid="stSidebar"] [data-testid="stBaseButton-primaryFormSubmit"] {
  background: linear-gradient(180deg, #2563eb, #1d4ed8) !important;
  color: var(--dtck-on-dark) !important;
  border-color: #1d4ed8 !important;
}
section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] *,
section[data-testid="stSidebar"] [data-testid="stBaseButton-primaryFormSubmit"] * {
  color: var(--dtck-on-dark) !important;
}
section[data-testid="stSidebar"] [role="radiogroup"] > label > div:first-child,
section[data-testid="stSidebar"] [data-testid="stCheckbox"] input[type="checkbox"] {
  background-color: var(--dtck-field-dark);
  border-color: rgba(148,163,184,.45);
}
section[data-testid="stSidebar"] [data-testid="stForm"] {
  background: rgba(255,255,255,.04); border: 1px solid rgba(148,163,184,.20);
  border-radius: var(--dtck-radius); box-shadow: none; padding: .85rem .8rem .35rem;
}
section[data-testid="stSidebar"] [role="radiogroup"] {
  display: flex; flex-direction: column; gap: 3px;
}
section[data-testid="stSidebar"] [role="radiogroup"] > label {
  display: flex; align-items: center; min-height: var(--dtck-tap);
  padding: 6px 12px; margin: 0; border-radius: 10px; cursor: pointer;
  border: 1px solid transparent;
  transition: background var(--dtck-dur) ease, border-color var(--dtck-dur) ease;
}
section[data-testid="stSidebar"] [role="radiogroup"] > label:hover {
  background: rgba(96,165,250,.14); border-color: rgba(96,165,250,.30);
}
section[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) {
  background: linear-gradient(90deg, rgba(59,130,246,.26), rgba(59,130,246,.05));
  border-color: rgba(96,165,250,.45);
  box-shadow: inset 3px 0 0 0 var(--dtck-brand-2);
}
section[data-testid="stSidebar"] [role="radiogroup"] > label p {
  font-size: .86rem !important; font-weight: 550;
}
section[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) p {
  color: #ffffff !important; font-weight: 650;
}

/* ===== Cards: KPI metrics ============================================= */
[data-testid="stMetric"] {
  position: relative; overflow: hidden;
  background: var(--dtck-surface); border: 1px solid var(--dtck-line);
  border-radius: var(--dtck-radius); padding: 13px 16px 11px;
  box-shadow: var(--dtck-shadow-1);
  transition: box-shadow var(--dtck-dur) ease, transform var(--dtck-dur) ease,
    border-color var(--dtck-dur) ease;
}
[data-testid="stMetric"]::before {
  content: ""; position: absolute; inset: 0 auto 0 0; width: 3px;
  background: linear-gradient(180deg, var(--dtck-brand), var(--dtck-brand-2));
}
[data-testid="stMetric"]:hover {
  box-shadow: var(--dtck-shadow-2); transform: translateY(-1px);
  border-color: var(--dtck-line-2);
}
[data-testid="stMetricLabel"] p {
  color: var(--dtck-ink-3) !important; font-size: .72rem !important;
  font-weight: 700 !important; text-transform: uppercase; letter-spacing: .07em;
}
[data-testid="stMetricValue"] {
  font-family: var(--dtck-font); font-size: 1.34rem; font-weight: 650;
  font-variant-numeric: tabular-nums; color: var(--dtck-ink); letter-spacing: -.01em;
}
[data-testid="stMetricDelta"] {
  font-size: .78rem !important; font-weight: 600; font-variant-numeric: tabular-nums;
}
[data-testid="stMetricDelta"] svg { width: .75rem; height: .75rem; }

/* ===== Cards: data / chart / form surfaces ============================ */
[data-testid="stDataFrame"] {
  border: 1px solid var(--dtck-line); border-radius: var(--dtck-radius);
  overflow: hidden; background: var(--dtck-surface); box-shadow: var(--dtck-shadow-1);
  /* glide-data-grid paints into a canvas and reads these variables, so a
     Streamlit dark theme would otherwise render light text on our white card. */
  --gdg-accent-color: var(--dtck-brand);
  --gdg-accent-light-color: rgba(29,78,216,.12);
  --gdg-text-dark: var(--dtck-ink);
  --gdg-text-medium: var(--dtck-ink-2);
  --gdg-text-light: var(--dtck-ink-3);
  --gdg-text-bubble: var(--dtck-ink);
  --gdg-bg-cell: var(--dtck-surface);
  --gdg-bg-cell-medium: var(--dtck-surface-2);
  --gdg-bg-header: var(--dtck-surface-2);
  --gdg-bg-header-hovered: var(--dtck-surface-3);
  --gdg-bg-bubble: var(--dtck-surface);
  --gdg-border-color: var(--dtck-line);
  --gdg-horizontal-border-color: var(--dtck-line);
  --gdg-drilldown-border: var(--dtck-line-2);
}
[data-testid="stDataFrame"] [role="columnheader"] {
  font-weight: 700 !important; text-transform: uppercase; letter-spacing: .04em;
}
[data-testid="stPlotlyChart"] {
  background: var(--dtck-surface); border: 1px solid var(--dtck-line);
  border-radius: var(--dtck-radius); padding: .4rem .5rem .15rem;
  box-shadow: var(--dtck-shadow-1);
}
[data-testid="stForm"] {
  background: var(--dtck-surface); border: 1px solid var(--dtck-line);
  border-radius: var(--dtck-radius-lg); padding: 1.05rem 1.15rem .45rem;
  box-shadow: var(--dtck-shadow-1);
}
[data-testid="stExpander"] {
  background: var(--dtck-surface); border: 1px solid var(--dtck-line) !important;
  border-radius: var(--dtck-radius); box-shadow: var(--dtck-shadow-1); overflow: hidden;
}
[data-testid="stExpander"] summary { font-weight: 600; color: var(--dtck-ink); }
[data-testid="stExpander"] summary:hover { background: var(--dtck-surface-3); }
[data-testid="stJson"], [data-testid="stCode"], pre {
  background: var(--dtck-surface-2) !important; border: 1px solid var(--dtck-line);
  border-radius: var(--dtck-radius-sm);
}

/* ===== Tabs =========================================================== */
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--dtck-line); }
.stTabs [data-baseweb="tab"] {
  height: auto; padding: 8px 14px; border-radius: 10px 10px 0 0;
  font-weight: 600; font-size: .86rem; color: var(--dtck-ink-2);
  transition: background var(--dtck-dur) ease, color var(--dtck-dur) ease;
}
.stTabs [data-baseweb="tab"]:hover { background: var(--dtck-surface-3); }
.stTabs [aria-selected="true"] {
  color: var(--dtck-brand) !important; background: rgba(29,78,216,.08);
}
.stTabs [data-baseweb="tab-highlight"] { background-color: var(--dtck-brand); height: 2px; }
.stTabs [data-baseweb="tab-border"] { background: transparent; }


/* ===== Controls: buttons, inputs, sliders ============================= */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
  border-radius: 10px; font-weight: 600; font-size: .85rem; min-height: 40px;
  border: 1px solid var(--dtck-line-2); background: var(--dtck-field);
  color: var(--dtck-ink); cursor: pointer;
  transition: transform var(--dtck-dur) ease, box-shadow var(--dtck-dur) ease,
    background var(--dtck-dur) ease, border-color var(--dtck-dur) ease;
}
/* Button captions live in a child <p>; without this reset a host theme (or the
   sidebar scope) can colour the label independently of the button surface. */
.stButton > button *, .stDownloadButton > button *,
[data-testid="stFormSubmitButton"] > button * { color: inherit !important; }
.stButton > button:hover, .stDownloadButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {
  transform: translateY(-1px); box-shadow: var(--dtck-shadow-2);
  border-color: var(--dtck-brand-2); color: var(--dtck-brand-ink);
}
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
  background: linear-gradient(180deg, #2563eb, #1d4ed8) !important;
  border-color: #1d4ed8 !important; color: var(--dtck-on-dark) !important;
  box-shadow: 0 1px 2px rgba(29,78,216,.30);
}
[data-testid="stBaseButton-primary"] *, [data-testid="stBaseButton-primaryFormSubmit"] * {
  color: var(--dtck-on-dark) !important;
}
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stBaseButton-primaryFormSubmit"]:hover {
  background: linear-gradient(180deg, #1d4ed8, #1e40af) !important;
  color: var(--dtck-on-dark) !important;
}
/* Fields: opaque surface + explicit ink so the pair can never invert when the
   viewer runs Streamlit's dark theme. */
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input, [data-baseweb="select"] > div,
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"] textarea {
  border-radius: var(--dtck-radius-sm); border-color: var(--dtck-line-2);
  background: var(--dtck-field) !important; color: var(--dtck-field-ink) !important;
}
[data-testid="stTextInput"] input::placeholder, [data-testid="stNumberInput"] input::placeholder,
[data-baseweb="textarea"] textarea::placeholder {
  color: var(--dtck-placeholder) !important; opacity: 1;
}
[data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus {
  border-color: var(--dtck-brand-2); box-shadow: var(--dtck-ring);
}
[data-testid="stSelectbox"] [data-baseweb="select"] svg,
[data-testid="stMultiSelect"] [data-baseweb="select"] svg { fill: var(--dtck-ink-2); color: var(--dtck-ink-2); }
/* Dropdown menus render in a portal *outside* the sidebar/form scope, so they
   need their own explicit light surface + dark ink. */
[data-baseweb="popover"] [role="listbox"], [data-baseweb="popover"] [role="menu"] {
  background: var(--dtck-field) !important; border: 1px solid var(--dtck-line-2);
  box-shadow: var(--dtck-shadow-2); border-radius: var(--dtck-radius-sm);
}
[data-baseweb="popover"] [role="option"], [data-baseweb="popover"] [role="menuitem"] {
  color: var(--dtck-field-ink) !important;
}
[data-baseweb="popover"] [role="option"]:hover, [data-baseweb="popover"] [role="menuitem"]:hover,
[data-baseweb="popover"] [aria-selected="true"] {
  background-color: var(--dtck-surface-3) !important; color: var(--dtck-brand-ink) !important;
}
[data-baseweb="popover"] [role="option"] * , [data-baseweb="popover"] [role="menuitem"] * {
  color: inherit !important;
}
[data-testid="stTooltipContent"], [data-baseweb="tooltip"] {
  background: var(--dtck-chrome) !important; color: var(--dtck-on-dark) !important;
}
[data-testid="stTooltipContent"] *, [data-baseweb="tooltip"] * {
  color: var(--dtck-on-dark) !important;
}
[data-baseweb="tag"] {
  background: rgba(29,78,216,.10) !important; color: var(--dtck-brand-ink) !important;
  border-radius: 6px !important;
}
[data-baseweb="tag"] span, [data-baseweb="tag"] svg { color: var(--dtck-brand-ink) !important; }
[data-testid="stProgress"] > div > div > div {
  background: linear-gradient(90deg, var(--dtck-brand), #0ea5e9);
}
[data-testid="stProgress"] > div > div { background: var(--dtck-surface-3); }

/* ===== Alerts ========================================================= */
[data-testid="stAlert"] {
  border-radius: var(--dtck-radius); border: 1px solid var(--dtck-line);
  box-shadow: var(--dtck-shadow-1);
}
[data-testid="stAlert"] [data-baseweb="notification"] { border-radius: var(--dtck-radius); }
[data-baseweb="notification"][kind="info"] {
  background: var(--dtck-info-soft); border-left: 3px solid var(--dtck-info);
}
[data-baseweb="notification"][kind="positive"] {
  background: var(--dtck-up-soft); border-left: 3px solid var(--dtck-up);
}
[data-baseweb="notification"][kind="warning"] {
  background: var(--dtck-warn-soft); border-left: 3px solid var(--dtck-warn);
}
[data-baseweb="notification"][kind="negative"] {
  background: var(--dtck-down-soft); border-left: 3px solid var(--dtck-down);
}

/* ===== Scrollbars ===================================================== */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: rgba(100,116,139,.35); border-radius: 999px;
  border: 2px solid transparent; background-clip: content-box;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(71,85,105,.55); background-clip: content-box;
}



/* ===== DTCK components ================================================ */
.dtck-icon { flex: 0 0 auto; display: inline-block; vertical-align: -0.15em; }

.dtck-appbar {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  flex-wrap: wrap; padding: 14px 18px; margin: 0 0 14px;
  border: 1px solid rgba(255,255,255,.10); border-radius: var(--dtck-radius-lg);
  background: linear-gradient(120deg, #0b1527 0%, #16264a 58%, #1d4ed8 100%);
  box-shadow: var(--dtck-shadow-2);
}
.dtck-appbar__brand { display: flex; align-items: center; gap: 12px; }
.dtck-appbar__title { color: #ffffff; font-size: 1.04rem; font-weight: 700; letter-spacing: -.012em; }
.dtck-appbar__sub { color: #bacae3; font-size: .78rem; margin-top: 1px; }
.dtck-appbar__meta { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.dtck-logo {
  display: inline-flex; align-items: center; justify-content: center;
  width: 38px; height: 38px; border-radius: 11px; color: #04121f;
  background: linear-gradient(135deg, #60a5fa, #22d3ee);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.45);
}
.dtck-logo--sm { width: 32px; height: 32px; border-radius: 9px; }

.dtck-hero {
  display: flex; align-items: flex-start; gap: 14px;
  padding: 14px 18px; margin: 2px 0 16px;
  background: var(--dtck-surface); border: 1px solid var(--dtck-line);
  border-left: 4px solid var(--dtck-brand); border-radius: var(--dtck-radius-lg);
  box-shadow: var(--dtck-shadow-1);
}
.dtck-hero__icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 36px; height: 36px; border-radius: 10px; color: var(--dtck-brand);
  background: rgba(29,78,216,.10); border: 1px solid rgba(29,78,216,.18);
}
.dtck-hero__eyebrow {
  color: var(--dtck-ink-3); font-size: .68rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: .1em;
}
.dtck-hero__title {
  color: var(--dtck-ink); font-size: 1.24rem; font-weight: 700;
  letter-spacing: -.016em; margin: .1rem 0 .18rem;
}
.dtck-hero__sub { color: var(--dtck-ink-2); font-size: .82rem; line-height: 1.5; max-width: 96ch; }
.dtck-hero__meta { margin-left: auto; display: flex; gap: 6px; flex-wrap: wrap; }

.dtck-chip {
  display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px;
  border-radius: 999px; border: 1px solid var(--dtck-line-2);
  background: var(--dtck-surface-3); color: var(--dtck-ink-2);
  font-size: .71rem; font-weight: 600; letter-spacing: .01em; white-space: nowrap;
}
.dtck-chip--mono, .dtck-chip__mono { font-family: var(--dtck-mono); }
.dtck-chip--up { background: var(--dtck-up-soft); border-color: rgba(21,128,61,.28); color: #14532d; }
.dtck-chip--down { background: var(--dtck-down-soft); border-color: rgba(185,28,28,.28); color: #7f1d1d; }
.dtck-chip--warn { background: var(--dtck-warn-soft); border-color: rgba(180,83,9,.28); color: #7c2d12; }
.dtck-chip--info { background: var(--dtck-info-soft); border-color: rgba(3,105,161,.28); color: #0c4a6e; }
.dtck-chip--brand { background: rgba(29,78,216,.10); border-color: rgba(29,78,216,.26); color: var(--dtck-brand-ink); }
.dtck-chip--onDark {
  background: rgba(255,255,255,.12); border-color: rgba(255,255,255,.22); color: #eaf1fd;
}

.dtck-label { font-size: .86rem; font-weight: 700; letter-spacing: -.005em; }
.dtck-label--neutral { color: var(--dtck-ink); }
.dtck-label--up { color: var(--dtck-up); }
.dtck-label--down { color: var(--dtck-down); }
.dtck-label--warn { color: var(--dtck-warn); }
.dtck-label--brand { color: var(--dtck-brand); }

.dtck-brand { display: flex; align-items: center; gap: 10px; padding: 2px 2px 10px; }
.dtck-brand__name { color: #ffffff; font-size: .98rem; font-weight: 700; letter-spacing: -.01em; }
.dtck-brand__badge {
  display: inline-block; margin-left: 4px; padding: 1px 7px; border-radius: 999px;
  background: rgba(96,165,250,.22); color: #cfe0ff; font-size: .62rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: .08em; vertical-align: middle;
}
.dtck-brand__sub { color: var(--dtck-chrome-ink-2); font-size: .7rem; margin-top: 1px; }
.dtck-navtitle {
  color: #7d90ad; font-size: .66rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: .11em; margin: 4px 0 6px;
}
.dtck-sidecard {
  padding: 9px 11px; margin: 6px 0; border-radius: var(--dtck-radius);
  background: rgba(255,255,255,.05); border: 1px solid rgba(148,163,184,.22);
  border-left: 3px solid rgba(148,163,184,.5);
}
.dtck-sidecard--up { border-left-color: var(--dtck-up); background: rgba(21,128,61,.16); }
.dtck-sidecard--down { border-left-color: var(--dtck-down); background: rgba(185,28,28,.16); }
.dtck-sidecard--brand { border-left-color: var(--dtck-brand-2); background: rgba(37,99,235,.16); }
.dtck-sidecard__t {
  color: var(--dtck-chrome-ink-2); font-size: .66rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: .09em;
}
.dtck-sidecard__v { color: #eef3fb; font-size: .8rem; margin-top: 2px; word-break: break-word; }
.dtck-sidecard__v--mono { font-family: var(--dtck-mono); font-size: .74rem; }

.dtck-foot { margin-top: 28px; padding-top: 14px; border-top: 1px solid var(--dtck-line); }
.dtck-foot__row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.dtck-foot__note { margin-top: 8px; color: var(--dtck-ink-3); font-size: .76rem; line-height: 1.5; }

/* ===== Accessibility & motion ========================================= */
:where(a, button, input, select, textarea, summary, [role="radio"], [role="tab"], [tabindex]):focus-visible {
  outline: 2px solid var(--dtck-brand-2); outline-offset: 2px;
  box-shadow: var(--dtck-ring); border-radius: var(--dtck-radius-sm);
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    transition-duration: .001ms !important; animation-duration: .001ms !important;
    scroll-behavior: auto !important;
  }
  [data-testid="stMetric"]:hover, .stButton > button:hover { transform: none; }
}

/* ===== Responsive ===================================================== */
@media (max-width: 1100px) {
  .block-container { padding: 1rem 1rem 2.5rem; }
  [data-testid="stMetricValue"] { font-size: 1.18rem; }
  .dtck-hero__title { font-size: 1.1rem; }
}
@media (max-width: 768px) {
  .dtck-appbar { padding: 12px 14px; }
  .dtck-appbar__meta { width: 100%; }
  .dtck-hero { flex-wrap: wrap; padding: 12px 14px; }
  .dtck-hero__meta { margin-left: 0; width: 100%; }
}
"""


def inject_css() -> str:
    """Return the ``<style>`` block for ``st.markdown(..., unsafe_allow_html=True)``."""
    return f"<style>{GLOBAL_CSS}</style>"


__all__ = [
    "CHART_COLORWAY",
    "CHART_MA20_COLOR",
    "CHART_MA50_COLOR",
    "CHART_VOLUME_COLOR",
    "COLORS",
    "FONTS",
    "GLOBAL_CSS",
    "ICON_PATHS",
    "PLOTLY_CONFIG",
    "PLOTLY_TEMPLATE",
    "SIGNAL_HEX",
    "TONES",
    "app_bar",
    "brand_html",
    "chart_layout",
    "chip",
    "footer",
    "inject_css",
    "nav_title",
    "page_header",
    "section_label",
    "side_card",
    "signal_hex",
    "svg_icon",
]
