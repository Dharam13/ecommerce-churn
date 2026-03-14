"""
dashboards package
══════════════════
Each module exposes a single render_*() function that takes a filtered DataFrame.
"""

from dashboards.marketing import render_marketing_dashboard
from dashboards.support import render_support_dashboard
from dashboards.product import render_product_dashboard
from dashboards.risk_overview import render_risk_overview

__all__ = [
    "render_marketing_dashboard",
    "render_support_dashboard",
    "render_product_dashboard",
    "render_risk_overview",
]
