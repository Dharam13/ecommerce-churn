"""
app.py — ChurnGuard Entry Point
════════════════════════════════
E-Commerce Customer Churn Prediction & Retention Dashboard.

Reads from a PostgreSQL Data Warehouse using a Bronze → Silver → Gold
star schema.  DB credentials come from the project's .env file.

Slim orchestrator that wires together:
  config       → palettes, thresholds, schema names (from .env)
  database     → connect_db(), load_data()  (Gold + Silver enrichment)
  filters      → apply_filters()
  components   → reusable UI primitives
  personas/    → persona-specific dashboard views

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
)


# ════════════════════════════════════════════════════════════════════
# PAGE CONFIG & GLOBAL CSS
# ════════════════════════════════════════════════════════════════════

def _inject_css():
    """Inject global custom styles once."""
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="st-"] {
            font-family: 'Inter', sans-serif;
        }

        /* Hide Streamlit default chrome */
        #MainMenu {visibility: hidden;}
        footer    {visibility: hidden;}
        header    {visibility: hidden;}

        /* Sidebar */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #13151A 0%, #1A1D23 100%);
            border-right: 1px solid rgba(108,99,255,0.12);
        }

        /* Dataframe corners */
        [data-testid="stDataFrame"] {
            border-radius: 12px;
            overflow: hidden;
        }

        /* Metrics */
        [data-testid="stMetric"] {
            background: #1A1D23;
            border-radius: 12px;
            padding: 1rem;
        }

        /* Custom scrollbar */
        ::-webkit-scrollbar       { width: 6px; }
        ::-webkit-scrollbar-track { background: #0E1117; }
        ::-webkit-scrollbar-thumb { background: #6C63FF; border-radius: 3px; }
    </style>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════════

def _render_sidebar() -> str:
    """Draw the branding + persona selector and return the chosen persona."""
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center;padding:1rem 0 1.5rem;">
            <div style="font-size:2.8rem;">🛡️</div>
            <h2 style="margin:0.3rem 0 0;color:{PALETTE['primary']};font-weight:700;">
                ChurnGuard
            </h2>
            <p style="color:#9CA3AF;font-size:0.8rem;margin:0;">
                E-Commerce Retention Intelligence
            </p>
            <p style="color:#6B7280;font-size:0.65rem;margin:0.3rem 0 0;">
                Gold Star Schema · PostgreSQL DW
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        persona = st.selectbox(
            "🎭  Select Persona",
            ["Marketing Manager", "Customer Success / Support", "Product Team"],
            key="persona_selector",
        )

        st.markdown("---")
        st.markdown(
            "<p style='color:#9CA3AF;font-size:0.75rem;'>FILTERS</p>",
            unsafe_allow_html=True,
        )

    return persona


# ════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="ChurnGuard – E-Commerce Churn Dashboard",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    _inject_css()

    persona = _render_sidebar()

    # ── Load data from Gold + Silver ─────────────────────────
    try:
        raw_df = load_data()
    except Exception as e:
        st.error(
            f"⚠️  **Database Connection Error**\n\n"
            f"Could not connect to PostgreSQL or load data.\n\n"
            f"```\n{e}\n```\n\n"
            f"Make sure PostgreSQL is running and the Gold schema is populated.\n\n"
            f"1. Check `.env` has the correct `DATABASE_URL`\n"
            f"2. Run the ETL pipeline: `python -m src.etl.build_gold_schema`"
        )
        st.stop()

    # ── Apply sidebar filters ────────────────────────────────
    df = apply_filters(raw_df)

    if df.empty:
        st.warning("No data matches the current filters. Please adjust the sidebar filters.")
        st.stop()

    # ── Render persona dashboard ─────────────────────────────
    if persona == "Marketing Manager":
        render_marketing_dashboard(df)
    elif persona == "Customer Success / Support":
        render_support_dashboard(df)
    else:
        render_product_dashboard(df)

    # ── Shared risk segmentation ─────────────────────────────
    st.markdown("---")
    render_risk_overview(df)

    # ── Footer ───────────────────────────────────────────────
    st.markdown("""
    <div style="text-align:center;padding:2rem 0 1rem;color:#6B7280;font-size:0.75rem;">
        ChurnGuard v2.0  ·  Gold Star Schema  ·  Powered by Streamlit &amp; PostgreSQL
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
