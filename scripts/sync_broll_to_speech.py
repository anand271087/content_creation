"""
sync_broll_to_speech.py
-----------------------
Aligns script section timestamps (start_sec / end_sec) to the actual speech
timestamps captured by Whisper, so broll switches land exactly when the avatar
starts speaking that section's content.

Also updates:
  - bgm_dip_timestamps  → actual trigger section start times
  - bgm_transition_sec  → actual grand_takeaway start time
  - total_duration_sec  → actual avatar video duration (last word end + 1.5s buffer)

Reads:  assets/script_data.json
        assets/captions/avatar_video.json   (Whisper word timestamps)
Writes: assets/script_data.json   (in-place update, original backed up as .bak)

Usage:
    python3 scripts/sync_broll_to_speech.py [--dry-run]
"""

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPT_DATA = ROOT / "assets" / "script_data.json"
CAPTIONS_JSON = ROOT / "assets" / "captions" / "avatar_video.json"


# ---------------------------------------------------------------------------
# Text normalisation helpers
# ---------------------------------------------------------------------------

_CONTRACTIONS = {
    "im": "i am", "ive": "i have", "ill": "i will", "id": "i would",
    "its": "it is", "thats": "that is", "theres": "there is",
    "theyre": "they are", "theyve": "they have", "theyd": "they would",
    "were": None,  # ambiguous — skip expansion
    "youre": "you are", "youve": "you have", "youd": "you would",
    "hes": "he is", "shes": "she is", "weve": "we have",
    "cant": "can not", "wont": "will not", "dont": "do not",
    "doesnt": "does not", "didnt": "did not", "isnt": "is not",
    "arent": "are not", "wasnt": "was not", "werent": "were not",
    "havent": "have not", "hasnt": "has not", "hadnt": "had not",
    "wouldnt": "would not", "couldnt": "could not", "shouldnt": "should not",
    "lets": "let us",
}


