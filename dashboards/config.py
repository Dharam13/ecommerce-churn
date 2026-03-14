"""
config.py
═════════
Central configuration — database credentials, colour palettes, and constants.
Edit this single file when credentials or theming change.
"""

# ── Database ───────────────────────────────────────────────
DB_USER = "postgres"
DB_PASSWORD = "2271"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "churn_db"

DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

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
HIGH_RISK_THRESHOLD = 0.75
MEDIUM_RISK_THRESHOLD = 0.50

# ── Cache TTL (seconds) ───────────────────────────────────
DATA_CACHE_TTL = 300
