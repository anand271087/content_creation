"""
scripts/pre_evaluate_script.py — Script Pre-Evaluator

Critically evaluates assets/script_data.json BEFORE spending on HeyGen/Kie.ai.
Acts as an external critic (not the self-scoring Claude that wrote the script).

Checks:
  1. Hook TAM — no tool jargon in hook, speaks to broadest possible audience
  2. Grand takeaway — must be ONE quotable sentence, max 15 words
  3. Trigger 3 — must have real numbers: city, tool, rupees/dollars, time saved
  4. emotion_save — must name ONE specific tool explicitly
  5. Overall DSSCL text score — independent re-evaluation

Returns:
  {"passed": bool, "score": float, "issues": [...], "feedback": str}

Used by pipeline.py between Stage 1 and Stage 2/3.
"""

import json
import logging
import os
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPT_DATA = PROJECT_ROOT / "assets" / "script_data.json"
LOG_FILE = PROJECT_ROOT / "logs" / "pipeline.log"

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [pre_evaluate] %(levelname)s — %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("pre_evaluate")

MODEL = "claude-sonnet-4-6"
PRE_EVAL_PASS_SCORE = 8.5   # text-only threshold before spending on HeyGen/Kie.ai
MAX_PRE_EVAL_ITERATIONS = 3

# Tool jargon that should NEVER appear in the hook section
HOOK_JARGON_TERMS = [
    "gws", "gsc", "n8n", "zapier", "make", "airtable", "notion",
    "heygen", "runway", "kie", "cli", "api", "webhook", "workflow",
    "claude code", "chatgpt", "openai", "anthropic", "gemini",
]

EVALUATION_PROMPT = """You are a harsh external critic evaluating a viral reel script for @automatewithanand (AI automation, India audience age 22–45).

You did NOT write this script. Score it ruthlessly as if you are a top Instagram content strategist deciding whether to spend $50 on production.

SCRIPT JSON:
{script_json}

Score on DSSCL framework (1–10 each, be strict):
- D (Double Watch): Info density, curiosity loops, rewatch value — will people watch twice?
- Share: Is there a quotable line people will send to 3 friends RIGHT NOW?
- Save: Is there a specific tool named + actionable step they'll bookmark?
- C (Comment): Does it trigger a debate or relatable frustration?
- L (Like): Overall production-readiness of the script

Formula: Final = (D×0.30) + (Share×0.25) + (Save×0.25) + (C×0.10) + (L×0.10)

Also check these NON-NEGOTIABLES — each failure drops the score:
1. HOOK TAM: Does the hook (first 5 seconds) avoid tool-specific jargon? "GWS CLI", "GSC", "n8n" in the hook = automatic TAM failure. Hook must speak to anyone earning money, not just developers.
2. GRAND TAKEAWAY: Is grand_takeaway.spoken exactly ONE sentence, max 15 words, quotable enough to screenshot?
3. TRIGGER 3 SPECIFICITY: Does trigger_3.spoken include a real city name + tool name + rupee/dollar amount + time saved? All four must be present.
4. TOOL IN CTA: Does emotion_save.spoken explicitly name one specific tool (n8n, Zapier, Claude, etc)?
5. NO FILLER: Count the filler words (basically, obviously, literally, so, like). More than 3 = rewrite needed.

Return ONLY valid JSON, no markdown:
{
  "dsscl_scores": {
    "D": 8.0,
    "Share": 7.5,
    "Save": 8.5,
    "C": 7.0,
    "L": 8.0,
    "final": 7.93
  },
  "passed": false,
  "issues": [
    "Hook uses 'GWS CLI' — jargon excludes 80% of audience",
    "Grand takeaway is 2 sentences — needs to be 1 quotable line",
    "Trigger 3 missing rupee amount and time saved"
  ],
  "feedback": "Specific rewrite instructions for Stage 1 to fix each issue above"
}"""


def evaluate_script(script_data: dict) -> dict:
    """Send script to Claude for independent DSSCL evaluation. Returns evaluation dict."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Check hook for jargon first (free check, no API call)
    hook_section = next((s for s in script_data.get("sections", []) if s["id"] == "hook"), None)
    hook_spoken = (hook_section or {}).get("spoken", "").lower()
    jargon_found = [t for t in HOOK_JARGON_TERMS if t in hook_spoken]

    prompt = EVALUATION_PROMPT.replace(
        "{script_json}",
        json.dumps(script_data, indent=2, ensure_ascii=False)[:6000]  # truncate for token efficiency
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw

    result = json.loads(raw)

    # Recalculate final score
    s = result.get("dsscl_scores", {})
    final = (
        s.get("D", 0) * 0.30 + s.get("Share", 0) * 0.25 +
        s.get("Save", 0) * 0.25 + s.get("C", 0) * 0.10 + s.get("L", 0) * 0.10
    )
    result["dsscl_scores"]["final"] = round(final, 2)

    # Inject jargon check findings
    if jargon_found:
        jargon_issue = f"Hook contains jargon: {', '.join(jargon_found)} — will exclude 80% of audience"
        if jargon_issue not in result.get("issues", []):
            result.setdefault("issues", []).insert(0, jargon_issue)
        result["passed"] = False

    result["passed"] = final >= PRE_EVAL_PASS_SCORE and len(result.get("issues", [])) == 0

    return result


def run_pre_evaluate(script_path: str = None) -> dict:
    """
    Evaluate script at script_path (defaults to assets/script_data.json).

    Returns:
        {"passed": bool, "score": float, "issues": [...], "feedback": str,
         "success": bool, "duration_sec": float, "error": str|None}
    """
    start = time.time()
    path = Path(script_path) if script_path else SCRIPT_DATA

    if not path.exists():
        return {"success": False, "passed": False, "score": 0, "issues": [],
                "feedback": "", "duration_sec": 0, "error": f"Script not found: {path}"}

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"success": False, "passed": False, "score": 0, "issues": [],
                "feedback": "", "duration_sec": 0, "error": "ANTHROPIC_API_KEY not set"}

    try:
        script_data = json.loads(path.read_text(encoding="utf-8"))
        log.info("Pre-evaluating script: '%s'", script_data.get("title", "untitled"))

        result = evaluate_script(script_data)
        score = result["dsscl_scores"]["final"]
        passed = result["passed"]
        issues = result.get("issues", [])

        log.info(
            "Pre-eval — D:%.1f Share:%.1f Save:%.1f C:%.1f L:%.1f → Final:%.2f | Passed:%s | Issues:%d",
            result["dsscl_scores"].get("D", 0), result["dsscl_scores"].get("Share", 0),
            result["dsscl_scores"].get("Save", 0), result["dsscl_scores"].get("C", 0),
            result["dsscl_scores"].get("L", 0), score, passed, len(issues),
        )
        for issue in issues:
            log.warning("  ✗ %s", issue)

        return {
            "success": True,
            "passed": passed,
            "score": score,
            "dsscl_scores": result["dsscl_scores"],
            "issues": issues,
            "feedback": result.get("feedback", ""),
            "duration_sec": round(time.time() - start, 2),
            "error": None,
        }

    except Exception as exc:
        log.exception("Pre-evaluation failed")
        return {"success": False, "passed": False, "score": 0, "issues": [],
                "feedback": "", "duration_sec": round(time.time() - start, 2), "error": str(exc)}


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else None
    result = run_pre_evaluate(path)
    print(json.dumps(result, indent=2))
