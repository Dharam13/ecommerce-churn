"""
personas/support.py
═══════════════════
Persona 2 — Customer Success / Support
Goal: Monitor complaints and satisfaction.

Uses:
  Gold fact:  complain, churn
  Silver:     satisfactionscore, daysincelastorder
"""

import pandas as pd
import streamlit as st
import plotly.express as px

from config import PALETTE, PLOTLY_TEMPLATE
from components import kpi_card, section_header, styled_dataframe


def render_support_dashboard(df: pd.DataFrame):
    """Render the Customer Success / Support persona view."""

    # ── Header ───────────────────────────────────────────────
    st.markdown(f"""
    <div style="
        background: linear-gradient(90deg, rgba(255,101,132,0.25), transparent);
        padding: 1.2rem 1.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
    ">
        <h1 style="margin:0;font-size:1.8rem;">🛟  Customer Success / Support</h1>
        <p style="color:#9CA3AF;margin:0.3rem 0 0;">
            Monitor complaints, satisfaction &amp; customer inactivity
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── KPIs ─────────────────────────────────────────────────
    total = len(df)
    complaint_count = df["complain"].sum()
    complaint_rate = complaint_count / total * 100 if total else 0
    avg_sat = df["satisfactionscore"].mean() if "satisfactionscore" in df.columns else 0
    inactive = (
        (df["daysincelastorder"] > 30).sum()
        if "daysincelastorder" in df.columns
        else 0
    )

    cols = st.columns(4)
    with cols[0]:
        kpi_card("Complaint Rate", f"{complaint_rate:.1f}%", icon="📢")
    with cols[1]:
        kpi_card("Avg. Satisfaction", f"{avg_sat:.2f} / 5", icon="⭐")
    with cols[2]:
        kpi_card("Complaint Customers", f"{complaint_count:,}", icon="😤")
    with cols[3]:
        kpi_card("Inactive (>30 days)", f"{inactive:,}", icon="💤")

    section_header("📊  Charts", "Complaint & satisfaction analysis")

    # ── Row 1 ────────────────────────────────────────────────
    c1, c2 = st.columns(2)

    with c1:
        complaint_churn = (
            df.groupby("complain")["churn"]
            .mean()
            .reset_index()
            .rename(columns={"churn": "churn_rate"})
        )
        complaint_churn["complain_label"] = complaint_churn["complain"].map(
            {0: "No Complaint", 1: "Complaint"}
        )
        fig = px.bar(
            complaint_churn, x="complain_label", y="churn_rate",
            color="complain_label",
            color_discrete_map={
                "No Complaint": PALETTE["accent"],
                "Complaint": PALETTE["secondary"],
            },
            title="Complaints vs Churn Rate",
            template=PLOTLY_TEMPLATE,
        )
        fig.update_layout(
            margin=dict(t=50, b=20, l=20, r=20), height=380,
            showlegend=False,
            xaxis_title="", yaxis_title="Churn Rate",
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        if "satisfactionscore" in df.columns:
            fig = px.histogram(
                df, x="satisfactionscore", nbins=5,
                title="Satisfaction Score Distribution",
                template=PLOTLY_TEMPLATE,
                color_discrete_sequence=[PALETTE["info"]],
            )
            fig.update_layout(
                margin=dict(t=50, b=20, l=20, r=20), height=380,
                xaxis_title="Satisfaction Score", yaxis_title="Count",
                bargap=0.1,
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Row 2 ────────────────────────────────────────────────
    c3, c4 = st.columns(2)

    with c3:
        if "satisfactionscore" in df.columns:
            box_df = df.copy()
            box_df["churn_label"] = box_df["churn"].map({0: "Retained", 1: "Churned"})
            fig = px.box(
                box_df, x="churn_label", y="satisfactionscore",
                color="churn_label",
                color_discrete_map={
                    "Retained": PALETTE["accent"],
                    "Churned": PALETTE["secondary"],
                },
                title="Satisfaction vs Churn",
                template=PLOTLY_TEMPLATE,
            )
            fig.update_layout(
                margin=dict(t=50, b=20, l=20, r=20), height=380,
                showlegend=False,
                xaxis_title="", yaxis_title="Satisfaction Score",
            )
            st.plotly_chart(fig, use_container_width=True)

    with c4:
        if "daysincelastorder" in df.columns:
            fig = px.histogram(
                df, x="daysincelastorder", nbins=30,
                title="Days Since Last Order",
                template=PLOTLY_TEMPLATE,
                color_discrete_sequence=[PALETTE["warning"]],
            )
            fig.update_layout(
                margin=dict(t=50, b=20, l=20, r=20), height=380,
                xaxis_title="Days Since Last Order", yaxis_title="Count",
                bargap=0.05,
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Complaint Customers Table ────────────────────────────
    section_header("📋  Complaint Customers", "Customers who filed complaints")
    comp_cols = [
        "customerid", "complain", "satisfactionscore",
        "daysincelastorder", "churn_probability",
    ]
    avail_cols = [c for c in comp_cols if c in df.columns]
    comp_df = (
        df[df["complain"] == 1][avail_cols]
        .sort_values("churn_probability", ascending=False)
        .reset_index(drop=True)
    )
    styled_dataframe(comp_df)
