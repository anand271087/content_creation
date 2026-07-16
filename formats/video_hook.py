"""Video hook — Vaibhav Sisinty-style AI-footage open (analysis 2026-07-16).

The grammar (from DaqBTo1AcvY + 3-reel survey, 4/4 recent reels):
  1. 4-6s of AI-generated footage that VISUALLY ACTS OUT the spoken hook line
     (metaphor skit / celebrity-lookalike scene / the tool's own output) —
     the real face never appears in this window.
  2. The creator's VOICE carries over the AI footage (hook clip audio is
     dropped — our HeyGen avatar speaks the hook line as usual).
  3. Light-leak flash lands EXACTLY when the subject is named → cut to the
     real reel (avatar enters).

Usage:
    from formats.video_hook import hook_prompt, apply_hook
    from core.gemini_omni import generate, edit
    p = hook_prompt("If you're only using ChatGPT you're missing the "
                    "biggest AI launch of the year",
                    "an office worker drowning in paper while a robot "
                    "quietly builds a rocket behind them")
    r = generate(p, Path("assets/hooks/hook.mp4"))
    # iterate: edit(r["id"], "make the robot bigger", ...)
    apply_hook(reel=Path("assets/final/reel.mp4"),
               hook=r["path"], until=5.2,
               out=Path("assets/final/reel_hooked.mp4"))

HOUSE RULES:
  - AI-news / story / editorial reels ONLY (the Friday 10-section slot and
    Format #8). NEVER board formats — their no-hook rule stands (the board
    IS the hook).
  - `until` comes from Scribe: the word_start of the subject name-drop in the
    avatar audio ("Meet **Grok** 4.5" → until = that word's start).
  - Run BEFORE the finish chain (1.3x + thumbnail), on the raw composite.
"""
from __future__ import annotations
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.brand import CRF_FINAL
from core.cards import light_leak

log = logging.getLogger("video_hook")
ROOT = Path(__file__).resolve().parent.parent


def hook_prompt(hook_line: str, metaphor_scene: str,
                style: str = "fisheye lens, handheld, slightly surreal "
                             "office-campus setting, natural daylight") -> str:
    """Build the Omni prompt for a hook clip. The scene must act out the hook
    line as a visual metaphor — never show text, never show a talking face."""
    return (
        f"{metaphor_scene}. {style}. Single continuous shot, no scene cuts. "
        f"The scene is a visual metaphor for: \"{hook_line}\". "
        f"Cinematic, high energy, builds toward the final second. "
        f"No dialogue, no on-screen text, no captions, no logos. "
        f"Ambient sound only, quiet."
    )


def apply_hook(reel: Path, hook: Path, until: float, out: Path,
               flash_dur: float = 0.22) -> Path:
    """Replace the reel's VISUALS for t=0→until with the hook clip, keep the
    reel's full audio (avatar voice speaks the hook line over the AI footage),
    light-leak flash + brightness pulse at the seam."""
    leak = light_leak(Path(tempfile.mkdtemp(prefix="hook-")) / "leak.png")
    f0, f1 = until - flash_dur / 2, until + flash_dur / 2
    fc = (
        # hook video normalized + trimmed to the window, shown 0→until
        f"[1:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,fps=30,setsar=1,trim=0:{until:.3f},"
        f"setpts=PTS-STARTPTS[hv];"
        f"[0:v]fps=30,setsar=1[rv];"
        f"[rv][hv]overlay=x=0:y=0:enable='lt(t,{until:.3f})'[v0];"
        # light-leak + brightness pulse at the seam
        f"[v0][2:v]overlay=x=0:y=0:enable='between(t,{f0:.3f},{f1:.3f})'[v1];"
        f"[v1]eq=brightness=0.13:enable='between(t,{f0:.3f},{until:.3f})'[v]"
    )
    subprocess.run([
        "ffmpeg", "-y", "-i", str(reel), "-i", str(hook), "-i", str(leak),
        "-filter_complex", fc,
        "-map", "[v]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "slow", "-crf", str(CRF_FINAL),
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(out),
    ], check=True)
    log.info("hook applied 0→%.2fs → %s", until, out.name)
    return out
