"""Bad/Good/Great tier stack (Dan Martell DaEDt-igYil replica).

3-card row pinned top per category, ALL logos blurred at category start,
each un-blurs on its spoken word. Question pill per category. No captions.
"""
from __future__ import annotations
import logging
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.brand import W, FONT_BLACK, FONT_BOLD
from core.cards import BRANDS, logo_image, title_pill  # noqa: F401
from core.overlays import OverlayChain
from core.words import load_words, normalize, clean, duration_of

log = logging.getLogger("tier_stack")

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "assets" / "tier_cards"

SIDE, CENTER = 240, 280
ROW_Y_SIDE, ROW_Y_CENTER = 130, 100
X_BAD, X_GOOD, X_GREAT = 230, 540, 850
PILL_Y = 1450
CROP = "grey_187"

CATEGORIES = [
    {"pill": "Scripting?",      "brands": ["chatgpt", "gemini", "claude"]},
    {"pill": "Your AI Avatar?", "brands": ["sora", "synthesia", "heygen"]},
    {"pill": "The Voice?",      "brands": ["free_clone", "descript", "elevenlabs"]},
]


def build_card(key: str, size: int, blurred: bool) -> Path:
    _tier, name, _a, _m = BRANDS[key]
    card = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.18),
                        fill=(255, 255, 255, 255))
    logo_px = int(size * 0.52)
    logo = logo_image(key, logo_px, ASSET_DIR)
    if blurred:
        big = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        big.paste(logo, ((size - logo_px) // 2, (size - logo_px) // 2), logo)
        big = big.filter(ImageFilter.GaussianBlur(int(size * 0.07)))
        card.alpha_composite(big)
    else:
        f = ImageFont.truetype(FONT_BOLD, int(size * 0.085))
        label = name.upper()
        tw = d.textlength(label, font=f)
        d.text(((size - tw) / 2, int(size * 0.09)), label, font=f, fill=(17, 24, 39, 255))
        card.alpha_composite(logo, ((size - logo_px) // 2, int(size * 0.30)))
    out = ASSET_DIR / f"{key}_{'blur' if blurred else 'sharp'}_{size}.png"
    card.save(out)
    return out


def build_labels_strip() -> Path:
    strip = Image.new("RGBA", (W, 100), (0, 0, 0, 0))
    d = ImageDraw.Draw(strip)
    f = ImageFont.truetype(FONT_BLACK, 36)
    for text, cx, y in [("BAD", X_BAD, 52), ("GOOD", X_GOOD, 22), ("GREAT", X_GREAT, 52)]:
        tw = d.textlength(text, font=f)
        d.text((cx - tw / 2, y), text, font=f, fill=(255, 255, 255, 255),
               stroke_width=5, stroke_fill=(0, 0, 0, 255))
    out = ASSET_DIR / "labels_strip.png"
    strip.save(out)
    return out


def build_pill(text: str, idx: int) -> Path:
    f = ImageFont.truetype(FONT_BLACK, 46)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = tmp.textlength(text, font=f)
    pw, ph = int(tw + 76), 96
    pill = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(pill)
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=16, fill=(255, 255, 255, 255))
    d.text((38, (ph - 60) / 2), text, font=f, fill=(10, 10, 10, 255))
    out = ASSET_DIR / f"pill_{idx}.png"
    pill.save(out)
    return out


def compute_timings(words, duration):
    def find(pred, after=0.0):
        for w in words:
            if w["start"] >= after and pred(clean(w["word"])):
                return w["start"]
        return None

    t2 = (find(lambda c: c == "avatar") or 6.0) - 0.9
    t3 = (find(lambda c: c == "voice") or 12.0) - 0.9
    t_cta = find(lambda c: c == "thats") or find(lambda c: c == "comment") or duration - 5
    windows = [(0.0, t2), (t2, t3), (t3, duration)]
    pill_end = [t2, t3, t_cta]

    anchor_map = {}
    for key, (_t, _n, anchors, _s) in BRANDS.items():
        for a in anchors:
            anchor_map[a] = key

    out = []
    for i, cat in enumerate(CATEGORIES):
        reveals = {}
        for w in words:
            k = anchor_map.get(clean(w["word"]))
            if k in cat["brands"] and k not in reveals and windows[i][0] <= w["start"] < windows[i][1] + 2:
                reveals[k] = max(windows[i][0], w["start"] - 0.15)
        out.append({**cat, "start": windows[i][0], "end": windows[i][1],
                    "pill_end": pill_end[i], "reveals": reveals})
    return out


def build(avatar: Path, captions: Path, out: Path) -> Path:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    duration = duration_of(avatar)
    words = normalize(load_words(captions))
    cats = compute_timings(words, duration)
    for c in cats:
        log.info("%-16s %5.2f→%5.2f  reveals=%s", c["pill"], c["start"], c["end"],
                 {k: round(v, 2) for k, v in c["reveals"].items()})

    chain = OverlayChain(avatar, CROP, ASSET_DIR)
    chain.add_image(build_labels_strip(), 0, 20, 0.0, duration)
    for ci, cat in enumerate(cats):
        pill = build_pill(cat["pill"], ci)
        pw = Image.open(pill).width
        chain.add_image(pill, (W - pw) // 2, PILL_Y, cat["start"], cat["pill_end"])
        for pos, key in enumerate(cat["brands"]):
            size = CENTER if pos == 1 else SIDE
            cx = [X_BAD, X_GOOD, X_GREAT][pos]
            y = ROW_Y_CENTER if pos == 1 else ROW_Y_SIDE
            x = cx - size // 2
            reveal = cat["reveals"].get(key, cat["start"] + 1.0)
            chain.add_image(build_card(key, size, True), x, y, cat["start"], reveal)
            chain.add_image(build_card(key, size, False), x, y, reveal, cat["end"])
    return chain.render(out, duration, preset="slow")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build(ROOT / "assets/avatar/avatar_trimmed.mp4",
          ROOT / "assets/captions/avatar_trimmed.json",
          ROOT / "assets/final/tier_stack.mp4")
