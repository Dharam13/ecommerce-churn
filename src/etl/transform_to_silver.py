"""
Transform data from bronze.ecommerce_raw to silver.ecommerce_clean.

Sub-tasks:
1. Handle nulls by filling with median (numeric) with ffill/bfill fallback.
2. Label encoding for categoricals: PreferredLoginDevice, Gender, MaritalStatus.
3. Outlier clipping (IQR) for CashbackAmount, OrderCount.
4. Write audit log with run ID, input row count, output row count, and error summary.

Column names match bronze table (lowercase, no underscores): e.g. warehousetohome,
orderamounthikefromlastyear, hourspendonapp, daysincelastorder, couponused,
preferredlogindevice, maritalstatus, cashbackamount, ordercount.
"""

import os
import uuid

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.db.connection import get_engine, ensure_schemas


# Exact column names as they appear in bronze.ecommerce_raw (from Excel load).
NUMERIC_NULL_COLS = [
    "tenure",
    "warehousetohome",
    "orderamounthikefromlastyear",
    "hourspendonapp",
    "daysincelastorder",
    "couponused",
    "ordercount",
]

# Exact column names as they appear in bronze.ecommerce_raw (from Excel load).
CATEGORICAL_COLS = [
    "preferredlogindevice",
    "gender",
    "maritalstatus",
]

OUTLIER_COLS = [
    "cashbackamount",
    "ordercount",
]


def _impute_nulls(df: pd.DataFrame) -> pd.DataFrame:
    """Fill numeric nulls with median; if still null, ffill then bfill."""
    for col in NUMERIC_NULL_COLS:
        if col not in df.columns:
            continue

        median_val = df[col].median()
        df[col] = df[col].fillna(median_val)

        # If still null (e.g., column is all NaN), fill from neighbors.
        df[col] = df[col].ffill().bfill()

    return df


def _encode_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    for col in CATEGORICAL_COLS:
        if col in df.columns:
            df[col] = df[col].astype("category")
            df[f"{col}_encoded"] = df[col].cat.codes.replace({-1: np.nan})
    return df


def _clip_outliers(df: pd.DataFrame) -> pd.DataFrame:
    for col in OUTLIER_COLS:
        if col in df.columns:
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            df[col] = df[col].clip(lower=lower, upper=upper)
    return df


def transform_bronze_to_silver() -> None:
    run_id = f"silver_transform_{uuid.uuid4()}"

    engine = get_engine()
    ensure_schemas(engine)

    bronze_schema = os.getenv("BRONZE_SCHEMA", "bronze")
    silver_schema = os.getenv("SILVER_SCHEMA", "silver")

    with engine.begin() as conn:
        df = pd.read_sql(
            sql=text(f"SELECT * FROM {bronze_schema}.ecommerce_raw"),
            con=conn,
        )

    input_rows = len(df)
    error_summary = None
    output_rows = 0

    try:
        df = _impute_nulls(df)
        df = _encode_categoricals(df)
        df = _clip_outliers(df)

        with engine.begin() as conn:
            df.to_sql(
                "ecommerce_clean",
                con=conn,
                schema=silver_schema,
                if_exists="replace",
                index=False,
            )
            output_rows = len(df)
    except Exception as exc:  # noqa: BLE001
        error_summary = str(exc)

    # Write audit log
    with engine.begin() as conn:
        conn.execute(
            text(
                f"INSERT INTO {bronze_schema}.etl_audit_log "
                "(run_id, stage, input_rows, output_rows, error_summary) "
                "VALUES (:run_id, :stage, :input_rows, :output_rows, :error_summary)"
            ),
            {
                "run_id": run_id,
                "stage": "silver_transform",
                "input_rows": int(input_rows),
                "output_rows": int(output_rows),
                "error_summary": error_summary,
            },
        )

    if error_summary:
        raise RuntimeError(f"Silver transform failed: {error_summary}")


if __name__ == "__main__":
    transform_bronze_to_silver()
