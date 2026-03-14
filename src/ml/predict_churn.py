"""
predict_churn.py
════════════════
ML Pipeline: Train a Random Forest model on Silver data and store
churn predictions into a Gold table (gold.churn_predictions).

Pipeline flow:
    silver.ecommerce_clean  →  train / predict  →  gold.churn_predictions

Features are aligned with the warehouse column naming convention
(lowercase, no underscores for multi-word columns).

Usage:
    python -m src.ml.predict_churn            # train + predict + store
    python -m src.ml.predict_churn --predict   # predict only (load saved model)
"""

import os
import sys
import uuid
import warnings
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer, KNNImputer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, MinMaxScaler
from sqlalchemy import text

warnings.filterwarnings("ignore")

# ── Ensure project root is on path ────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.db.connection import get_engine, ensure_schemas

# ── Paths ─────────────────────────────────────────────────
MODEL_DIR = _PROJECT_ROOT / "models"
MODEL_DIR.mkdir(exist_ok=True)
MODEL_PATH = MODEL_DIR / "churn_rf_model.pkl"

# ── Schema names from env ─────────────────────────────────
SILVER_SCHEMA = os.getenv("SILVER_SCHEMA", "silver")
GOLD_SCHEMA = os.getenv("GOLD_SCHEMA", "gold")
BRONZE_SCHEMA = os.getenv("BRONZE_SCHEMA", "bronze")

# ── Feature columns used for training ─────────────────────
# These correspond to silver.ecommerce_clean columns.
# Categoricals that need encoding: preferedordercat, preferredpaymentmode
# Already encoded in silver: preferredlogindevice_encoded, gender_encoded,
#                             maritalstatus_encoded
NUMERIC_FEATURES = [
    "tenure",
    "citytier",
    "warehousetohome",
    "hourspendonapp",
    "numberofdeviceregistered",
    "satisfactionscore",
    "numberofaddress",
    "complain",
    "orderamounthikefromlastyear",
    "couponused",
    "ordercount",
    "daysincelastorder",
    "cashbackamount",
]

# Pre-encoded in silver (by transform_to_silver.py)
PRE_ENCODED_FEATURES = [
    "preferredlogindevice_encoded",
    "gender_encoded",
    "maritalstatus_encoded",
]

# Categoricals we need to encode ourselves
CATEGORICALS_TO_ENCODE = [
    "preferedordercat",
    "preferredpaymentmode",
]

TARGET = "churn"


# ════════════════════════════════════════════════════════════
# 1. LOAD DATA FROM SILVER
# ════════════════════════════════════════════════════════════

def load_silver_data(engine) -> pd.DataFrame:
    """Read the cleaned data from silver.ecommerce_clean."""
    with engine.connect() as conn:
        df = pd.read_sql(
            text(f"SELECT * FROM {SILVER_SCHEMA}.ecommerce_clean"),
            conn,
        )
    print(f"  📥  Loaded {len(df):,} rows from {SILVER_SCHEMA}.ecommerce_clean")
    return df


# ════════════════════════════════════════════════════════════
# 2. PREPARE FEATURES
# ════════════════════════════════════════════════════════════

def prepare_features(df: pd.DataFrame) -> tuple:
    """
    Prepare feature matrix X and target y from Silver data.
    Returns (X, y, encoders_dict, feature_columns_list).
    """
    work = df.copy()

    # ── Fix inconsistent category names (same as reference) ──
    if "preferedordercat" in work.columns:
        work.loc[work["preferedordercat"] == "Mobile", "preferedordercat"] = "Mobile Phone"

    if "preferredpaymentmode" in work.columns:
        work.loc[work["preferredpaymentmode"] == "COD", "preferredpaymentmode"] = "Cash on Delivery"
        work.loc[work["preferredpaymentmode"] == "CC", "preferredpaymentmode"] = "Credit Card"

    # ── Encode remaining categoricals ────────────────────────
    encoders = {}
    for col in CATEGORICALS_TO_ENCODE:
        if col in work.columns:
            le = LabelEncoder()
            work[f"{col}_encoded"] = le.fit_transform(work[col].astype(str))
            encoders[col] = le

    # ── Build feature list ───────────────────────────────────
    encoded_cat_features = [f"{c}_encoded" for c in CATEGORICALS_TO_ENCODE if c in work.columns]
    feature_cols = NUMERIC_FEATURES + PRE_ENCODED_FEATURES + encoded_cat_features

    # Keep only columns that actually exist
    feature_cols = [c for c in feature_cols if c in work.columns]

    X = work[feature_cols].copy()
    y = work[TARGET].astype(int)

    # ── Fill any remaining NaN ───────────────────────────────
    for col in X.columns:
        if X[col].isna().any():
            X[col] = X[col].fillna(X[col].median())

    print(f"  🧮  Feature matrix: {X.shape[0]} rows × {X.shape[1]} features")
    print(f"  📋  Features: {feature_cols}")

    return X, y, encoders, feature_cols


