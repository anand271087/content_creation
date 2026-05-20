"""
process_raw_recording.py — Convert a real terminal screen recording into a broll clip.

Usage:
  python3 scripts/process_raw_recording.py <section_id> <recording_path>

Examples:
  python3 scripts/process_raw_recording.py body_1 ~/Desktop/claude_demo.mov
  python3 scripts/process_raw_recording.py body_2 ~/Desktop/n8n_workflow.mp4

What it does:
  1. Detects the terminal window region using ffmpeg (looks for the darkest 880×1100 crop)
     OR just centers the recording in the 880×1100 target with dark background padding.
  2. Adds a 880×1100 dark background (#0d1117) and overlays the cropped recording centered.
  3. Adds a macOS-style title bar overlay (dark bar + dots) if --add-titlebar is passed.
  4. Re-encodes to H264 Baseline (Remotion-safe).
  5. Saves to assets/broll/<section_id>.mp4 — the pipeline treats this as a "clip" broll.

After running:
  In script_data.json, set broll_type to "clip" for that section (raw recordings are
  treated as regular video clips by Remotion — no ScreenDemoLayer needed).
  The clip will appear in the 880×1100 rounded broll box with Ken Burns zoom.

Options:
  --crop x y w h   Explicit crop region in source video (e.g. --crop 0 80 1440 820)
  --trim start end  Trim the recording (seconds, e.g. --trim 2 15 = use seconds 2–15)
  --speed n        Playback speed multiplier (e.g. --speed 1.5)
  --add-titlebar   Overlay a dark macOS-style title bar with traffic light dots
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
BROLL_DIR = ROOT / "assets" / "broll"

TARGET_W = 880
TARGET_H = 1100
DARK_BG  = "0d1117"   # terminal dark background color

def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kwargs)


def process(section_id: str, src: Path, crop: tuple | None, trim: tuple | None,
            speed: float, add_titlebar: bool) -> None:
    BROLL_DIR.mkdir(parents=True, exist_ok=True)
    out = BROLL_DIR / f"{section_id}.mp4"
    tmp = BROLL_DIR / f".{section_id}_raw.mp4"

    # ── Build filter chain ──────────────────────────────────────────────────
    filters = []

    # 1. Speed adjustment (setpts + atempo)
    if speed != 1.0:
        pts = round(1.0 / speed, 4)
        filters.append(f"setpts={pts}*PTS")

    # 2. Crop if specified
    if crop:
        x, y, w, h = crop
        filters.append(f"crop={w}:{h}:{x}:{y}")

    # 3. Scale to fit inside target box (preserve aspect ratio)
    filters.append(
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease"
    )

    # 4. Pad to exact target size with dark background
    filters.append(
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:color={DARK_BG}"
    )

    # 5. macOS title bar overlay (drawn with drawbox + drawtext — no external image needed)
    if add_titlebar:
        bar_h = 52
        # Dark title bar background
        filters.append(
            f"drawbox=x=0:y=0:w={TARGET_W}:h={bar_h}:color=1e222a:t=fill"
        )
        # Bottom border of title bar
        filters.append(
            f"drawbox=x=0:y={bar_h}:w={TARGET_W}:h=1:color=333840:t=fill"
        )
        # Traffic light dots (red, yellow, green)
        for i, (cx, color) in enumerate([(20, "ff5f57"), (42, "febc2e"), (64, "28c840")]):
            filters.append(
                f"drawbox=x={cx-7}:y={bar_h//2-7}:w=14:h=14:color={color}:t=fill"
            )

    vf = ",".join(filters)

    # ── Build ffmpeg command ────────────────────────────────────────────────
    cmd = ["ffmpeg", "-y"]

    if trim:
        start, end = trim
        cmd += ["-ss", str(start), "-to", str(end)]

    cmd += ["-i", str(src)]
    cmd += ["-vf", vf]
    cmd += [
        "-c:v", "libx264",
        "-profile:v", "baseline",
        "-level", "3.1",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-r", "30",
        "-an",    # strip audio — broll clips are silent
        str(out),
    ]

    print(f"\n▶ Processing {src.name} → assets/broll/{section_id}.mp4")
    run(cmd)

    size_kb = out.stat().st_size // 1024
    print(f"\n✅ Done: assets/broll/{section_id}.mp4 ({size_kb}KB)")
    print(f"   Set broll_type: \"clip\" in script_data.json for section '{section_id}'")


def main():
    parser = argparse.ArgumentParser(description="Process real terminal recording → broll clip")
    parser.add_argument("section_id", help="Section ID (e.g. body_1, context)")
    parser.add_argument("recording", help="Path to screen recording (.mov, .mp4, .mkv)")
    parser.add_argument("--crop", nargs=4, type=int, metavar=("X", "Y", "W", "H"),
                        help="Crop region in source: x y width height")
    parser.add_argument("--trim", nargs=2, type=float, metavar=("START", "END"),
                        help="Trim seconds: start end (e.g. --trim 2 15)")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="Playback speed multiplier (default 1.0, 1.5 = 1.5x faster)")
    parser.add_argument("--add-titlebar", action="store_true",
                        help="Add macOS-style dark title bar overlay")
    args = parser.parse_args()

    src = Path(args.recording).expanduser().resolve()
    if not src.exists():
        print(f"❌ Recording not found: {src}")
        sys.exit(1)

    if not shutil.which("ffmpeg"):
        print("❌ ffmpeg not found — install with: brew install ffmpeg")
        sys.exit(1)

    crop = tuple(args.crop) if args.crop else None
    trim = tuple(args.trim) if args.trim else None

    process(args.section_id, src, crop, trim, args.speed, args.add_titlebar)


if __name__ == "__main__":
    main()
