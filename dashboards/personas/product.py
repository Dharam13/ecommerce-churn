"""
personas/product.py
═══════════════════
Persona 3 — Product Team
Goal: Understand product usage and engagement.
"""

import pandas as pd
import streamlit as st
import plotly.express as px

from config import PALETTE, CHART_COLORS, PLOTLY_TEMPLATE
from components import kpi_card, section_header, persona_header


def _chart_layout(fig, title="", height=380):
    """Apply standard professional chart layout."""
    fig.update_layout(
        margin=dict(t=45, b=25, l=25, r=25),
        height=height,
        font=dict(family="Inter, sans-serif", size=12, color=PALETTE["text_secondary"]),
        title=dict(
            text=title,
            font=dict(size=14, color=PALETTE["text"], family="Inter"),
            x=0.02, y=0.97,
        ) if title else {},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor="#F3F4F6", zerolinecolor="#E5E7EB"),
        yaxis=dict(gridcolor="#F3F4F6", zerolinecolor="#E5E7EB"),
    )
    return fig


def render_product_dashboard(df: pd.DataFrame):
    """Render the Product Team persona view."""

    persona_header(
        title="Product Team Dashboard",
        subtitle="Understand product usage, engagement & device preferences",
        accent_color=PALETTE["accent"],
    )

    # ── KPIs ─────────────────────────────────────────────────
    avg_app = (
        df["hourspendonapp"].mean()
        if "hourspendonapp" in df.columns
        else 0
    )
    avg_devices = (
        df["numberofdeviceregistered"].mean()
        if "numberofdeviceregistered" in df.columns
        else 0
    )
    top_login = (
        df["preferredlogindevice"].mode().iloc[0]
        if len(df) and "preferredlogindevice" in df.columns
        else "—"
    )
    top_cat = (
        df["preferedordercat"].mode().iloc[0]
        if len(df) and "preferedordercat" in df.columns
        else "—"
    )

    cols = st.columns(4)
    with cols[0]:
        kpi_card("Avg. App Usage (hrs)", f"{avg_app:.1f}",
                 accent_color=PALETTE["info"])
    with cols[1]:
        kpi_card("Avg. Devices", f"{avg_devices:.1f}",
                 accent_color=PALETTE["primary"])
    with cols[2]:
        kpi_card("Top Login Device", top_login,
                 accent_color=PALETTE["accent"])
    with cols[3]:
        kpi_card("Top Category", top_cat,
                 accent_color=PALETTE["warning"])

    section_header("Charts", "Product engagement & usage patterns")

    # ── Row 1 ────────────────────────────────────────────────
    c1, c2 = st.columns(2)

    with c1:
        if "preferredlogindevice" in df.columns:
            login_df = df["preferredlogindevice"].value_counts().reset_index()
            login_df.columns = ["device", "count"]
            fig = px.pie(
                login_df, names="device", values="count",
                hole=0.52,
                template=PLOTLY_TEMPLATE,
                color_discrete_sequence=CHART_COLORS,
            )
            fig.update_traces(
                textinfo="percent+label", textfont_size=11,
                marker=dict(line=dict(color="#FFFFFF", width=2)),
            )
            fig = _chart_layout(fig, title="Login Device Distribution", height=380)
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        if "numberofdeviceregistered" in df.columns:
            dev_churn = (
                df.groupby("numberofdeviceregistered")["churn"]
                .mean()
                .reset_index()
                .rename(columns={"churn": "churn_rate"})
            )
            fig = px.bar(
                dev_churn, x="numberofdeviceregistered", y="churn_rate",
                template=PLOTLY_TEMPLATE,
                color_discrete_sequence=[PALETTE["primary"]],
            )
            fig = _chart_layout(fig, title="Devices Registered vs Churn Rate", height=380)
            fig.update_layout(
                xaxis_title="Devices Registered", yaxis_title="Churn Rate",
            )
            fig.update_traces(marker_cornerradius=6)
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 2 ────────────────────────────────────────────────
    c3, c4 = st.columns(2)

    with c3:
        if "hourspendonapp" in df.columns:
            fig = px.histogram(
                df, x="hourspendonapp", nbins=25,
                template=PLOTLY_TEMPLATE,
                color_discrete_sequence=[PALETTE["info"]],
            )
            fig = _chart_layout(fig, title="Hours Spent on App", height=380)
            fig.update_layout(
                xaxis_title="Hours", yaxis_title="Count",
                bargap=0.05,
            )
            fig.update_traces(marker_cornerradius=4)
            st.plotly_chart(fig, use_container_width=True)

    with c4:
        if "preferedordercat" in df.columns:
            cat_df = df["preferedordercat"].value_counts().reset_index()
            cat_df.columns = ["category", "count"]
            fig = px.bar(
                cat_df, x="category", y="count",
                template=PLOTLY_TEMPLATE,
                color_discrete_sequence=[PALETTE["accent"]],
            )
            fig = _chart_layout(fig, title="Category Preference", height=380)
            fig.update_layout(xaxis_title="", yaxis_title="Count")
            fig.update_traces(marker_cornerradius=6)
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 3 ────────────────────────────────────────────────
    if "preferredpaymentmode" in df.columns:
        pay_df = df["preferredpaymentmode"].value_counts().reset_index()
        pay_df.columns = ["mode", "count"]
        fig = px.pie(
            pay_df, names="mode", values="count",
            hole=0.52,
            template=PLOTLY_TEMPLATE,
            color_discrete_sequence=CHART_COLORS,
        )
        fig.update_traces(
            textinfo="percent+label", textfont_size=11,
            marker=dict(line=dict(color="#FFFFFF", width=2)),
        )
        fig = _chart_layout(fig, title="Payment Mode Distribution", height=400)
        st.plotly_chart(fig, use_container_width=True)
