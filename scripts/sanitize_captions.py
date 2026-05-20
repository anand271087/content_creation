"""
Sanitize Whisper captions — fix known misheard words and flag/replace vulgar words.
Run after Whisper, before Remotion render.
Usage: python3 scripts/sanitize_captions.py [path/to/captions.json]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEFAULT_PATH = ROOT / "assets" / "captions" / "avatar_video.json"

# Whisper mishears of common words in this channel's content
# Format: "wrong_word_lowercase": "correct_word"
REPLACEMENTS = {
    "sexual": "scheduled",
    "sexualized": "scheduled",
    "scheduling": "scheduling",   # keep — just ensuring no mis-map
    "anthropic's": "anthropic's",
    "n eight n": "n8n",
    "in eight n": "n8n",
    "clay code": "claude code",
    "cloud code": "claude code",
}

# Vulgar words — replace with phonetically similar safe alternatives or flag
VULGAR_REPLACEMENTS = {
    "fuck": "[BLEEP]",
    "fucking": "[BLEEP]",
    "shit": "[BLEEP]",
    "bullshit": "[BLEEP]",
    "bitch": "[BLEEP]",
    "asshole": "[BLEEP]",
    "cunt": "[BLEEP]",
    "dick": "[BLEEP]",
    "cock": "[BLEEP]",
    "pussy": "[BLEEP]",
    "bastard": "[BLEEP]",
    "whore": "[BLEEP]",
    "nigger": "[BLEEP]",
    "nigga": "[BLEEP]",
}

ALL_REPLACEMENTS = {**REPLACEMENTS, **VULGAR_REPLACEMENTS}


def _replace_word(text: str) -> tuple[str, list[str]]:
    """Apply all replacements to a text string. Returns (fixed_text, list_of_changes)."""
    changes = []
    for wrong, correct in ALL_REPLACEMENTS.items():
        pattern = r'\b' + re.escape(wrong) + r'\b'
        if re.search(pattern, text, flags=re.IGNORECASE):
            fixed = re.sub(pattern, correct, text, flags=re.IGNORECASE)
            changes.append(f'"{wrong}" → "{correct}"')
            text = fixed
    return text, changes


def sanitize(captions_path: Path) -> int:
    if not captions_path.exists():
        print(f"Captions file not found: {captions_path}")
        return 1

    data = json.loads(captions_path.read_text(encoding="utf-8"))
    total_changes = []

    # Top-level text
    fixed, changes = _replace_word(data.get("text", ""))
    if changes:
        data["text"] = fixed
        for c in changes:
            total_changes.append(f"top-level text: {c}")

    # Segments
    for seg in data.get("segments", []):
        fixed, changes = _replace_word(seg.get("text", ""))
        if changes:
            seg["text"] = fixed
            for c in changes:
                total_changes.append(f"segment[{seg['id']}] text: {c}")

        for w in seg.get("words", []):
            original = w.get("word", "")
            fixed, changes = _replace_word(original)
            if changes:
                w["word"] = fixed
                for c in changes:
                    total_changes.append(f"word at {w.get('start', '?')}s: {c}")

    captions_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if total_changes:
        print(f"sanitize_captions: {len(total_changes)} fix(es) applied:")
        for c in total_changes:
            print(f"  {c}")
    else:
        print("sanitize_captions: no issues found.")

    return 0


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    sys.exit(sanitize(path))
