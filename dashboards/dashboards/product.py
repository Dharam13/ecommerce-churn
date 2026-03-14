"""
dashboards/product.py
═════════════════════
Persona 3 — Product Team
Goal: Understand product usage and engagement.
"""

import pandas as pd
import streamlit as st
import plotly.express as px

from config import PALETTE, PLOTLY_TEMPLATE
from components import kpi_card, section_header


def render_product_dashboard(df: pd.DataFrame):
    """Render the Product Team persona view."""

    # ── Header ───────────────────────────────────────────────
    st.markdown(f"""
    <div style="
        background: linear-gradient(90deg, rgba(0,208,132,0.25), transparent);
        padding: 1.2rem 1.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
    ">
        <h1 style="margin:0;font-size:1.8rem;">🧪  Product Team Dashboard</h1>
        <p style="color:#9CA3AF;margin:0.3rem 0 0;">
            Understand product usage, engagement &amp; device preferences
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── KPIs ─────────────────────────────────────────────────
    avg_app = df["hour_spend_on_app"].mean()
    avg_devices = df["number_of_device_registered"].mean()
    top_login = df["preferred_login_device"].mode().iloc[0] if len(df) else "—"
    top_cat = df["prefered_order_cat"].mode().iloc[0] if len(df) else "—"

    cols = st.columns(4)
    with cols[0]:
        kpi_card("Avg. App Usage (hrs)", f"{avg_app:.1f}", icon="📱")
    with cols[1]:
        kpi_card("Avg. Devices", f"{avg_devices:.1f}", icon="💻")
    with cols[2]:
        kpi_card("Top Login Device", top_login, icon="🔑")
    with cols[3]:
        kpi_card("Top Category", top_cat, icon="📦")

    section_header("📊  Charts", "Product engagement & usage patterns")

    # ── Chart Row 1 ──────────────────────────────────────────
    c1, c2 = st.columns(2)

    with c1:
        login_df = df["preferred_login_device"].value_counts().reset_index()
        login_df.columns = ["device", "count"]
        fig = px.pie(
            login_df, names="device", values="count",
            title="Login Device Distribution",
            hole=0.45,
            template=PLOTLY_TEMPLATE,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_traces(textinfo="percent+label")
        fig.update_layout(margin=dict(t=50, b=20, l=20, r=20), height=380)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        dev_churn = (
            df.groupby("number_of_device_registered")["churn"]
            .mean()
            .reset_index()
            .rename(columns={"churn": "churn_rate"})
        )
        fig = px.bar(
            dev_churn, x="number_of_device_registered", y="churn_rate",
            title="Devices Registered vs Churn Rate",
            template=PLOTLY_TEMPLATE,
            color_discrete_sequence=[PALETTE["primary"]],
        )
        fig.update_layout(
            margin=dict(t=50, b=20, l=20, r=20), height=380,
            xaxis_title="Devices Registered", yaxis_title="Churn Rate",
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Chart Row 2 ──────────────────────────────────────────
    c3, c4 = st.columns(2)

    with c3:
        fig = px.histogram(
            df, x="hour_spend_on_app", nbins=25,
            title="Hours Spent on App",
            template=PLOTLY_TEMPLATE,
            color_discrete_sequence=[PALETTE["info"]],
        )
        fig.update_layout(
            margin=dict(t=50, b=20, l=20, r=20), height=380,
            xaxis_title="Hours", yaxis_title="Count",
            bargap=0.05,
        )
        st.plotly_chart(fig, use_container_width=True)

    with c4:
        cat_df = df["prefered_order_cat"].value_counts().reset_index()
        cat_df.columns = ["category", "count"]
        fig = px.bar(
            cat_df, x="category", y="count",
            title="Category Preference",
            template=PLOTLY_TEMPLATE,
            color_discrete_sequence=[PALETTE["accent"]],
        )
        fig.update_layout(
            margin=dict(t=50, b=20, l=20, r=20), height=380,
            xaxis_title="", yaxis_title="Count",
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Chart Row 3: Payment Mode Pie ────────────────────────
    pay_df = df["preferred_payment_mode"].value_counts().reset_index()
    pay_df.columns = ["mode", "count"]
    fig = px.pie(
        pay_df, names="mode", values="count",
        title="Payment Mode Distribution",
        hole=0.45,
        template=PLOTLY_TEMPLATE,
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    fig.update_traces(textinfo="percent+label")
    fig.update_layout(margin=dict(t=50, b=20, l=20, r=20), height=400)
    st.plotly_chart(fig, use_container_width=True)
