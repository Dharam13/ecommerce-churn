"""
Build the Gold star schema from the Silver layer.

Reads from:
    silver.ecommerce_clean

Populates:
    gold.dim_customer
    gold.dim_product
    gold.dim_location
    gold.dim_date
    gold.fact_orders

Notes:
- Column names follow the cleaned silver table (lowercase, no underscores),
  e.g. customerid, citytier, preferedordercat, warehousetohome, ordercount, etc.
- For simplicity this is a snapshot load: all gold tables are rebuilt from silver
  on each run (idempotent daily batch).
"""

import os
import uuid
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.db.connection import get_engine, ensure_schemas


def _build_dim_customer(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "customerid",
        "gender",
        "maritalstatus",
        "citytier",
        "preferredlogindevice",
        "tenure",
        "warehousetohome",
    ]
    dim = df[cols].drop_duplicates("customerid").reset_index(drop=True)
    dim.insert(0, "customer_sk", np.arange(1, len(dim) + 1, dtype="int64"))

    today = date.today()
    dim["valid_from"] = today
    dim["valid_to"] = pd.NaT
    dim["is_current"] = True
    return dim


def _build_dim_product(df: pd.DataFrame) -> pd.DataFrame:
    dim = (
        df[["preferedordercat"]]
        .drop_duplicates("preferedordercat")
        .reset_index(drop=True)
    )
    dim.insert(0, "product_sk", np.arange(1, len(dim) + 1, dtype="int64"))
    return dim


def _build_dim_location(df: pd.DataFrame) -> pd.DataFrame:
    dim = df[["citytier"]].drop_duplicates("citytier").reset_index(drop=True)
    dim.insert(0, "location_sk", np.arange(1, len(dim) + 1, dtype="int64"))
    return dim


def _derive_order_date(df: pd.DataFrame) -> pd.Series:
    """
    Derive an order_date from daysincelastorder.

    Assumption: each row represents the latest snapshot for that customer,
    so we back-calculate the last order date as (today - daysincelastorder).
    """
    today = date.today()
    if "daysincelastorder" not in df.columns:
        return pd.Series([today] * len(df), name="order_date")

    return pd.to_datetime(
        [today - timedelta(days=int(d)) for d in df["daysincelastorder"]]
    ).rename("order_date")


def _build_dim_date(order_dates: pd.Series) -> pd.DataFrame:
    # Ensure we end up with a normalized datetime *Series* (not DatetimeIndex)
    order_dates = pd.to_datetime(order_dates)
    if isinstance(order_dates, pd.DatetimeIndex):
        order_dates = pd.Series(order_dates, name="date")
    order_dates = order_dates.dt.normalize()

    dim = (
        order_dates.drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
        .to_frame(name="date")
    )
    dim["date_sk"] = dim["date"].dt.strftime("%Y%m%d").astype(int)
    dim["year"] = dim["date"].dt.year
    dim["month"] = dim["date"].dt.month
    dim["day"] = dim["date"].dt.day
    dim["week"] = dim["date"].dt.isocalendar().week.astype(int)
    dim["is_weekend"] = dim["date"].dt.weekday >= 5
    return dim[
        ["date_sk", "date", "year", "month", "day", "week", "is_weekend"]
    ]


def build_gold_from_silver() -> None:
    run_id = f"gold_load_{uuid.uuid4()}"

    engine = get_engine()
    ensure_schemas(engine)

    bronze_schema = os.getenv("BRONZE_SCHEMA", "bronze")
    silver_schema = os.getenv("SILVER_SCHEMA", "silver")
    gold_schema = os.getenv("GOLD_SCHEMA", "gold")

    with engine.begin() as conn:
        silver_df = pd.read_sql(
            sql=text(f"SELECT * FROM {silver_schema}.ecommerce_clean"),
            con=conn,
        )

    input_rows = len(silver_df)
    error_summary: str | None = None
    fact_rows = 0

    try:
        # Build dimensions in-memory
        dim_customer = _build_dim_customer(silver_df)
        dim_product = _build_dim_product(silver_df)
        dim_location = _build_dim_location(silver_df)

        order_dates = _derive_order_date(silver_df)
        silver_df["order_date"] = order_dates
        dim_date = _build_dim_date(order_dates)

        # Write dimensions (replace snapshot)
        with engine.begin() as conn:
            dim_customer.to_sql(
                "dim_customer",
                con=conn,
                schema=gold_schema,
                if_exists="replace",
                index=False,
            )
            dim_product.to_sql(
                "dim_product",
                con=conn,
                schema=gold_schema,
                if_exists="replace",
                index=False,
            )
            dim_location.to_sql(
                "dim_location",
                con=conn,
                schema=gold_schema,
                if_exists="replace",
                index=False,
            )
            dim_date.to_sql(
                "dim_date",
                con=conn,
                schema=gold_schema,
                if_exists="replace",
                index=False,
            )

        # Build mapping from business keys to surrogate keys
        customer_map = dim_customer.set_index("customerid")["customer_sk"]
        product_map = dim_product.set_index("preferedordercat")["product_sk"]
        location_map = dim_location.set_index("citytier")["location_sk"]
        date_map = dim_date.set_index("date")["date_sk"]

        silver_df["customer_sk"] = silver_df["customerid"].map(customer_map)
        silver_df["product_sk"] = silver_df["preferedordercat"].map(product_map)
        silver_df["location_sk"] = silver_df["citytier"].map(location_map)
        silver_df["date_sk"] = silver_df["order_date"].map(date_map)

        fact_cols = [
            "customer_sk",
            "product_sk",
            "date_sk",
            "location_sk",
            "ordercount",
            "couponused",
            "cashbackamount",
            "orderamounthikefromlastyear",
            "churn",
            "complain",
        ]
        fact_df = silver_df[fact_cols].copy()

        with engine.begin() as conn:
            fact_df.to_sql(
                "fact_orders",
                con=conn,
                schema=gold_schema,
                if_exists="replace",
                index=False,
            )
            fact_rows = len(fact_df)

    except Exception as exc:  # noqa: BLE001
        error_summary = str(exc)

    # Audit log for gold load
    with engine.begin() as conn:
        conn.execute(
            text(
                f"INSERT INTO {bronze_schema}.etl_audit_log "
                "(run_id, stage, input_rows, output_rows, error_summary) "
                "VALUES (:run_id, :stage, :input_rows, :output_rows, :error_summary)"
            ),
            {
                "run_id": run_id,
                "stage": "gold_load",
                "input_rows": int(input_rows),
                "output_rows": int(fact_rows),
                "error_summary": error_summary,
            },
        )

    if error_summary:
        raise RuntimeError(f"Gold load failed: {error_summary}")


if __name__ == "__main__":
    build_gold_from_silver()

