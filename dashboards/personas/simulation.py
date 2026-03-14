"""
personas/simulation.py
══════════════════════
Simulation page — run real-time simulations from the dashboard.

Two modes:
  1. Simulate Activity  — update a random customer's behaviour
  2. Simulate New User  — add a brand-new customer end-to-end
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Ensure project root is importable
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import PALETTE, RISK_COLORS, RISK_BG_COLORS
from components import kpi_card, section_header, persona_header


# Choice options for the new customer form
_LOGIN_DEVICES = ["Mobile Phone", "Computer", "Phone"]
_GENDERS = ["Male", "Female"]
_MARITAL_STATUSES = ["Single", "Married", "Divorced"]
_PAYMENT_MODES = ["Debit Card", "Credit Card", "E wallet", "UPI", "Cash on Delivery"]
_ORDER_CATS = ["Laptop & Accessory", "Mobile Phone", "Fashion", "Grocery", "Others"]


def _risk_badge(segment: str) -> str:
    """Return a styled badge HTML for a risk segment."""
    color = RISK_COLORS.get(segment, "#64748B")
    bg = RISK_BG_COLORS.get(segment, "#F1F5F9")
    return (
        f'<span style="background:{bg};color:{color};padding:4px 12px;'
        f'border-radius:100px;font-size:0.82rem;font-weight:600;">{segment}</span>'
    )


def _prediction_card(title: str, prediction: dict, accent: str):
    """Render a prediction result card."""
    if prediction is None:
        st.info("No prediction available")
        return

    prob = prediction.get("churn_probability", 0)
    seg = prediction.get("risk_segment", "Unknown")
    badge = _risk_badge(seg)

    prob_pct = prob * 100
    bar_color = RISK_COLORS.get(seg, PALETTE["primary"])

    st.markdown(f"""
    <div style="
        background:{PALETTE['card_bg']};
        border:1px solid {PALETTE['card_border']};
        border-left:4px solid {accent};
        border-radius:12px;
        padding:1.25rem 1.5rem;
        box-shadow:0 1px 3px rgba(0,0,0,0.04);
    ">
        <div style="color:{PALETTE['text_muted']};font-size:0.72rem;font-weight:600;
             text-transform:uppercase;letter-spacing:0.8px;margin-bottom:0.5rem;">
            {title}
        </div>
        <div style="display:flex;align-items:center;gap:1rem;margin-bottom:0.75rem;">
            <span style="font-size:1.75rem;font-weight:700;color:{PALETTE['text']};">
                {prob_pct:.1f}%
            </span>
            {badge}
        </div>
        <div style="background:{PALETTE['card_border']};border-radius:4px;height:8px;overflow:hidden;">
            <div style="width:{prob_pct}%;height:100%;background:{bar_color};
                 border-radius:4px;transition:width 0.3s ease;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_simulation_dashboard(df: pd.DataFrame):
    """Render the simulation page with two modes."""
    persona_header(
        title="Simulation Lab",
        subtitle="Run real-time simulations — test how behaviour changes affect churn predictions",
        accent_color=PALETTE["info"],
    )

    tab1, tab2 = st.tabs(["Simulate Activity", "New Customer"])

    # ════════════════════════════════════════════════════════
    # TAB 1: SIMULATE ACTIVITY UPDATE
    # ════════════════════════════════════════════════════════
    with tab1:
        section_header(
            "Simulate Customer Activity",
            "Pick a customer (or random) and simulate a new order. "
            "The pipeline updates bronze → silver → gold → re-predicts churn.",
        )

        col_id, col_btn = st.columns([3, 1])
        with col_id:
            customer_ids = sorted(df["customerid"].unique().tolist())
            selected_id = st.selectbox(
                "Customer ID (leave default for random)",
                options=["Random"] + [str(c) for c in customer_ids],
                key="sim_activity_id",
            )
        with col_btn:
            st.markdown("<div style='height:1.7rem;'></div>", unsafe_allow_html=True)
            run_activity = st.button("Run Simulation", key="btn_sim_activity",
                                     use_container_width=True, type="primary")

        if run_activity:
            cid = None if selected_id == "Random" else str(selected_id)

            with st.spinner("Running pipeline: bronze → silver → gold → predict..."):
                try:
                    from src.simulation.engine import simulate_activity
                    result = simulate_activity(customer_id=cid)
                except Exception as e:
                    st.error(f"Simulation failed: {e}")
                    return

            if "error" in result:
                st.error(result["error"])
                return

            st.success(f"Simulation complete for customer **{result['customer_id']}**")

            # Show changes
            section_header("Changes Applied", "What was updated in this simulation")
            changes = result.get("changes_applied", {})
            change_rows = []
            for field, change in changes.items():
                change_rows.append({"Field": field, "Change": change})
            st.dataframe(pd.DataFrame(change_rows), use_container_width=True, hide_index=True)

            # Before / After predictions
            st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                _prediction_card(
                    "Before Simulation",
                    result.get("before_prediction"),
                    PALETTE["text_muted"],
                )
            with c2:
                _prediction_card(
                    "After Simulation",
                    result.get("after_prediction"),
                    PALETTE["accent"],
                )

            # Interpretation
            before_p = result.get("before_prediction")
            after_p = result.get("after_prediction")
            if before_p and after_p:
                delta = after_p["churn_probability"] - before_p["churn_probability"]
                if delta < -0.05:
                    st.markdown(
                        f"<p style='color:{PALETTE['accent']};font-weight:600;margin-top:1rem;'>"
                        f"Churn risk decreased by {abs(delta)*100:.1f}pp after the activity update.</p>",
                        unsafe_allow_html=True,
                    )
                elif delta > 0.05:
                    st.markdown(
                        f"<p style='color:{PALETTE['secondary']};font-weight:600;margin-top:1rem;'>"
                        f"Churn risk increased by {delta*100:.1f}pp — this customer may need attention.</p>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"<p style='color:{PALETTE['text_muted']};font-weight:600;margin-top:1rem;'>"
                        f"Churn risk remained stable (delta: {delta*100:+.1f}pp).</p>",
                        unsafe_allow_html=True,
                    )

    # ════════════════════════════════════════════════════════
    # TAB 2: SIMULATE NEW CUSTOMER
    # ════════════════════════════════════════════════════════
    with tab2:
        section_header(
            "Add New Customer",
            "Fill in customer details and run the full pipeline: "
            "bronze insert → ETL → gold → churn prediction.",
        )

        with st.form("new_customer_form"):
            st.markdown(
                f"<p style='color:{PALETTE['text_muted']};font-size:0.8rem;'>"
                "Fill in what you'd like — empty fields will be randomised.</p>",
                unsafe_allow_html=True,
            )

            r1c1, r1c2, r1c3, r1c4 = st.columns(4)
            with r1c1:
                gender = st.selectbox("Gender", _GENDERS, key="new_gender")
            with r1c2:
                marital = st.selectbox("Marital Status", _MARITAL_STATUSES, key="new_marital")
            with r1c3:
                city_tier = st.selectbox("City Tier", [1, 2, 3], key="new_city")
            with r1c4:
                login_dev = st.selectbox("Login Device", _LOGIN_DEVICES, key="new_device")

            r2c1, r2c2, r2c3, r2c4 = st.columns(4)
            with r2c1:
                tenure = st.number_input("Tenure (months)", min_value=0, max_value=60, value=6, key="new_tenure")
            with r2c2:
                order_count = st.number_input("Order Count", min_value=1, max_value=20, value=2, key="new_orders")
            with r2c3:
                satisfaction = st.slider("Satisfaction Score", 1, 5, 3, key="new_sat")
            with r2c4:
                complain = st.selectbox("Complain", [0, 1], key="new_complain")

            r3c1, r3c2, r3c3, r3c4 = st.columns(4)
            with r3c1:
                days_since = st.number_input("Days Since Last Order", 0, 60, 5, key="new_days")
            with r3c2:
                coupon = st.number_input("Coupons Used", 0, 10, 1, key="new_coupon")
            with r3c3:
                cashback = st.number_input("Cashback Amount", 0.0, 500.0, 150.0, key="new_cashback")
            with r3c4:
                payment = st.selectbox("Payment Mode", _PAYMENT_MODES, key="new_payment")

            r4c1, r4c2, r4c3, r4c4 = st.columns(4)
            with r4c1:
                order_cat = st.selectbox("Order Category", _ORDER_CATS, key="new_cat")
            with r4c2:
                warehouse = st.number_input("Warehouse to Home (km)", 5, 50, 15, key="new_wh")
            with r4c3:
                app_hours = st.number_input("Hours on App", 0.0, 6.0, 3.0, step=0.5, key="new_app")
            with r4c4:
                devices = st.number_input("Devices Registered", 1, 6, 3, key="new_devcount")

            submitted = st.form_submit_button("Add Customer & Predict", type="primary",
                                              use_container_width=True)

        if submitted:
            overrides = {
                "gender": gender,
                "maritalstatus": marital,
                "citytier": city_tier,
                "preferredlogindevice": login_dev,
                "tenure": tenure,
                "ordercount": order_count,
                "satisfactionscore": satisfaction,
                "complain": complain,
                "daysincelastorder": days_since,
                "couponused": coupon,
                "cashbackamount": cashback,
                "preferredpaymentmode": payment,
                "preferedordercat": order_cat,
                "warehousetohome": warehouse,
                "hourspendonapp": app_hours,
                "numberofdeviceregistered": devices,
            }

            with st.spinner("Inserting customer and running pipeline..."):
                try:
                    from src.simulation.engine import simulate_new_customer
                    result = simulate_new_customer(overrides=overrides)
                except Exception as e:
                    st.error(f"Simulation failed: {e}")
                    return

            st.success(f"New customer **{result['customer_id']}** added and processed")

            # Show customer data
            section_header("Customer Profile", f"Customer ID: {result['customer_id']}")
            cust_data = result.get("customer_data", {})
            display_data = {k: v for k, v in cust_data.items() if k != "customerid"}
            col_pairs = list(display_data.items())

            # Display as a clean 2-column key-value layout
            for i in range(0, len(col_pairs), 4):
                cols = st.columns(4)
                for j, col in enumerate(cols):
                    idx = i + j
                    if idx < len(col_pairs):
                        key, val = col_pairs[idx]
                        col.metric(key.replace("_", " ").title(), val)

            # Show prediction
            st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
            _prediction_card(
                "Churn Prediction (ML Model)",
                result.get("prediction"),
                PALETTE["primary"],
            )
