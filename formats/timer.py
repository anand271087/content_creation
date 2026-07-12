"""Live countdown-timer reel (ref: Dand0dtCcrZ "fear of rejection in 60s").

A white timer card ticks down live (ffmpeg drawtext expression) for the whole
video — the visible time-boxed promise is the retention device.
"""
from __future__ import annotations
import logging
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.brand import W, FONT_MONO, CRF_FINAL
from core.cards import title_pill
from core.framing import crop as crop_chain
from core.words import duration_of

log = logging.getLogger("timer")

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "assets" / "timer_assets"

CROP = "grey_166"
TITLE_LINES = ["Deleting your fear", "of the camera"]
TIMER_W, TIMER_H = 560, 240
TIMER_X, TIMER_Y = (W - TIMER_W) // 2, 1430


def timer_card() -> Path:
    card = Image.new("RGBA", (TIMER_W, TIMER_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, TIMER_W - 1, TIMER_H - 1], radius=34,
                        fill=(250, 250, 250, 252))
    d.rounded_rectangle([0, 0, TIMER_W - 1, TIMER_H - 1], radius=34,
                        outline=(20, 20, 20, 255), width=5)
    out = ASSET_DIR / "timer_card.png"
    card.save(out)
    return out


def build(avatar: Path, captions: Path | None, out: Path, from_secs: int = 60) -> Path:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    duration = duration_of(avatar)
    title = title_pill(TITLE_LINES, ASSET_DIR / "title.png", size=40)
    tw = Image.open(title).width

    mono = FONT_MONO.replace(" ", "\\ ")
    timer_txt = (
        f"drawtext=fontfile={mono}"
        f":text='%{{eif\\:max(0\\,({from_secs}-t))/60\\:d\\:2}}\\:%{{eif\\:mod(max(0\\,{from_secs}-t)\\,60)\\:d\\:2}}'"
        f":fontsize=132:fontcolor=#111111"
        f":x={TIMER_X}+({TIMER_W}-text_w)/2:y={TIMER_Y}+({TIMER_H}-text_h)/2"
    )
    fc = (
        f"[0:v]{crop_chain(CROP)}[base];"
        f"[base][1:v]overlay=x={(W - tw) // 2}:y=60[t1];"
        f"[t1][2:v]overlay=x={TIMER_X}:y={TIMER_Y}[t2];"
        f"[t2]{timer_txt}[final]"
    )
    subprocess.run([
        "ffmpeg", "-y", "-i", str(avatar), "-i", str(title), "-i", str(timer_card()),
        "-filter_complex", fc,
        "-map", "[final]", "-map", "0:a", "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", str(CRF_FINAL),
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(out),
    ], check=True)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build(ROOT / "assets/avatar/avatar_trimmed.mp4", None,
          ROOT / "assets/final/timer_demo.mp4")
