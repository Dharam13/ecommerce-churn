"""
database.py
═══════════
Database connection and data loading logic.
"""

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

from config import (
    DB_URL,
    DATA_CACHE_TTL,
    HIGH_RISK_THRESHOLD,
    MEDIUM_RISK_THRESHOLD,
)


@st.cache_resource
def connect_db():
    """Return a cached SQLAlchemy engine connected to the churn_db."""
    return create_engine(DB_URL)


@st.cache_data(ttl=DATA_CACHE_TTL)
def load_data() -> pd.DataFrame:
    """
    Join all three warehouse tables on customer_id and return a single
    DataFrame.  Also adds the derived *churn* binary flag and ensures
    risk_segment is present.
    """
    engine = connect_db()
    query = text("""
        SELECT
            c.customer_id,
            c.tenure,
            c.gender,
            c.marital_status,
            c.city_tier,
            c.preferred_login_device,
            c.preferred_payment_mode,
            c.number_of_address,

            b.hour_spend_on_app,
            b.number_of_device_registered,
            b.prefered_order_cat,
            b.order_count,
            b.coupon_used,
            b.cashback_amount,
            b.day_since_last_order,
            b.complain,
            b.satisfaction_score,
            b.order_amount_hike_from_last_year,
            b.warehouse_to_home,

            p.churn_probability,
            p.risk_segment,
            p.prediction_time
        FROM customers c
        JOIN customer_behavior b USING (customer_id)
        JOIN churn_predictions  p USING (customer_id)
    """)
    df = pd.read_sql(query, engine)

    # ── Derived columns ──────────────────────────────────────
    df["churn"] = (df["churn_probability"] > MEDIUM_RISK_THRESHOLD).astype(int)

    # Ensure risk_segment is populated
    if df["risk_segment"].isna().any():
        df["risk_segment"] = df["churn_probability"].apply(_compute_segment)

    return df


def _compute_segment(prob: float) -> str:
    """Assign a risk segment label based on churn probability."""
    if prob > HIGH_RISK_THRESHOLD:
        return "High Risk"
    elif prob >= MEDIUM_RISK_THRESHOLD:
        return "Medium Risk"
    return "Low Risk"
