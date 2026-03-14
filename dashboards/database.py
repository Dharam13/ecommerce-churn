"""
database.py
═══════════
Database connection (via src.db.connection) and data loading.

Reads from the Gold star schema (fact + dimensions) and enriches with
columns from Silver that aren't in the Gold layer (e.g. satisfactionscore,
hourspendonapp, daysincelastorder, etc.).
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


@st.cache_data(ttl=DATA_CACHE_TTL)
def load_data() -> pd.DataFrame:
    """
    Build a rich analytical DataFrame by joining Gold star-schema tables
    and enriching with Silver-layer columns not present in Gold.

    Gold provides:
        fact_orders  → ordercount, couponused, cashbackamount, churn, complain …
        dim_customer → customerid, gender, maritalstatus, citytier, tenure …
        dim_product  → preferedordercat
        dim_date     → date, year, month, week, is_weekend
        dim_location → citytier

    Silver enrichment (not in Gold fact):
        satisfactionscore, hourspendonapp, numberofdeviceregistered,
        daysincelastorder, preferredpaymentmode, numberofaddress
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

    # ── 3. Derived columns ────────────────────────────────────
    # churn is already boolean/int from fact — ensure int
    df["churn"] = df["churn"].astype(int)

    # Churn probability placeholder (no ML model yet → use a rule-based proxy)
    df["churn_probability"] = _estimate_churn_probability(df)

    # Risk segment
    df["risk_segment"] = df["churn_probability"].apply(_compute_segment)

    return df


def _estimate_churn_probability(df: pd.DataFrame) -> pd.Series:
    """
    Simple rule-based churn probability until a real ML model is trained.
    For customers where churn==1 (already churned) → high probability.
    For others → lower, modulated by complaints, satisfaction, inactivity.
    """
    import numpy as np

    prob = pd.Series(0.15, index=df.index)

    prob += (df["complain"] == 1).astype(float) * 0.25
    prob += (df.get("satisfactionscore", pd.Series(3, index=df.index)) <= 2).astype(float) * 0.20
    prob += (df.get("daysincelastorder", pd.Series(0, index=df.index)) > 30).astype(float) * 0.15
    prob += (df["ordercount"] <= 2).astype(float) * 0.10

    # If they actually churned, nudge up
    prob = prob + df["churn"].astype(float) * 0.15

    # Add slight noise for scatter variety
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
