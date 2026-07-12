"""Avatar crop presets — framing differs per HeyGen avatar recording.

Rules learned (memory: feedback_tier_timeline_format):
  - 1.66x is the approved default zoom ("1.87x too zoomed").
  - ALWAYS verify a new avatar's framing with a test frame before compositing;
    face position shifts between recordings.
"""
from __future__ import annotations

# preset name -> ffmpeg crop+scale chain producing 1080x1920
CROPS = {
    # Grey Everlast-hoodie avatar
    "grey_166": "crop=650:1156:185:144,scale=1080:1920",   # approved default
    "grey_187": "crop=579:1029:221:271,scale=1080:1920",   # tighter (tier_stack/board)
    # Blue striped-sweatshirt avatar (face sits lower/left vs grey)
    "blue_183": "crop=591:1050:179:250,scale=1080:1920",
    # No crop (already-framed source)
    "none": "null",
}

# Useful landmarks per crop at output scale (approx, for label placement)
CHIN_Y = {"grey_166": 1421, "grey_187": 1520, "blue_183": 1126}


def crop(preset: str) -> str:
    if preset not in CROPS:
        raise KeyError(f"unknown crop preset {preset!r} — add it to core/framing.py "
                       f"after verifying a test frame")
    return CROPS[preset]
