"""Append a 1.5s still-frame thumbnail card to the END of both final reels.

Picks up:
  - assets/final/thumbnail.png   (still image)
  - assets/final/final_reel.mp4       (1× full-quality render)
  - assets/final/final_reel_fast.mp4  (1.25× speed-up render)

Writes:
  - assets/final/final_reel_with_thumb.mp4
  - assets/final/final_reel_fast_with_thumb.mp4

How it works:
  1. Build a 1.5s 9:16 silent-audio MP4 from the thumbnail PNG (matched fps/codec to source).
  2. Concat the source video + the thumb card using ffmpeg's concat demuxer.
  3. Re-encode the final to keep audio sync clean (concat with stream copy is fragile when
     the source has variable-fps audio from HeyGen + sting overlays).

Usage:
  python3 scripts/append_thumbnail.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FINAL_DIR = ROOT / "assets" / "final"

THUMB_PNG = FINAL_DIR / "thumbnail.png"
THUMB_SECONDS = 1.5
THUMB_FPS = 30
WIDTH, HEIGHT = 1080, 1920

INPUTS = [
    (FINAL_DIR / "final_reel.mp4",      FINAL_DIR / "final_reel_with_thumb.mp4"),
    (FINAL_DIR / "final_reel_fast.mp4", FINAL_DIR / "final_reel_fast_with_thumb.mp4"),
]


def run(cmd: list[str]) -> None:
    """Run ffmpeg quietly. Raise on non-zero exit."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("ffmpeg cmd failed:", " ".join(cmd))
        print(result.stderr[-2000:])
        sys.exit(1)


def build_thumb_card(out_path: Path) -> None:
    """Render thumbnail.png into a 1.5s 1080x1920 mp4 with silent stereo audio."""
    run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(THUMB_PNG),
        "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo",
        "-t", str(THUMB_SECONDS),
        "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},setsar=1",
        "-c:v", "libx264", "-profile:v", "baseline", "-level", "3.1",
        "-pix_fmt", "yuv420p", "-r", str(THUMB_FPS),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-shortest", "-movflags", "+faststart",
        str(out_path),
    ])


def append_thumb(source: Path, thumb_card: Path, output: Path) -> None:
    """Concat source + thumb_card → output, re-encoding for clean audio sync."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(f"file '{source.as_posix()}'\n")
        f.write(f"file '{thumb_card.as_posix()}'\n")
        list_path = Path(f.name)
    try:
        run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(list_path),
            "-c:v", "libx264", "-profile:v", "baseline", "-level", "3.1",
            "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "fast", "-r", str(THUMB_FPS),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart",
            str(output),
        ])
    finally:
        list_path.unlink(missing_ok=True)


def main() -> int:
    if not THUMB_PNG.exists():
        print(f"ERROR: thumbnail not found at {THUMB_PNG}")
        return 1

    missing = [src for src, _ in INPUTS if not src.exists()]
    if missing:
        for m in missing:
            print(f"ERROR: source missing → {m}")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        thumb_card = Path(tmp) / "thumb_card.mp4"
        print(f"  Building 1.5s thumbnail card → {thumb_card.name}")
        build_thumb_card(thumb_card)
        size = thumb_card.stat().st_size
        print(f"  thumb_card built ({size/1024:.0f} KB)\n")

        for source, output in INPUTS:
            print(f"  Appending → {output.name}")
            append_thumb(source, thumb_card, output)
            print(f"    {source.name}: {source.stat().st_size/1024/1024:.1f} MB")
            print(f"    {output.name}: {output.stat().st_size/1024/1024:.1f} MB ✓")

    print("\nDone. New files written to assets/final/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
