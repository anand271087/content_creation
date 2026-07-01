"""
Stage 8 — Social Media Copy Generator
Reads assets/script_data.json and generates platform-specific post copy
for Instagram, LinkedIn, and YouTube Shorts using the Claude API.

Applies the same GOAT principles as Stage 1:
- Plain language, max 12 words per sentence
- Specific numbers from the script
- Platform-native tone and structure
- Save/share/comment triggers baked in

Output files:
  assets/social/instagram.txt   — caption + hashtags
  assets/social/linkedin.txt    — long-form post
  assets/social/youtube.txt     — title + description
  assets/social/social_copy.json — all three combined
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPT_PATH = PROJECT_ROOT / "assets" / "script_data.json"
SOCIAL_DIR = PROJECT_ROOT / "assets" / "social"
LOG_FILE = PROJECT_ROOT / "logs" / "pipeline.log"

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("stage8_social")
logger.setLevel(logging.DEBUG)

_fmt = logging.Formatter("%(asctime)s [stage8_social] %(levelname)s %(message)s")
_fh = logging.FileHandler(LOG_FILE)
_fh.setFormatter(_fmt)
logger.addHandler(_fh)
_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(_fmt)
logger.addHandler(_sh)

CLAUDE_MODEL = "claude-sonnet-4-5"


def _build_prompt(script: dict) -> str:
    title = script.get("title", "")
    spoken = script.get("full_spoken_script", "")
    takeaway = script.get("grand_takeaway_line", "")
    tool = script.get("tool_mentioned", "")
    hook_section = next((s for s in script.get("sections", []) if s["id"] == "hook"), {})
    hook_spoken = hook_section.get("spoken", "")
    emotion_section = next((s for s in script.get("sections", []) if s["id"] == "emotion_save"), {})
    cta_spoken = emotion_section.get("spoken", "")

    return f"""You are writing social media post copy for @automatewithanand — an AI automation channel for Indian entrepreneurs aged 22–45.

The channel posts vertical reels about AI tools, workflows, and automations.
Tone: confident, direct, friend-to-friend. Never corporate. Never hype.
Language rules: plain English, max 12 words per sentence, sounds like natural speech.

Here is the reel you are writing copy for:

TITLE: {title}
HOOK (first 5 seconds): {hook_spoken}
GRAND TAKEAWAY: {takeaway}
TOOL MENTIONED: {tool}
FULL SCRIPT: {spoken}
CTA SECTION: {cta_spoken}

---

Write post copy for THREE platforms. Return a JSON object with exactly these keys:
"instagram", "linkedin", "youtube"

INSTAGRAM rules:
- First line = hook. Must stop the scroll. Must match or be stronger than the video hook.
- Use line breaks and arrows (→) for readability.
- Include the grand takeaway line word-for-word.
- End with: "Save this. Follow @automatewithanand for a new AI build every week."
- 8–10 relevant hashtags at the bottom (mix of niche + broad).
- 150–250 words total (excluding hashtags).

LINKEDIN rules:
- First line = hook. No preamble. Starts with "I" or a bold statement.
- 3–5 short paragraphs with a blank line between each.
- More context than Instagram — explain the "why" briefly.
- Include the grand takeaway line word-for-word.
- End with: "Follow for more AI automation builds every week."
- 3–5 hashtags only (LinkedIn penalises hashtag spam).
- 200–300 words total.

YOUTUBE rules:
- First key: "title" — max 90 characters, SEO-friendly, includes the tool name and a strong benefit. No clickbait.
- Second key: "description" — 200–350 words. Start with the hook. List what viewers will learn (3–5 bullet points with →). Include the grand takeaway. End with subscribe CTA. 8–10 relevant hashtags at the bottom.

Return ONLY the JSON object. No extra text. No markdown fences. No explanation.

Example structure (fill with real content):
{{
  "instagram": "...",
  "linkedin": "...",
  "youtube": {{
    "title": "...",
    "description": "..."
  }}
}}"""


def run_stage8() -> dict:
    """
    Generate social media copy for Instagram, LinkedIn, and YouTube Shorts.

    Returns:
        {{
            "success": bool,
            "output_path": str,
            "duration_sec": float,
            "error": str | None,
        }}
    """
    start = time.time()

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"success": False, "output_path": None, "duration_sec": 0.0, "error": "ANTHROPIC_API_KEY not set"}

    if not SCRIPT_PATH.exists():
        return {"success": False, "output_path": None, "duration_sec": 0.0,
                "error": f"script_data.json not found at {SCRIPT_PATH}"}

    with open(SCRIPT_PATH, encoding="utf-8") as fh:
        script = json.load(fh)

    logger.info("Generating social copy for: %s", script.get("title", ""))

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_prompt(script)

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
    except Exception as exc:
        return {"success": False, "output_path": None,
                "duration_sec": round(time.time() - start, 2), "error": str(exc)}

    # Parse JSON response
    try:
        # Strip markdown fences if Claude added them anyway
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        copy = json.loads(raw.strip())
    except json.JSONDecodeError as exc:
        return {"success": False, "output_path": None,
                "duration_sec": round(time.time() - start, 2),
                "error": f"Failed to parse Claude response as JSON: {exc}\nRaw: {raw[:500]}"}

    # Write output files
    SOCIAL_DIR.mkdir(parents=True, exist_ok=True)

    instagram = copy.get("instagram", "")
    linkedin = copy.get("linkedin", "")
    youtube = copy.get("youtube", {})
    youtube_title = youtube.get("title", "") if isinstance(youtube, dict) else ""
    youtube_desc = youtube.get("description", "") if isinstance(youtube, dict) else str(youtube)

    (SOCIAL_DIR / "instagram.txt").write_text(instagram, encoding="utf-8")
    (SOCIAL_DIR / "linkedin.txt").write_text(linkedin, encoding="utf-8")
    (SOCIAL_DIR / "youtube.txt").write_text(
        f"TITLE:\n{youtube_title}\n\nDESCRIPTION:\n{youtube_desc}", encoding="utf-8"
    )

    combined = {
        "title": script.get("title", ""),
        "tool": script.get("tool_mentioned", ""),
        "instagram": instagram,
        "linkedin": linkedin,
        "youtube": {"title": youtube_title, "description": youtube_desc},
    }
    output_path = SOCIAL_DIR / "social_copy.json"
    output_path.write_text(json.dumps(combined, indent=2, ensure_ascii=False), encoding="utf-8")

    duration = round(time.time() - start, 2)
    logger.info("Stage 8 complete in %.1fs — social copy written to %s", duration, SOCIAL_DIR)

    # Print copy to terminal for easy review
    print("\n" + "=" * 60)
    print("SOCIAL COPY GENERATED")
    print("=" * 60)
    print("\n── INSTAGRAM ──\n")
    print(instagram)
    print("\n── LINKEDIN ──\n")
    print(linkedin)
    print(f"\n── YOUTUBE ──\nTitle: {youtube_title}\n")
    print(youtube_desc)
    print("\n" + "=" * 60)

    return {
        "success": True,
        "output_path": str(output_path),
        "duration_sec": duration,
        "error": None,
    }


if __name__ == "__main__":
    result = run_stage8()
    print(json.dumps({"success": result["success"], "output_path": result["output_path"],
                      "duration_sec": result["duration_sec"]}, indent=2))
    sys.exit(0 if result["success"] else 1)
