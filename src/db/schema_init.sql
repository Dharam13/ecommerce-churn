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

-- Gold: star schema dimensions and fact table

-- Customer dimension (simplified SCD Type 2 snapshot)
CREATE TABLE IF NOT EXISTS gold.dim_customer (
    customer_sk         BIGSERIAL PRIMARY KEY,
    customerid          VARCHAR NOT NULL,
    gender              VARCHAR,
    maritalstatus       VARCHAR,
    citytier            INTEGER,
    preferredlogindevice VARCHAR,
    tenure              INTEGER,
    warehousetohome     INTEGER,
    valid_from          DATE,
    valid_to            DATE,
    is_current          BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_dim_customer_customerid
    ON gold.dim_customer (customerid);

CREATE INDEX IF NOT EXISTS idx_dim_customer_is_current
    ON gold.dim_customer (is_current);

-- Product dimension (from PreferedOrderCat)
CREATE TABLE IF NOT EXISTS gold.dim_product (
    product_sk       BIGSERIAL PRIMARY KEY,
    preferedordercat VARCHAR NOT NULL
);

-- Location dimension (from CityTier / geo enrichment)
CREATE TABLE IF NOT EXISTS gold.dim_location (
    location_sk  BIGSERIAL PRIMARY KEY,
    citytier     INTEGER NOT NULL
);

-- Date dimension
CREATE TABLE IF NOT EXISTS gold.dim_date (
    date_sk     INTEGER PRIMARY KEY,
    date        DATE NOT NULL,
    year        INTEGER,
    month       INTEGER,
    day         INTEGER,
    week        INTEGER,
    is_weekend  BOOLEAN
);

-- Orders fact table
CREATE TABLE IF NOT EXISTS gold.fact_orders (
    order_sk                     BIGSERIAL PRIMARY KEY,
    customer_sk                  BIGINT REFERENCES gold.dim_customer(customer_sk),
    product_sk                   BIGINT REFERENCES gold.dim_product(product_sk),
    date_sk                      INTEGER REFERENCES gold.dim_date(date_sk),
    location_sk                  BIGINT REFERENCES gold.dim_location(location_sk),
    ordercount                   NUMERIC,
    couponused                   NUMERIC,
    cashbackamount               NUMERIC,
    orderamounthikefromlastyear  NUMERIC,
    churn                        BOOLEAN,
    complain                     INTEGER
);

CREATE INDEX IF NOT EXISTS idx_fact_orders_customer_sk
    ON gold.fact_orders (customer_sk);

CREATE INDEX IF NOT EXISTS idx_fact_orders_churn
    ON gold.fact_orders (churn);

CREATE INDEX IF NOT EXISTS idx_fact_orders_date_sk
    ON gold.fact_orders (date_sk);

-- Churn predictions (from ML model)
CREATE TABLE IF NOT EXISTS gold.churn_predictions (
    customerid          VARCHAR PRIMARY KEY,
    churn_probability   FLOAT,
    churn_prediction    INTEGER,
    risk_segment        VARCHAR(20),
    prediction_time     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_churn_pred_risk
    ON gold.churn_predictions (risk_segment);

