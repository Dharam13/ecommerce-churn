"""
Temporary diagnostics script to compare bronze and silver tables.

It will:
- Load bronze.ecommerce_raw and silver.ecommerce_clean into pandas.
- Print row counts for each.
- For each table, print per-column null counts and null percentages.
- For columns shared between both tables, print basic stats comparison
  (min, max, mean for numeric; unique count for categoricals).
"""

import os

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.db.connection import get_engine


def describe_nulls(df: pd.DataFrame, name: str) -> None:
    print(f"\n=== NULL SUMMARY: {name} ===")
    null_counts = df.isna().sum()
    total = len(df)
    for col, cnt in null_counts.items():
        pct = (cnt / total * 100) if total else 0.0
        print(f"{col:30s}  nulls={cnt:6d}  ({pct:6.2f}%)")


def compare_shared_columns(bronze: pd.DataFrame, silver: pd.DataFrame) -> None:
    shared_cols = sorted(set(bronze.columns) & set(silver.columns))
    print(f"\n=== SHARED COLUMNS BETWEEN BRONZE & SILVER ({len(shared_cols)}) ===")
    for col in shared_cols:
        b = bronze[col]
        s = silver[col]
        print(f"\n--- Column: {col} ---")
        if pd.api.types.is_numeric_dtype(b) and pd.api.types.is_numeric_dtype(s):
            print(
                f"bronze: count={b.count()}, mean={b.mean():.3f}, "
                f"min={b.min()}, max={b.max()}"
            )
            print(
                f"silver: count={s.count()}, mean={s.mean():.3f}, "
                f"min={s.min()}, max={s.max()}"
            )
        else:
            print(
                f"bronze: non-null={b.count()}, unique={b.nunique(dropna=True)}"
            )
            print(
                f"silver: non-null={s.count()}, unique={s.nunique(dropna=True)}"
            )


def main() -> None:
    engine = get_engine()
    bronze_schema = os.getenv("BRONZE_SCHEMA", "bronze")
    silver_schema = os.getenv("SILVER_SCHEMA", "silver")

    with engine.begin() as conn:
        bronze_df = pd.read_sql(
            text(f"SELECT * FROM {bronze_schema}.ecommerce_raw"),
            con=conn,
        )
        silver_df = pd.read_sql(
            text(f"SELECT * FROM {silver_schema}.ecommerce_clean"),
            con=conn,
        )

    print("=== ROW COUNTS ===")
    print(f"bronze.ecommerce_raw   : {len(bronze_df)} rows")
    print(f"silver.ecommerce_clean : {len(silver_df)} rows")

    describe_nulls(bronze_df, "bronze.ecommerce_raw")
    describe_nulls(silver_df, "silver.ecommerce_clean")

    compare_shared_columns(bronze_df, silver_df)


if __name__ == "__main__":
    main()

