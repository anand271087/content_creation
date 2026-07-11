"""
tier_timeline_reel.py — Dan Martell timeline-board replica (reference: DafvfVaASFn
"Money moves to make you wealthy").

Visual grammar copied from the reference reel:
  - Title pill pinned TOP the whole video
  - Vertical rail of outlined circle badges down the LEFT edge (stage axis),
    visible from frame one
  - Per item: label floats mid-frame while being evaluated → lands NEXT TO its
    stage badge the moment the stage is spoken; items ACCUMULATE
  - No hook, no captions, no spoken CTA

Adaptation: age decades → business revenue stages ("When to automate what").

Reads  assets/avatar/avatar_video_bg.mp4     (studio background version)
       assets/captions/tier_timeline.json    (Scribe word timestamps)
Writes assets/final/tier_timeline.mp4

Usage:
    python3 scripts/tier_timeline_reel.py
"""
from __future__ import annotations
import json, logging, re, subprocess, sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
AVATAR = ROOT / "assets" / "avatar" / "avatar_video_bg.mp4"
CAPS = ROOT / "assets" / "captions" / "tier_timeline.json"
FINAL = ROOT / "assets" / "final" / "tier_timeline.mp4"
ASSET_DIR = ROOT / "assets" / "tier_timeline_assets"
ASSET_DIR.mkdir(parents=True, exist_ok=True)
FINAL.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="[tier_timeline] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("tier_timeline")

W, H = 1080, 1920
FONT_BLACK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

# Zoom 1.66× (user: 1.87× was "too much zoomed") — same chest-level bottom cut
CROP = "crop=650:1156:185:144,scale=1080:1920"

TITLE_LINES = ["AI FOUNDER:", "When to automate what in your business"]

# Stage rail (top→bottom). Badge text must stay short — it sits in a 96px circle.
STAGES = ["Day 1", "Client 1", "1L/mo", "5L/mo", "20L/mo"]
RAIL_X = 44                 # badge left edge
BADGE_D = 96                # badge diameter
RAIL_Y0, RAIL_STEP = 470, 250   # first badge top, vertical spacing
LABEL_X = RAIL_X + BADGE_D + 22  # landed labels start here
FLOAT_Y = 1480    # below the chin at the 1.66× crop

# Items: (anchor word, land word after anchor, stage index, slot, label)
ITEMS = [
    ("content",   "day",    0, 0, "AI content system"),
    ("email",     "day",    0, 1, "ChatGPT email"),
    ("crm",       "first",  1, 0, "CRM automation"),
    ("assistant", "lakh",   2, 0, "Virtual assistant"),
    ("agents",    "lakhs",  3, 0, "Custom AI agents"),
    ("employee",  "lakhs",  4, 0, "First employee"),
]
SLOT_DX = [0, 350]          # x offset per slot within a stage row


# ── Assets ──────────────────────────────────────────────────────────────────

def build_title_pill() -> Path:
    f = ImageFont.truetype(FONT_BLACK, 36)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = max(tmp.textlength(t, font=f) for t in TITLE_LINES)
    pw, ph = int(tw + 80), 146
    pill = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(pill)
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=20, fill=(255, 255, 255, 248))
    for i, t in enumerate(TITLE_LINES):
        lw = d.textlength(t, font=f)
        d.text(((pw - lw) / 2, 18 + i * 54), t, font=f, fill=(10, 10, 10, 255))
    out = ASSET_DIR / "title_pill.png"
    pill.save(out)
    return out


