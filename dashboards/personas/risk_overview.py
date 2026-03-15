"""
personas/risk_overview.py
═════════════════════════
Shared risk-segmentation section shown at the bottom of every persona.
"""

import pandas as pd
import streamlit as st
import plotly.express as px

from config import PALETTE, RISK_COLORS, PLOTLY_TEMPLATE
from components import kpi_card, section_header, styled_dataframe


def render_risk_overview(df: pd.DataFrame):
    """Render a risk-segmentation breakdown with KPIs, chart, and table."""
    section_header("Churn Risk Segmentation Overview",
                   "Distribution of customers across risk levels")

    seg_counts = df["risk_segment"].value_counts().reindex(
        ["High Risk", "Medium Risk", "Low Risk"], fill_value=0
    )

    cols = st.columns(3)
    segments = ["High Risk", "Medium Risk", "Low Risk"]
    for i, seg in enumerate(segments):
        with cols[i]:
            kpi_card(seg, f"{seg_counts[seg]:,}",
                     accent_color=RISK_COLORS[seg])

    st.markdown("<div style='height:0.75rem;'></div>", unsafe_allow_html=True)

    seg_df = seg_counts.reset_index()
    seg_df.columns = ["segment", "count"]
    fig = px.bar(
        seg_df,
        x="count",
        y=["All Customers"] * len(seg_df),
        color="segment",
        color_discrete_map=RISK_COLORS,
        orientation="h",
        template=PLOTLY_TEMPLATE,
    )
    fig.update_layout(
        barmode="stack",
        margin=dict(t=45, b=20, l=20, r=20),
        height=160,
        showlegend=True,
        yaxis_title="",
        xaxis_title="Customer Count",
        font=dict(family="Inter, sans-serif", size=12, color=PALETTE["text_secondary"]),
        title=dict(
            text="Risk Distribution",
            font=dict(size=14, color=PALETTE["text"], family="Inter"),
            x=0.02, y=0.95,
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1, font=dict(size=11),
        ),
    )
    fig.update_traces(marker_cornerradius=4)
    st.plotly_chart(fig, use_container_width=True)

    section_header("High Risk Customer List",
                   "Customers most likely to churn — prioritize outreach")
    high_risk_cols = [
        "customerid", "churn_probability", "risk_segment",
        "ordercount", "couponused", "cashbackamount",
        "daysincelastorder", "satisfactionscore", "complain",
    ]
    avail_cols = [c for c in high_risk_cols if c in df.columns]
    hr_df = (
        df[df["risk_segment"] == "High Risk"][avail_cols]
        .sort_values("churn_probability", ascending=False)
        .reset_index(drop=True)
    )
    styled_dataframe(hr_df, height=350)
