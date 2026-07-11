"""
timer_reel.py — live countdown-timer reel (ref: Dand0dtCcrZ "Deleting your
fear of rejection in under 60s"). A visible timer ticks down for the whole
video — the time-boxed promise is the retention device.

The timer is a clean rounded card with a live mm:ss countdown rendered by an
ffmpeg drawtext expression (no assets to animate).

FORMAT-DEMO MODE: runs on any existing avatar video; the timer starts at
--from-secs (default 60) and ticks in real time.

Reads  assets/avatar/avatar_trimmed.mp4  (or --input)
Writes assets/final/timer_demo.mp4
"""
from __future__ import annotations
import argparse, logging, subprocess, sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "assets" / "timer_assets"
ASSET_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="[timer] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("timer")

W, H = 1080, 1920
FONT_BLACK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
MONO = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"

CROP = "crop=650:1156:185:144,scale=1080:1920"   # approved 1.66x chest crop

TITLE_LINES = ["Deleting your fear", "of the camera"]
TIMER_W, TIMER_H = 560, 240
TIMER_X, TIMER_Y = (W - TIMER_W) // 2, 1430


def build_title() -> Path:
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


def build_timer_card() -> Path:
    """White rounded timer card — the ticking digits draw on top via drawtext."""
    card = Image.new("RGBA", (TIMER_W, TIMER_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, TIMER_W - 1, TIMER_H - 1], radius=34,
                        fill=(250, 250, 250, 252))
    d.rounded_rectangle([0, 0, TIMER_W - 1, TIMER_H - 1], radius=34,
                        outline=(20, 20, 20, 255), width=5)
    out = ASSET_DIR / "timer_card.png"
    card.save(out)
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=ROOT / "assets/avatar/avatar_trimmed.mp4")
    p.add_argument("--output", type=Path, default=ROOT / "assets/final/timer_demo.mp4")
    p.add_argument("--from-secs", type=int, default=60)
    args = p.parse_args()
    if not args.input.exists():
        log.error("missing %s", args.input); return 2

    duration = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(args.input)]).decode().strip())

    title = build_title()
    card = build_timer_card()
    tw_ = Image.open(title).width

    start = args.from_secs
    mono = MONO.replace(" ", "\\ ")
    # live countdown text: MM:SS remaining, floors at 0
    timer_txt = (
        f"drawtext=fontfile={mono}"
        f":text='%{{eif\\:max(0\\,({start}-t))/60\\:d\\:2}}\\:%{{eif\\:mod(max(0\\,{start}-t)\\,60)\\:d\\:2}}'"
        f":fontsize=132:fontcolor=#111111"
        f":x={TIMER_X}+({TIMER_W}-text_w)/2:y={TIMER_Y}+({TIMER_H}-text_h)/2"
    )

    fc = (
        f"[0:v]{CROP}[base];"
        f"[base][1:v]overlay=x={(W - tw_) // 2}:y=60[t1];"
        f"[t1][2:v]overlay=x={TIMER_X}:y={TIMER_Y}[t2];"
        f"[t2]{timer_txt}[final]"
    )

    subprocess.run([
        "ffmpeg", "-y", "-i", str(args.input), "-i", str(title), "-i", str(card),
        "-filter_complex", fc,
        "-map", "[final]", "-map", "0:a", "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", str(args.output),
    ], check=True)
    print(f"\n✅ timer demo → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
