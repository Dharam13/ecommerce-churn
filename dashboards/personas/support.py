"""
personas/support.py
═══════════════════
Persona 2 — Customer Success / Support
Goal: Monitor complaints and satisfaction.
"""

import pandas as pd
import streamlit as st
import plotly.express as px

from config import PALETTE, PLOTLY_TEMPLATE
from components import kpi_card, section_header, styled_dataframe, persona_header


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


def render_support_dashboard(df: pd.DataFrame):
    """Render the Customer Success / Support persona view."""

    persona_header(
        title="Customer Success / Support",
        subtitle="Monitor complaints, satisfaction & customer inactivity",
        accent_color=PALETTE["secondary"],
    )

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
        kpi_card("Complaint Rate", f"{complaint_rate:.1f}%",
                 accent_color=PALETTE["secondary"])
    with cols[1]:
        kpi_card("Avg. Satisfaction", f"{avg_sat:.2f} / 5",
                 accent_color=PALETTE["warning"])
    with cols[2]:
        kpi_card("Complaint Customers", f"{complaint_count:,}",
                 accent_color=PALETTE["secondary"])
    with cols[3]:
        kpi_card("Inactive (>30 days)", f"{inactive:,}",
                 accent_color=PALETTE["text_muted"])

    section_header("Charts", "Complaint & satisfaction analysis")

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
            template=PLOTLY_TEMPLATE,
        )
        fig = _chart_layout(fig, title="Complaints vs Churn Rate", height=380)
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Churn Rate")
        fig.update_traces(marker_cornerradius=6)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        if "satisfactionscore" in df.columns:
            fig = px.histogram(
                df, x="satisfactionscore", nbins=5,
                template=PLOTLY_TEMPLATE,
                color_discrete_sequence=[PALETTE["info"]],
            )
            fig = _chart_layout(fig, title="Satisfaction Score Distribution", height=380)
            fig.update_layout(
                xaxis_title="Satisfaction Score", yaxis_title="Count",
                bargap=0.15,
            )
            fig.update_traces(marker_cornerradius=6)
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
                template=PLOTLY_TEMPLATE,
            )
            fig = _chart_layout(fig, title="Satisfaction vs Churn", height=380)
            fig.update_layout(
                showlegend=False,
                xaxis_title="", yaxis_title="Satisfaction Score",
            )
            st.plotly_chart(fig, use_container_width=True)

    with c4:
        if "daysincelastorder" in df.columns:
            fig = px.histogram(
                df, x="daysincelastorder", nbins=30,
                template=PLOTLY_TEMPLATE,
                color_discrete_sequence=[PALETTE["warning"]],
            )
            fig = _chart_layout(fig, title="Days Since Last Order", height=380)
            fig.update_layout(
                xaxis_title="Days Since Last Order", yaxis_title="Count",
                bargap=0.05,
            )
            fig.update_traces(marker_cornerradius=4)
            st.plotly_chart(fig, use_container_width=True)

    # ── Complaint Customers Table ────────────────────────────
    section_header("Complaint Customers", "Customers who filed complaints")
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
