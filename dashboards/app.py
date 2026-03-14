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
    render_ai_insights,
)


# ════════════════════════════════════════════════════════════════════
# GLOBAL CSS — Industry-grade analytics dashboard styling
# ════════════════════════════════════════════════════════════════════

def _inject_css():
    """Inject professional light-theme styles inspired by Google Analytics / Datadog."""
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
        html, body, [class*="st-"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
        }
        #MainMenu {visibility: hidden;}
        footer    {visibility: hidden;}
        header    {visibility: hidden;}
        .stApp, [data-testid="stAppViewContainer"] {
            background-color: #F3F4F6;
        }
        [data-testid="stAppViewContainer"] > section {
            padding-top: 130px !important;
        }
        /* Fixed header styles - full width over sidebar */
        .fixed-header {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            right: 0 !important;
            width: 100vw !important;
            z-index: 999999 !important;
            background: #FFFFFF;
            border-bottom: 1px solid #E5E7EB;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        [data-testid="stSidebar"] {
            background: #FFFFFF;
            border-right: 1px solid #E5E7EB;
            box-shadow: 2px 0 8px rgba(0,0,0,0.03);
            padding-top: 130px !important;
            margin-top: 0 !important;
        }
        [data-testid="stSidebar"] > div:first-child {
            padding-top: 130px !important;
        }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
            color: #6B7280;
            font-size: 0.82rem;
        }
        [data-testid="stSidebar"] .stSelectbox label,
        [data-testid="stSidebar"] .stMultiSelect label {
            font-size: 0.72rem !important;
            font-weight: 600 !important;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #9CA3AF !important;
        }
        [data-testid="stDataFrame"] {
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid #E5E7EB;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }
        [data-testid="stPlotlyChart"] {
            background: #FFFFFF;
            border-radius: 10px;
            border: 1px solid #E5E7EB;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            padding: 0.35rem;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0;
            background: #FFFFFF;
            border-bottom: 2px solid #E5E7EB;
            border-radius: 10px 10px 0 0;
            padding: 0 0.5rem;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 0.75rem 1.25rem;
            font-size: 0.82rem;
            font-weight: 600;
            color: #6B7280;
            border-bottom: 2px solid transparent;
            margin-bottom: -2px;
            transition: all 0.2s ease;
        }
        .stTabs [data-baseweb="tab"]:hover {
            color: #2563EB;
            background: #EFF6FF;
        }
        .stTabs [aria-selected="true"] {
            color: #2563EB !important;
            border-bottom-color: #2563EB !important;
            font-weight: 700;
        }
        .stTabs [data-baseweb="tab-panel"] {
            padding: 1rem 0 0;
        }
        .stButton > button {
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.82rem;
            padding: 0.55rem 1.25rem;
            transition: all 0.2s ease;
            border: 1px solid #E5E7EB;
        }
        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(37,99,235,0.15);
        }
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #2563EB, #3B82F6);
            border: none;
            color: white;
        }
        hr {
            border: none;
            border-top: 1px solid #E5E7EB;
            margin: 1.5rem 0;
        }
        [data-testid="stAlert"] {
            border-radius: 10px;
            font-size: 0.82rem;
            border: 1px solid #E5E7EB;
        }
        [data-testid="stMetric"] {
            background: #FFFFFF;
            border-radius: 10px;
            padding: 0.75rem 1rem;
            border: 1px solid #E5E7EB;
            box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.7rem !important;
            font-weight: 600 !important;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #9CA3AF !important;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.3rem !important;
            font-weight: 800 !important;
            color: #111827 !important;
        }
        .stNumberInput, .stSelectbox {
            font-size: 0.85rem;
        }
        ::-webkit-scrollbar       { width: 5px; height: 5px; }
        ::-webkit-scrollbar-track { background: #F3F4F6; }
        ::-webkit-scrollbar-thumb { background: #D1D5DB; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #9CA3AF; }
        [data-testid="stExpander"] {
            background: #FFFFFF;
            border-radius: 10px;
            border: 1px solid #E5E7EB;
            box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        }
        [data-testid="stForm"] {
            background: #FFFFFF;
            border-radius: 10px;
            border: 1px solid #E5E7EB;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            padding: 1.25rem;
        }
    </style>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
# TOP NAVIGATION BAR
# ════════════════════════════════════════════════════════════════════

def _render_topbar(persona: str):
    """Render a professional fixed-style top navigation bar."""
    personas_map = {
        "Marketing Manager": "Marketing",
        "Customer Success / Support": "Support",
        "Product Team": "Product",
        "Simulation Lab": "Simulation",
    }

    tabs_html = ""
    for full_name, short in personas_map.items():
        is_active = full_name == persona
        if is_active:
            tab_style = "padding:0.65rem 1rem;font-size:0.78rem;color:#2563EB;border-bottom:2px solid #2563EB;font-weight:700;display:inline-block;cursor:default;"
        else:
            tab_style = "padding:0.65rem 1rem;font-size:0.78rem;color:#6B7280;border-bottom:2px solid transparent;display:inline-block;cursor:default;"
        tabs_html += f'<span style="{tab_style}">{short}</span>'

    # Brand section with logo
    brand_html = (
        '<div style="display:flex;align-items:center;gap:0.75rem;">'
        '<div style="width:36px;height:36px;background:linear-gradient(135deg,#2563EB,#7C3AED);border-radius:8px;display:flex;align-items:center;justify-content:center;color:white;font-size:1.1rem;font-weight:900;">C</div>'
        '<div>'
        '<span style="font-size:1.05rem;font-weight:800;color:#111827;letter-spacing:-0.5px;">Churn<span style="color:#2563EB;">Guard</span></span>'
        '<span style="font-size:0.6rem;color:#9CA3AF;font-weight:500;margin-left:0.5rem;vertical-align:super;">ANALYTICS</span>'
        '</div>'
        '</div>'
    )

    badge_html = (
        '<div style="display:flex;align-items:center;gap:0.75rem;">'
        '<span style="background:#EFF6FF;color:#2563EB;padding:4px 12px;border-radius:100px;font-size:0.68rem;font-weight:600;letter-spacing:0.5px;">LIVE DATA</span>'
        '<div style="width:32px;height:32px;background:#F3F4F6;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:0.85rem;color:#6B7280;border:1px solid #E5E7EB;">👤</div>'
        '</div>'
    )

    topbar_html = (
        '<div class="fixed-header">'
        '<div style="padding:0 1.5rem;">'
        '<div style="display:flex;align-items:center;justify-content:space-between;padding:0.75rem 0;">'
        f'{brand_html}'
        f'{badge_html}'
        '</div>'
        f'<div style="display:flex;gap:0;border-top:1px solid #F3F4F6;">{tabs_html}</div>'
        '</div>'
        '</div>'
    )

    st.markdown(topbar_html, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════════

def _render_sidebar() -> str:
    """Draw the persona selector and filters, return the chosen persona."""
    with st.sidebar:

        st.markdown(
            '<p style="color:#9CA3AF;font-size:0.62rem;font-weight:700;'
            'text-transform:uppercase;letter-spacing:1.2px;margin-bottom:0.3rem;">Navigation</p>',
            unsafe_allow_html=True,
        )

        persona = st.selectbox(
            "Persona",
            ["Marketing Manager", "Customer Success / Support", "Product Team", "Simulation Lab"],
            key="persona_selector",
            label_visibility="collapsed",
        )

        st.markdown("---")

        st.markdown(
            '<p style="color:#9CA3AF;font-size:0.62rem;font-weight:700;'
            'text-transform:uppercase;letter-spacing:1.2px;margin-bottom:0.3rem;">Filters</p>',
            unsafe_allow_html=True,
        )

    return persona


# ════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="ChurnGuard — E-Commerce Analytics",
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

    # Top nav bar
    _render_topbar(persona)

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

    st.markdown("---")
    st.markdown('<div id="ai-insights-anchor"></div>', unsafe_allow_html=True)
    render_ai_insights()

    # Footer
    st.markdown(
        '<div style="text-align:center;padding:2rem 0 1.25rem;color:#9CA3AF;font-size:0.68rem;font-weight:500;letter-spacing:0.3px;">'
        '<span style="color:#D1D5DB;">━━━</span>&nbsp;&nbsp;'
        'ChurnGuard Analytics v2.0 &nbsp;·&nbsp; Gold Star Schema &nbsp;·&nbsp; '
        'Powered by Streamlit &amp; PostgreSQL'
        '&nbsp;&nbsp;<span style="color:#D1D5DB;">━━━</span>'
        '</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
