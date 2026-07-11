"""
sort_board_reel.py — 3-column sort board (ref: DaliD7IDyvi "Success Habits").
Column headers pinned from frame one — MATTERS / DOESN'T MATTER / HURTFUL —
items float at chest, land under their column, accumulate.

FORMAT-DEMO MODE: without word timestamps, items land on an even cadence.
For the postable version wire anchors like tier_timeline_reel.py.

Reads  assets/avatar/avatar_video_bg.mp4  (or --input)
Writes assets/final/sortboard_demo.mp4
"""
from __future__ import annotations
import argparse, logging, subprocess, sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "assets" / "sortboard_assets"
ASSET_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="[sortboard] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("sortboard")

W, H = 1080, 1920
FONT_BLACK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

# Blue-avatar framing crop (from countdown_reel)
CROP = "crop=591:1050:179:250,scale=1080:1920"

TITLE_LINES = ["CONTENT HABITS:", "What ACTUALLY matters?"]
COLUMNS = [("MATTERS", "#2ecc71"), ("DOESN'T\nMATTER", "#ffd32a"), ("HURTFUL", "#ff5757")]
COL_X = [190, 540, 890]          # column center x
HEAD_Y = 250                     # column headers top
ITEMS_Y0, ITEM_H = 360, 74       # landed items start / per-item spacing
FLOAT_Y = 1500

# (label, column index) in spoken order
ITEMS = [
    ("Posting daily",      0),
    ("Fancy camera",       1),
    ("Buying followers",   2),
    ("Strong hooks",       0),
    ("Perfect editing",    1),
    ("AI avatar",          0),
    ("Waiting till ready", 2),
]


def build_title() -> Path:
    f = ImageFont.truetype(FONT_BLACK, 38)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = max(tmp.textlength(t, font=f) for t in TITLE_LINES)
    pw, ph = int(tw + 80), 146
    pill = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(pill)
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=20, fill=(255, 255, 255, 248))
    for i, t in enumerate(TITLE_LINES):
        lw = d.textlength(t, font=f)
        d.text(((pw - lw) / 2, 16 + i * 56), t, font=f, fill=(10, 10, 10, 255))
    out = ASSET_DIR / "title.png"
    pill.save(out)
    return out


def build_headers() -> Path:
    """Column header pills + dotted dividers, full-width strip."""
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
    # dotted dividers between columns
    for x in [(COL_X[0] + COL_X[1]) // 2, (COL_X[1] + COL_X[2]) // 2]:
        for y in range(0, 130, 18):
            d.rectangle([x - 1, y, x + 1, y + 9], fill=(255, 255, 255, 120))
    out = ASSET_DIR / "headers.png"
    strip.save(out)
    return out


def build_label(text: str, big: bool, idx: int) -> Path:
    size = 42 if big else 24
    f = ImageFont.truetype(FONT_BLACK if big else FONT_BOLD, size)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = int(tmp.textlength(text, font=f))
    if big:
        pad, stroke = 14, 5
        img = Image.new("RGBA", (tw + (pad + stroke) * 2, size + (pad + stroke) * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.text((pad + stroke, pad), text, font=f, fill=(255, 255, 255, 255),
               stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    else:
        img = Image.new("RGBA", (tw + 32, size + 22), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=11,
                            fill=(14, 14, 14, 205))
        d.text((16, 9), text, font=f, fill=(255, 255, 255, 255))
    out = ASSET_DIR / f"label_{'f' if big else 'l'}_{idx}.png"
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
    p.add_argument("--input", type=Path, default=ROOT / "assets/avatar/avatar_video_bg.mp4")
    p.add_argument("--output", type=Path, default=ROOT / "assets/final/sortboard_demo.mp4")
    args = p.parse_args()
    if not args.input.exists():
        log.error("missing %s", args.input); return 2

    duration = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(args.input)]).decode().strip())

    n = len(ITEMS)
    span = duration * 0.8
    starts = [1.0 + i * (span - 1.0) / n for i in range(n)]
    lands = [s + 2.0 for s in starts]

    title = build_title()
    headers = build_headers()
    leak = build_lightleak()
    tw_ = Image.open(title).width

    inputs = ["-i", str(args.input), "-i", str(title), "-i", str(headers)]
    overlays = [
        (1, (W - tw_) // 2, 60, 0.0, duration),
        (2, 0, HEAD_Y, 0.0, duration),
    ]
    idx = 3
    col_counts = [0, 0, 0]
    for k, (label, col) in enumerate(ITEMS):
        fl = build_label(label, True, k)
        fw = Image.open(fl).width
        inputs += ["-i", str(fl)]
        overlays.append((idx, (W - fw) // 2, FLOAT_Y, starts[k], lands[k]))
        idx += 1

        ll = build_label(label, False, k)
        lw = Image.open(ll).width
        slot = col_counts[col]; col_counts[col] += 1
        inputs += ["-i", str(ll)]
        overlays.append((idx, COL_X[col] - lw // 2,
                         ITEMS_Y0 + slot * ITEM_H, lands[k], duration))
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
    flash = "+".join(f"between(t\\,{t:.2f}\\,{t + 0.22:.2f})" for t in lands)
    parts.append(f"[{prev}][{leak_idx}:v]overlay=x=0:y=0:enable='{flash}'[fl]")
    eq = "+".join(f"between(t\\,{t:.2f}\\,{t + 0.14:.2f})" for t in lands)
    parts.append(f"[fl]eq=brightness=0.13:enable='{eq}'[final]")

    subprocess.run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", ";".join(parts),
        "-map", "[final]", "-map", "0:a", "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", str(args.output),
    ], check=True)
    print(f"\n✅ sort board demo → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