def _clean(text: str) -> str:
    """Lowercase, strip punctuation and extra spaces."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


def _expand_contraction(word: str) -> list[str]:
    """Expand a cleaned (no-apostrophe) contraction into multiple words."""
    expanded = _CONTRACTIONS.get(word)
    if expanded is None:
        return [word]
    return expanded.split()


def _words(text: str) -> list[str]:
    """Tokenise spoken text, expanding contractions so they match Whisper output."""
    raw = [w for w in _clean(text).split() if w]
    out = []
    for w in raw:
        out.extend(_expand_contraction(w))
    return out


# ---------------------------------------------------------------------------
# Whisper word extraction
# ---------------------------------------------------------------------------

def extract_whisper_words(captions: dict) -> list[dict]:
    """Flatten all Whisper segments into [{"word": str, "start": float, "end": float}].
    Contractions like "i'm" are expanded to ["i", "am"] so they match spoken text."""
    out = []
    for seg in captions.get("segments", []):
        for w in seg.get("words") or []:
            clean = _clean(w["word"])
            if not clean:
                continue
            expanded = _expand_contraction(clean)
            if len(expanded) == 1:
                out.append({"word": clean, "start": w["start"], "end": w["end"]})
            else:
                # Distribute the timestamp evenly across expanded tokens
                dur = (w["end"] - w["start"]) / len(expanded)
                for k, tok in enumerate(expanded):
                    out.append({
                        "word": tok,
                        "start": round(w["start"] + k * dur, 3),
                        "end": round(w["start"] + (k + 1) * dur, 3),
                    })
    return out


# ---------------------------------------------------------------------------
# Section → Whisper timestamp matching
# ---------------------------------------------------------------------------

def find_section_start(
    spoken: str,
    whisper_words: list[dict],
    search_from_idx: int = 0,
    n_match: int = 4,
) -> tuple[float, int] | tuple[None, int]:
    """
    Find the Whisper word index where this section starts speaking.

    Strategy:
      1. Take the first `n_match` words of `spoken`.
      2. Slide a window over whisper_words starting from `search_from_idx`.
      3. Return (timestamp, matched_index) of the first word that matches.

    Falls back to matching only the first 2 words if 4-word match fails.
    Returns (None, search_from_idx) if no match found.
    """
    target = _words(spoken)[:n_match]
    if not target:
        return None, search_from_idx

    wlen = len(whisper_words)

    for attempt_n in (len(target), max(2, len(target) - 2), 1):
        attempt_target = target[:attempt_n]
        for i in range(search_from_idx, wlen - attempt_n + 1):
            window = [whisper_words[i + j]["word"] for j in range(attempt_n)]
            if window == attempt_target:
                # Advance past the match so the next section can't reuse
                # the same position (prevents zero-duration sections).
                return whisper_words[i]["start"], i + attempt_n

    print(f"  [WARN] Could not match spoken start: '{' '.join(target)}'")
    return None, search_from_idx


# ---------------------------------------------------------------------------
# Main sync logic
# ---------------------------------------------------------------------------

def sync(dry_run: bool = False) -> None:
    if not SCRIPT_DATA.exists():
        sys.exit(f"script_data.json not found: {SCRIPT_DATA}")
    if not CAPTIONS_JSON.exists():
        sys.exit(f"Whisper captions not found: {CAPTIONS_JSON}. Run stage5 first.")

    with open(SCRIPT_DATA) as f:
        script = json.load(f)
    with open(CAPTIONS_JSON) as f:
        captions = json.load(f)

    whisper_words = extract_whisper_words(captions)
    if not whisper_words:
        sys.exit("No word-level timestamps found in Whisper output.")

    total_actual_sec = whisper_words[-1]["end"] + 1.5  # buffer after last word
    print(f"Whisper timeline: {whisper_words[0]['start']:.2f}s → {whisper_words[-1]['end']:.2f}s")
    print(f"Actual avatar duration (with buffer): {total_actual_sec:.2f}s")
    print(f"Planned total_duration_sec: {script['total_duration_sec']}s")
    print()

    sections = script["sections"]
    search_from = 0
    matched_starts: list[float | None] = []

    for sec in sections:
        t_start, search_from = find_section_start(
            sec["spoken"], whisper_words, search_from_idx=search_from
        )
        matched_starts.append(t_start)
        label = sec["label"]
        planned = f"{sec['start_sec']}→{sec['end_sec']}s"
        actual = f"{t_start:.2f}s" if t_start is not None else "NOT FOUND"
        print(f"  [{label:20s}] planned={planned:10s}  actual_start={actual}")

    # Match summary — show before interpolation so user sees which sections failed
    n_matched = sum(1 for t in matched_starts if t is not None)
    n_total = len(sections)
    failed_sections = [sections[i]["id"] for i, t in enumerate(matched_starts) if t is None]
    print(f"Match result: {n_matched}/{n_total} sections matched to Whisper timestamps")
    if failed_sections:
        print(f"  ⚠ FALLBACK sections (will use interpolated timestamps — may be out of sync):")
        for sid in failed_sections:
            print(f"    - {sid}")
    else:
        print(f"  ✓ All sections matched — sync is reliable")
    print()

    # Fill gaps for unmatched sections using linear interpolation
    for i, (sec, t) in enumerate(zip(sections, matched_starts)):
        if t is not None:
            continue
        # Interpolate: find nearest non-None neighbours
        prev = next((matched_starts[j] for j in range(i - 1, -1, -1) if matched_starts[j] is not None), None)
        nxt = next((matched_starts[j] for j in range(i + 1, len(matched_starts)) if matched_starts[j] is not None), None)
        if prev is not None and nxt is not None:
            matched_starts[i] = (prev + nxt) / 2
        elif prev is not None:
            matched_starts[i] = prev + (sec["end_sec"] - sec["start_sec"])
        else:
            matched_starts[i] = sec["start_sec"]  # fall back to planned
        print(f"  [{sec['label']:20s}] interpolated start → {matched_starts[i]:.2f}s")

    # Assign start_sec / end_sec
    for i, (sec, t_start) in enumerate(zip(sections, matched_starts)):
        new_start = round(t_start, 2)
        # end_sec = next section's start, or total_actual_sec for the last
        if i + 1 < len(sections) and matched_starts[i + 1] is not None:
            new_end = round(matched_starts[i + 1], 2)
        else:
            new_end = round(total_actual_sec, 2)

        old = f"{sec['start_sec']}→{sec['end_sec']}s"
        new = f"{new_start}→{new_end}s"
        if old != new:
            print(f"  Update [{sec['id']:20s}]: {old} → {new}")
        sec["start_sec"] = new_start
        sec["end_sec"] = new_end

    # Derive BGM control timestamps from updated section positions
    trigger_sections = [s for s in sections if s["id"].startswith("trigger_")]
    new_dip_timestamps = [s["start_sec"] for s in trigger_sections]

    grand_takeaway = next((s for s in sections if s["id"] == "grand_takeaway"), None)
    new_bgm_transition = grand_takeaway["start_sec"] if grand_takeaway else script["bgm_transition_sec"]

    print()
    print(f"bgm_dip_timestamps:  {script['bgm_dip_timestamps']} → {new_dip_timestamps}")
    print(f"bgm_transition_sec:  {script['bgm_transition_sec']} → {new_bgm_transition}")
    print(f"total_duration_sec:  {script['total_duration_sec']} → {round(total_actual_sec, 2)}")

    if dry_run:
        print("\n[dry-run] No files written.")
        return

    # Back up original
    bak = SCRIPT_DATA.with_suffix(".json.bak")
    shutil.copy(SCRIPT_DATA, bak)
    print(f"\nBackup written: {bak}")

    script["bgm_dip_timestamps"] = new_dip_timestamps
    script["bgm_transition_sec"] = new_bgm_transition
    script["total_duration_sec"] = round(total_actual_sec, 2)

    with open(SCRIPT_DATA, "w") as f:
        json.dump(script, f, indent=2, ensure_ascii=False)

    print(f"Updated: {SCRIPT_DATA}")
    if failed_sections:
        print(f"\n⚠ Sync warning: {len(failed_sections)} section(s) used interpolated timestamps: {failed_sections}")
        print("  → These sections may have b-roll appearing slightly early or late.")
        print("  → Upgrade WHISPER_MODEL=large-v3 in .env for better match accuracy.")
    else:
        print(f"\n✓ Sync complete — all {n_total} sections matched. B-roll and captions are reliable.")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    sync(dry_run=dry_run)
