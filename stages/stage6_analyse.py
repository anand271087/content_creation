"""
Stage 6 — Video DSSCL Analyser
Extracts frames from the rendered video, sends to Claude vision API,
scores on DSSCL framework, and returns feedback for pipeline loop decisions.
"""

import base64
import json
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
VIDEO_PATH = PROJECT_ROOT / "assets" / "final" / "final_reel.mp4"
ANALYSIS_DIR = PROJECT_ROOT / "assets" / "analysis"
ANALYSIS_OUTPUT = ANALYSIS_DIR / "video_analysis.json"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [stage6_analyse] %(levelname)s — %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "pipeline.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("stage6_analyse")

MODEL = "claude-opus-4-6"   # Opus for best vision quality
MAX_TOKENS = 2000
N_FRAMES = 12                         # frames sampled across the video
VIDEO_DSSCL_PASS = 9.0               # threshold for pipeline to accept and stop looping

ANALYSIS_PROMPT = """You are a viral content analyst evaluating a short-form vertical reel for @automatewithanand (AI automation niche, India audience, age 22–45, working professionals).

These frames are sampled in order from start to end of the video. Analyze them as a sequence and score the video on the DSSCL virality framework:

| Signal | Weight | What to evaluate |
|--------|--------|-----------------|
| D — Double Watch | 30% | Info density, curiosity loops, pacing that makes viewers rewatch |
| S — Share | 25% | Quotable moments, identity signal, "send this to a friend" factor |
| S — Save | 25% | Concrete takeaway, specific tool named, bookmark-worthy advice |
| C — Comment | 10% | Debate potential, relatable frustration, opinion trigger |
| L — Like | 10% | Production quality, visual composition, text legibility |

Formula: Final = (D×0.30) + (Share×0.25) + (Save×0.25) + (C×0.10) + (L×0.10)
Target: Final ≥ 9.0

Evaluate these specific production elements:
- Hook (first 2 frames): Does it stop the scroll? Pattern interrupt? Open loop?
- B-roll (top half): Quality, relevance to speech, no text/watermarks?
- On-screen text: Readable, punchy, max 3-5 words?
- Avatar (bottom half): Energy, lighting, eye contact?
- Captions: Visible, synced, Hormozi style?
- Grand Takeaway frame: Quotable line clearly visible?
- CTA / emotion_save: Warm close, specific tool mentioned?

Return ONLY a valid JSON object, no markdown, no explanation:
{
  "dsscl_scores": {
    "D": 8.5,
    "Share": 9.0,
    "Save": 9.0,
    "C": 7.5,
    "L": 8.0,
    "final": 8.63
  },
  "passed": false,
  "strengths": ["strong hook pattern interrupt", "clear CTA with tool named"],
  "weaknesses": ["B-roll not matching speech topic", "grand takeaway not quotable enough"],
  "script_feedback": "Specific script improvements needed: hook needs broader TAM appeal, grand takeaway must be a single screenshot-worthy sentence, trigger 3 needs real numbers (city, tool, rupees, time saved)",
  "visual_feedback": "B-roll quality notes, text overlay issues, caption legibility, avatar energy"
}"""


# ---------------------------------------------------------------------------
# Frame extraction
# ---------------------------------------------------------------------------

