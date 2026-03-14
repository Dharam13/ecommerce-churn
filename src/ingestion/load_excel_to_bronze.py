"""
Load the raw Excel dataset into the bronze Postgres schema.

Steps:
1. Read Excel from data/raw/ecommerce_dataset.xlsx with pandas.
2. Normalize column names to snake_case.
3. Write to Postgres table bronze.ecommerce_raw (append).
4. Log basic audit info into bronze.etl_audit_log.
"""

import os
import uuid

import pandas as pd
from sqlalchemy import text

from src.db.connection import get_engine, ensure_schemas


EXCEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "raw",
    "new_churn.xlsx",
)


def load_excel_to_bronze() -> None:
    run_id = f"bronze_load_{uuid.uuid4()}"

    engine = get_engine()
    ensure_schemas(engine)

    # Explicitly read the data sheet, not the data dictionary sheet.
    # Adjust sheet_name if your tab is named differently.
    df = pd.read_excel(EXCEL_PATH, sheet_name="E Comm", engine="openpyxl")
    input_rows = len(df)

    # Standardize column names to snake_case to match schema_init.sql
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("%", "pct")
        .str.replace("-", "_")
    )

    bronze_schema = os.getenv("BRONZE_SCHEMA", "bronze")
    table_name = "ecommerce_raw"
    error_summary = None
    output_rows = 0

    try:
        with engine.begin() as conn:
            df.to_sql(
                table_name,
                con=conn,
                schema=bronze_schema,
                if_exists="replace",
                index=False,
            )
            output_rows = input_rows
    except Exception as exc:  # noqa: BLE001
        error_summary = str(exc)

    # Write audit log
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO bronze.etl_audit_log
                    (run_id, stage, input_rows, output_rows, error_summary)
                VALUES
                    (:run_id, :stage, :input_rows, :output_rows, :error_summary)
                """
            ),
            {
                "run_id": run_id,
                "stage": "bronze_load",
                "input_rows": input_rows,
                "output_rows": output_rows,
                "error_summary": error_summary,
            },
        )

    if error_summary:
        raise RuntimeError(f"Bronze load failed: {error_summary}")


if __name__ == "__main__":
    load_excel_to_bronze()

