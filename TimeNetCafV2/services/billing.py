"""
services/billing.py — Pure billing / cost-calculation helpers.
"""

from ui.theme import HOURLY_RATE, MINUTE_RATE


def calc_cost(minutes: int) -> float:
    """Return the cost (PHP) for the given number of minutes."""
    return round(minutes * MINUTE_RATE * 100) / 100


def cost_summary(minutes: int) -> dict:
    """Return a dict with minutes, hours label, and formatted cost string."""
    from database.database import format_currency

    cost = calc_cost(minutes)
    if minutes >= 60 and minutes % 60 == 0:
        dur_str = f"{minutes // 60}h"
    elif minutes >= 60:
        dur_str = f"{minutes // 60}h {minutes % 60}m"
    else:
        dur_str = f"{minutes}m"

    return {
        "minutes":   minutes,
        "dur_str":   dur_str,
        "cost":      cost,
        "cost_str":  format_currency(cost),
        "rate_str":  f"₱{HOURLY_RATE:.2f} / hour",
    }