def get_video_duration(video_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", video_path],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def extract_frames(video_path: str, n_frames: int = N_FRAMES) -> list[str]:
    """Extract n frames evenly across the video. Returns list of base64-encoded JPEGs."""
    duration = get_video_duration(video_path)

    # Sample between 1s and duration-1s to skip fade-in/out black frames
    start = 1.0
    end = max(duration - 1.0, start + 1.0)
    interval = (end - start) / max(n_frames - 1, 1)
    timestamps = [start + i * interval for i in range(n_frames)]

    log.info("Extracting %d frames from %.1fs video (every %.1fs).", n_frames, duration, interval)

    frames_b64 = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, ts in enumerate(timestamps):
            frame_path = os.path.join(tmpdir, f"frame_{i:03d}.jpg")
            subprocess.run(
                [
                    "ffmpeg", "-ss", str(ts), "-i", video_path,
                    "-vframes", "1", "-q:v", "3",
                    "-vf", "scale=540:-1",   # half-width — saves tokens, still readable
                    frame_path, "-y",
                ],
                capture_output=True, check=True,
            )
            with open(frame_path, "rb") as fh:
                frames_b64.append(base64.standard_b64encode(fh.read()).decode("utf-8"))

    log.info("Extracted %d frames successfully.", len(frames_b64))
    return frames_b64


# ---------------------------------------------------------------------------
# Claude vision call
# ---------------------------------------------------------------------------

def call_claude_vision(frames_b64: list[str]) -> dict:
    """Send frames + DSSCL prompt to Claude. Returns parsed analysis dict."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    content = []
    for i, frame_b64 in enumerate(frames_b64):
        content.append({"type": "text", "text": f"Frame {i + 1}/{len(frames_b64)}:"})
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": frame_b64,
            },
        })
    content.append({"type": "text", "text": ANALYSIS_PROMPT})

    log.info("Calling Claude vision API with %d frames...", len(frames_b64))
    t0 = time.monotonic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": content}],
    )
    log.info("Claude vision response received in %.1fs.", time.monotonic() - t0)

    raw = response.content[0].text.strip()

    # Strip markdown fences if Claude adds them
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw

    return json.loads(raw)


# ---------------------------------------------------------------------------
# Main stage function
# ---------------------------------------------------------------------------

def run_stage6(video_path: str = None) -> dict:
    """
    Analyse the rendered video and score on DSSCL framework.

    Returns:
        {
          "success": bool,
          "passed": bool,          # True if Final >= VIDEO_DSSCL_PASS
          "dsscl_scores": {...},
          "script_feedback": str,
          "visual_feedback": str,
          "strengths": [...],
          "weaknesses": [...],
          "output_path": str,
          "duration_sec": float,
          "error": str|None,
        }
    """
    start_time = time.time()
    vpath = str(video_path or VIDEO_PATH)

    if not Path(vpath).exists():
        return {
            "success": False,
            "passed": False,
            "output_path": str(ANALYSIS_OUTPUT),
            "duration_sec": 0.0,
            "error": f"Video not found: {vpath}",
        }

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "success": False,
            "passed": False,
            "output_path": str(ANALYSIS_OUTPUT),
            "duration_sec": 0.0,
            "error": "ANTHROPIC_API_KEY not set.",
        }

    # Pre-check: rendered video must cover the full avatar speech (Hook → CTA).
    # If final_reel is >3s shorter than the avatar, stage5 likely cut the video
    # early (sync_broll not run, or total_duration_sec not updated). Fail fast
    # before wasting Claude API calls on an incomplete video.
    AVATAR_VIDEO = PROJECT_ROOT / "assets" / "avatar" / "avatar_video.mp4"
    if AVATAR_VIDEO.exists():
        try:
            def _get_duration(path: str) -> float:
                r = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-print_format", "json",
                     "-show_format", str(path)],
                    capture_output=True, text=True, check=True,
                )
                return float(json.loads(r.stdout)["format"]["duration"])

            avatar_dur = _get_duration(str(AVATAR_VIDEO))
            reel_dur = _get_duration(vpath)
            # Avatar plays at 1.25x speed in Remotion — expected reel duration is shorter
            PLAYBACK_RATE = 1.25
            expected_reel_dur = avatar_dur / PLAYBACK_RATE
            gap = expected_reel_dur - reel_dur
            log.info(
                "Duration check — avatar: %.1fs | reel: %.1fs | expected reel: %.1fs | gap: %.1fs",
                avatar_dur, reel_dur, expected_reel_dur, gap,
            )
            if gap > 3.0:
                return {
                    "success": False,
                    "passed": False,
                    "output_path": str(ANALYSIS_OUTPUT),
                    "duration_sec": time.time() - start_time,
                    "error": (
                        f"Final reel ({reel_dur:.1f}s) is {gap:.1f}s shorter than expected "
                        f"({expected_reel_dur:.1f}s = avatar {avatar_dur:.1f}s / 1.25x) — "
                        "video was cut early, CTA likely missing. "
                        "Re-run Stage 5 (sync_broll_to_speech will update total_duration_sec)."
                    ),
                }
        except Exception as exc:
            log.warning("Duration pre-check failed (non-fatal): %s", exc)

    try:
        frames_b64 = extract_frames(vpath)
        analysis = call_claude_vision(frames_b64)

        # Recalculate final score from raw components (don't trust Claude's arithmetic)
        s = analysis.get("dsscl_scores", {})
        final = (
            s.get("D", 0) * 0.30
            + s.get("Share", 0) * 0.25
            + s.get("Save", 0) * 0.25
            + s.get("C", 0) * 0.10
            + s.get("L", 0) * 0.10
        )
        analysis["dsscl_scores"]["final"] = round(final, 2)
        analysis["passed"] = final >= VIDEO_DSSCL_PASS

        # Persist analysis
        ANALYSIS_OUTPUT.write_text(json.dumps(analysis, indent=2, ensure_ascii=False))
        log.info(
            "Video DSSCL — D:%.1f Share:%.1f Save:%.1f C:%.1f L:%.1f → Final:%.2f | Passed:%s",
            s.get("D", 0), s.get("Share", 0), s.get("Save", 0),
            s.get("C", 0), s.get("L", 0), final, analysis["passed"],
        )

        return {
            "success": True,
            "passed": analysis["passed"],
            "dsscl_scores": analysis["dsscl_scores"],
            "script_feedback": analysis.get("script_feedback", ""),
            "visual_feedback": analysis.get("visual_feedback", ""),
            "strengths": analysis.get("strengths", []),
            "weaknesses": analysis.get("weaknesses", []),
            "output_path": str(ANALYSIS_OUTPUT),
            "duration_sec": time.time() - start_time,
            "error": None,
        }

    except Exception as exc:  # noqa: BLE001
        log.exception("Stage 6 failed")
        return {
            "success": False,
            "passed": False,
            "output_path": str(ANALYSIS_OUTPUT),
            "duration_sec": time.time() - start_time,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    vpath = sys.argv[1] if len(sys.argv) > 1 else None
    result = run_stage6(vpath)
    print(json.dumps(result, indent=2))
