"""5-step rainbow checklist reveal (ref: DaJNU6KD4BG "Sell Anyone In 5 Steps").

All steps ghosted in a dark panel from t=0; each lights up in its rainbow
color on its beat, with a light-leak flash. Fully-lit list = payoff.
Demo mode (captions=None): even cadence across 75% of runtime.
"""
from __future__ import annotations
import logging
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.brand import W, FONT_BLACK, RAINBOW
from core.cards import title_pill
from core.overlays import OverlayChain
from core.words import load_words, normalize, find_word, duration_of

log = logging.getLogger("checklist")

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "assets" / "checklist_assets"

CROP = "grey_166"
TITLE_LINES = ["BUILD YOUR AI AVATAR", "IN 5 STEPS"]
# (step label, anchor word for timed mode)
STEPS = [
    ("SCRIPT WITH CLAUDE",  "claude"),
    ("AVATAR IN HEYGEN",    "heygen"),
    ("VOICE IN ELEVENLABS", "elevenlabs"),
    ("EDIT RUNS ITSELF",    "edit"),
    ("POST EVERY DAY",      "post"),
]
LIST_X, LIST_Y = 90, 1150
ROW_H, PAD = 104, 26


def panel_base() -> Path:
    ph = PAD * 2 + ROW_H * len(STEPS)
    pw = W - LIST_X * 2
    panel = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(panel)
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=26, fill=(10, 10, 12, 175))
    f = ImageFont.truetype(FONT_BLACK, 44)
    for i, (text, _a) in enumerate(STEPS):
        d.text((44, PAD + i * ROW_H + 24), f"{i + 1}. {text}", font=f,
               fill=(255, 255, 255, 60))
    out = ASSET_DIR / "panel_base.png"
    panel.save(out)
    return out


def lit_row(i: int) -> Path:
    text, _a = STEPS[i]
    f = ImageFont.truetype(FONT_BLACK, 44)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    label = f"{i + 1}. {text}"
    tw = int(tmp.textlength(label, font=f))
    img = Image.new("RGBA", (tw + 16, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((4, 2), label, font=f, fill=RAINBOW[i % len(RAINBOW)],
           stroke_width=2, stroke_fill=(0, 0, 0, 220))
    out = ASSET_DIR / f"lit_{i}.png"
    img.save(out)
    return out


def build(avatar: Path, captions: Path | None, out: Path) -> Path:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    duration = duration_of(avatar)
    n = len(STEPS)
    if captions and Path(captions).exists():
        words = normalize(load_words(captions))
        reveals, after = [], 0.0
        for _label, anchor in STEPS:
            t = find_word(words, anchor, after)
            reveals.append(max(0.4, (t or after + 3) - 0.15))
            after = reveals[-1] + 0.3
    else:
        span = duration * 0.75
        reveals = [1.2 + i * (span - 1.2) / n for i in range(n)]
    log.info("reveals: %s", [round(r, 1) for r in reveals])

    chain = OverlayChain(avatar, CROP, ASSET_DIR)
    title = title_pill(TITLE_LINES, ASSET_DIR / "title.png", size=40)
    tw = Image.open(title).width
    chain.add_image(title, (W - tw) // 2, 60, 0.0, duration)
    chain.add_image(panel_base(), LIST_X, LIST_Y, 0.0, duration)
    for i in range(n):
        chain.add_image(lit_row(i), LIST_X + 40, LIST_Y + PAD + i * ROW_H + 22,
                        reveals[i], duration)
        chain.flash_at(reveals[i])
    return chain.render(out, duration)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build(ROOT / "assets/avatar/avatar_trimmed.mp4", None,
          ROOT / "assets/final/checklist_demo.mp4")
