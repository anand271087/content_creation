"""
scripts/check_broll_quality.py — Broll Quality Checker

After Stage 2 downloads all broll clips, extracts one frame from each clip
and sends to Claude vision to check for:
  - Text overlays / watermarks
  - Generic stock footage (server racks, neural networks, typing hands, desk shots)
  - Relevance to the section's spoken content

Returns list of section IDs that need regeneration.
Used by pipeline.py after Stage 2, before Stage 3 (HeyGen — expensive).

Usage:
  python3 scripts/check_broll_quality.py              # checks all clips
  python3 scripts/check_broll_quality.py hook body_1  # checks specific sections
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
BROLL_DIR = PROJECT_ROOT / "assets" / "broll"
SCRIPT_DATA = PROJECT_ROOT / "assets" / "script_data.json"
LOG_FILE = PROJECT_ROOT / "logs" / "pipeline.log"

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [check_broll] %(levelname)s — %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("check_broll")

MODEL = "claude-sonnet-4-6"  # Vision capable, cheaper than Opus

QUALITY_PROMPT = """You are reviewing broll clips for a viral Instagram reel about AI automation.

Each image is a frame extracted from a broll clip. The section ID and expected content are shown before each frame.

For each clip, check:
1. WATERMARK/TEXT: Is there any visible text, watermark, subtitle, logo, or UI overlay?
2. GENERIC STOCK: Is it generic stock footage? (server rooms, data center racks, neural network animations, random typing hands, generic desk with laptop, abstract blue particles, stock office scenes)
3. RELEVANCE: Does the visual match the spoken content for that section?

Scoring per clip: PASS or FAIL
- FAIL if: has watermark/text, OR is obvious generic stock with no connection to AI automation tools

Return ONLY valid JSON, no markdown:
{
  "results": [
    {
      "section_id": "hook",
      "verdict": "FAIL",
      "reason": "Generic server rack stock footage — no connection to AI tools or automation",
      "has_text": false,
      "is_generic_stock": true
    },
    {
      "section_id": "body_1",
      "verdict": "PASS",
      "reason": "Shows workflow automation visual, relevant to content",
      "has_text": false,
      "is_generic_stock": false
    }
  ],
  "failed_sections": ["hook", "trigger_2"],
  "pass_count": 8,
  "fail_count": 2
}"""


def extract_frame(clip_path: Path, tmpdir: str) -> str | None:
    """Extract frame at 1s from clip. Returns base64-encoded JPEG or None on failure."""
    frame_path = os.path.join(tmpdir, f"{clip_path.stem}.jpg")
    try:
        subprocess.run(
            ["ffmpeg", "-ss", "1", "-i", str(clip_path),
             "-vframes", "1", "-q:v", "4", "-vf", "scale=480:-1",
             frame_path, "-y"],
            capture_output=True, check=True,
        )
        with open(frame_path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")
    except Exception as exc:
        log.warning("Frame extraction failed for %s: %s", clip_path.name, exc)
        return None


def check_broll_quality(section_ids: list[str] | None = None) -> dict:
    """
    Check quality of broll clips. If section_ids provided, only checks those sections.

    Returns:
        {"success": bool, "failed_sections": [...], "results": [...],
         "duration_sec": float, "error": str|None}
    """
    start = time.time()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"success": False, "failed_sections": [], "results": [],
                "duration_sec": 0, "error": "ANTHROPIC_API_KEY not set"}

    # Load script to get section spoken text for relevance check
    script_data = {}
    if SCRIPT_DATA.exists():
        script_data = json.loads(SCRIPT_DATA.read_text(encoding="utf-8"))

    sections_map = {s["id"]: s for s in script_data.get("sections", [])}

    # Find clips to check
    clips = sorted(BROLL_DIR.glob("*.mp4"))
    if section_ids:
        clips = [c for c in clips if c.stem in section_ids]

    if not clips:
        return {"success": False, "failed_sections": [], "results": [],
                "duration_sec": 0, "error": "No broll clips found to check"}

    log.info("Checking quality of %d broll clips...", len(clips))

    with tempfile.TemporaryDirectory() as tmpdir:
        # Build message content: label + frame for each clip
        content = []
        checked_sections = []

        for clip in clips:
            section_id = clip.stem
            section = sections_map.get(section_id, {})
            spoken = section.get("spoken", "")[:80]

            frame_b64 = extract_frame(clip, tmpdir)
            if not frame_b64:
                continue

            content.append({
                "type": "text",
                "text": f"Section: {section_id} | Spoken: \"{spoken}\""
            })
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": frame_b64}
            })
            checked_sections.append(section_id)

        if not content:
            return {"success": False, "failed_sections": [], "results": [],
                    "duration_sec": round(time.time() - start, 2),
                    "error": "Frame extraction failed for all clips"}

        content.append({"type": "text", "text": QUALITY_PROMPT})

        log.info("Sending %d frames to Claude vision for quality check...", len(checked_sections))

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            messages=[{"role": "user", "content": content}],
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw

        result = json.loads(raw)
        failed = result.get("failed_sections", [])

        log.info(
            "Broll check — %d/%d passed | Failed: %s",
            result.get("pass_count", 0), len(checked_sections),
            ", ".join(failed) if failed else "none"
        )

        for r in result.get("results", []):
            if r.get("verdict") == "FAIL":
                log.warning("  ✗ [%s] %s", r["section_id"], r.get("reason", ""))

        return {
            "success": True,
            "failed_sections": failed,
            "pass_count": result.get("pass_count", 0),
            "fail_count": result.get("fail_count", 0),
            "results": result.get("results", []),
            "duration_sec": round(time.time() - start, 2),
            "error": None,
        }


if __name__ == "__main__":
    import sys
    ids = sys.argv[1:] if len(sys.argv) > 1 else None
    result = check_broll_quality(ids)
    print(json.dumps(result, indent=2))
