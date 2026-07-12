"""Countdown 5→1 + LIVE screen-demo cards (Dan Martell Dak4_ygAPXc replica).

Hook text → "NUMBER N" markers → browser-chrome cards playing real screen
recordings (assets/screen_demos/{key}.mp4, see capture/) → CTA pill.
Light-leak flash at every item start + card entry.
"""
from __future__ import annotations
import logging
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.brand import W, FONT_BLACK, FONT_BOLD, BRAND_BLUE
from core.overlays import OverlayChain
from core.words import load_words, normalize, clean, duration_of

log = logging.getLogger("countdown")

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "assets" / "countdown_assets"
DEMO_DIR = ROOT / "assets" / "screen_demos"

CROP = "blue_183"
HOOK_TEXT = "5 AI TOOLS"
NUM_Y = 120
CARD_W, CARD_H = 760, 740
CARD_X, CARD_Y = (W - CARD_W) // 2, 1160
VID_W, VID_H = 744, 636
VID_X, VID_Y = (W - VID_W) // 2, CARD_Y + 92
CTA_TEXT = "COMMENT: STACK"
DEMO_TOP_CROP = {"elevenlabs": 70}

# (number word, demo/logo key, name, domain)
ITEMS = [
    ("five",  "perplexity", "Perplexity", "perplexity.ai"),
    ("four",  "n8n",        "n8n",        "n8n.io"),
    ("three", "elevenlabs", "ElevenLabs", "elevenlabs.io"),
    ("two",   "claude",     "Claude",     "claude.ai"),
    ("one",   "heygen",     "HeyGen",     "heygen.com"),
]


def big_text(text: str, name: str, size: int = 76) -> Path:
    f = ImageFont.truetype(FONT_BLACK, size)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = int(tmp.textlength(text, font=f))
    stroke, pad = 6, 16
    img = Image.new("RGBA", (tw + (pad + stroke) * 2, size + (pad + stroke) * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((pad + stroke, pad), text, font=f, fill=(255, 255, 255, 255),
           stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    out = ASSET_DIR / f"{name}.png"
    img.save(out)
    return out


def card_frame(idx: int, domain: str) -> Path:
    card = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, CARD_W - 1, CARD_H - 1], radius=26, fill=(250, 250, 250, 252))
    d.rounded_rectangle([0, 0, CARD_W - 1, 84], radius=26, fill=(235, 235, 238, 255))
    d.rectangle([0, 44, CARD_W - 1, 84], fill=(235, 235, 238, 255))
    for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        d.ellipse([28 + i * 34, 32, 48 + i * 34, 52], fill=c)
    d.rounded_rectangle([150, 24, CARD_W - 40, 62], radius=19, fill=(255, 255, 255, 255))
    fu = ImageFont.truetype(FONT_BOLD, 24)
    d.text((172, 30), domain, font=fu, fill=(90, 90, 96, 255))
    out = ASSET_DIR / f"frame_{idx}.png"
    card.save(out)
    return out


def cta_pill() -> Path:
    f = ImageFont.truetype(FONT_BLACK, 52)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = int(tmp.textlength(CTA_TEXT, font=f))
    pw, ph = tw + 90, 110
    pill = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(pill)
    rgb = tuple(int(BRAND_BLUE[i:i + 2], 16) for i in (1, 3, 5))
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=22, fill=(*rgb, 255))
    d.text((45, (ph - 66) / 2), CTA_TEXT, font=f, fill=(255, 255, 255, 255))
    out = ASSET_DIR / "cta_pill.png"
    pill.save(out)
    return out


def compute_timings(words, duration):
    markers = []
    for i, w in enumerate(words):
        if clean(w["word"]) == "number" and i + 1 < len(words):
            markers.append((clean(words[i + 1]["word"]), w["start"]))
    cta_t = next((w["start"] for w in words if clean(w["word"]) == "comment"), duration - 5)

    out = []
    for k, (numword, key, name, domain) in enumerate(ITEMS):
        start = next((t for nn, t in markers if nn == numword), None)
        if start is None:
            log.warning("marker 'number %s' not found — skipped", numword)
            continue
        nxt = [t for _, t in markers if t > start + 0.5]
        end = min(min(nxt) if nxt else cta_t, cta_t)
        out.append({"key": key, "name": name, "domain": domain,
                    "start": max(0.0, start - 0.10), "end": end, "n": 5 - k})
    hook_end = out[0]["start"] if out else 4.0
    return out, hook_end, cta_t


def build(avatar: Path, captions: Path, out: Path) -> Path:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    duration = duration_of(avatar)
    words = normalize(load_words(captions))
    items, hook_end, cta_t = compute_timings(words, duration)
    for it in items:
        log.info("NUMBER %d %-12s %5.2f → %5.2f", it["n"], it["name"], it["start"], it["end"])

    chain = OverlayChain(avatar, CROP, ASSET_DIR)
    hook = big_text(HOOK_TEXT, "hook", 84)
    hw = Image.open(hook).width
    chain.add_image(hook, (W - hw) // 2, NUM_Y, 0.0, hook_end)
    cta = cta_pill()
    cw = Image.open(cta).width
    chain.add_image(cta, (W - cw) // 2, 1520, cta_t, duration)

    for k, it in enumerate(items):
        num = big_text(f"NUMBER {it['n']}", f"num_{it['n']}", 76)
        nw = Image.open(num).width
        chain.add_image(num, (W - nw) // 2, NUM_Y, it["start"], it["end"])

        demo_start = it["start"] + 1.2
        chain.add_image(card_frame(k, it["domain"]), CARD_X, CARD_Y, demo_start, it["end"])
        demo = DEMO_DIR / f"{it['key']}.mp4"
        if demo.exists():
            chain.add_video(demo, VID_X, VID_Y, demo_start, it["end"],
                            VID_W, VID_H, top_crop=DEMO_TOP_CROP.get(it["key"], 0))
        else:
            log.warning("no screen demo for %s — frame only", it["key"])
        chain.flash_at(it["start"], demo_start)

    return chain.render(out, duration, preset="slow")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build(ROOT / "assets/avatar/avatar_video_bg.mp4",
          ROOT / "assets/captions/countdown.json",
          ROOT / "assets/final/countdown.mp4")
