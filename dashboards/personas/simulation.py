"""
personas/simulation.py
══════════════════════
Simulation page — run real-time simulations from the dashboard.

Two modes:
  1. Simulate Activity  — update a random customer's behaviour
  2. Simulate New User  — add a brand-new customer end-to-end
"""

import os
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
    color = RISK_COLORS.get(segment, "#6B7280")
    bg = RISK_BG_COLORS.get(segment, "#F3F4F6")
    return (
        f'<span style="background:{bg};color:{color};padding:4px 14px;'
        f'border-radius:100px;font-size:0.75rem;font-weight:700;'
        f'letter-spacing:0.3px;">{segment}</span>'
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

    card_style = (
        f"background:{PALETTE['card_bg']};"
        f"border:1px solid {PALETTE['card_border']};"
        f"border-left:4px solid {accent};"
        f"border-radius:10px;"
        f"padding:1.25rem 1.5rem;"
        f"box-shadow:0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);"
    )
    label_style = (
        f"color:{PALETTE['text_muted']};font-size:0.68rem;font-weight:700;"
        f"text-transform:uppercase;letter-spacing:0.8px;margin-bottom:0.5rem;"
    )
    html = (
        f'<div style="{card_style}">'
        f'<div style="{label_style}">{title}</div>'
        f'<div style="display:flex;align-items:center;gap:1rem;margin-bottom:0.75rem;">'
        f'<span style="font-size:1.75rem;font-weight:800;color:{PALETTE["text"]};letter-spacing:-0.5px;">{prob_pct:.1f}%</span>'
        f'{badge}'
        f'</div>'
        f'<div style="background:{PALETTE["card_border"]};border-radius:6px;height:8px;overflow:hidden;">'
        f'<div style="width:{prob_pct}%;height:100%;background:{bar_color};border-radius:6px;transition:width 0.4s ease;"></div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_simulation_dashboard(df: pd.DataFrame):
    """Render the simulation page with two modes."""
    persona_header(
        title="Simulation Lab",
        subtitle="Run real-time simulations — test how behaviour changes affect churn predictions",
        accent_color=PALETTE["info"],
    )

    tab1, tab2, tab3 = st.tabs(["Simulate Activity", "New Customer", "Retention Message"])

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
                        f"<p style='color:{PALETTE['accent']};font-weight:700;margin-top:1rem;'>"
                        f"✓ Churn risk decreased by {abs(delta)*100:.1f}pp after the activity update.</p>",
                        unsafe_allow_html=True,
                    )
                elif delta > 0.05:
                    st.markdown(
                        f"<p style='color:{PALETTE['secondary']};font-weight:700;margin-top:1rem;'>"
                        f"⚠ Churn risk increased by {delta*100:.1f}pp — this customer may need attention.</p>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"<p style='color:{PALETTE['text_muted']};font-weight:600;margin-top:1rem;'>"
                        f"― Churn risk remained stable (delta: {delta*100:+.1f}pp).</p>",
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

    # ════════════════════════════════════════════════════════
    # TAB 3: RETENTION MESSAGE (GEMINI AI)
    # ════════════════════════════════════════════════════════
    with tab3:
        section_header(
            "AI Retention Message Generator",
            "Select a customer to generate a personalised retention message using Gemini AI. "
            "High-risk customers receive discount offers, medium-risk get engagement messages.",
        )

        # Build customer options with risk info
        cust_risk = df.drop_duplicates("customerid")[["customerid", "risk_segment", "churn_probability"]].copy()
        cust_risk = cust_risk.sort_values("churn_probability", ascending=False)

        # Customer selector
        col_sel, col_info = st.columns([3, 2])
        with col_sel:
            options = cust_risk["customerid"].tolist()
            selected_cust = st.selectbox(
                "Select Customer ID",
                options=options,
                key="retention_cust_id",
            )

        # Show selected customer's risk info
        if selected_cust:
            cust_row = cust_risk[cust_risk["customerid"] == selected_cust].iloc[0]
            risk_seg = cust_row["risk_segment"]
            churn_prob = cust_row["churn_probability"]

            with col_info:
                st.markdown("<div style='height:1.7rem;'></div>", unsafe_allow_html=True)
                badge = _risk_badge(risk_seg)
                st.markdown(
                    f"<div style='display:flex;align-items:center;gap:0.75rem;'>"
                    f"<span style='color:{PALETTE['text_muted']};font-size:0.82rem;'>"
                    f"Churn: <b>{churn_prob*100:.1f}%</b></span>"
                    f"{badge}</div>",
                    unsafe_allow_html=True,
                )

            # Customer profile summary
            cust_full = df[df["customerid"] == selected_cust].iloc[0]
            profile_cols = st.columns(5)
            profile_fields = [
                ("Tenure", cust_full.get("tenure", "?")),
                ("Orders", cust_full.get("ordercount", "?")),
                ("Satisfaction", cust_full.get("satisfactionscore", "?")),
                ("Complaint", "Yes" if cust_full.get("complain", 0) == 1 else "No"),
                ("Days Since Order", cust_full.get("daysincelastorder", "?")),
            ]
            for col, (label, val) in zip(profile_cols, profile_fields):
                col.metric(label, val)

            st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)

            # Generate button
            generate_btn = st.button(
                "Generate Retention Message",
                key="btn_generate_retention",
                use_container_width=True,
                type="primary",
            )

            if generate_btn:
                with st.spinner("Generating message with Gemini AI..."):
                    message = _generate_retention_message(cust_full, risk_seg, churn_prob)

                if message:
                    # Styled message card
                    if risk_seg == "High Risk":
                        border_color = RISK_COLORS["High Risk"]
                        msg_label = "DISCOUNT OFFER"
                    elif risk_seg == "Medium Risk":
                        border_color = RISK_COLORS["Medium Risk"]
                        msg_label = "RETENTION MESSAGE"
                    else:
                        border_color = RISK_COLORS["Low Risk"]
                        msg_label = "APPRECIATION MESSAGE"

                    msg_card_style = (
                        f"background:{PALETTE['card_bg']};"
                        f"border:1px solid {PALETTE['card_border']};"
                        f"border-left:5px solid {border_color};"
                        f"border-radius:10px;"
                        f"padding:1.5rem 1.75rem;"
                        f"margin-top:1rem;"
                        f"box-shadow:0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);"
                    )
                    msg_html = (
                        f'<div style="{msg_card_style}">'
                        f'<div style="color:{border_color};font-size:0.65rem;font-weight:800;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:0.75rem;">{msg_label}</div>'
                        f'<div style="color:{PALETTE["text_secondary"]};font-size:0.9rem;line-height:1.7;">{message}</div>'
                        f'</div>'
                    )
                    st.markdown(msg_html, unsafe_allow_html=True)
                else:
                    st.error("Failed to generate message. Check your GEMINI_API_KEY in .env")


def _generate_retention_message(customer_data, risk_segment: str, churn_prob: float) -> str:
    """
    Use Gemini API to generate a personalised retention message.
    """
    from dotenv import load_dotenv
    load_dotenv(_PROJECT_ROOT / ".env")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    # Build customer context
    tenure = customer_data.get("tenure", "unknown")
    orders = customer_data.get("ordercount", "unknown")
    satisfaction = customer_data.get("satisfactionscore", "unknown")
    complain = "yes" if customer_data.get("complain", 0) == 1 else "no"
    category = customer_data.get("preferedordercat", "unknown")
    days_since = customer_data.get("daysincelastorder", "unknown")
    gender = customer_data.get("gender", "unknown")
    payment = customer_data.get("preferredpaymentmode", "unknown")
    cashback = customer_data.get("cashbackamount", "unknown")

    if risk_segment == "High Risk":
        tone = (
            "This is a HIGH RISK customer about to churn. "
            "Write a compelling message offering an exclusive DISCOUNT or special offer "
            "to win them back. Include a specific percentage discount or cashback offer. "
            "Be urgent but respectful."
        )
    elif risk_segment == "Medium Risk":
        tone = (
            "This is a MEDIUM RISK customer showing signs of reduced engagement. "
            "Write a warm retention message encouraging them to return. "
            "Suggest products they might like based on their preferences. "
            "Be friendly and highlight what they're missing."
        )
    else:
        tone = (
            "This is a LOW RISK loyal customer. "
            "Write a short appreciation message thanking them for their loyalty. "
            "Make them feel valued."
        )

    prompt = f"""
You are an e-commerce retention marketing specialist. Generate a personalised customer retention
message based on the following customer profile:

- Customer tenure: {tenure} months
- Total orders: {orders}
- Satisfaction score: {satisfaction}/5
- Has complained: {complain}
- Preferred category: {category}
- Days since last order: {days_since}
- Gender: {gender}
- Preferred payment: {payment}
- Cashback amount: {cashback}
- Churn probability: {churn_prob*100:.1f}%
- Risk segment: {risk_segment}

{tone}

Keep the message under 150 words. Write it as if you are sending it directly to the customer
(use "you/your"). Do not include subject line or greeting prefix like "Dear Customer".
Start directly with the message content.
"""

    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        # Same model fallback order as the working chatbot
        models_to_try = [
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.0-flash-lite",
            "gemini-2.0-flash",
        ]
        last_error = None

        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                return response.text.strip()
            except Exception as e:
                last_error = e
                error_str = str(e).upper()
                if any(code in error_str for code in [
                    "RESOURCE_EXHAUSTED", "429", "NOT_FOUND", "404",
                ]):
                    continue
                raise e

        raise last_error
    except Exception as e:
        st.error(f"Gemini API error: {e}")
        return None
