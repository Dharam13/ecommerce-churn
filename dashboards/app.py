"""
app.py — ChurnGuard Entry Point
════════════════════════════════
E-Commerce Customer Churn Prediction & Retention Dashboard.

Run from the dashboards/ directory:
    streamlit run app.py
"""

import streamlit as st
from config import PALETTE
from database import load_data
from filters import apply_filters
from personas import (
    render_marketing_dashboard,
    render_support_dashboard,
    render_product_dashboard,
    render_risk_overview,
    render_simulation_dashboard,
)


# ════════════════════════════════════════════════════════════════════
# GLOBAL CSS
# ════════════════════════════════════════════════════════════════════

def _inject_css():
    """Inject professional light-theme styles."""
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="st-"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        #MainMenu {visibility: hidden;}
        footer    {visibility: hidden;}
        header    {visibility: hidden;}

        .stApp {
            background-color: #F8FAFC;
        }

        [data-testid="stAppViewContainer"] {
            background-color: #F8FAFC;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #FFFFFF, #F1F5F9);
            border-right: 1px solid #E2E8F0;
        }

        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
            color: #475569;
        }

        [data-testid="stDataFrame"] {
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #E2E8F0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }

        [data-testid="stPlotlyChart"] {
            background: #FFFFFF;
            border-radius: 12px;
            border: 1px solid #E2E8F0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            padding: 0.5rem;
        }

        hr {
            border: none;
            border-top: 1px solid #E2E8F0;
            margin: 2rem 0;
        }

        [data-testid="stAlert"] {
            border-radius: 10px;
            font-size: 0.82rem;
        }

        ::-webkit-scrollbar       { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #F1F5F9; }
        ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #94A3B8; }
    </style>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════════

def _render_sidebar() -> str:
    """Draw the persona selector and filters, return the chosen persona."""
    with st.sidebar:
        st.markdown(f"""
        <div style="padding:0.75rem 0 1rem;">
            <h3 style="
                margin:0;
                color:{PALETTE['text']};
                font-weight:700;
                font-size:1.1rem;
                letter-spacing:-0.3px;
            ">Churn Dashboard</h3>
            <p style="
                color:{PALETTE['text_muted']};
                font-size:0.72rem;
                margin:0.15rem 0 0;
                font-weight:500;
            ">E-Commerce Retention Analytics</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        persona = st.selectbox(
            "Persona",
            ["Marketing Manager", "Customer Success / Support", "Product Team", "Simulation Lab"],
            key="persona_selector",
        )

        st.markdown("---")
        st.markdown(
            f"<p style='color:{PALETTE['text_muted']};font-size:0.7rem;"
            f"font-weight:600;text-transform:uppercase;letter-spacing:1px;'>"
            f"Filters</p>",
            unsafe_allow_html=True,
        )

    return persona


# ════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="E-Commerce Churn Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    _inject_css()

    persona = _render_sidebar()

    try:
        raw_df = load_data()
    except Exception as e:
        st.error(
            f"**Database Connection Error**\n\n"
            f"Could not connect to PostgreSQL or load data.\n\n"
            f"```\n{e}\n```\n\n"
            f"Make sure PostgreSQL is running and the Gold schema is populated.\n\n"
            f"1. Check `.env` has the correct `DATABASE_URL`\n"
            f"2. Run the ETL pipeline: `python -m src.etl.build_gold_schema`"
        )
        st.stop()

    df = apply_filters(raw_df)

    if df.empty:
        st.warning("No data matches the current filters. Please adjust the sidebar filters.")
        st.stop()

    if persona == "Marketing Manager":
        render_marketing_dashboard(df)
    elif persona == "Customer Success / Support":
        render_support_dashboard(df)
    elif persona == "Simulation Lab":
        render_simulation_dashboard(df)
    else:
        render_product_dashboard(df)

    # Show risk overview for analytics personas only
    if persona != "Simulation Lab":
        st.markdown("---")
        render_risk_overview(df)

    st.markdown(f"""
    <div style="
        text-align:center;
        padding:2.5rem 0 1.5rem;
        color:{PALETTE['text_light']};
        font-size:0.72rem;
        font-weight:500;
    ">
        Churn Dashboard v2.0 &nbsp;·&nbsp; Gold Star Schema &nbsp;·&nbsp;
        Powered by Streamlit &amp; PostgreSQL
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
