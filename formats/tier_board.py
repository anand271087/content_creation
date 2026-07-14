"""S-F tier board (Dan Martell DaYBCF7Fdln replica).

Title pill top, empty S/A/B/C/D/F board lower half from frame one; item label
floats mid-frame during evaluation → lands in its tier row at the spoken
grade; items accumulate. Script pattern: "[ITEM]. [GRADE]. [reason]."
"""
from __future__ import annotations
import logging
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.brand import W, H, FONT_BLACK, FONT_BOLD, TIER_COLORS
from core.cards import title_pill, float_label
from core.overlays import OverlayChain
from core.words import load_words, normalize, find_after_anchor, duration_of

log = logging.getLogger("tier_board")

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "assets" / "tier_board_assets"

CROP = "grey_187"
TIERS = ["S", "A", "B", "C", "D", "F"]
BOARD_X, BOARD_W = 40, 1000
ROW_H, ROW_GAP, BADGE = 90, 4, 90
BOARD_Y = H - (ROW_H + ROW_GAP) * len(TIERS) - 70
FLOAT_Y = 1140
SLOT_X = [BADGE + 26, BADGE + 460]

TITLE_LINES = ["AI FOUNDER:", "Ranking how founders show up online"]
# (anchor word, grade, row slot, board label)
ITEMS = [
    ("filming",   "C", 0, "Filming daily"),
    ("editor",    "B", 0, "Video editor"),
    ("followers", "F", 0, "Bought followers"),
    ("text",      "D", 0, "Text only"),
    ("podcast",   "A", 0, "Podcast"),
    ("avatar",    "S", 0, "AI avatar system"),
    ("nothing",   "F", 1, "Doing nothing"),
]


def build_board_base() -> Path:
    bh = (ROW_H + ROW_GAP) * len(TIERS)
    board = Image.new("RGBA", (BOARD_W, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(board)
    f = ImageFont.truetype(FONT_BLACK, 42)
    for i, tier in enumerate(TIERS):
        y = i * (ROW_H + ROW_GAP)
        d.rectangle([BADGE, y, BOARD_W, y + ROW_H], fill=(18, 18, 18, 216))
        d.rectangle([0, y, BADGE, y + ROW_H], fill=TIER_COLORS[tier])
        lw = d.textlength(tier, font=f)
        d.text(((BADGE - lw) / 2, y + (ROW_H - 56) / 2), tier, font=f, fill=(15, 15, 15, 255))
    out = ASSET_DIR / "board_base.png"
    board.save(out)
    return out


def row_label(text: str, idx: int) -> Path:
    """Row label style used by the approved render: white text + soft shadow
    (rows themselves are dark, so no extra pill needed)."""
    f = ImageFont.truetype(FONT_BOLD, 30)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = int(tmp.textlength(text, font=f))
    img = Image.new("RGBA", (tw + 16, 46), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((10, 10), text, font=f, fill=(0, 0, 0, 200))
    d.text((8, 8), text, font=f, fill=(255, 255, 255, 255))
    out = ASSET_DIR / f"label_row_{idx}.png"
    img.save(out)
    return out


def build(avatar: Path, captions: Path, out: Path,
          items=None, title_lines=None, crop: str = CROP,
          letterbox_band: str | None = None, sharp_crop: str | None = None,
          sharp_y: int = 150) -> Path:
    global ITEMS, TITLE_LINES
    if items is not None:
        ITEMS = items
    if title_lines is not None:
        TITLE_LINES = title_lines
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    duration = duration_of(avatar)
    words = normalize(load_words(captions))

    chain = OverlayChain(avatar, crop, ASSET_DIR)
    if letterbox_band:
        chain.set_letterbox_base(letterbox_band, sharp_crop, sharp_y)
    title = title_pill(TITLE_LINES, ASSET_DIR / "title_pill.png")
    tw = Image.open(title).width
    chain.add_image(title, (W - tw) // 2, 60, 0.0, duration)
    chain.add_image(build_board_base(), BOARD_X, BOARD_Y, 0.0, duration)

    for n, (anchor, grade, slot, label) in enumerate(ITEMS):
        hit = find_after_anchor(words, anchor, grade)
        if not hit:
            log.warning("anchor %r not found — skipped", anchor)
            continue
        a_t, g_t = hit
        a_t = max(0.0, a_t - 0.20)
        log.info("%-18s %s  eval %5.2f → graded %5.2f", label, grade, a_t, g_t)

        fl = float_label(label, ASSET_DIR / f"label_float_{n}.png")
        fw = Image.open(fl).width
        chain.add_image(fl, (W - fw) // 2, FLOAT_Y, a_t, g_t)

        rl = row_label(label, n)
        rh = Image.open(rl).height
        row_i = TIERS.index(grade)
        y = BOARD_Y + row_i * (ROW_H + ROW_GAP) + (ROW_H - rh) // 2
        chain.add_image(rl, BOARD_X + SLOT_X[slot], y, g_t, duration)

    return chain.render(out, duration, preset="slow")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build(ROOT / "assets/avatar/avatar_video_bg.mp4",
          ROOT / "assets/captions/tier_board.json",
          ROOT / "assets/final/tier_board.mp4")
