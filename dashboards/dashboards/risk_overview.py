"""
dashboards/risk_overview.py
═══════════════════════════
Shared risk-segmentation section shown at the bottom of every persona.
"""

import pandas as pd
import streamlit as st
import plotly.express as px

from config import RISK_COLORS, PLOTLY_TEMPLATE
from components import kpi_card, section_header, styled_dataframe


def render_risk_overview(df: pd.DataFrame):
    """Render a risk-segmentation breakdown with KPIs, chart, and table."""
    section_header("🎯  Churn Risk Segmentation Overview")

    seg_counts = df["risk_segment"].value_counts().reindex(
        ["High Risk", "Medium Risk", "Low Risk"], fill_value=0
    )

    # ── KPI cards ────────────────────────────────────────────
    cols = st.columns(3)
    icons = ["🔴", "🟠", "🟢"]
    for i, seg in enumerate(["High Risk", "Medium Risk", "Low Risk"]):
        with cols[i]:
            kpi_card(seg, f"{seg_counts[seg]:,}", icon=icons[i])

    # ── Horizontal stacked bar ───────────────────────────────
    seg_df = seg_counts.reset_index()
    seg_df.columns = ["segment", "count"]
    fig = px.bar(
        seg_df,
        x="count",
        y=["All Customers"] * len(seg_df),
        color="segment",
        color_discrete_map=RISK_COLORS,
        orientation="h",
        title="Risk Distribution",
        template=PLOTLY_TEMPLATE,
    )
    fig.update_layout(
        barmode="stack",
        margin=dict(t=50, b=20, l=20, r=20),
        height=180,
        showlegend=True,
        yaxis_title="",
        xaxis_title="Customer Count",
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── High Risk table ──────────────────────────────────────
    section_header("🚨  High Risk Customer List")
    high_risk_cols = [
        "customer_id", "churn_probability", "risk_segment",
        "order_count", "coupon_used", "cashback_amount",
        "day_since_last_order", "satisfaction_score", "complain",
    ]
    hr_df = (
        df[df["risk_segment"] == "High Risk"][high_risk_cols]
        .sort_values("churn_probability", ascending=False)
        .reset_index(drop=True)
    )
    styled_dataframe(hr_df, height=350)
