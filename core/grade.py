"""Color grading pass — the videographer's notes as code.

"Increase the saturation" (2026-07-12): raw HeyGen/camera output reads flat;
boost color intensity so skin is warmer and set colors pop. Applied as the
LAST video filter so overlays/cards keep their exact brand colors is wrong —
cards are designed against the graded look, so grade the BASE avatar before
overlays (OverlayChain does this when grade= is passed).

Presets:
    videographer  — sat 1.22, slight contrast + warmth (the requested look)
    subtle        — sat 1.10
    none          — passthrough
"""
from __future__ import annotations
import subprocess
from pathlib import Path

PRESETS = {
    # eq handles saturation/contrast/brightness; colorbalance adds gentle warmth
    "videographer": "eq=saturation=1.22:contrast=1.05:brightness=0.01,"
                    "colorbalance=rm=0.03:bm=-0.02",
    "subtle":       "eq=saturation=1.10:contrast=1.02",
    # For UPSCALED sources (letterboxed looks): stronger color + unsharp to
    # recover crispness lost in the 1.8-2x scale-up
    "bright_sharp": "eq=saturation=1.30:contrast=1.08:brightness=0.005,"
                    "colorbalance=rm=0.02:bm=-0.02,"
                    "unsharp=5:5:0.9:5:5:0.35",
    # Max punch (user request 2026-07-15): "increase saturation, make sharp,
    # everything to 4k". Strong color + aggressive unsharp; pair with a 4K
    # upscale in the finish pass for a crisp master.
    "sharp_4k":     "eq=saturation=1.42:contrast=1.10:brightness=0.006,"
                    "colorbalance=rm=0.03:bm=-0.02,"
                    "unsharp=7:7:1.2:7:7:0.5",
    "none":         "null",
}


def chain(preset: str = "videographer") -> str:
    if preset not in PRESETS:
        raise KeyError(f"unknown grade preset {preset!r} ({', '.join(PRESETS)})")
    return PRESETS[preset]


def grade_file(src: Path, dst: Path, preset: str = "videographer") -> Path:
    """Grade a finished video (audio copied)."""
    subprocess.run([
        "ffmpeg", "-y", "-i", str(src), "-vf", chain(preset),
        "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p",
        "-c:a", "copy", str(dst),
    ], check=True)
    return dst