# ════════════════════════════════════════════════════════════
# 3. TRAIN MODEL
# ════════════════════════════════════════════════════════════

def train_model(X: pd.DataFrame, y: pd.Series) -> tuple:
    """
    Train a Random Forest classifier with class-imbalance handling.
    Returns (model, scaler).
    """
    # ── Handle class imbalance ───────────────────────────────
    try:
        from imblearn.combine import SMOTETomek
        smt = SMOTETomek(random_state=42)
        X_res, y_res = smt.fit_resample(X, y)
        print(f"  ⚖️  SMOTETomek resampling: {len(X)} → {len(X_res)} rows")
    except ImportError:
        print("  ⚠️  imbalanced-learn not installed, skipping SMOTETomek")
        X_res, y_res = X, y

    # ── Train/test split ─────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X_res, y_res, test_size=0.30, random_state=42
    )

    # ── Scale features ───────────────────────────────────────
    scaler = MinMaxScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # ── Train Random Forest ──────────────────────────────────
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=15,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train_scaled, y_train)

    train_acc = model.score(X_train_scaled, y_train)
    test_acc = model.score(X_test_scaled, y_test)
    print(f"  🎯  Train accuracy: {train_acc:.4f}")
    print(f"  🎯  Test  accuracy: {test_acc:.4f}")

    return model, scaler


# ════════════════════════════════════════════════════════════
# 4. PREDICT FOR ALL CUSTOMERS
# ════════════════════════════════════════════════════════════

def predict_all(
    df: pd.DataFrame,
    model,
    scaler,
    encoders: dict,
    feature_cols: list,
) -> pd.DataFrame:
    """
    Run predictions for every row in the Silver data and return a
    DataFrame with columns:
        customerid, churn_probability, churn_prediction, risk_segment, prediction_time
    """
    work = df.copy()

    # ── Re-apply same categorical encoding ───────────────────
    if "preferedordercat" in work.columns:
        work.loc[work["preferedordercat"] == "Mobile", "preferedordercat"] = "Mobile Phone"
    if "preferredpaymentmode" in work.columns:
        work.loc[work["preferredpaymentmode"] == "COD", "preferredpaymentmode"] = "Cash on Delivery"
        work.loc[work["preferredpaymentmode"] == "CC", "preferredpaymentmode"] = "Credit Card"

    for col, le in encoders.items():
        if col in work.columns:
            # Handle unseen categories → assign -1, then clip to known range
            work[f"{col}_encoded"] = work[col].astype(str).apply(
                lambda x: le.transform([x])[0] if x in le.classes_ else -1
            )

    X_pred = work[feature_cols].copy()
    for col in X_pred.columns:
        if X_pred[col].isna().any():
            X_pred[col] = X_pred[col].fillna(X_pred[col].median())

    X_scaled = scaler.transform(X_pred)

    # ── Probabilities & predictions ──────────────────────────
    probas = model.predict_proba(X_scaled)[:, 1]  # P(churn=1)
    predictions = model.predict(X_scaled)

    # ── Risk segmentation ────────────────────────────────────
    def _risk_segment(p):
        if p > 0.75:
            return "High Risk"
        elif p >= 0.50:
            return "Medium Risk"
        return "Low Risk"

    now = datetime.now()

    result = pd.DataFrame({
        "customerid": work["customerid"].values,
        "churn_probability": np.round(probas, 4),
        "churn_prediction": predictions.astype(int),
        "risk_segment": [_risk_segment(p) for p in probas],
        "prediction_time": now,
    })

    # De-duplicate — keep the latest per customer
    result = result.drop_duplicates(subset="customerid", keep="last")

    print(f"  🔮  Predictions generated for {len(result):,} customers")
    high = (result["risk_segment"] == "High Risk").sum()
    med = (result["risk_segment"] == "Medium Risk").sum()
    low = (result["risk_segment"] == "Low Risk").sum()
    print(f"      High Risk: {high}  |  Medium Risk: {med}  |  Low Risk: {low}")

    return result


# ════════════════════════════════════════════════════════════
# 5. STORE PREDICTIONS IN GOLD
# ════════════════════════════════════════════════════════════

