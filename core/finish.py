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
    """Concat a still end-card after the reel (YouTube Shorts thumbnail trick).

    Uses the concat FILTER with explicit fps/scale/sar normalization on BOTH
    inputs — the concat DEMUXER mis-times sources of differing framerate
    (HeyGen renders 25fps; a 30fps card stretched the video ~1.2x). 30fps out.
    """
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
        # concat FILTER (not demuxer) with per-input normalization → no re-timing
        fc = ("[0:v]fps=30,scale=1080:1920,setsar=1[v0];"
              "[1:v]fps=30,scale=1080:1920,setsar=1[v1];"
              "[0:a]aresample=48000[a0];[1:a]aresample=48000[a1];"
              "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]")
        subprocess.run([
            "ffmpeg", "-y", "-i", str(src), "-i", str(card),
            "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "slow", "-crf", str(CRF_FINAL),
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(dst),
        ], check=True, capture_output=True)
    return dst


def upscale_4k(src: Path, dst: Path) -> Path:
    """Upscale a 1080x1920 master to 4K (2160x3840) with lanczos + a light
    unsharp — supersampled crispness (user request 2026-07-15). IG downscales
    on upload, but a 4K master survives the transcode noticeably sharper."""
    subprocess.run([
        "ffmpeg", "-y", "-i", str(src),
        "-vf", "scale=2160:3840:flags=lanczos,unsharp=5:5:0.6:5:5:0.2",
        "-c:v", "libx264", "-preset", "slow", "-crf", "16",
        "-pix_fmt", "yuv420p", "-c:a", "copy", str(dst),
    ], check=True)
    return dst


def finish(raw: Path, out_stem: str | None = None, four_k: bool = False) -> Path:
    """raw composite → *_fast.mp4 → *_fast_with_thumb.mp4. Returns final path.

    four_k=True adds a final 2160x3840 upscale pass → *_4k.mp4."""
    stem = out_stem or raw.stem
    fast = raw.with_name(f"{stem}_fast.mp4")
    final = raw.with_name(f"{stem}_fast_with_thumb.mp4")
    speed_up(raw, fast)
    append_thumbnail(fast, final)
    if four_k:
        master = raw.with_name(f"{stem}_4k.mp4")
        return upscale_4k(final, master)
    return final
