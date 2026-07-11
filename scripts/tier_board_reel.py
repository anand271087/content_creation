"""
tier_board_reel.py — Dan Martell S-F tier-board replica (reference: DaYBCF7Fdln).

Visual grammar copied from the reference reel:
  - Title pill pinned TOP for the whole video (2 lines, white pill, black bold)
  - Classic S/A/B/C/D/F tier board over the lower half — colored rank badges,
    dark semi-transparent rows
  - Per item: label floats mid-frame while it's being evaluated → lands in its
    tier row the moment the grade is spoken; items ACCUMULATE (full board = payoff)
  - No hook, no captions, no spoken CTA — video ends the instant the last grade lands

Reads  assets/avatar/avatar_video_bg.mp4   (studio background version)
       assets/captions/tier_board.json     (Scribe word timestamps)
Writes assets/final/tier_board.mp4

Usage:
    python3 scripts/tier_board_reel.py
"""
from __future__ import annotations
import json, logging, re, subprocess, sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
AVATAR = ROOT / "assets" / "avatar" / "avatar_video_bg.mp4"
CAPS = ROOT / "assets" / "captions" / "tier_board.json"
FINAL = ROOT / "assets" / "final" / "tier_board.mp4"
ASSET_DIR = ROOT / "assets" / "tier_board_assets"
ASSET_DIR.mkdir(parents=True, exist_ok=True)
FINAL.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="[tier_board] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("tier_board")

W, H = 1080, 1920
FONT_BLACK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

# Chest-up crop (same geometry as tier_stack_reel — same avatar recording)
CROP = "crop=579:1029:221:271,scale=1080:1920"

TITLE_LINES = ["AI FOUNDER:", "Ranking how founders show up online"]

# Tier board geometry
TIERS = ["S", "A", "B", "C", "D", "F"]
TIER_COLORS = {
    "S": "#fa7ce8", "A": "#7cb5fa", "B": "#fabd7c",
    "C": "#d8fa7c", "D": "#7cfa96", "F": "#fa7c7c",
}
BOARD_X, BOARD_W = 40, 1000
ROW_H, ROW_GAP, BADGE = 90, 4, 90
BOARD_Y = H - (ROW_H + ROW_GAP) * len(TIERS) - 70
FLOAT_Y = 1140            # floating "being evaluated" label y

# Items: (anchor word, grade, row slot index, board label)
ITEMS = [
    ("filming",   "C", 0, "Filming daily"),
    ("editor",    "B", 0, "Video editor"),
    ("followers", "F", 0, "Bought followers"),
    ("text",      "D", 0, "Text only"),
    ("podcast",   "A", 0, "Podcast"),
    ("avatar",    "S", 0, "AI avatar system"),
    ("nothing",   "F", 1, "Doing nothing"),
]
SLOT_X = [BADGE + 26, BADGE + 460]     # x offsets inside a row per slot


# ── Asset rendering ─────────────────────────────────────────────────────────

def build_title_pill() -> Path:
    f = ImageFont.truetype(FONT_BLACK, 38)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = max(tmp.textlength(t, font=f) for t in TITLE_LINES)
    pw, ph = int(tw + 80), 150
    pill = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(pill)
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=20, fill=(255, 255, 255, 248))
    for i, t in enumerate(TITLE_LINES):
        lw = d.textlength(t, font=f)
        d.text(((pw - lw) / 2, 18 + i * 56), t, font=f, fill=(10, 10, 10, 255))
    out = ASSET_DIR / "title_pill.png"
    pill.save(out)
    return out


def build_board_base() -> Path:
    """Empty tier board: colored badges + dark rows."""
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


def build_label(text: str, big: bool, idx: int) -> Path:
    """Item label. big=True → floating evaluation label (white + black stroke).
    big=False → row label (white bold, subtle shadow)."""
    size = 42 if big else 30
    f = ImageFont.truetype(FONT_BLACK if big else FONT_BOLD, size)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = int(tmp.textlength(text, font=f))
    pad, stroke = (14, 5) if big else (8, 0)
    img = Image.new("RGBA", (tw + pad * 2 + stroke * 2, size + pad * 2 + stroke * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if big:
        d.text((pad + stroke, pad), text, font=f, fill=(255, 255, 255, 255),
               stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    else:
        d.text((pad + 2, pad + 2), text, font=f, fill=(0, 0, 0, 200))   # shadow
        d.text((pad, pad), text, font=f, fill=(255, 255, 255, 255))
    out = ASSET_DIR / f"label_{'float' if big else 'row'}_{idx}.png"
    img.save(out)
    return out


# ── Timing ──────────────────────────────────────────────────────────────────

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
    """Per item: eval window start (anchor spoken) + grade moment (letter spoken)."""
    out = []
    for anchor, grade, slot, label in ITEMS:
        a_t = g_t = None
        for i, w in enumerate(words):
            if a_t is None and clean(w["word"]) == anchor:
                a_t = max(0.0, w["start"] - 0.20)
                # find the grade letter after the anchor
                for w2 in words[i + 1:]:
                    if clean(w2["word"]) == grade.lower():
                        g_t = w2["start"]
                        break
                break
        if a_t is None:
            log.warning("anchor %r not found — skipping timing", anchor)
            continue
        if g_t is None:
            g_t = a_t + 1.5
        out.append({"anchor": anchor, "grade": grade, "slot": slot,
                    "label": label, "start": a_t, "grade_t": g_t})
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
        log.info("%-18s %s  eval %5.2f → graded %5.2f", it["label"], it["grade"],
                 it["start"], it["grade_t"])

    title = build_title_pill()
    board = build_board_base()
    tp_w = Image.open(title).width

    inputs = ["-i", str(AVATAR), "-i", str(title), "-i", str(board)]
    overlays = [
        (1, (W - tp_w) // 2, 60, 0.0, duration),        # title pill — whole video
        (2, BOARD_X, BOARD_Y, 0.0, duration),           # empty board — whole video
    ]
    idx = 3

    for n, it in enumerate(items):
        # floating evaluation label (centered) — from anchor until grade lands
        fl = build_label(it["label"], big=True, idx=n)
        fw = Image.open(fl).width
        inputs += ["-i", str(fl)]
        overlays.append((idx, (W - fw) // 2, FLOAT_Y, it["start"], it["grade_t"]))
        idx += 1

        # row label — from grade moment to end (accumulates)
        rl = build_label(it["label"], big=False, idx=n)
        rh = Image.open(rl).height
        row_i = TIERS.index(it["grade"])
        y = BOARD_Y + row_i * (ROW_H + ROW_GAP) + (ROW_H - rh) // 2
        x = BOARD_X + SLOT_X[it["slot"]]
        inputs += ["-i", str(rl)]
        overlays.append((idx, x, y, it["grade_t"], duration))
        idx += 1

    parts = [f"[0:v]{CROP}[base]"]
    prev = "base"
    for n, (i, x, y, s, e) in enumerate(overlays):
        lab = f"o{n}"
        parts.append(f"[{prev}][{i}:v]overlay=x={x}:y={y}"
                     f":enable='between(t\\,{s:.2f}\\,{e:.2f})'[{lab}]")
        prev = lab
    fc = ";".join(parts)

    log.info("%d overlays", len(overlays))
    subprocess.run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", fc,
        "-map", f"[{prev}]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", str(FINAL),
    ], check=True)

    mb = FINAL.stat().st_size / 1e6
    print(f"\n✅ tier_board built — {duration:.1f}s / {mb:.1f} MB → {FINAL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
