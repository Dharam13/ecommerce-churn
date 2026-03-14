"""
config.py
═════════
Central configuration — colour palettes, thresholds, and constants.
DB credentials are loaded from .env via src.db.connection.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (one level up from dashboards/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# ── Schema names (from .env) ──────────────────────────────
BRONZE_SCHEMA = os.getenv("BRONZE_SCHEMA", "bronze")
SILVER_SCHEMA = os.getenv("SILVER_SCHEMA", "silver")
GOLD_SCHEMA   = os.getenv("GOLD_SCHEMA",   "gold")

# ── Industry-grade colour palette ────────────────────────────
PALETTE = {
    # Primary brand
    "primary":        "#2563EB",   # Blue-600  – primary accent
    "primary_light":  "#EFF6FF",   # Blue-50
    "primary_dark":   "#1E40AF",   # Blue-800

    # Semantic colours
    "secondary":      "#EF4444",   # Red-500   – danger / churn
    "accent":         "#10B981",   # Emerald-500 – success / retained
    "accent_light":   "#ECFDF5",   # Emerald-50
    "warning":        "#F59E0B",   # Amber-500
    "warning_light":  "#FFFBEB",   # Amber-50
    "info":           "#06B6D4",   # Cyan-500
    "info_light":     "#ECFEFF",   # Cyan-50

    # Surfaces
    "bg":             "#F3F4F6",   # Gray-100  – page background
    "card_bg":        "#FFFFFF",   # White     – card fill
    "card_border":    "#E5E7EB",   # Gray-200  – subtle border
    "card_shadow":    "0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)",

    # Text hierarchy
    "text":           "#111827",   # Gray-900  – headings
    "text_secondary": "#374151",   # Gray-700  – body
    "text_muted":     "#6B7280",   # Gray-500  – captions
    "text_light":     "#9CA3AF",   # Gray-400  – hints

    # Sidebar
    "sidebar_bg":     "#FFFFFF",
    "sidebar_border": "#E5E7EB",

    # Top nav bar
    "topbar_bg":      "#FFFFFF",
    "topbar_border":  "#E5E7EB",

    # Dividers
    "divider":        "#E5E7EB",   # Gray-200

    # Delta badges (KPI cards)
    "delta_up":       "#059669",   # Emerald-600
    "delta_up_bg":    "#D1FAE5",   # Emerald-100
    "delta_down":     "#DC2626",   # Red-600
    "delta_down_bg":  "#FEE2E2",   # Red-100

    # Chart palette (ordered for sequential use)
    "chart_1":        "#2563EB",
    "chart_2":        "#10B981",
    "chart_3":        "#F59E0B",
    "chart_4":        "#8B5CF6",
    "chart_5":        "#EC4899",
    "chart_6":        "#06B6D4",
}

CHART_COLORS = [
    PALETTE["chart_1"], PALETTE["chart_2"], PALETTE["chart_3"],
    PALETTE["chart_4"], PALETTE["chart_5"], PALETTE["chart_6"],
]

RISK_COLORS = {
    "High Risk":   "#EF4444",    # Red-500
    "Medium Risk": "#F59E0B",    # Amber-500
    "Low Risk":    "#10B981",    # Emerald-500
}

RISK_BG_COLORS = {
    "High Risk":   "#FEF2F2",    # Red-50
    "Medium Risk": "#FFFBEB",    # Amber-50
    "Low Risk":    "#ECFDF5",    # Emerald-50
}

# ── Plotly ─────────────────────────────────────────────────
PLOTLY_TEMPLATE = "plotly_white"

# ── Risk thresholds ────────────────────────────────────────
HIGH_RISK_THRESHOLD  = 0.75
MEDIUM_RISK_THRESHOLD = 0.50

# ── Cache TTL (seconds) ───────────────────────────────────
DATA_CACHE_TTL = 300
