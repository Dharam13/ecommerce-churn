"""
Database Setup Script
Creates the churn_db database, tables, and seeds sample data for the
E-Commerce Customer Churn Prediction & Retention Dashboard.

Run this script ONCE before launching the Streamlit dashboard.
"""

import random
import datetime
from sqlalchemy import create_engine, text

# ──────────────────────────────────────────────
# Configuration — imported from config.py
# ──────────────────────────────────────────────
from config import DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME

NUM_CUSTOMERS = 800  # number of synthetic customers


def create_database():
    """Create the churn_db database if it doesn't exist."""
    engine = create_engine(
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres",
        isolation_level="AUTOCOMMIT",
    )
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :db"), {"db": DB_NAME}
        )
        if not result.fetchone():
            conn.execute(text(f'CREATE DATABASE "{DB_NAME}"'))
            print(f"✅  Database '{DB_NAME}' created.")
        else:
            print(f"ℹ️  Database '{DB_NAME}' already exists.")
    engine.dispose()


def create_tables(engine):
    """Create the three warehouse tables."""
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id    INTEGER PRIMARY KEY,
                tenure         INTEGER,
                gender         VARCHAR(10),
                marital_status VARCHAR(20),
                city_tier      INTEGER,
                preferred_login_device  VARCHAR(30),
                preferred_payment_mode  VARCHAR(30),
                number_of_address       INTEGER
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS customer_behavior (
                customer_id                    INTEGER PRIMARY KEY REFERENCES customers(customer_id),
                hour_spend_on_app              FLOAT,
                number_of_device_registered    INTEGER,
                prefered_order_cat             VARCHAR(40),
                order_count                    INTEGER,
                coupon_used                    INTEGER,
                cashback_amount                FLOAT,
                day_since_last_order           INTEGER,
                complain                       INTEGER,
                satisfaction_score             INTEGER,
                order_amount_hike_from_last_year FLOAT,
                warehouse_to_home              INTEGER
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS churn_predictions (
                customer_id       INTEGER PRIMARY KEY REFERENCES customers(customer_id),
                churn_probability  FLOAT,
                risk_segment       VARCHAR(20),
                prediction_time    TIMESTAMP
            );
        """))
    print("✅  Tables created.")


def _risk_segment(prob: float) -> str:
    if prob > 0.75:
        return "High Risk"
    elif prob >= 0.50:
        return "Medium Risk"
    return "Low Risk"


def seed_data(engine):
    """Insert synthetic but realistic data."""
    genders = ["Male", "Female"]
    marital = ["Single", "Married", "Divorced"]
    city_tiers = [1, 2, 3]
    login_devices = ["Mobile Phone", "Computer", "Phone"]
    payment_modes = ["Debit Card", "Credit Card", "UPI", "E Wallet", "Cash on Delivery"]
    order_cats = ["Laptop & Accessory", "Mobile Phone", "Fashion", "Grocery", "Others"]

    random.seed(42)

    customers_rows = []
    behavior_rows = []
    prediction_rows = []

    for cid in range(1, NUM_CUSTOMERS + 1):
        tenure = random.randint(0, 72)
        gender = random.choice(genders)
        marital_st = random.choice(marital)
        tier = random.choice(city_tiers)
        login_dev = random.choice(login_devices)
        pay_mode = random.choice(payment_modes)
        n_addr = random.randint(1, 10)

        customers_rows.append(dict(
            customer_id=cid, tenure=tenure, gender=gender,
            marital_status=marital_st, city_tier=tier,
            preferred_login_device=login_dev,
            preferred_payment_mode=pay_mode,
            number_of_address=n_addr,
        ))

        hours = round(random.uniform(0, 5), 1)
        devices = random.randint(1, 6)
        cat = random.choice(order_cats)
        orders = random.randint(1, 20)
        coupons = random.randint(0, 16)
        cashback = round(random.uniform(50, 350), 2)
        days_last = random.randint(0, 60)
        complain = random.choices([0, 1], weights=[0.7, 0.3])[0]
        sat = random.randint(1, 5)
        hike = round(random.uniform(11, 26), 1)
        wh_dist = random.randint(5, 40)

        behavior_rows.append(dict(
            customer_id=cid, hour_spend_on_app=hours,
            number_of_device_registered=devices,
            prefered_order_cat=cat, order_count=orders,
            coupon_used=coupons, cashback_amount=cashback,
            day_since_last_order=days_last, complain=complain,
            satisfaction_score=sat,
            order_amount_hike_from_last_year=hike,
            warehouse_to_home=wh_dist,
        ))

        # churn probability loosely correlated with complaints, low satisfaction,
        # inactivity
        base = 0.15
        if complain == 1:
            base += 0.25
        if sat <= 2:
            base += 0.20
        if days_last > 30:
            base += 0.15
        if orders <= 2:
            base += 0.10
        prob = min(round(base + random.uniform(-0.10, 0.10), 4), 1.0)
        prob = max(prob, 0.01)

        prediction_rows.append(dict(
            customer_id=cid,
            churn_probability=prob,
            risk_segment=_risk_segment(prob),
            prediction_time=datetime.datetime.now() - datetime.timedelta(
                minutes=random.randint(0, 1440)
            ),
        ))

    # Bulk insert
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE churn_predictions, customer_behavior, customers CASCADE"))

        for r in customers_rows:
            conn.execute(text("""
                INSERT INTO customers
                (customer_id, tenure, gender, marital_status, city_tier,
                 preferred_login_device, preferred_payment_mode, number_of_address)
                VALUES (:customer_id, :tenure, :gender, :marital_status, :city_tier,
                        :preferred_login_device, :preferred_payment_mode, :number_of_address)
            """), r)

        for r in behavior_rows:
            conn.execute(text("""
                INSERT INTO customer_behavior
                (customer_id, hour_spend_on_app, number_of_device_registered,
                 prefered_order_cat, order_count, coupon_used, cashback_amount,
                 day_since_last_order, complain, satisfaction_score,
                 order_amount_hike_from_last_year, warehouse_to_home)
                VALUES (:customer_id, :hour_spend_on_app, :number_of_device_registered,
                        :prefered_order_cat, :order_count, :coupon_used, :cashback_amount,
                        :day_since_last_order, :complain, :satisfaction_score,
                        :order_amount_hike_from_last_year, :warehouse_to_home)
            """), r)

        for r in prediction_rows:
            conn.execute(text("""
                INSERT INTO churn_predictions
                (customer_id, churn_probability, risk_segment, prediction_time)
                VALUES (:customer_id, :churn_probability, :risk_segment, :prediction_time)
            """), r)

    print(f"✅  Seeded {NUM_CUSTOMERS} customers into all three tables.")


# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("🔧  Setting up churn_db …")
    create_database()
    engine = create_engine(
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    create_tables(engine)
    seed_data(engine)
    engine.dispose()
    print("🎉  Setup complete! Run the dashboard with:  streamlit run app.py")
