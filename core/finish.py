"""Finish chain: 1.3x speed + thumbnail end-card concat.

Previously lived only in ad-hoc shell commands — now the one place it exists.
"""
from __future__ import annotations
import subprocess
import tempfile
from pathlib import Path

from core.brand import FINAL_SPEED, CRF_FINAL

ROOT = Path(__file__).resolve().parent.parent
THUMB_PNG = ROOT / "assets" / "final" / "thumbnail.png"


def speed_up(src: Path, dst: Path, factor: float = FINAL_SPEED) -> Path:
    subprocess.run([
        "ffmpeg", "-y", "-i", str(src),
        "-filter_complex", f"[0:v]setpts=PTS/{factor}[v];[0:a]atempo={factor}[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "slow", "-crf", str(CRF_FINAL),
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(dst),
    ], check=True)
    return dst


def append_thumbnail(src: Path, dst: Path, thumb_png: Path = THUMB_PNG,
                     secs: float = 1.5) -> Path:
    """Concat a still end-card after the reel (YouTube Shorts thumbnail trick)."""
    if not thumb_png.exists():
        raise FileNotFoundError(f"thumbnail missing: {thumb_png}")
    with tempfile.TemporaryDirectory() as td:
        card = Path(td) / "thumb_card.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-t", str(secs), "-i", str(thumb_png),
            "-f", "lavfi", "-t", str(secs), "-i", "anullsrc=r=48000:cl=stereo",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-r", "30", "-vf", "scale=1080:1920,setsar=1",
            "-c:a", "aac", "-b:a", "192k", "-shortest", str(card),
        ], check=True, capture_output=True)
        lst = Path(td) / "concat.txt"
        lst.write_text(f"file '{src.resolve()}'\nfile '{card.resolve()}'\n")
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
            "-c:v", "libx264", "-preset", "slow", "-crf", str(CRF_FINAL),
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(dst),
        ], check=True, capture_output=True)
    return dst


def finish(raw: Path, out_stem: str | None = None) -> Path:
    """raw composite → *_fast.mp4 → *_fast_with_thumb.mp4. Returns final path."""
    stem = out_stem or raw.stem
    fast = raw.with_name(f"{stem}_fast.mp4")
    final = raw.with_name(f"{stem}_fast_with_thumb.mp4")
    speed_up(raw, fast)
    append_thumbnail(fast, final)
    return final
