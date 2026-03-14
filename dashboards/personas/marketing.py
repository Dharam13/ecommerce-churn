"""
personas/marketing.py
═════════════════════
Persona 1 — Marketing Manager
Goal: Monitor churn and retention campaigns.

Uses Gold star-schema column names:
  ordercount, couponused, cashbackamount, churn, risk_segment, churn_probability
"""

import pandas as pd
import streamlit as st
import plotly.express as px

from config import PALETTE, RISK_COLORS, PLOTLY_TEMPLATE
from components import kpi_card, section_header, styled_dataframe


def render_marketing_dashboard(df: pd.DataFrame):
    """Render the Marketing Manager persona view."""

    # ── Header ───────────────────────────────────────────────
    st.markdown(f"""
    <div style="
        background: linear-gradient(90deg, rgba(108,99,255,0.25), transparent);
        padding: 1.2rem 1.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
    ">
        <h1 style="margin:0;font-size:1.8rem;">📈  Marketing Manager Dashboard</h1>
        <p style="color:#9CA3AF;margin:0.3rem 0 0;">
            Monitor churn trends, retention campaigns &amp; coupon effectiveness
        </p>
    </div>
    """, unsafe_allow_html=True)

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
        kpi_card("Churn Rate", f"{churn_rate:.1f}%", icon="🔻")
    with cols[1]:
        kpi_card("At-Risk Customers", f"{at_risk:,}", icon="⚠️")
    with cols[2]:
        kpi_card("Retention Rate", f"{retention_rate:.1f}%", icon="🛡️")
    with cols[3]:
        kpi_card("Avg. Orders", f"{avg_orders:.1f}", icon="🛒")
    with cols[4]:
        kpi_card("Coupon Churn %", f"{coupon_eff:.1f}%", icon="🎟️")

    section_header("📊  Charts", "Churn drivers & retention insights")

    # ── Row 1: Churn Distribution + Orders vs Churn ──────────
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
            title="Churn Distribution",
            hole=0.45,
            template=PLOTLY_TEMPLATE,
        )
        fig.update_traces(textinfo="percent+label", pull=[0.03, 0.06])
        fig.update_layout(margin=dict(t=50, b=20, l=20, r=20), height=380)
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
            title="Orders vs Churn",
            template=PLOTLY_TEMPLATE,
        )
        fig.update_layout(
            margin=dict(t=50, b=20, l=20, r=20), height=380,
            showlegend=False,
            xaxis_title="", yaxis_title="Order Count",
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Row 2: Cashback Scatter + Coupon Usage Bar ───────────
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
            title="Cashback vs Churn Probability",
            opacity=0.65,
            template=PLOTLY_TEMPLATE,
        )
        fig.update_layout(
            margin=dict(t=50, b=20, l=20, r=20), height=380,
            xaxis_title="Cashback Amount", yaxis_title="Churn Probability",
        )
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
            title="Coupon Usage vs Churn Rate",
            template=PLOTLY_TEMPLATE,
            color_discrete_sequence=[PALETTE["primary"]],
        )
        fig.update_layout(
            margin=dict(t=50, b=20, l=20, r=20), height=380,
            xaxis_title="Coupons Used", yaxis_title="Churn Rate",
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Row 3: Churn Risk Segmentation ───────────────────────
    seg_df = df["risk_segment"].value_counts().reset_index()
    seg_df.columns = ["risk_segment", "count"]
    fig = px.bar(
        seg_df, x="risk_segment", y="count",
        color="risk_segment",
        color_discrete_map=RISK_COLORS,
        title="Churn Risk Segmentation",
        template=PLOTLY_TEMPLATE,
    )
    fig.update_layout(
        margin=dict(t=50, b=20, l=20, r=20), height=380,
        showlegend=False,
        xaxis_title="Risk Segment", yaxis_title="Customer Count",
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── High Risk Table ──────────────────────────────────────
    section_header(
        "🚨  High Risk Customers",
        "Sorted by churn probability (descending)",
    )
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
