"""3-column sort board (ref: DaliD7IDyvi "Success Habits").

MATTERS / DOESN'T MATTER / HURTFUL headers pinned from frame one; items float
at chest then land under their column; accumulate. Contrarian placements are
the comment engine. Demo mode (captions=None): even cadence.
"""
from __future__ import annotations
import logging
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.brand import W, FONT_BLACK, SORT_COLORS
from core.cards import title_pill, float_label, dark_label
from core.overlays import OverlayChain
from core.words import load_words, normalize, find_word, duration_of

log = logging.getLogger("sort_board")

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "assets" / "sortboard_assets"

CROP = "blue_183"
TITLE_LINES = ["CONTENT HABITS:", "What ACTUALLY matters?"]
COLUMNS = [("MATTERS", SORT_COLORS["matters"]),
           ("DOESN'T\nMATTER", SORT_COLORS["doesnt"]),
           ("HURTFUL", SORT_COLORS["hurtful"])]
COL_X = [190, 540, 890]
HEAD_Y, ITEMS_Y0, ITEM_H = 250, 360, 74
FLOAT_Y = 1500

# (label, column index, anchor word for timed mode)
ITEMS = [
    ("Posting daily",      0, "daily"),
    ("Fancy camera",       1, "camera"),
    ("Buying followers",   2, "followers"),
    ("Strong hooks",       0, "hooks"),
    ("Perfect editing",    1, "editing"),
    ("AI avatar",          0, "avatar"),
    ("Waiting till ready", 2, "waiting"),
]


def headers_strip() -> Path:
    strip = Image.new("RGBA", (W, 130), (0, 0, 0, 0))
    d = ImageDraw.Draw(strip)
    f = ImageFont.truetype(FONT_BLACK, 30)
    for (label, color), cx in zip(COLUMNS, COL_X):
        lines = label.split("\n")
        wmax = max(d.textlength(t, font=f) for t in lines)
        pw = int(wmax + 44)
        ph = 52 + (len(lines) - 1) * 36
        x0 = cx - pw // 2
        d.rounded_rectangle([x0, 0, x0 + pw, ph], radius=14, fill=(12, 12, 14, 205))
        for i, t in enumerate(lines):
            lw = d.textlength(t, font=f)
            d.text((cx - lw / 2, 8 + i * 36), t, font=f, fill=color)
    for x in [(COL_X[0] + COL_X[1]) // 2, (COL_X[1] + COL_X[2]) // 2]:
        for y in range(0, 130, 18):
            d.rectangle([x - 1, y, x + 1, y + 9], fill=(255, 255, 255, 120))
    out = ASSET_DIR / "headers.png"
    strip.save(out)
    return out


def build(avatar: Path, captions: Path | None, out: Path) -> Path:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    duration = duration_of(avatar)
    n = len(ITEMS)
    if captions and Path(captions).exists():
        words = normalize(load_words(captions))
        starts, after = [], 0.0
        for _l, _c, anchor in ITEMS:
            t = find_word(words, anchor, after)
            starts.append(max(0.4, (t or after + 4) - 0.20))
            after = starts[-1] + 0.5
        lands = [s + 2.0 for s in starts]
    else:
        span = duration * 0.8
        starts = [1.0 + i * (span - 1.0) / n for i in range(n)]
        lands = [s + 2.0 for s in starts]

    chain = OverlayChain(avatar, CROP, ASSET_DIR)
    title = title_pill(TITLE_LINES, ASSET_DIR / "title.png")
    tw = Image.open(title).width
    chain.add_image(title, (W - tw) // 2, 60, 0.0, duration)
    chain.add_image(headers_strip(), 0, HEAD_Y, 0.0, duration)

    col_counts = [0, 0, 0]
    for k, (label, col, _anchor) in enumerate(ITEMS):
        fl = float_label(label, ASSET_DIR / f"label_f_{k}.png")
        fw = Image.open(fl).width
        chain.add_image(fl, (W - fw) // 2, FLOAT_Y, starts[k], lands[k])

        ll = dark_label(label, ASSET_DIR / f"label_l_{k}.png", size=24)
        lw = Image.open(ll).width
        slot = col_counts[col]; col_counts[col] += 1
        chain.add_image(ll, COL_X[col] - lw // 2, ITEMS_Y0 + slot * ITEM_H,
                        lands[k], duration)
        chain.flash_at(lands[k])

    return chain.render(out, duration)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build(ROOT / "assets/avatar/avatar_video_bg.mp4", None,
          ROOT / "assets/final/sortboard_demo.mp4")
