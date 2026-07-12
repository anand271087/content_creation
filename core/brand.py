"""Single source of truth for brand + typography constants.

Every compositor previously redeclared these; change them here, every format
picks it up.
"""
from __future__ import annotations

# Canvas
W, H, FPS = 1080, 1920, 30

# Fonts (macOS system paths)
FONT_BLACK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_MONO = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"

# Brand palette
BRAND_BLUE = "#2979ff"
DANGER_RED = "#E31A1A"

# Tier-board badge colors (classic TierMaker, matched to Dan Martell's board)
TIER_COLORS = {
    "S": "#fa7ce8", "A": "#7cb5fa", "B": "#fabd7c",
    "C": "#d8fa7c", "D": "#7cfa96", "F": "#fa7c7c",
}

# Bad/Good/Great column palette (tier-stack format)
BGG_COLORS = {"bad": "#ef4444", "good": "#facc15", "great": "#22c55e"}

# Rainbow ladder for checklist steps
RAINBOW = ["#ff5757", "#ff9f43", "#ffd32a", "#2ecc71", "#54a0ff"]

# Sort-board verdict colors
SORT_COLORS = {"matters": "#2ecc71", "doesnt": "#ffd32a", "hurtful": "#ff5757"}

# Post-production
FINAL_SPEED = 1.3          # HeyGen ~142wpm → ~185wpm (Martell zone)
CRF_FINAL = 17
DARK_PILL = (14, 14, 14, 205)   # rule: landed text ALWAYS sits on a dark pill
