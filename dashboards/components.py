"""
components.py
═════════════
Reusable UI building blocks — KPI metric cards, section headers, styled tables.
Industry-grade dashboard components inspired by Google Analytics / Datadog / Mixpanel.

NOTE: All HTML must be compact (no blank lines between tags) because
Streamlit's markdown parser interprets blank lines as paragraph breaks
and will render inner HTML as text.
"""

import pandas as pd
import streamlit as st

from config import PALETTE


# ════════════════════════════════════════════════════════════════════
# KPI METRIC CARD
# ════════════════════════════════════════════════════════════════════

def kpi_card(label: str, value, delta=None, delta_color="normal",
             accent_color=None):
    """
    Render a clean KPI metric card with a solid accent left border,
    dashed border on other sides, and large typography.
    """
    border_color = accent_color or PALETTE["primary"]

    # Delta badge
    delta_html = ""
    if delta is not None:
        if delta_color == "normal":
            badge_bg = PALETTE["delta_up_bg"]
            badge_fg = PALETTE["delta_up"]
            arrow = "▲"
        else:
            badge_bg = PALETTE["delta_down_bg"]
            badge_fg = PALETTE["delta_down"]
            arrow = "▼"
        delta_html = (
            f'<span style="display:inline-flex;align-items:center;gap:3px;'
            f'background:{badge_bg};color:{badge_fg};'
            f'padding:2px 8px;border-radius:100px;'
            f'font-size:0.7rem;font-weight:600;white-space:nowrap;'
            f'">{arrow} {delta}</span>'
        )

    # Build compact HTML (NO blank lines between tags!)
    card_style = (
        f"background:{PALETTE['card_bg']};"
        f"border-radius:10px;"
        f"padding:1.15rem 1.35rem;"
        f"border:1px dashed {PALETTE['card_border']};"
        f"border-left:3px solid {border_color};"
        f"box-shadow:0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);"
        f"min-height:110px;"
        f"display:flex;flex-direction:column;justify-content:center;"
    )
    label_style = (
        f"color:{PALETTE['text_muted']};"
        f"font-size:0.7rem;"
        f"font-weight:600;"
        f"text-transform:uppercase;"
        f"letter-spacing:0.6px;"
    )
    value_style = (
        f"font-size:1.65rem;"
        f"font-weight:800;"
        f"color:{PALETTE['text']};"
        f"line-height:1.15;"
        f"letter-spacing:-0.5px;"
    )

    html = (
        f'<div style="{card_style}">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.4rem;">'
        f'<span style="{label_style}">{label}</span>'
        f'{delta_html}'
        f'</div>'
        f'<div style="{value_style}">{value}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
# SECTION HEADER
# ════════════════════════════════════════════════════════════════════

def section_header(title: str, subtitle: str = ""):
    """Render a section title with a thin underline divider."""
    sub_html = ""
    if subtitle:
        sub_html = (
            f'<p style="color:{PALETTE["text_muted"]};margin:0.2rem 0 0;'
            f'font-size:0.82rem;font-weight:400;">{subtitle}</p>'
        )

    header_style = (
        f"margin:2rem 0 1rem;"
        f"padding-bottom:0.65rem;"
        f"border-bottom:2px solid {PALETTE['divider']};"
    )
    title_style = (
        f"margin:0;"
        f"color:{PALETTE['text']};"
        f"font-size:1.15rem;"
        f"font-weight:700;"
        f"letter-spacing:-0.3px;"
    )

    html = (
        f'<div style="{header_style}">'
        f'<h2 style="{title_style}">{title}</h2>'
        f'{sub_html}'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
# STYLED DATAFRAME (Table)
# ════════════════════════════════════════════════════════════════════

def styled_dataframe(df: pd.DataFrame, height: int = 400):
    """Display a dataframe with clean styling."""
    st.dataframe(
        df.style.format(precision=3),
        use_container_width=True,
        height=height,
    )


# ════════════════════════════════════════════════════════════════════
# PERSONA HEADER BANNER
# ════════════════════════════════════════════════════════════════════

def persona_header(title: str, subtitle: str, accent_color: str):
    """Render a persona-specific header banner with a gradient accent strip."""

    # Map personas to icons
    icon_map = {
        "Marketing":  "📊",
        "Support":    "🎧",
        "Customer":   "🎧",
        "Product":    "🧱",
        "Simulation": "🧪",
    }
    icon = "📈"
    for key, emoji in icon_map.items():
        if key.lower() in title.lower():
            icon = emoji
            break

    outer_style = (
        f"background:{PALETTE['card_bg']};"
        f"border-radius:12px;"
        f"border:1px solid {PALETTE['card_border']};"
        f"box-shadow:0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);"
        f"overflow:hidden;"
        f"margin-bottom:1.5rem;"
    )
    strip_style = (
        f"height:4px;"
        f"background:linear-gradient(90deg,{accent_color},{accent_color}88);"
    )
    content_style = (
        f"padding:1.25rem 1.75rem;"
        f"display:flex;align-items:center;gap:1rem;"
    )
    icon_style = (
        f"width:44px;height:44px;"
        f"background:{accent_color}12;"
        f"border-radius:10px;"
        f"display:flex;align-items:center;justify-content:center;"
        f"font-size:1.35rem;"
        f"border:1px solid {accent_color}25;"
    )
    title_style = (
        f"margin:0;"
        f"font-size:1.35rem;"
        f"font-weight:800;"
        f"color:{PALETTE['text']};"
        f"letter-spacing:-0.5px;"
    )
    sub_style = (
        f"color:{PALETTE['text_muted']};"
        f"margin:0.15rem 0 0;"
        f"font-size:0.82rem;"
        f"font-weight:400;"
    )

    html = (
        f'<div style="{outer_style}">'
        f'<div style="{strip_style}"></div>'
        f'<div style="{content_style}">'
        f'<div style="{icon_style}">{icon}</div>'
        f'<div>'
        f'<h1 style="{title_style}">{title}</h1>'
        f'<p style="{sub_style}">{subtitle}</p>'
        f'</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
# CHART CONTAINER WRAPPER
# ════════════════════════════════════════════════════════════════════

def chart_card_start(title: str = ""):
    """Open a clean white container for a plotly chart."""
    title_html = ""
    if title:
        title_html = (
            f'<div style="padding:0.9rem 1.2rem 0;font-size:0.85rem;font-weight:700;'
            f'color:{PALETTE["text"]};letter-spacing:-0.2px;">{title}</div>'
        )
    card_style = (
        f"background:{PALETTE['card_bg']};"
        f"border-radius:10px;"
        f"border:1px solid {PALETTE['card_border']};"
        f"box-shadow:0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);"
        f"overflow:hidden;margin-bottom:0.5rem;"
    )
    st.markdown(f'<div style="{card_style}">{title_html}', unsafe_allow_html=True)


def chart_card_end():
    """Close the chart container."""
    st.markdown("</div>", unsafe_allow_html=True)
