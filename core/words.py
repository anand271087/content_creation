"""Scribe/Whisper word-timestamp utilities shared by every format compositor."""
from __future__ import annotations
import json
import re
from pathlib import Path

# Known Whisper mishears (Scribe rarely needs these, kept for safety)
WHISPER_FIXES = {"heigen": "HeyGen", "heigan": "HeyGen", "haygen": "HeyGen"}
COMPOUND_MERGES = [
    ("chat", "gpt", "ChatGPT"),
    ("eleven", "labs", "ElevenLabs"),
]


def clean(w: str) -> str:
    """Lowercase alnum-only token for anchor matching."""
    return re.sub(r"[^a-z0-9]", "", w.lower())


def load_words(caps_json: Path) -> list[dict]:
    """Flatten a Scribe/Whisper JSON into [{word, start, end}, ...]."""
    data = json.loads(Path(caps_json).read_text())
    out = []
    for seg in data.get("segments", []):
        for w in seg.get("words", []) or []:
            t = (w.get("word") or w.get("text") or "").strip()
            if not t:
                continue
            try:
                out.append({"word": t, "start": float(w["start"]), "end": float(w["end"])})
            except (KeyError, TypeError, ValueError):
                continue
    return out


def normalize(words: list[dict]) -> list[dict]:
    """Fix mishears + merge split compound brand names."""
    fixed = [{**w, "word": WHISPER_FIXES.get(clean(w["word"]), w["word"])} for w in words]
    merged: list[dict] = []
    i = 0
    while i < len(fixed):
        if i + 1 < len(fixed):
            a, b = clean(fixed[i]["word"]), clean(fixed[i + 1]["word"])
            hit = next((m for (x, y, m) in COMPOUND_MERGES if x == a and y == b), None)
            if hit:
                merged.append({"word": hit, "start": fixed[i]["start"], "end": fixed[i + 1]["end"]})
                i += 2
                continue
        merged.append(fixed[i])
        i += 1
    return merged


def find_word(words: list[dict], target: str, after: float = 0.0) -> float | None:
    """Start time of the first occurrence of `target` at/after `after` seconds."""
    t = clean(target)
    for w in words:
        if w["start"] >= after and clean(w["word"]) == t:
            return w["start"]
    return None


def find_after_anchor(words: list[dict], anchor: str, follow: str) -> tuple[float, float] | None:
    """(anchor_start, follow_start): first `anchor`, then first `follow` after it.
    The standard reveal pattern: item name → grade/stage word."""
    a = clean(anchor)
    f = clean(follow)
    for i, w in enumerate(words):
        if clean(w["word"]) == a:
            for w2 in words[i + 1:]:
                if clean(w2["word"]) == f:
                    return w["start"], w2["start"]
            return w["start"], w["start"] + 1.5
    return None


def duration_of(video: Path) -> float:
    import subprocess
    return float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(video)]).decode().strip())
