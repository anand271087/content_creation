"""Pick the right infographic style (architect / field-journal / marker-board) for the current script.

Deterministic — same inputs always produce the same recommendation.

Signal sources, in order of trust:
  1. assets/script_data.json — format_used, hook text, grand_takeaway, tone
  2. assets/analysis/video_analysis.json — Stage 6 DSSCL.C (comment) score
                                          + strengths/weaknesses if it ran

Rules (first match wins):
  MARKER-BOARD — contrarian, decision-framework, debate-trigger content
    • format_used contains "Counterintuitive", "Before AI vs After", "Manual vs
      Automated", "Old School vs New School", "Common vs Elite"
    • Hook contains contrarian markers ("is dying", "is dead", "you're wrong",
      "everyone is", "nobody is", "the truth is", "stop ...", "no one")
    • Stage 6 DSSCL.C (Comment score) ≥ 8 → high debate signal

  FIELD-JOURNAL — personal, reflective, "I built this" content
    • Hook starts with first-person experience ("I set up", "I built", "I tried",
      "I tested", "Last weekend I", "Last night I")
    • tone field includes "personal", "vulnerable", "reflection"
    • Title contains "my" / "I" in a personal-story sense (not "I'll DM you")

  ARCHITECT — default for explainers, frameworks, thought-leadership
    • Everything else
    • Especially: format_used contains "Steps", "Framework", "Three / Five /
      N-thing", "Checklist", "Recipe", "Anatomy of"

Usage:
  python3 scripts/recommend_infographic_style.py
  python3 scripts/recommend_infographic_style.py --json    # machine-readable

Exit code is always 0. Recommendation goes to stdout.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DATA = ROOT / "assets" / "script_data.json"
VIDEO_ANALYSIS = ROOT / "assets" / "analysis" / "video_analysis.json"

# ── Signal patterns ──────────────────────────────────────────────────────────
MARKER_BOARD_FORMATS = re.compile(
    r"counterintuitive|before .* vs .* after|manual .* vs .* automated|"
    r"old school .* vs .* new school|common .* vs .* elite|vs\.?\s",
    re.IGNORECASE,
)

# Cheap contrarian/debate markers in the hook or grand takeaway.
MARKER_BOARD_PHRASES = [
    r"\b(is|are) dying\b",
    r"\b(is|are) dead\b",
    r"\bnot dying\b",
    r"\bnot dead\b",
    r"\byou(?:'re| are) wrong\b",
    r"\beveryone (?:is|says|thinks)\b",
    r"\bnobody (?:is|talks|tells|knows|wants)\b",
    r"\bno one (?:is|talks|tells|knows)\b",
    r"\bthe truth (?:is|nobody)\b",
    r"^stop\b",
    r"\bstop (?:trying|building|chasing|using|paying|wasting)\b",
    r"\bquietly (?:shipped|dropped|launched|released)\b",
    r"\bdon(?:'t| not) (?:miss|wait|ignore)\b",
]

FIELD_JOURNAL_PHRASES = [
    r"^i (?:set up|built|tested|tried|ran|deployed|shipped|wrote|spent|started)\b",
    r"^last (?:night|weekend|week) i\b",
    r"^last weekend\b",
    r"\bmy (?:weekend|laptop|terminal|workspace|inbox|workflow)\b",
    r"^a few (?:days|weeks|months) ago i\b",
]

ARCHITECT_FORMAT_HINTS = re.compile(
    r"\b(?:steps?|framework|recipe|checklist|anatomy|playbook|stack|blueprint|"
    r"how to|guide to)\b",
    re.IGNORECASE,
)

ARCHITECT_FORMAT_NUMBERS = re.compile(
    r"\b(?:three|four|five|six|seven|eight|nine|ten|\d+)[\s-]?"
    r"(?:steps?|things?|tips?|moves?|levers?|tools?|models?|stages?|primitives?)\b",
    re.IGNORECASE,
)


def _has_pattern(text: str, patterns: list[str]) -> str | None:
    """Return the first matching pattern (for debugging), or None."""
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return p
    return None


def recommend(script_data: dict, video_analysis: dict | None = None) -> dict:
    """Pick a style based on script + (optional) Stage 6 analysis signals.

    Returns dict with keys:
      style: "architect" | "field-journal" | "marker-board"
      reason: one-line explanation
      signals: list of signal strings that fired (for debugging)
    """
    signals: list[str] = []
    hook = ""
    title = script_data.get("title", "")
    grand = script_data.get("grand_takeaway_line", "")
    format_used = script_data.get("format_used", "")
    tone = script_data.get("tone", "")
    for sec in script_data.get("sections", []):
        if sec.get("id") == "hook":
            hook = sec.get("spoken", "") or ""
            break

    haystack_contrarian = f"{title}\n{hook}\n{grand}"
    haystack_personal = hook  # only the actual spoken hook for personal voice
    haystack_format = f"{format_used}\n{title}"

    # ── 1. MARKER-BOARD signals ───────────────────────────────────────────────
    if MARKER_BOARD_FORMATS.search(format_used):
        signals.append(f"format='{format_used}' matches contrarian/vs format")
    m = _has_pattern(haystack_contrarian, MARKER_BOARD_PHRASES)
    if m:
        signals.append(f"contrarian phrase matched: {m!r}")

    comment_score = None
    if video_analysis:
        comment_score = (
            video_analysis.get("dsscl_scores", {}).get("C")
            or video_analysis.get("dsscl_scores", {}).get("Comment")
        )
        if comment_score is not None and comment_score >= 8.0:
            signals.append(f"Stage 6 Comment score {comment_score} ≥ 8 (debate-trigger)")

    marker_score = sum(1 for s in signals if s)
    if marker_score >= 1:
        return {
            "style": "marker-board",
            "reason": (
                "Contrarian / debate-trigger content. "
                + " | ".join(signals)
            ),
            "signals": signals,
        }

    # ── 2. FIELD-JOURNAL signals ──────────────────────────────────────────────
    personal_signals: list[str] = []
    m = _has_pattern(haystack_personal, FIELD_JOURNAL_PHRASES)
    if m:
        personal_signals.append(f"personal hook matched: {m!r}")
    if tone and any(t in tone.lower() for t in ("personal", "vulnerable", "reflection", "warm")):
        personal_signals.append(f"tone='{tone}'")

    if personal_signals:
        return {
            "style": "field-journal",
            "reason": (
                "Personal / reflective content. "
                + " | ".join(personal_signals)
            ),
            "signals": personal_signals,
        }

    # ── 3. ARCHITECT (default) ────────────────────────────────────────────────
    arch_signals: list[str] = []
    if ARCHITECT_FORMAT_HINTS.search(haystack_format):
        arch_signals.append("framework / steps / playbook language detected")
    if ARCHITECT_FORMAT_NUMBERS.search(haystack_format):
        arch_signals.append("numbered-list framing detected")
    if not arch_signals:
        arch_signals.append("default — explainer / thought-leadership")

    return {
        "style": "architect",
        "reason": "Explainer / framework content. " + " | ".join(arch_signals),
        "signals": arch_signals,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--json", action="store_true",
                   help="Emit machine-readable JSON instead of text.")
    p.add_argument("--script", default=str(SCRIPT_DATA),
                   help=f"Path to script_data.json (default: {SCRIPT_DATA})")
    args = p.parse_args()

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"ERROR: {script_path} not found.", file=sys.stderr)
        return 1
    script_data = json.loads(script_path.read_text())

    video_analysis = None
    if VIDEO_ANALYSIS.exists():
        try:
            video_analysis = json.loads(VIDEO_ANALYSIS.read_text())
        except Exception:
            video_analysis = None

    rec = recommend(script_data, video_analysis)

    if args.json:
        print(json.dumps(rec, indent=2))
    else:
        print(f"  Recommended style: {rec['style']}")
        print(f"  Why: {rec['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
