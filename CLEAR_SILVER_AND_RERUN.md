# Clear Silver and Re-run ETL

## How to remove wrong data from `silver.ecommerce_clean` and reload from bronze

### Option 1: Just re-run the ETL (recommended)

The transform script **replaces** the silver table every time (`if_exists="replace"`). So you do **not** need to delete anything manually.

1. From project root `ecommerce_churn`, with your venv active:
   ```powershell
   python -m src.etl.transform_to_silver
   ```
2. This will:
   - Read from `bronze.ecommerce_raw`
   - Fill numeric nulls with median (with ffill/bfill fallback)
   - Encode categoricals and clip outliers
   - **Overwrite** `silver.ecommerce_clean` with the new result

### Option 2: Manually clear silver first, then run ETL

If you want to empty the silver table before re-running (e.g. for auditing or to ensure a clean state):

1. **In pgAdmin** (Query Tool on database `ecommerce_churn`), run:
   ```sql
   TRUNCATE TABLE silver.ecommerce_clean;
   ```
   Or to drop and recreate the table:
   ```sql
   DROP TABLE IF EXISTS silver.ecommerce_clean;
   ```
   (The next ETL run will recreate it via `to_sql(..., if_exists="replace")`.)

2. **Then run the ETL** from the project folder:
   ```powershell
   python -m src.etl.transform_to_silver
   ```

### Verify

After re-running, check row counts and nulls:

```powershell
python -m src.etl.compare_bronze_silver
```

You should see:
- `silver.ecommerce_clean` with **no nulls** in key numeric columns (and `ordercount`), due to median filling
- Same row count as bronze (no dropping)
- `preferredlogindevice_encoded`, `gender_encoded`, `maritalstatus_encoded` present
- Outlier clipping applied to `cashbackamount` and `ordercount`