def create_predictions_table(engine) -> None:
    """Create gold.churn_predictions table if it doesn't exist."""
    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {GOLD_SCHEMA}.churn_predictions (
                customerid          VARCHAR PRIMARY KEY,
                churn_probability   FLOAT,
                churn_prediction    INTEGER,
                risk_segment        VARCHAR(20),
                prediction_time     TIMESTAMPTZ DEFAULT NOW()
            );
        """))
        conn.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_churn_pred_risk
                ON {GOLD_SCHEMA}.churn_predictions (risk_segment);
        """))


def store_predictions(engine, predictions_df: pd.DataFrame) -> None:
    """Write predictions to gold.churn_predictions (full replace)."""
    create_predictions_table(engine)

    with engine.begin() as conn:
        predictions_df.to_sql(
            "churn_predictions",
            con=conn,
            schema=GOLD_SCHEMA,
            if_exists="replace",
            index=False,
        )
    print(f"  💾  Stored {len(predictions_df):,} predictions in {GOLD_SCHEMA}.churn_predictions")


def log_audit(engine, run_id: str, input_rows: int, output_rows: int, error: str = None):
    """Write an audit log entry for this prediction run."""
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"INSERT INTO {BRONZE_SCHEMA}.etl_audit_log "
                    "(run_id, stage, input_rows, output_rows, error_summary) "
                    "VALUES (:run_id, :stage, :input_rows, :output_rows, :error_summary)"
                ),
                {
                    "run_id": run_id,
                    "stage": "churn_prediction",
                    "input_rows": int(input_rows),
                    "output_rows": int(output_rows),
                    "error_summary": error,
                },
            )
    except Exception:
        pass  # Don't fail pipeline if audit logging fails


# ════════════════════════════════════════════════════════════
# 6. MAIN PIPELINE
# ════════════════════════════════════════════════════════════

def run_pipeline(retrain: bool = True) -> None:
    """
    Full ML pipeline:
        1. Load from Silver
        2. Train model (or load saved)
        3. Predict for all customers
        4. Store to gold.churn_predictions
    """
    run_id = f"churn_predict_{uuid.uuid4()}"
    print("═" * 55)
    print("  🛡️  CHURN PREDICTION PIPELINE")
    print("═" * 55)

    engine = get_engine()
    ensure_schemas(engine)

    # ── 1. Load Silver data ──────────────────────────────────
    print("\n📦  Step 1: Loading Silver data...")
    silver_df = load_silver_data(engine)
    input_rows = len(silver_df)

    error_summary = None
    output_rows = 0

    try:
        # ── 2. Prepare features ──────────────────────────────
        print("\n🔧  Step 2: Preparing features...")
        X, y, encoders, feature_cols = prepare_features(silver_df)

        # ── 3. Train or load model ───────────────────────────
        if retrain or not MODEL_PATH.exists():
            print("\n🏋️  Step 3: Training Random Forest model...")
            model, scaler = train_model(X, y)

            # Save model + metadata
            joblib.dump(
                {
                    "model": model,
                    "scaler": scaler,
                    "encoders": encoders,
                    "feature_cols": feature_cols,
                },
                MODEL_PATH,
            )
            print(f"  💾  Model saved to {MODEL_PATH}")
        else:
            print("\n📂  Step 3: Loading saved model...")
            saved = joblib.load(MODEL_PATH)
            model = saved["model"]
            scaler = saved["scaler"]
            encoders = saved["encoders"]
            feature_cols = saved["feature_cols"]
            print(f"  ✅  Model loaded from {MODEL_PATH}")

        # ── 4. Predict ───────────────────────────────────────
        print("\n🔮  Step 4: Generating predictions...")
        predictions = predict_all(silver_df, model, scaler, encoders, feature_cols)
        output_rows = len(predictions)

        # ── 5. Store in Gold ─────────────────────────────────
        print("\n💾  Step 5: Storing predictions in Gold schema...")
        store_predictions(engine, predictions)

    except Exception as exc:
        error_summary = str(exc)
        print(f"\n  ❌  Pipeline failed: {error_summary}")
        raise

    finally:
        log_audit(engine, run_id, input_rows, output_rows, error_summary)
        engine.dispose()

    print("\n" + "═" * 55)
    print("  ✅  PIPELINE COMPLETE")
    print("═" * 55)


# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Churn Prediction Pipeline")
    parser.add_argument(
        "--predict",
        action="store_true",
        help="Predict only (load saved model, skip retraining)",
    )
    args = parser.parse_args()

    run_pipeline(retrain=not args.predict)
