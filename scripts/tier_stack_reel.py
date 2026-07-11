"""
tier_stack_reel.py — Dan Martell tier-list replica (reference: DaEDt-igYil).

Visual grammar copied from the reference reel:
  - 3-card row pinned at TOP for the whole category:
      BAD (left, 240px) | GOOD (center, 280px — bigger) | GREAT (right, 240px)
  - Tier labels (BAD/GOOD/GREAT) in bold white above each card — persistent
  - ALL 3 logos BLURRED at category start → each un-blurs on the spoken word
  - ONE persistent category pill at chest level ("Scripting?") — a question
  - NO word-by-word captions
  - No hook — video starts inside category 1

Reads  assets/avatar/avatar_trimmed.mp4      (hookless, studio background)
       assets/captions/avatar_trimmed.json   (Scribe word timestamps)
Writes assets/final/tier_stack.mp4

Usage:
    python3 scripts/tier_stack_reel.py
"""
from __future__ import annotations
import json, logging, re, subprocess, sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
AVATAR = ROOT / "assets" / "avatar" / "avatar_trimmed.mp4"
CAPS = ROOT / "assets" / "captions" / "avatar_trimmed.json"
FINAL = ROOT / "assets" / "final" / "tier_stack.mp4"
CARD_DIR = ROOT / "assets" / "tier_cards"
CARD_DIR.mkdir(parents=True, exist_ok=True)
FINAL.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="[tier_stack] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("tier_stack")

W, H = 1080, 1920
FONT_BLACK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

SIDE, CENTER = 240, 280          # card sizes
ROW_Y_SIDE, ROW_Y_CENTER = 130, 100
X_BAD, X_GOOD, X_GREAT = 230, 540, 850   # card center x
LABEL_STRIP_H = 100
PILL_Y = 1450                     # category pill top (chest level)

# Chest-up crop of the studio avatar (user: "keep till chest level").
# Lands hairline ≈ y 570 (below the card row) and cuts the frame at the chest.
CROP = "crop=579:1029:221:271,scale=1080:1920"

# Categories: (pill_text, window anchor word, [(brand_key, reveal word), ...])
# Brand marks reuse authority_stack's SVG library.
sys.path.insert(0, str(ROOT / "scripts"))
from authority_stack import BRANDS  # noqa: E402  (tier, name, anchors, svg)

CATEGORIES = [
    {"pill": "Scripting?",      "brands": ["chatgpt", "gemini", "claude"]},
    {"pill": "Your AI Avatar?", "brands": ["sora", "synthesia", "heygen"]},
    {"pill": "The Voice?",      "brands": ["free_clone", "descript", "elevenlabs"]},
]


# ── Asset rendering ─────────────────────────────────────────────────────────

REAL_LOGO_DIR = CARD_DIR / "real_logos"


def rasterize_mark(key: str, px: int) -> Image.Image:
    """Real downloaded brand logo if present (assets/tier_cards/real_logos/{key}.png),
    else fall back to the stylized SVG mark. Non-square logos (wordmarks) are
    scaled to fit a px×px box preserving aspect ratio."""
    real = REAL_LOGO_DIR / f"{key}.png"
    if real.exists():
        logo = Image.open(real).convert("RGBA")
        scale = min(px / logo.width, px / logo.height)
        nw, nh = max(1, round(logo.width * scale)), max(1, round(logo.height * scale))
        logo = logo.resize((nw, nh), Image.LANCZOS)
        box = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        box.paste(logo, ((px - nw) // 2, (px - nh) // 2), logo)
        return box

    _tier, _name, _a, mark = BRANDS[key]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" '
           f'width="{px}" height="{px}">{mark}</svg>')
    svg_p = CARD_DIR / f"_{key}.svg"
    png_p = CARD_DIR / f"_{key}.png"
    svg_p.write_text(svg, encoding="utf-8")
    subprocess.run(["rsvg-convert", "-w", str(px), "-h", str(px),
                    "-o", str(png_p), str(svg_p)], check=True, capture_output=True)
    return Image.open(png_p).convert("RGBA")


def build_card(key: str, size: int, blurred: bool) -> Path:
    """White rounded card. Sharp = tool name top + crisp logo.
    Blurred = heavily blurred logo, no name (the suspense state)."""
    _tier, name, _a, _m = BRANDS[key]
    card = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.18),
                        fill=(255, 255, 255, 255))

    logo_px = int(size * 0.52)
    logo = rasterize_mark(key, logo_px)
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

    out = CARD_DIR / f"{key}_{'blur' if blurred else 'sharp'}_{size}.png"
    card.save(out)
    return out


