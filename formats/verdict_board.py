"""2-column binary verdict board (Dan Martell Da8tNEnk8R4 replica).

Grammar: NO hook, NO captions, NO spoken CTA. Frame 1 shows the empty
FUTURE | FINISHED T-chart pinned lower-third. Per beat: big logo card pops
center-frame with a motion-blur-in on the spoken tool name (pop_card motion
template, chroma-keyed), then a small tile lands under the verdict column and
accumulates. Hard end after the last verdict; CTA lives in the IG caption.

Script pattern: "[TOOL]. [VERDICT]. [punchy reason]." — include one
split-verdict beat (comment engine).

Palette derives from the avatar look's set (palette-from-background rule) —
pass `palette` sampled from the render.
"""
from __future__ import annotations
import logging
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.brand import W, FONT_BLACK, FONT_BOLD
from core.cards import logo_image
from core.motion import pop_card, MAGENTA
from core.overlays import OverlayChain
from core.words import load_words, normalize, find_after_anchor, duration_of

log = logging.getLogger("verdict_board")

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "assets" / "verdict_assets"
LOGO_DIR = ROOT / "assets" / "tier_cards" / "real_logos"

# white_chair set: sage green chair / red niche / gold frames / charcoal wall
DEFAULT_PALETTE = {
    "future":  (143, 191, 108),   # sage green (chair)
    "finished": (214, 69, 51),    # red niche accent
    "header_pill": (20, 23, 27, 216),
    "gold": (176, 141, 63),       # frame gold — rules/divider
    "tile_bg": (244, 241, 233),   # warm white (polo)
    "tile_text": (24, 27, 31),
    "card_bg": "#F4F1E9",
    "card_text": "#181B1F",
}

COL_X = [300, 780]                # FUTURE | FINISHED centers
HEAD_Y, ITEMS_Y0, ITEM_H = 1130, 1252, 72
# pop renders at 720x520 but displays smaller at CHEST level (below face,
# above board) — the Dan card sits over the torso, never the face
POP_DISP_W, POP_DISP_H = 560, 404
POP_X, POP_Y = (W - POP_DISP_W) // 2, 660

# (label, logo key or None, column 0=future 1=finished, name anchor, verdict word)
ITEMS = [
    ("ChatGPT Chat", "chatgpt",   1, "chatgpt",   "finished"),
    ("Agent Mode",   "chatgpt",   0, "agent",     "future"),
    ("Zapier",       "zapier",    1, "zapier",    "finished"),
    ("n8n",          "n8n",       0, "n8n",       "future"),
    ("LangChain",    "langchain", 1, "langchain", "finished"),
    ("Make",         "make",      1, "make",      "finished"),
    ("HeyGen",       "heygen",    0, "heygen",    "future"),
    ("Claude Code",  "claude",    0, "claude",    "future"),
    ("AI Agents",    None,        0, "agents",    "future"),
]


