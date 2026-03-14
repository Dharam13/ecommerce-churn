"""
src/simulation/engine.py
========================
Two simulation pipelines:

1. simulate_activity(customer_id)
   - Picks a random existing customer (or the given ID)
   - Applies realistic activity updates (ordercount+1, daysincelastorder=0, …)
   - Pushes changes through bronze → silver → gold → churn prediction

2. simulate_new_customer(data_dict)
   - Inserts a new customer row into bronze
   - Pushes through bronze → silver → gold → churn prediction

Both return a result dict with before/after snapshots and the new prediction.
"""

import os
import sys
import random
from datetime import datetime, date
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sqlalchemy import text

# Ensure project root is importable
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.db.connection import get_engine, ensure_schemas

BRONZE_SCHEMA = os.getenv("BRONZE_SCHEMA", "bronze")
SILVER_SCHEMA = os.getenv("SILVER_SCHEMA", "silver")
GOLD_SCHEMA = os.getenv("GOLD_SCHEMA", "gold")

MODEL_PATH = _PROJECT_ROOT / "models" / "churn_rf_model.pkl"


# ════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════

def _load_model():
    """Load saved model + scaler + encoders + feature_cols."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"No saved model at {MODEL_PATH}. "
            "Run `python -m src.ml.predict_churn` first."
        )
    return joblib.load(MODEL_PATH)


def _predict_single(row_df: pd.DataFrame, model_bundle: dict) -> dict:
    """
    Predict churn probability for a single-row DataFrame.
    Returns {churn_probability, churn_prediction, risk_segment}.
    """
    from sklearn.preprocessing import LabelEncoder

    model = model_bundle["model"]
    scaler = model_bundle["scaler"]
    encoders = model_bundle["encoders"]
    feature_cols = model_bundle["feature_cols"]

    work = row_df.copy()

    # Fix category names (same as predict_churn.py)
    if "preferedordercat" in work.columns:
        work.loc[work["preferedordercat"] == "Mobile", "preferedordercat"] = "Mobile Phone"
    if "preferredpaymentmode" in work.columns:
        work.loc[work["preferredpaymentmode"] == "COD", "preferredpaymentmode"] = "Cash on Delivery"
        work.loc[work["preferredpaymentmode"] == "CC", "preferredpaymentmode"] = "Credit Card"

    # Apply label encoding
    for col, le in encoders.items():
        if col in work.columns:
            work[f"{col}_encoded"] = work[col].astype(str).apply(
                lambda x, _le=le: _le.transform([x])[0] if x in _le.classes_ else 0
            )

    # Build feature vector
    X = work.reindex(columns=feature_cols, fill_value=0).copy()
    for col in X.columns:
        if X[col].isna().any():
            X[col] = X[col].fillna(0)

    X_scaled = scaler.transform(X)
    prob = float(model.predict_proba(X_scaled)[0, 1])
    pred = int(model.predict(X_scaled)[0])

    if prob > 0.75:
        seg = "High Risk"
    elif prob >= 0.50:
        seg = "Medium Risk"
    else:
        seg = "Low Risk"

    return {
        "churn_probability": round(prob, 4),
        "churn_prediction": pred,
        "risk_segment": seg,
    }


def _upsert_bronze_row(engine, row: dict):
    """Insert or update a row in bronze.ecommerce_raw."""
    cols = list(row.keys())
    placeholders = ", ".join([f":{c}" for c in cols])
    col_names = ", ".join(cols)

    # Delete existing row with same customerid, then insert
    with engine.begin() as conn:
        conn.execute(
            text(f"DELETE FROM {BRONZE_SCHEMA}.ecommerce_raw WHERE customerid = :cid"),
            {"cid": row["customerid"]},
        )
        conn.execute(
            text(f"INSERT INTO {BRONZE_SCHEMA}.ecommerce_raw ({col_names}) VALUES ({placeholders})"),
            row,
        )


def _run_mini_etl(engine, customer_id: str):
    """
    Run a targeted ETL for a single customer:
    1. Re-transform the full bronze → silver (snapshot replace)
    2. Re-build the gold schema from silver
    3. Re-predict churn for the affected customer
    """
    from src.etl.transform_to_silver import transform_bronze_to_silver
    from src.etl.build_gold_schema import build_gold_from_silver

    # Step 1: Bronze → Silver
    transform_bronze_to_silver()

    # Step 2: Silver → Gold
    build_gold_from_silver()

    # Step 3: Re-predict for this customer
    model_bundle = _load_model()

    # Read this customer's silver row
    with engine.connect() as conn:
        cust_df = pd.read_sql(
            text(f"SELECT * FROM {SILVER_SCHEMA}.ecommerce_clean WHERE customerid = :cid"),
            conn,
            params={"cid": customer_id},
        )

    if cust_df.empty:
        return None

    prediction = _predict_single(cust_df.iloc[[0]], model_bundle)

    # Update gold.churn_predictions
    with engine.begin() as conn:
        conn.execute(
            text(f"DELETE FROM {GOLD_SCHEMA}.churn_predictions WHERE customerid = :cid"),
            {"cid": customer_id},
        )
        conn.execute(
            text(
                f"INSERT INTO {GOLD_SCHEMA}.churn_predictions "
                "(customerid, churn_probability, churn_prediction, risk_segment, prediction_time) "
                "VALUES (:cid, :prob, :pred, :seg, :ts)"
            ),
            {
                "cid": customer_id,
                "prob": prediction["churn_probability"],
                "pred": prediction["churn_prediction"],
                "seg": prediction["risk_segment"],
                "ts": datetime.now(),
            },
        )

    return prediction


# ════════════════════════════════════════════════════════════
# PIPELINE 1: SIMULATE ACTIVITY UPDATE
# ════════════════════════════════════════════════════════════

def simulate_activity(customer_id: str = None) -> dict:
    """
    Simulate a customer placing a new order or performing activity.

    Updates:
      - ordercount += 1
      - daysincelastorder = 0
      - couponused += random(0 or 1)
      - cashbackamount += random(10-100)
      - orderamounthikefromlastyear += random(1-5)
      - complain = random(0 or 1, weighted 90% no complaint)
      - satisfactionscore = random(1-5)

    Returns dict with before/after data and new prediction.
    """
    engine = get_engine()
    ensure_schemas(engine)

    # Pick a random customer if none specified
    if customer_id is None:
        with engine.connect() as conn:
            ids = pd.read_sql(
                text(f"SELECT DISTINCT customerid FROM {BRONZE_SCHEMA}.ecommerce_raw"),
                conn,
            )["customerid"].tolist()
        customer_id = str(random.choice(ids))

    # Read current bronze row
    with engine.connect() as conn:
        before_df = pd.read_sql(
            text(f"SELECT * FROM {BRONZE_SCHEMA}.ecommerce_raw WHERE customerid = :cid"),
            conn,
            params={"cid": customer_id},
        )

    if before_df.empty:
        return {"error": f"Customer {customer_id} not found in bronze"}

    before = before_df.iloc[0].to_dict()

    # Get old prediction
    old_pred = None
    with engine.connect() as conn:
        old_pred_df = pd.read_sql(
            text(f"SELECT * FROM {GOLD_SCHEMA}.churn_predictions WHERE customerid = :cid"),
            conn,
            params={"cid": customer_id},
        )
    if not old_pred_df.empty:
        old_pred = {
            "churn_probability": float(old_pred_df.iloc[0]["churn_probability"]),
            "risk_segment": str(old_pred_df.iloc[0]["risk_segment"]),
        }

    # Apply activity updates
    after = before.copy()
    after["ordercount"] = float(before.get("ordercount", 0) or 0) + 1
    after["daysincelastorder"] = 0
    after["couponused"] = float(before.get("couponused", 0) or 0) + random.choice([0, 1])
    after["cashbackamount"] = float(before.get("cashbackamount", 0) or 0) + round(random.uniform(10, 100), 2)
    after["orderamounthikefromlastyear"] = float(before.get("orderamounthikefromlastyear", 0) or 0) + round(random.uniform(1, 5), 1)
    after["complain"] = random.choices([0, 1], weights=[90, 10])[0]
    after["satisfactionscore"] = random.randint(3, 5)  # leaning positive since they just ordered

    # Remove non-bronze columns / timestamps
    for key in ["created_at"]:
        after.pop(key, None)

    # Write updated row to bronze
    _upsert_bronze_row(engine, after)

    # Run ETL + prediction
    new_pred = _run_mini_etl(engine, customer_id)

    engine.dispose()

    return {
        "customer_id": customer_id,
        "simulation_type": "activity_update",
        "changes_applied": {
            "ordercount": f"{before.get('ordercount', 0)} → {after['ordercount']}",
            "daysincelastorder": f"{before.get('daysincelastorder', '?')} → 0",
            "couponused": f"{before.get('couponused', 0)} → {after['couponused']}",
            "cashbackamount": f"{before.get('cashbackamount', 0):.2f} → {after['cashbackamount']:.2f}",
            "complain": f"{before.get('complain', 0)} → {after['complain']}",
            "satisfactionscore": f"{before.get('satisfactionscore', '?')} → {after['satisfactionscore']}",
        },
        "before_prediction": old_pred,
        "after_prediction": new_pred,
    }


# ════════════════════════════════════════════════════════════
# PIPELINE 2: SIMULATE NEW CUSTOMER
# ════════════════════════════════════════════════════════════

# Default choices for random generation
_LOGIN_DEVICES = ["Mobile Phone", "Computer", "Phone"]
_GENDERS = ["Male", "Female"]
_MARITAL_STATUSES = ["Single", "Married", "Divorced"]
_PAYMENT_MODES = ["Debit Card", "Credit Card", "E wallet", "UPI", "Cash on Delivery"]
_ORDER_CATS = ["Laptop & Accessory", "Mobile Phone", "Fashion", "Grocery", "Others"]


def simulate_new_customer(overrides: dict = None) -> dict:
    """
    Generate and insert a new customer into bronze, then run full ETL + prediction.

    overrides: dict of column_name → value to override random defaults.

    Returns dict with the new customer data and churn prediction.
    """
    engine = get_engine()
    ensure_schemas(engine)

    # Generate next customer ID
    with engine.connect() as conn:
        all_ids = pd.read_sql(
            text(f"SELECT customerid FROM {BRONZE_SCHEMA}.ecommerce_raw"),
            conn,
        )["customerid"].tolist()

    # Filter numeric IDs and find max
    numeric_ids = [int(x) for x in all_ids if str(x).isdigit()]
    next_id = str(max(numeric_ids, default=70000) + 1)

    # Random realistic defaults
    new_customer = {
        "customerid": next_id,
        "churn": 0,
        "tenure": random.randint(0, 30),
        "preferredlogindevice": random.choice(_LOGIN_DEVICES),
        "citytier": random.choice([1, 2, 3]),
        "warehousetohome": random.randint(5, 35),
        "preferredpaymentmode": random.choice(_PAYMENT_MODES),
        "gender": random.choice(_GENDERS),
        "hourspendonapp": round(random.uniform(0.5, 5.0), 1),
        "numberofdeviceregistered": random.randint(1, 6),
        "preferedordercat": random.choice(_ORDER_CATS),
        "satisfactionscore": random.randint(1, 5),
        "maritalstatus": random.choice(_MARITAL_STATUSES),
        "numberofaddress": random.randint(1, 15),
        "complain": random.choices([0, 1], weights=[85, 15])[0],
        "orderamounthikefromlastyear": round(random.uniform(11, 26), 1),
        "couponused": random.randint(0, 5),
        "ordercount": random.randint(1, 8),
        "daysincelastorder": random.randint(0, 20),
        "cashbackamount": round(random.uniform(50, 350), 2),
    }

    # Apply user overrides
    if overrides:
        for k, v in overrides.items():
            if k in new_customer and k != "customerid":
                new_customer[k] = v

    # Insert into bronze
    _upsert_bronze_row(engine, new_customer)

    # Run ETL + prediction
    prediction = _run_mini_etl(engine, next_id)

    engine.dispose()

    return {
        "customer_id": next_id,
        "simulation_type": "new_customer",
        "customer_data": new_customer,
        "prediction": prediction,
    }


# ════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Churn Simulation Pipeline")
    sub = parser.add_subparsers(dest="command")

    act = sub.add_parser("activity", help="Simulate activity for existing customer")
    act.add_argument("--customer-id", default=None, help="Customer ID (random if omitted)")

    new = sub.add_parser("new", help="Simulate adding a new customer")

    args = parser.parse_args()

    if args.command == "activity":
        result = simulate_activity(args.customer_id)
        print("\n=== ACTIVITY SIMULATION RESULT ===")
        for k, v in result.items():
            print(f"  {k}: {v}")
    elif args.command == "new":
        result = simulate_new_customer()
        print("\n=== NEW CUSTOMER SIMULATION RESULT ===")
        for k, v in result.items():
            print(f"  {k}: {v}")
    else:
        parser.print_help()
