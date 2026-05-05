"""
ui/theme.py — Color palette, typography constants, and theme helpers.
"""

# ─────────────────────────────────────────────
#  COLOURS (dark theme)
# ─────────────────────────────────────────────
BG        = "#0f172a"
BG2       = "#1e293b"
BG3       = "#334155"
BORDER    = "#334155"
TEXT      = "#f1f5f9"
TEXT2     = "#94a3b8"
CYAN      = "#22d3ee"
GREEN     = "#4ade80"
RED       = "#f87171"
YELLOW    = "#facc15"
PURPLE    = "#c084fc"
BLUE      = "#60a5fa"

# ─────────────────────────────────────────────
#  APP CONFIG
# ─────────────────────────────────────────────
HOURLY_RATE    = 15.0           # PHP per hour
MINUTE_RATE    = HOURLY_RATE / 60
GRACE_SECONDS  = 0              # 0 = re-lock immediately when session ends
ADMIN_EXIT_PIN = "1234"         # Ctrl+Shift+Q PIN

PRICING_TIERS = [
    {"label": "15 minutes",  "minutes": 1},
    {"label": "30 minutes",  "minutes": 30},
    {"label": "1 hour",      "minutes": 60},
    {"label": "1.5 hours",   "minutes": 90},
    {"label": "2 hours",     "minutes": 120},
    {"label": "3 hours",     "minutes": 180},
    {"label": "5 hours",     "minutes": 300},
    {"label": "8 hours",     "minutes": 480},
]