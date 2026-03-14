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

# ── Light-theme colour palette ────────────────────────────
PALETTE = {
    "primary":      "#4F46E5",   # Indigo-600
    "primary_light": "#EEF2FF",  # Indigo-50
    "secondary":    "#F43F5E",   # Rose-500
    "accent":       "#10B981",   # Emerald-500
    "accent_light": "#ECFDF5",   # Emerald-50
    "warning":      "#F59E0B",   # Amber-500
    "warning_light":"#FFFBEB",   # Amber-50
    "info":         "#06B6D4",   # Cyan-500
    "info_light":   "#ECFEFF",   # Cyan-50
    "bg":           "#F8FAFC",   # Slate-50
    "card_bg":      "#FFFFFF",   # White
    "card_border":  "#E2E8F0",   # Slate-200
    "text":         "#1E293B",   # Slate-800
    "text_muted":   "#64748B",   # Slate-500
    "text_light":   "#94A3B8",   # Slate-400
    "sidebar_bg":   "#F1F5F9",   # Slate-100
    "divider":      "#E2E8F0",   # Slate-200
}

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
