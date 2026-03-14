-- Create schemas
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- Bronze: raw ecommerce data (structure matches Excel; minimal typing assumptions)
CREATE TABLE IF NOT EXISTS bronze.ecommerce_raw (
    customerid              VARCHAR,
    churn                   BOOLEAN,
    tenure                  INTEGER,
    warehouse_to_home       INTEGER,
    order_amount_hike_from_last_year NUMERIC,
    hour_spend_on_app       NUMERIC,
    day_since_last_order    INTEGER,
    coupon_used             INTEGER,
    order_count             INTEGER,
    cashback_amount         NUMERIC,
    preferred_login_device  VARCHAR,
    gender                  VARCHAR,
    marital_status          VARCHAR,
    prefered_order_cat      VARCHAR,
    order_date              DATE,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- Bronze audit log
CREATE TABLE IF NOT EXISTS bronze.etl_audit_log (
    id              BIGSERIAL PRIMARY KEY,
    run_id          VARCHAR NOT NULL,
    stage           VARCHAR NOT NULL, -- e.g. 'bronze_load', 'silver_transform'
    input_rows      INTEGER,
    output_rows     INTEGER,
    error_summary   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Silver: cleaned ecommerce data
CREATE TABLE IF NOT EXISTS silver.ecommerce_clean (
    customerid              VARCHAR,
    churn                   BOOLEAN,
    tenure                  INTEGER,
    warehouse_to_home       INTEGER,
    order_amount_hike_from_last_year NUMERIC,
    hour_spend_on_app       NUMERIC,
    day_since_last_order    INTEGER,
    coupon_used             INTEGER,
    order_count             INTEGER,
    cashback_amount         NUMERIC,
    preferred_login_device  VARCHAR,
    gender                  VARCHAR,
    marital_status          VARCHAR,
    prefered_order_cat      VARCHAR,
    order_date              DATE,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

