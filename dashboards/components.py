"""
components.py
═════════════
Reusable UI building blocks — KPI cards, section headers, styled tables.
"""

import pandas as pd
import streamlit as st

from config import PALETTE


def kpi_card(label: str, value, delta=None, delta_color="normal", icon="📊"):
    """Render a single KPI inside a styled container."""
    delta_html = ""
    if delta is not None:
        color = "#00D084" if delta_color == "normal" else "#FF4D6A"
        arrow = "▲" if delta_color == "normal" else "▼"
        delta_html = (
            f'<span style="color:{color};font-size:0.85rem;">{arrow} {delta}</span>'
        )

    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {PALETTE['card_bg']} 0%, #22252E 100%);
        border-radius: 16px;
        padding: 1.4rem 1.6rem;
        border: 1px solid rgba(108,99,255,0.18);
        box-shadow: 0 4px 24px rgba(0,0,0,0.25);
        text-align: center;
    ">
        <div style="font-size:1.6rem;margin-bottom:0.3rem;">{icon}</div>
        <div style="color:#9CA3AF;font-size:0.8rem;text-transform:uppercase;letter-spacing:1.5px;">
            {label}
        </div>
        <div style="font-size:2rem;font-weight:700;color:{PALETTE['text']};margin:0.3rem 0;">
            {value}
        </div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def section_header(title: str, subtitle: str = ""):
    """Render a styled section heading with optional subtitle."""
    st.markdown(f"""
    <div style="margin:2rem 0 1rem;">
        <h2 style="margin:0;color:{PALETTE['text']};">{title}</h2>
        <p style="color:#9CA3AF;margin:0.2rem 0 0;">{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


def styled_dataframe(df: pd.DataFrame, height: int = 400):
    """Display a dataframe with highlight styling."""
    st.dataframe(
        df.style.format(precision=3),
        use_container_width=True,
        height=height,
    )