def build_rail() -> Path:
    """Vertical rail of outlined circle badges with stage text."""
    rail_h = RAIL_Y0 + RAIL_STEP * (len(STAGES) - 1) + BADGE_D
    rail = Image.new("RGBA", (RAIL_X + BADGE_D + 8, rail_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(rail)
    for i, s in enumerate(STAGES):
        y = RAIL_Y0 + i * RAIL_STEP
        # translucent dark fill + white ring (reads over any background)
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


def build_label(text: str, big: bool, idx: int) -> Path:
    """Float label = big white text w/ black stroke. Landed label = white text
    on a dark rounded pill — raw white text vanished against the warm bokeh
    background (user correction), so landed labels always carry their own bg."""
    size = 42 if big else 28
    f = ImageFont.truetype(FONT_BLACK if big else FONT_BOLD, size)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = int(tmp.textlength(text, font=f))
    if big:
        pad, stroke = 14, 5
        img = Image.new("RGBA", (tw + pad * 2 + stroke * 2, size + pad * 2 + stroke * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.text((pad + stroke, pad), text, font=f, fill=(255, 255, 255, 255),
               stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    else:
        pad_x, pad_y = 18, 10
        img = Image.new("RGBA", (tw + pad_x * 2, size + pad_y * 2 + 6), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=12,
                            fill=(14, 14, 14, 205))
        d.text((pad_x, pad_y), text, font=f, fill=(255, 255, 255, 255))
    out = ASSET_DIR / f"label_{'float' if big else 'land'}_{idx}.png"
    img.save(out)
    return out


# ── Timing ──────────────────────────────────────────────────────────────────

def clean(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


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
    out = []
    used_anchor_idx = -1
    for anchor, land, stage_i, slot, label in ITEMS:
        a_t = l_t = None
        for i, w in enumerate(words):
            if i <= used_anchor_idx:
                continue
            if a_t is None and clean(w["word"]) == anchor:
                a_t = max(0.0, w["start"] - 0.20)
                used_anchor_idx = i
                for w2 in words[i + 1:]:
                    if clean(w2["word"]) == land:
                        l_t = w2["start"]
                        break
                break
        if a_t is None:
            log.warning("anchor %r not found — skipping", anchor)
            continue
        if l_t is None:
            l_t = a_t + 1.5
        out.append({"label": label, "stage": stage_i, "slot": slot,
                    "start": a_t, "land": l_t})
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
    items = compute_timings(words, duration)
    for it in items:
        log.info("%-20s stage=%d  eval %5.2f → land %5.2f",
                 it["label"], it["stage"], it["start"], it["land"])

    title = build_title_pill()
    rail = build_rail()
    tp_w = Image.open(title).width

    inputs = ["-i", str(AVATAR), "-i", str(title), "-i", str(rail)]
    overlays = [
        (1, (W - tp_w) // 2, 60, 0.0, duration),   # title pill
        (2, 0, 0, 0.0, duration),                  # stage rail (pre-positioned)
    ]
    idx = 3

    for n, it in enumerate(items):
        fl = build_label(it["label"], big=True, idx=n)
        fw = Image.open(fl).width
        inputs += ["-i", str(fl)]
        overlays.append((idx, (W - fw) // 2, FLOAT_Y, it["start"], it["land"]))
        idx += 1

        ll = build_label(it["label"], big=False, idx=n)
        lh = Image.open(ll).height
        y = RAIL_Y0 + it["stage"] * RAIL_STEP + (BADGE_D - lh) // 2
        x = LABEL_X + SLOT_DX[it["slot"]]
        inputs += ["-i", str(ll)]
        overlays.append((idx, x, y, it["land"], duration))
        idx += 1

    parts = [f"[0:v]{CROP}[base]"]
    prev = "base"
    for n, (i, x, y, s, e) in enumerate(overlays):
        lab = f"o{n}"
        parts.append(f"[{prev}][{i}:v]overlay=x={x}:y={y}"
                     f":enable='between(t\\,{s:.2f}\\,{e:.2f})'[{lab}]")
        prev = lab

    subprocess.run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", ";".join(parts),
        "-map", f"[{prev}]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", str(FINAL),
    ], check=True)

    mb = FINAL.stat().st_size / 1e6
    print(f"\n✅ tier_timeline built — {duration:.1f}s / {mb:.1f} MB → {FINAL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
