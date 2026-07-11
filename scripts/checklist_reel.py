"""
checklist_reel.py — numbered checklist reveal (ref: DaJNU6KD4BG "Sell Anyone
In 5 Steps"). All steps on screen from the start, DIMMED — each lights up in
its own color (rainbow ladder) on its beat. Fully-lit list = screenshot payoff.

FORMAT-DEMO MODE: without --caps (word timestamps), steps reveal on an even
cadence across the video — used to preview the look on existing footage
without a new HeyGen render. For the postable version, pass --caps and set
ITEMS anchor words.

Reads  assets/avatar/avatar_trimmed.mp4  (or --input)
Writes assets/final/checklist_demo.mp4
"""
from __future__ import annotations
import argparse, logging, subprocess, sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "assets" / "checklist_assets"
ASSET_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="[checklist] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("checklist")

W, H = 1080, 1920
FONT_BLACK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"

CROP = "crop=650:1156:185:144,scale=1080:1920"   # approved 1.66x chest crop

TITLE_LINES = ["BUILD YOUR AI AVATAR", "IN 5 STEPS"]
STEPS = [
    ("SCRIPT WITH CLAUDE",    "#ff5757"),
    ("AVATAR IN HEYGEN",      "#ff9f43"),
    ("VOICE IN ELEVENLABS",   "#ffd32a"),
    ("EDIT RUNS ITSELF",      "#2ecc71"),
    ("POST EVERY DAY",        "#54a0ff"),
]
LIST_X, LIST_Y = 90, 1150      # panel position (below chin at 1.66x crop)
ROW_H, PAD = 104, 26


def build_title_pill() -> Path:
    f = ImageFont.truetype(FONT_BLACK, 40)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = max(tmp.textlength(t, font=f) for t in TITLE_LINES)
    pw, ph = int(tw + 80), 150
    pill = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(pill)
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=20, fill=(255, 255, 255, 248))
    for i, t in enumerate(TITLE_LINES):
        lw = d.textlength(t, font=f)
        d.text(((pw - lw) / 2, 18 + i * 58), t, font=f, fill=(10, 10, 10, 255))
    out = ASSET_DIR / "title.png"
    pill.save(out)
    return out


def build_panel_base() -> Path:
    """Dark translucent panel with ALL steps dimmed/ghosted (visible from t=0)."""
    ph = PAD * 2 + ROW_H * len(STEPS)
    pw = W - LIST_X * 2
    panel = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(panel)
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=26, fill=(10, 10, 12, 175))
    f = ImageFont.truetype(FONT_BLACK, 44)
    for i, (text, _color) in enumerate(STEPS):
        y = PAD + i * ROW_H + 24
        d.text((44, y), f"{i + 1}. {text}", font=f, fill=(255, 255, 255, 60))  # ghosted
    out = ASSET_DIR / "panel_base.png"
    panel.save(out)
    return out


def build_lit_row(i: int) -> Path:
    """Single step, fully lit in its rainbow color (overlays its ghost row)."""
    text, color = STEPS[i]
    f = ImageFont.truetype(FONT_BLACK, 44)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    label = f"{i + 1}. {text}"
    tw = int(tmp.textlength(label, font=f))
    img = Image.new("RGBA", (tw + 16, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((4, 2), label, font=f, fill=color, stroke_width=2, stroke_fill=(0, 0, 0, 220))
    out = ASSET_DIR / f"lit_{i}.png"
    img.save(out)
    return out


def build_lightleak() -> Path:
    yy, xx = np.mgrid[0:H, 0:W]
    d1 = np.sqrt(((yy - H * 0.25) / (H * 0.7)) ** 2 + ((xx - W * 0.85) / (W * 0.7)) ** 2)
    glow = np.clip(1 - d1, 0, 1) * 0.9
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[:, :, 0] = 255
    rgba[:, :, 1] = np.clip(150 + glow * 80, 0, 255).astype(np.uint8)
    rgba[:, :, 2] = 80
    rgba[:, :, 3] = np.clip(glow * 140, 0, 140).astype(np.uint8)
    out = ASSET_DIR / "leak.png"
    Image.fromarray(rgba).save(out)
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=ROOT / "assets/avatar/avatar_trimmed.mp4")
    p.add_argument("--output", type=Path, default=ROOT / "assets/final/checklist_demo.mp4")
    args = p.parse_args()
    if not args.input.exists():
        log.error("missing %s", args.input); return 2

    duration = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(args.input)]).decode().strip())

    # Demo cadence: reveal steps evenly across 75% of the runtime
    n = len(STEPS)
    span = duration * 0.75
    reveals = [1.2 + i * (span - 1.2) / n for i in range(n)]
    log.info("reveals: %s", [round(r, 1) for r in reveals])

    title = build_title_pill()
    panel = build_panel_base()
    leak = build_lightleak()
    tw_ = Image.open(title).width

    inputs = ["-i", str(args.input), "-i", str(title), "-i", str(panel)]
    overlays = [
        (1, (W - tw_) // 2, 60, 0.0, duration),
        (2, LIST_X, LIST_Y, 0.0, duration),
    ]
    idx = 3
    for i in range(n):
        lit = build_lit_row(i)
        inputs += ["-i", str(lit)]
        overlays.append((idx, LIST_X + 44 - 4, LIST_Y + PAD + i * ROW_H + 24 - 2,
                         reveals[i], duration))
        idx += 1

    inputs += ["-i", str(leak)]
    leak_idx = idx

    parts = [f"[0:v]{CROP}[base]"]
    prev = "base"
    for k, (i, x, y, s, e) in enumerate(overlays):
        lab = f"o{k}"
        parts.append(f"[{prev}][{i}:v]overlay=x={x}:y={y}"
                     f":enable='between(t\\,{s:.2f}\\,{e:.2f})'[{lab}]")
        prev = lab
    flash = "+".join(f"between(t\\,{t:.2f}\\,{t + 0.22:.2f})" for t in reveals)
    parts.append(f"[{prev}][{leak_idx}:v]overlay=x=0:y=0:enable='{flash}'[fl]")
    eq = "+".join(f"between(t\\,{t:.2f}\\,{t + 0.14:.2f})" for t in reveals)
    parts.append(f"[fl]eq=brightness=0.13:enable='{eq}'[final]")

    subprocess.run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", ";".join(parts),
        "-map", "[final]", "-map", "0:a", "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", str(args.output),
    ], check=True)
    print(f"\n✅ checklist demo → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
