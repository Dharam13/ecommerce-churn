"""
filters.py
══════════
Sidebar filter controls.  Returns a filtered copy of the DataFrame.
"""

import pandas as pd
import streamlit as st


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Render sidebar filters and return the filtered DataFrame."""

    # ── City Tier ────────────────────────────────────────────
    tiers = sorted(df["city_tier"].dropna().unique())
    sel_tiers = st.sidebar.multiselect(
        "🏙️  City Tier", tiers, default=tiers, key="filter_city_tier"
    )

    # ── Gender ───────────────────────────────────────────────
    genders = sorted(df["gender"].dropna().unique())
    sel_genders = st.sidebar.multiselect(
        "👤  Gender", genders, default=genders, key="filter_gender"
    )

    # ── Login Device ─────────────────────────────────────────
    devices = sorted(df["preferred_login_device"].dropna().unique())
    sel_devices = st.sidebar.multiselect(
        "📱  Login Device", devices, default=devices, key="filter_device"
    )

    mask = (
        df["city_tier"].isin(sel_tiers)
        & df["gender"].isin(sel_genders)
        & df["preferred_login_device"].isin(sel_devices)
    )
    return df[mask].copy()
