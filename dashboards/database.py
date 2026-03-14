"""
database.py
═══════════
Database connection (via src.db.connection) and data loading.

Reads from the Gold star schema (fact + dimensions), enriches with
Silver columns, and merges ML-based churn predictions from
gold.churn_predictions.
"""

import sys
from pathlib import Path

# Ensure the project root is on sys.path so `src.*` imports work
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pandas as pd
import streamlit as st
from sqlalchemy import text

from src.db.connection import get_engine
from config import (
    GOLD_SCHEMA,
    SILVER_SCHEMA,
    DATA_CACHE_TTL,
    HIGH_RISK_THRESHOLD,
    MEDIUM_RISK_THRESHOLD,
)


@st.cache_resource
def connect_db():
    """Return a cached SQLAlchemy engine (credentials from .env)."""
    return get_engine()


def _predictions_table_exists(engine) -> bool:
    """Check if gold.churn_predictions exists and has data."""
    try:
        result = pd.read_sql(
            text(f"SELECT COUNT(*) AS n FROM {GOLD_SCHEMA}.churn_predictions"),
            engine,
        )
        return result.iloc[0, 0] > 0
    except Exception:
        return False


@st.cache_data(ttl=DATA_CACHE_TTL)
def load_data() -> pd.DataFrame:
    """
    Build a rich analytical DataFrame by joining Gold star-schema tables,
    enriching with Silver-layer columns, and merging ML predictions from
    gold.churn_predictions.

    Gold provides:
        fact_orders  → ordercount, couponused, cashbackamount, churn, complain …
        dim_customer → customerid, gender, maritalstatus, citytier, tenure …
        dim_product  → preferedordercat
        dim_date     → date, year, month, week, is_weekend
        dim_location → citytier

    Silver enrichment (not in Gold fact):
        satisfactionscore, hourspendonapp, numberofdeviceregistered,
        daysincelastorder, preferredpaymentmode, numberofaddress

    ML predictions (gold.churn_predictions):
        churn_probability, churn_prediction, risk_segment, prediction_time
    """
    engine = connect_db()

    # ── 1. Star-schema join (Gold) ───────────────────────────
    gold_query = text(f"""
        SELECT
            dc.customerid,
            dc.gender,
            dc.maritalstatus,
            dc.citytier,
            dc.preferredlogindevice,
            dc.tenure,
            dc.warehousetohome,

            dp.preferedordercat,

            dd.date   AS order_date,
            dd.year   AS order_year,
            dd.month  AS order_month,
            dd.is_weekend,

            f.ordercount,
            f.couponused,
            f.cashbackamount,
            f.orderamounthikefromlastyear,
            f.churn,
            f.complain
        FROM {GOLD_SCHEMA}.fact_orders   f
        JOIN {GOLD_SCHEMA}.dim_customer  dc USING (customer_sk)
        JOIN {GOLD_SCHEMA}.dim_product   dp USING (product_sk)
        JOIN {GOLD_SCHEMA}.dim_date      dd USING (date_sk)
        JOIN {GOLD_SCHEMA}.dim_location  dl USING (location_sk)
    """)
    df = pd.read_sql(gold_query, engine)

    # ── 2. Silver enrichment ──────────────────────────────────
    silver_query = text(f"""
        SELECT
            customerid,
            satisfactionscore,
            hourspendonapp,
            numberofdeviceregistered,
            daysincelastorder,
            preferredpaymentmode,
            numberofaddress
        FROM {SILVER_SCHEMA}.ecommerce_clean
    """)
    silver_extra = pd.read_sql(silver_query, engine)
    df = df.merge(silver_extra, on="customerid", how="left")

    # ── 3. Churn → int ───────────────────────────────────────
    df["churn"] = df["churn"].astype(int)

    # ── 4. ML predictions from gold.churn_predictions ────────
    if _predictions_table_exists(engine):
        pred_query = text(f"""
            SELECT
                customerid,
                churn_probability,
                churn_prediction,
                risk_segment,
                prediction_time AS ml_prediction_time
            FROM {GOLD_SCHEMA}.churn_predictions
        """)
        pred_df = pd.read_sql(pred_query, engine)
        df = df.merge(pred_df, on="customerid", how="left")

        # Fill any customers not in predictions table
        if df["churn_probability"].isna().any():
            mask = df["churn_probability"].isna()
            df.loc[mask, "churn_probability"] = _fallback_probability(df.loc[mask])
            df.loc[mask, "risk_segment"] = df.loc[mask, "churn_probability"].apply(_compute_segment)

        st.sidebar.success("Using ML model predictions")
    else:
        # Fallback: rule-based if no ML predictions exist yet
        df["churn_probability"] = _fallback_probability(df)
        df["risk_segment"] = df["churn_probability"].apply(_compute_segment)
        st.sidebar.warning("No ML predictions found — using rule-based fallback.\n\nRun: `python -m src.ml.predict_churn`")

    return df


# ════════════════════════════════════════════════════════════
# FALLBACK (only used when gold.churn_predictions is empty)
# ════════════════════════════════════════════════════════════

def _fallback_probability(df: pd.DataFrame) -> pd.Series:
    """
    Simple rule-based churn probability — ONLY used as fallback
    when gold.churn_predictions has not been populated yet.
    """
    import numpy as np

    prob = pd.Series(0.15, index=df.index)

    prob += (df["complain"] == 1).astype(float) * 0.25
    prob += (df.get("satisfactionscore", pd.Series(3, index=df.index)) <= 2).astype(float) * 0.20
    prob += (df.get("daysincelastorder", pd.Series(0, index=df.index)) > 30).astype(float) * 0.15
    prob += (df["ordercount"] <= 2).astype(float) * 0.10
    prob = prob + df["churn"].astype(float) * 0.15

    rng = np.random.default_rng(42)
    noise = rng.uniform(-0.05, 0.05, size=len(df))
    prob = (prob + noise).clip(0.01, 0.99).round(4)

    return prob


def _compute_segment(prob: float) -> str:
    """Assign a risk segment label based on churn probability."""
    if prob > HIGH_RISK_THRESHOLD:
        return "High Risk"
    elif prob >= MEDIUM_RISK_THRESHOLD:
        return "Medium Risk"
    return "Low Risk"
