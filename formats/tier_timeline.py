"""Stage/timeline board (Dan Martell DafvfVaASFn replica).

Vertical rail of circle stage badges down the left edge; items float mid-frame
then land next to their stage badge; accumulate. Axis = WHEN, not quality.
User corrections baked in: dark pills behind landed labels, 1.66x crop.
"""
from __future__ import annotations
import logging
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.brand import W, FONT_BOLD
from core.cards import title_pill, float_label, dark_label
from core.overlays import OverlayChain
from core.words import load_words, normalize, clean, duration_of

log = logging.getLogger("tier_timeline")

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "assets" / "tier_timeline_assets"

CROP = "grey_166"
TITLE_LINES = ["AI FOUNDER:", "When to automate what in your business"]
STAGES = ["Day 1", "Client 1", "1L/mo", "5L/mo", "20L/mo"]
RAIL_X, BADGE_D = 44, 96
RAIL_Y0, RAIL_STEP = 470, 250
LABEL_X = RAIL_X + BADGE_D + 22
FLOAT_Y = 1480
SLOT_DX = [0, 350]

# (anchor word, land word after anchor, stage index, slot, label)
ITEMS = [
    ("content",   "day",    0, 0, "AI content system"),
    ("email",     "day",    0, 1, "ChatGPT email"),
    ("crm",       "first",  1, 0, "CRM automation"),
    ("assistant", "lakh",   2, 0, "Virtual assistant"),
    ("agents",    "lakhs",  3, 0, "Custom AI agents"),
    ("employee",  "lakhs",  4, 0, "First employee"),
]


def build_rail() -> Path:
    rail_h = RAIL_Y0 + RAIL_STEP * (len(STAGES) - 1) + BADGE_D
    rail = Image.new("RGBA", (RAIL_X + BADGE_D + 8, rail_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(rail)
    for i, s in enumerate(STAGES):
        y = RAIL_Y0 + i * RAIL_STEP
        d.ellipse([RAIL_X, y, RAIL_X + BADGE_D, y + BADGE_D],
                  fill=(15, 15, 15, 150), outline=(255, 255, 255, 235), width=4)
        size = 26 if len(s) <= 6 else 22
        f = ImageFont.truetype(FONT_BOLD, size)
        lw = d.textlength(s, font=f)
        d.text((RAIL_X + (BADGE_D - lw) / 2, y + (BADGE_D - size) / 2 - 2), s,
               font=f, fill=(255, 255, 255, 255))
    out = ASSET_DIR / "rail.png"
    rail.save(out)
    return out


def compute_timings(words, duration):
    out = []
    used = -1
    for anchor, land, stage_i, slot, label in ITEMS:
        a_t = l_t = None
        for i, w in enumerate(words):
            if i <= used:
                continue
            if clean(w["word"]) == anchor:
                a_t = max(0.0, w["start"] - 0.20)
                used = i
                for w2 in words[i + 1:]:
                    if clean(w2["word"]) == land:
                        l_t = w2["start"]
                        break
                break
        if a_t is None:
            log.warning("anchor %r not found — skipped", anchor)
            continue
        out.append({"label": label, "stage": stage_i, "slot": slot,
                    "start": a_t, "land": l_t if l_t is not None else a_t + 1.5})
    return out


def build(avatar: Path, captions: Path, out: Path) -> Path:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    duration = duration_of(avatar)
    words = normalize(load_words(captions))
    items = compute_timings(words, duration)
    for it in items:
        log.info("%-20s stage=%d  %5.2f → %5.2f", it["label"], it["stage"],
                 it["start"], it["land"])

    chain = OverlayChain(avatar, CROP, ASSET_DIR)
    title = title_pill(TITLE_LINES, ASSET_DIR / "title_pill.png", size=36)
    tw = Image.open(title).width
    chain.add_image(title, (W - tw) // 2, 60, 0.0, duration)
    chain.add_image(build_rail(), 0, 0, 0.0, duration)

    for n, it in enumerate(items):
        fl = float_label(it["label"], ASSET_DIR / f"label_float_{n}.png")
        fw = Image.open(fl).width
        chain.add_image(fl, (W - fw) // 2, FLOAT_Y, it["start"], it["land"])

        ll = dark_label(it["label"], ASSET_DIR / f"label_land_{n}.png")
        lh = Image.open(ll).height
        y = RAIL_Y0 + it["stage"] * RAIL_STEP + (BADGE_D - lh) // 2
        chain.add_image(ll, LABEL_X + SLOT_DX[it["slot"]], y, it["land"], duration)
        chain.flash_at(it["land"])

    return chain.render(out, duration, preset="slow")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build(ROOT / "assets/avatar/avatar_video_bg.mp4",
          ROOT / "assets/captions/tier_timeline.json",
          ROOT / "assets/final/tier_timeline.mp4")
