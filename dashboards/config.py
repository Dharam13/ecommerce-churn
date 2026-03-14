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

# ── Colour palette ────────────────────────────────────────
PALETTE = {
    "primary":   "#6C63FF",
    "secondary": "#FF6584",
    "accent":    "#00D084",
    "warning":   "#FFB347",
    "info":      "#36CFC9",
    "dark_bg":   "#0E1117",
    "card_bg":   "#1A1D23",
    "text":      "#FAFAFA",
}

RISK_COLORS = {
    "High Risk":   "#FF4D6A",
    "Medium Risk": "#FFB347",
    "Low Risk":    "#00D084",
}

# ── Plotly ─────────────────────────────────────────────────
PLOTLY_TEMPLATE = "plotly_dark"

# ── Risk thresholds ────────────────────────────────────────
HIGH_RISK_THRESHOLD  = 0.75
MEDIUM_RISK_THRESHOLD = 0.50

# ── Cache TTL (seconds) ───────────────────────────────────
DATA_CACHE_TTL = 300
