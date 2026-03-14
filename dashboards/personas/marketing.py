"""
personas/marketing.py
═════════════════════
Persona 1 — Marketing Manager
Goal: Monitor churn and retention campaigns.
"""

import pandas as pd
import streamlit as st
import plotly.express as px

from config import PALETTE, RISK_COLORS, CHART_COLORS, PLOTLY_TEMPLATE
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
        legend=dict(
            font=dict(size=11),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(gridcolor="#F3F4F6", zerolinecolor="#E5E7EB"),
        yaxis=dict(gridcolor="#F3F4F6", zerolinecolor="#E5E7EB"),
    )
    return fig


def render_marketing_dashboard(df: pd.DataFrame):
    """Render the Marketing Manager persona view."""

    persona_header(
        title="Marketing Manager Dashboard",
        subtitle="Monitor churn trends, retention campaigns & coupon effectiveness",
        accent_color=PALETTE["primary"],
    )

    # ── KPIs ─────────────────────────────────────────────────
    total = len(df)
    churned = df["churn"].sum()
    churn_rate = churned / total * 100 if total else 0
    at_risk = (df["risk_segment"] == "High Risk").sum()
    retention_rate = 100 - churn_rate
    avg_orders = df["ordercount"].mean()
    coupon_eff = (
        df[df["couponused"] > 0]["churn"].mean() * 100
        if (df["couponused"] > 0).any()
        else 0
    )

    cols = st.columns(5)
    with cols[0]:
        kpi_card("Churn Rate", f"{churn_rate:.1f}%",
                 accent_color=PALETTE["secondary"])
    with cols[1]:
        kpi_card("At-Risk Customers", f"{at_risk:,}",
                 accent_color=PALETTE["warning"])
    with cols[2]:
        kpi_card("Retention Rate", f"{retention_rate:.1f}%",
                 accent_color=PALETTE["accent"])
    with cols[3]:
        kpi_card("Avg. Orders", f"{avg_orders:.1f}",
                 accent_color=PALETTE["primary"])
    with cols[4]:
        kpi_card("Coupon Churn %", f"{coupon_eff:.1f}%",
                 accent_color=PALETTE["info"])

    section_header("Charts", "Churn drivers & retention insights")

    # ── Row 1 ────────────────────────────────────────────────
    c1, c2 = st.columns(2)

    with c1:
        pie_df = df["churn"].value_counts().reset_index()
        pie_df.columns = ["churn", "count"]
        pie_df["label"] = pie_df["churn"].map({0: "Retained", 1: "Churned"})
        fig = px.pie(
            pie_df, names="label", values="count",
            color="label",
            color_discrete_map={
                "Retained": PALETTE["accent"],
                "Churned": PALETTE["secondary"],
            },
            hole=0.52,
            template=PLOTLY_TEMPLATE,
        )
        fig.update_traces(
            textinfo="percent+label", pull=[0.02, 0.04],
            textfont_size=12,
            marker=dict(line=dict(color="#FFFFFF", width=2)),
        )
        fig = _chart_layout(fig, title="Churn Distribution", height=380)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        box_df = df.copy()
        box_df["churn_label"] = box_df["churn"].map({0: "Retained", 1: "Churned"})
        fig = px.box(
            box_df, x="churn_label", y="ordercount",
            color="churn_label",
            color_discrete_map={
                "Retained": PALETTE["accent"],
                "Churned": PALETTE["secondary"],
            },
            template=PLOTLY_TEMPLATE,
        )
        fig = _chart_layout(fig, title="Orders vs Churn", height=380)
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Order Count")
        st.plotly_chart(fig, use_container_width=True)

    # ── Row 2 ────────────────────────────────────────────────
    c3, c4 = st.columns(2)

    with c3:
        scatter_df = df.copy()
        scatter_df["churn_label"] = scatter_df["churn"].map(
            {0: "Retained", 1: "Churned"}
        )
        fig = px.scatter(
            scatter_df, x="cashbackamount", y="churn_probability",
            color="churn_label",
            color_discrete_map={
                "Retained": PALETTE["accent"],
                "Churned": PALETTE["secondary"],
            },
            opacity=0.55,
            template=PLOTLY_TEMPLATE,
        )
        fig = _chart_layout(fig, title="Cashback vs Churn Probability", height=380)
        fig.update_layout(xaxis_title="Cashback Amount", yaxis_title="Churn Probability")
        st.plotly_chart(fig, use_container_width=True)

    with c4:
        coupon_df = (
            df.groupby("couponused")["churn"]
            .mean()
            .reset_index()
            .rename(columns={"churn": "churn_rate"})
        )
        fig = px.bar(
            coupon_df, x="couponused", y="churn_rate",
            template=PLOTLY_TEMPLATE,
            color_discrete_sequence=[PALETTE["primary"]],
        )
        fig = _chart_layout(fig, title="Coupon Usage vs Churn Rate", height=380)
        fig.update_layout(xaxis_title="Coupons Used", yaxis_title="Churn Rate")
        fig.update_traces(marker_cornerradius=6)
        st.plotly_chart(fig, use_container_width=True)

    # ── Row 3 ────────────────────────────────────────────────
    seg_df = df["risk_segment"].value_counts().reset_index()
    seg_df.columns = ["risk_segment", "count"]
    fig = px.bar(
        seg_df, x="risk_segment", y="count",
        color="risk_segment",
        color_discrete_map=RISK_COLORS,
        template=PLOTLY_TEMPLATE,
    )
    fig = _chart_layout(fig, title="Churn Risk Segmentation", height=380)
    fig.update_layout(
        showlegend=False,
        xaxis_title="Risk Segment", yaxis_title="Customer Count",
    )
    fig.update_traces(marker_cornerradius=6)
    st.plotly_chart(fig, use_container_width=True)

    # ── High Risk Table ──────────────────────────────────────
    section_header("High Risk Customers", "Sorted by churn probability descending")
    high_risk_cols = [
        "customerid", "churn_probability", "ordercount",
        "couponused", "cashbackamount", "daysincelastorder",
    ]
    avail_cols = [c for c in high_risk_cols if c in df.columns]
    high_risk_df = (
        df[df["risk_segment"] == "High Risk"][avail_cols]
        .sort_values("churn_probability", ascending=False)
        .reset_index(drop=True)
    )
    styled_dataframe(high_risk_df)
