"""
personas package
════════════════
Each module exposes a single render_*() function that takes a filtered DataFrame.
"""

from personas.marketing import render_marketing_dashboard
from personas.support import render_support_dashboard
from personas.product import render_product_dashboard
from personas.risk_overview import render_risk_overview
from personas.simulation import render_simulation_dashboard
from personas.ai_insights import render_ai_insights

__all__ = [
    "render_marketing_dashboard",
    "render_support_dashboard",
    "render_product_dashboard",
    "render_risk_overview",
    "render_simulation_dashboard",
    "render_ai_insights",
]
