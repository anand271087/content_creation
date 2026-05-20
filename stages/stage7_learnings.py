"""
Stage 7 — Learning Capture
Extracts learnings from the current run (Stage 6 analysis + script data),
appends to persistent history, and uses Claude to distill accumulated rules
that Stage 1 injects into future prompts.

Output files:
  scripts/learnings/pipeline_learnings.json  — full per-run history
  scripts/learnings/accumulated_rules.md     — distilled rules for Stage 1
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
ANALYSIS_PATH = PROJECT_ROOT / "assets" / "analysis" / "video_analysis.json"
SCRIPT_PATH = PROJECT_ROOT / "assets" / "script_data.json"
LEARNINGS_DIR = PROJECT_ROOT / "scripts" / "learnings"
HISTORY_PATH = LEARNINGS_DIR / "pipeline_learnings.json"
RULES_PATH = LEARNINGS_DIR / "accumulated_rules.md"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
LEARNINGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [stage7_learnings] %(levelname)s — %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "pipeline.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("stage7_learnings")

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4000
MAX_HISTORY_ENTRIES = 10  # use last N runs when distilling rules


DISTILL_PROMPT = """You are a viral content strategist for @automatewithanand (AI automation reels, Indian working professionals, age 22-45).

Below is the history of pipeline runs. Each run records what the script generator did, what scored well, and what consistently failed in the final rendered video.

Your job: extract 10-15 concrete, actionable rules the script generator must follow on EVERY future run to avoid recurring failures.

HISTORY:
{history}

Output a markdown document with a section header and numbered rules. Each rule must be:
- Specific — not vague advice like "make it better"
- Actionable — the script writer can follow it literally
- Derived from actual failures that appear across runs

Format:
## Accumulated Rules from Past Runs

**Rule N: [SHORT TITLE]**
[One precise sentence describing exactly what to do or avoid, and why]

Return only the markdown, no preamble."""


# ---------------------------------------------------------------------------
# History helpers
# ---------------------------------------------------------------------------

def load_history() -> list:
    if HISTORY_PATH.exists():
        try:
            return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_history(history: list) -> None:
    HISTORY_PATH.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Rule distillation
# ---------------------------------------------------------------------------

def distill_rules(history: list, client: anthropic.Anthropic) -> str:
    """Use Claude to distill accumulated history into actionable rules."""
    history_text = ""
    for i, entry in enumerate(history[-MAX_HISTORY_ENTRIES:], 1):
        history_text += f"\n--- Run {i} ({entry.get('date', 'unknown')}) ---\n"
        history_text += f"Topic/Title: {entry.get('topic', 'unknown')}\n"
        history_text += f"Script DSSCL final: {entry.get('script_dsscl_final', '?')}\n"
        history_text += f"Video DSSCL final: {entry.get('video_dsscl_final', '?')} (passed: {entry.get('video_passed', False)})\n"
        strengths = entry.get('strengths', [])
        if strengths:
            history_text += f"Strengths:\n" + "\n".join(f"  - {s}" for s in strengths) + "\n"
        weaknesses = entry.get('weaknesses', [])
        if weaknesses:
            history_text += f"Weaknesses:\n" + "\n".join(f"  - {w}" for w in weaknesses) + "\n"
        if entry.get('script_feedback'):
            history_text += f"Script feedback: {entry['script_feedback']}\n"
        if entry.get('visual_feedback'):
            history_text += f"Visual feedback: {entry['visual_feedback']}\n"

    prompt = DISTILL_PROMPT.format(history=history_text)

    log.info("Calling Claude to distill rules from %d run(s)...", len(history))
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# Main stage function
# ---------------------------------------------------------------------------

def run_stage7() -> dict:
    """
    Capture learnings from the current run and update accumulated rules.

    Returns:
        {"success": bool, "output_path": str, "history_entries": int,
         "duration_sec": float, "error": str|None}
    """
    start_time = time.time()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "success": False,
            "output_path": str(RULES_PATH),
            "duration_sec": 0.0,
            "error": "ANTHROPIC_API_KEY not set.",
        }

    if not ANALYSIS_PATH.exists():
        return {
            "success": False,
            "output_path": str(RULES_PATH),
            "duration_sec": 0.0,
            "error": f"Stage 6 analysis not found: {ANALYSIS_PATH}. Run Stage 6 first.",
        }

    try:
        analysis = json.loads(ANALYSIS_PATH.read_text(encoding="utf-8"))
        script = {}
        if SCRIPT_PATH.exists():
            script = json.loads(SCRIPT_PATH.read_text(encoding="utf-8"))

        # Build this run's entry
        entry = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "topic": script.get("title", "unknown"),
            "script_dsscl_final": script.get("dsscl_scores", {}).get("final"),
            "video_dsscl_final": analysis.get("dsscl_scores", {}).get("final"),
            "video_passed": analysis.get("passed", False),
            "strengths": analysis.get("strengths", []),
            "weaknesses": analysis.get("weaknesses", []),
            "script_feedback": analysis.get("script_feedback", ""),
            "visual_feedback": analysis.get("visual_feedback", ""),
        }

        log.info(
            "Run captured — topic=%r | script DSSCL=%.2f | video DSSCL=%.2f | passed=%s",
            entry["topic"],
            entry["script_dsscl_final"] or 0,
            entry["video_dsscl_final"] or 0,
            entry["video_passed"],
        )

        # Append to history and save
        history = load_history()
        history.append(entry)
        save_history(history)
        log.info("History updated — %d total run(s) recorded.", len(history))

        # Distill rules from full history
        client = anthropic.Anthropic(api_key=api_key)
        rules_md = distill_rules(history, client)
        RULES_PATH.write_text(rules_md, encoding="utf-8")
        log.info("Accumulated rules written → %s (%d chars)", RULES_PATH, len(rules_md))

        duration = time.time() - start_time
        log.info("Stage 7 complete in %.1fs", duration)

        return {
            "success": True,
            "output_path": str(RULES_PATH),
            "history_entries": len(history),
            "duration_sec": round(duration, 2),
            "error": None,
        }

    except Exception as exc:
        log.exception("Stage 7 failed: %s", exc)
        return {
            "success": False,
            "output_path": str(RULES_PATH),
            "duration_sec": round(time.time() - start_time, 2),
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = run_stage7()
    print(json.dumps(result, indent=2))