def headers_strip(pal) -> Path:
    strip = Image.new("RGBA", (W, 110), (0, 0, 0, 0))
    d = ImageDraw.Draw(strip)
    f = ImageFont.truetype(FONT_BLACK, 40)
    for (label, color), cx in zip(
            [("FUTURE", pal["future"]), ("FINISHED", pal["finished"])], COL_X):
        lw = d.textlength(label, font=f)
        pw = int(lw + 56)
        d.rounded_rectangle([cx - pw // 2, 0, cx + pw // 2, 66], radius=16,
                            fill=pal["header_pill"])
        d.text((cx - lw / 2, 10), label, font=f, fill=(*color, 255))
    # gold rule under headers + dashed center divider
    d.rectangle([70, 84, W - 70, 88], fill=(*pal["gold"], 230))
    return _save(strip, "headers.png")


def divider(pal, height: int) -> Path:
    img = Image.new("RGBA", (8, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for y in range(0, height, 20):
        d.rectangle([3, y, 5, y + 11], fill=(*pal["gold"], 200))
    return _save(img, "divider.png")


def tile(label: str, logo_key: str | None, idx: int, pal) -> Path:
    f = ImageFont.truetype(FONT_BOLD, 26)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = int(tmp.textlength(label, font=f))
    lg = 40 if logo_key else 0
    w = tw + lg + (16 if logo_key else 0) + 40
    img = Image.new("RGBA", (w, 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w, 60], radius=14, fill=(*pal["tile_bg"], 245))
    x = 20
    if logo_key:
        li = logo_image(logo_key, lg, ASSET_DIR)
        img.paste(li, (x, 10), li if li.mode == "RGBA" else None)
        x += lg + 16
    d.text((x, 15), label, font=f, fill=(*pal["tile_text"], 255))
    return _save(img, f"tile_{idx}.png")


def _save(img: Image.Image, name: str) -> Path:
    out = ASSET_DIR / name
    img.save(out)
    return out


def build(avatar: Path, captions: Path, out: Path,
          items=None, palette: dict | None = None,
          crop: str = "none", letterbox_band: str | None = None,
          sharp_crop: str | None = None, sharp_y: int = 500,
          grade: str = "sharp_4k") -> Path:
    global ITEMS
    if items is not None:
        ITEMS = items
    pal = palette or DEFAULT_PALETTE
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    duration = duration_of(avatar)
    words = normalize(load_words(captions))

    chain = OverlayChain(avatar, crop, ASSET_DIR, grade=grade)
    if letterbox_band:
        chain.set_letterbox_base(letterbox_band, sharp_crop, sharp_y, grade=grade)

    chain.add_image(headers_strip(pal), 0, HEAD_Y, 0.0, duration)
    bh = len([i for i in ITEMS if i[2] == 0]) * ITEM_H + 30
    chain.add_image(divider(pal, bh), (W - 8) // 2, ITEMS_Y0 - 12, 0.0, duration)

    col_counts = [0, 0]
    cursor = 0.0    # anchors matched in SCRIPT ORDER — a tool name that also
    last_land = 0.0 # appears inside an earlier reason must not match early
    from core.words import clean
    for k, (label, logo_key, col, anchor, verdict) in enumerate(ITEMS):
        name_t = next((w["start"] for w in words
                       if clean(w["word"]) == anchor and w["start"] >= cursor), None)
        verdict_t = None if name_t is None else next(
            (w["start"] for w in words
             if clean(w["word"]) == verdict and w["start"] > name_t), None)
        if name_t is None or verdict_t is None:
            log.warning("anchor %r/%r not found after %.2f — skipped",
                        anchor, verdict, cursor)
            continue
        cursor = verdict_t
        last_land = max(last_land, verdict_t)
        pop_start = max(0.0, name_t - 0.15)
        log.info("%-13s %-8s pop %5.2f → land %5.2f", label, verdict.upper(),
                 pop_start, verdict_t)

        pop = pop_card(label, LOGO_DIR / f"{logo_key}.png" if logo_key else None,
                       ASSET_DIR / f"pop_{k}.mp4", card_bg=pal["card_bg"],
                       text_color=pal["card_text"],
                       duration=max(1.2, verdict_t - pop_start + 0.1))
        chain.add_video(pop, POP_X, POP_Y, pop_start, verdict_t,
                        POP_DISP_W, POP_DISP_H, chroma=MAGENTA)

        tl = tile(label, logo_key, k, pal)
        tw_ = Image.open(tl).width
        slot = col_counts[col]; col_counts[col] += 1
        chain.add_image(tl, COL_X[col] - tw_ // 2, ITEMS_Y0 + slot * ITEM_H,
                        verdict_t, duration)
        chain.flash_at(verdict_t)

    # hard end shortly after the last land — never show the avatar's dead tail
    end = min(duration, last_land + 1.6)
    return chain.render(out, end, preset="slow")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build(ROOT / "assets/avatar/avatar_video.mp4",
          ROOT / "assets/captions/verdict.json",
          ROOT / "assets/final/verdict_board.mp4")
