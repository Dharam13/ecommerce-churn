"""
components.py
═════════════
Reusable UI building blocks — KPI cards, section headers, styled tables.
"""

import pandas as pd
import streamlit as st

from config import PALETTE


def kpi_card(label: str, value, delta=None, delta_color="normal",
             accent_color=None):
    """
    Render a clean KPI card with a subtle accent stripe on the left.
    """
    border_color = accent_color or PALETTE["primary"]

    delta_html = ""
    if delta is not None:
        color = PALETTE["accent"] if delta_color == "normal" else PALETTE["secondary"]
        arrow = "▲" if delta_color == "normal" else "▼"
        delta_html = (
            f'<span style="color:{color};font-size:0.8rem;font-weight:500;">'
            f'{arrow} {delta}</span>'
        )

    st.markdown(f"""
    <div style="
        background: {PALETTE['card_bg']};
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        border: 1px solid {PALETTE['card_border']};
        border-left: 4px solid {border_color};
        box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06);
    ">
        <div style="
            color:{PALETTE['text_muted']};
            font-size:0.72rem;
            font-weight:600;
            text-transform:uppercase;
            letter-spacing:0.8px;
            margin-bottom:0.5rem;
        ">{label}</div>
        <div style="
            font-size:1.75rem;
            font-weight:700;
            color:{PALETTE['text']};
            line-height:1.2;
        ">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def section_header(title: str, subtitle: str = ""):
    """Render a clean section heading with optional subtitle."""
    st.markdown(f"""
    <div style="margin:2.5rem 0 1rem;padding-bottom:0.75rem;border-bottom:1px solid {PALETTE['divider']};">
        <h2 style="
            margin:0;
            color:{PALETTE['text']};
            font-size:1.3rem;
            font-weight:700;
            letter-spacing:-0.3px;
        ">{title}</h2>
        <p style="
            color:{PALETTE['text_muted']};
            margin:0.25rem 0 0;
            font-size:0.85rem;
        ">{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


def styled_dataframe(df: pd.DataFrame, height: int = 400):
    """Display a dataframe with clean styling."""
    st.dataframe(
        df.style.format(precision=3),
        use_container_width=True,
        height=height,
    )


def persona_header(title: str, subtitle: str, accent_color: str):
    """Render a clean persona header banner."""
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {accent_color}08 0%, {accent_color}15 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        border: 1px solid {accent_color}25;
        margin-bottom: 1.5rem;
    ">
        <h1 style="
            margin:0;
            font-size:1.6rem;
            font-weight:700;
            color:{PALETTE['text']};
            letter-spacing:-0.5px;
        ">{title}</h1>
        <p style="
            color:{PALETTE['text_muted']};
            margin:0.2rem 0 0;
            font-size:0.9rem;
        ">{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)