def build_labels_strip() -> Path:
    """BAD / GOOD / GREAT above the card positions, white + black stroke."""
    strip = Image.new("RGBA", (W, LABEL_STRIP_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(strip)
    f = ImageFont.truetype(FONT_BLACK, 36)
    for text, cx, y in [("BAD", X_BAD, 52), ("GOOD", X_GOOD, 22), ("GREAT", X_GREAT, 52)]:
        tw = d.textlength(text, font=f)
        d.text((cx - tw / 2, y), text, font=f, fill=(255, 255, 255, 255),
               stroke_width=5, stroke_fill=(0, 0, 0, 255))
    out = CARD_DIR / "labels_strip.png"
    strip.save(out)
    return out


def build_pill(text: str, idx: int) -> Path:
    """White rounded pill with bold black question text (chest level)."""
    f = ImageFont.truetype(FONT_BLACK, 46)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = tmp.textlength(text, font=f)
    pw, ph = int(tw + 76), 96
    pill = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(pill)
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=16, fill=(255, 255, 255, 255))
    d.text((38, (ph - 60) / 2), text, font=f, fill=(10, 10, 10, 255))
    out = CARD_DIR / f"pill_{idx}.png"
    pill.save(out)
    return out


# ── Timing from Scribe words ────────────────────────────────────────────────

def clean(w: str) -> str:
    return re.sub(r"[^a-z]", "", w.lower())


def load_words() -> list[dict]:
    data = json.loads(CAPS.read_text())
    out = []
    for seg in data.get("segments", []):
        for w in seg.get("words", []) or []:
            t = (w.get("word") or w.get("text") or "").strip()
            if t:
                out.append({"word": t, "start": float(w["start"]), "end": float(w["end"])})
    return out


def compute_timings(words: list[dict], duration: float) -> list[dict]:
    """Category windows + per-brand reveal times."""
    def find(pred, after=0.0):
        for w in words:
            if w["start"] >= after and pred(clean(w["word"])):
                return w["start"]
        return None

    # Category anchors: "scripting", "avatar", "voice"
    t1 = 0.0
    t2 = find(lambda c: c == "avatar")
    t2 = (t2 or 6.0) - 0.9          # window starts at "for your AI avatar" lead-in
    t3 = find(lambda c: c == "voice")
    t3 = (t3 or 12.0) - 0.9
    t_cta = find(lambda c: c == "thats") or find(lambda c: c == "comment") or duration - 5

    windows = [(t1, t2), (t2, t3), (t3, duration)]   # cat3 row persists to end
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
        out.append({"pill": cat["pill"], "brands": cat["brands"],
                    "start": windows[i][0], "end": windows[i][1],
                    "pill_end": pill_end[i], "reveals": reveals})
    return out


# ── Compose ─────────────────────────────────────────────────────────────────

def main() -> int:
    if not AVATAR.exists():
        log.error("missing %s", AVATAR); return 2
    if not CAPS.exists():
        log.error("missing %s", CAPS); return 2

    duration = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(AVATAR)]).decode().strip())

    words = load_words()
    cats = compute_timings(words, duration)
    for c in cats:
        log.info("%-16s %5.2f→%5.2f  reveals: %s", c["pill"], c["start"], c["end"],
                 {k: round(v, 2) for k, v in c["reveals"].items()})

    # Assets
    labels = build_labels_strip()
    inputs = ["-i", str(AVATAR), "-i", str(labels)]
    overlays = []   # (input_index, x, y, enable_start, enable_end)
    idx = 2

    # Labels strip visible the whole video
    overlays.append((1, 0, 20, 0.0, duration))

    for ci, cat in enumerate(cats):
        pill = build_pill(cat["pill"], ci)
        pw = Image.open(pill).width
        inputs += ["-i", str(pill)]
        overlays.append((idx, (W - pw) // 2, PILL_Y, cat["start"], cat["pill_end"]))
        idx += 1

        for pos, key in enumerate(cat["brands"]):     # bad, good, great
            size = CENTER if pos == 1 else SIDE
            cx = [X_BAD, X_GOOD, X_GREAT][pos]
            y = ROW_Y_CENTER if pos == 1 else ROW_Y_SIDE
            x = cx - size // 2
            reveal = cat["reveals"].get(key, cat["start"] + 1.0)

            blur_p = build_card(key, size, blurred=True)
            sharp_p = build_card(key, size, blurred=False)
            inputs += ["-i", str(blur_p)]
            overlays.append((idx, x, y, cat["start"], reveal)); idx += 1
            inputs += ["-i", str(sharp_p)]
            overlays.append((idx, x, y, reveal, cat["end"])); idx += 1

    # Build filter chain — chest-up crop first, then overlays on top
    parts = [f"[0:v]{CROP}[base]"]
    prev = "base"
    for n, (i, x, y, s, e) in enumerate(overlays):
        lab = f"o{n}"
        parts.append(f"[{prev}][{i}:v]overlay=x={x}:y={y}"
                     f":enable='between(t\\,{s:.2f}\\,{e:.2f})'[{lab}]")
        prev = lab
    fc = ";".join(parts)

    log.info("%d overlays, filter %d chars", len(overlays), len(fc))
    subprocess.run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", fc,
        "-map", f"[{prev}]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", str(FINAL),
    ], check=True)

    mb = FINAL.stat().st_size / 1e6
    print(f"\n✅ tier_stack built — {duration:.1f}s / {mb:.1f} MB → {FINAL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
