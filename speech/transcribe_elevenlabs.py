"""
Transcribe an audio/video file via the ElevenLabs Scribe speech-to-text API
and write Whisper-shaped JSON to the requested output path.

This script is the ElevenLabs branch of Stage 5's transcription step.
The Whisper-shaped output keeps downstream consumers (sync_broll_to_speech.py,
HormoziCaptions.tsx, sanitize_captions.py) untouched.

Usage:
    python3 scripts/transcribe_elevenlabs.py <input.mp4> --output <captions.json>

Requires:
    - ELEVENLABS_API_KEY in env or .env
    - ffmpeg on PATH (for audio extraction)
    - requests (already in requirements.txt)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = ROOT / "logs" / "pipeline.log"

ELEVENLABS_STT_ENDPOINT = "https://api.elevenlabs.io/v1/speech-to-text"
ELEVENLABS_MODEL_ID = "scribe_v1"

# Group flat ElevenLabs words into "segments" by punctuation OR by a silence gap.
# Whisper-shaped consumers don't care how segments are cut — they iterate every
# segment's words[]. We pick boundaries that look like natural sentences so the
# debug-view JSON is still human-readable.
SEGMENT_GAP_SECONDS = 0.8
SEGMENT_END_PUNCTUATION = {".", "?", "!"}

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("transcribe_elevenlabs")
logger.setLevel(logging.DEBUG)
_fmt = logging.Formatter(
    "%(asctime)s [transcribe_elevenlabs] %(levelname)s %(message)s"
)
_fh = logging.FileHandler(LOG_FILE)
_fh.setFormatter(_fmt)
logger.addHandler(_fh)
_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(_fmt)
logger.addHandler(_sh)


def _resolve_api_key() -> str:
    """Read ELEVENLABS_API_KEY from env or .env. Exit with a clean message if absent."""
    load_dotenv(ROOT / ".env")
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key:
        logger.error(
            "ELEVENLABS_API_KEY is not set.\n"
            "  Get a key: https://elevenlabs.io/app/settings/api-keys\n"
            "  Then add it to .env:  ELEVENLABS_API_KEY=...\n"
            "  Or set STT_PROVIDER=whisper to use the local fallback."
        )
        sys.exit(2)
    return key


def _extract_audio(input_path: Path) -> Path:
    """ffmpeg-extract a 16 kHz mono mp3 from the input. Returns path to a temp file.

    The caller is responsible for cleaning up the returned path (use a context
    manager via the temp dir). 16 kHz mono is plenty for STT and keeps the
    upload small — a 2-minute reel comes out under 1 MB.
    """
    if not shutil.which("ffmpeg"):
        logger.error("ffmpeg not found on PATH. Install with: brew install ffmpeg")
        sys.exit(2)

    tmp_dir = Path(tempfile.mkdtemp(prefix="elevenlabs_stt_"))
    out = tmp_dir / "audio.mp3"
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(input_path),
        "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "libmp3lame", "-b:a", "64k",
        str(out),
    ]
    logger.info("Extracting audio (16 kHz mono mp3) — %s", out)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        logger.error("ffmpeg failed (rc=%d):\n%s", proc.returncode, proc.stderr[-1000:])
        sys.exit(2)
    logger.info("Audio extracted — %d bytes", out.stat().st_size)
    return out


def _call_scribe(audio_path: Path, api_key: str) -> dict:
    """POST the audio to ElevenLabs Scribe. Return the parsed JSON response."""
    logger.info("POST %s (model=%s, words granularity)", ELEVENLABS_STT_ENDPOINT, ELEVENLABS_MODEL_ID)
    started = time.time()
    with open(audio_path, "rb") as fh:
        files = {"file": ("audio.mp3", fh, "audio/mpeg")}
        data = {
            "model_id": ELEVENLABS_MODEL_ID,
            "language_code": "eng",
            "timestamps_granularity": "word",
            "tag_audio_events": "false",
        }
        headers = {"xi-api-key": api_key}
        resp = requests.post(
            ELEVENLABS_STT_ENDPOINT,
            files=files, data=data, headers=headers,
            timeout=300,
        )
    elapsed = time.time() - started
    if resp.status_code != 200:
        logger.error(
            "ElevenLabs Scribe returned %d after %.1fs:\n%s",
            resp.status_code, elapsed, resp.text[:2000],
        )
        sys.exit(1)
    logger.info("Scribe responded in %.1fs (%d bytes)", elapsed, len(resp.content))
    return resp.json()


def _is_word_token(item: dict) -> bool:
    """Return True if this Scribe item is a word (not punctuation or spacing).

    Scribe items carry a `type` field: 'word', 'spacing', or 'audio_event'.
    We pull words for downstream timestamping and use punctuation tokens only
    to decide segment boundaries.
    """
    return item.get("type") == "word"


def _segment_text(words: list[dict]) -> str:
    """Reconstruct a readable segment string from its words."""
    return " ".join(w["text"] for w in words).strip()


def _to_whisper_shape(scribe: dict) -> dict:
    """Convert ElevenLabs Scribe response → Whisper-shaped JSON.

    Whisper shape (what downstream code expects):
      {
        "text":     <full transcript>,
        "language": "en",
        "segments": [
          {
            "id": <int>, "start": <float>, "end": <float>, "text": <segment text>,
            "words": [{"word": <str>, "start": <float>, "end": <float>, "probability": 1.0}, ...]
          },
          ...
        ]
      }

    Segments are cut at sentence-ending punctuation (`.`, `?`, `!`) or at a
    silence gap >= SEGMENT_GAP_SECONDS between consecutive words.
    """
    items = scribe.get("words", []) or []
    full_text = scribe.get("text", "")

    # Walk the flat item stream and bucket into segments.
    segments: list[dict] = []
    current_words: list[dict] = []
    last_word_end: float | None = None

    def flush(force: bool = False) -> None:
        nonlocal current_words
        if not current_words:
            return
        seg_start = float(current_words[0]["start"])
        seg_end = float(current_words[-1]["end"])
        segments.append({
            "id": len(segments),
            "start": seg_start,
            "end": seg_end,
            "text": _segment_text(current_words),
            "words": [
                {
                    "word": w["text"],
                    "start": float(w["start"]),
                    "end": float(w["end"]),
                    "probability": 1.0,
                }
                for w in current_words
            ],
        })
        current_words = []

    for item in items:
        if _is_word_token(item):
            # Gap-based segment break: if there's a big silence between the
            # previous word and this one, close the prior segment first.
            try:
                start_f = float(item["start"])
            except (KeyError, TypeError, ValueError):
                continue
            if (
                last_word_end is not None
                and start_f - last_word_end >= SEGMENT_GAP_SECONDS
                and current_words
            ):
                flush()
            current_words.append(item)
            try:
                last_word_end = float(item["end"])
            except (KeyError, TypeError, ValueError):
                last_word_end = None
        elif item.get("text") in SEGMENT_END_PUNCTUATION and current_words:
            # Punctuation-based segment break: include the punctuation by
            # appending it to the last word's `word` field, then flush.
            current_words[-1] = {
                **current_words[-1],
                "text": current_words[-1]["text"] + item["text"],
            }
            flush()
        # spacing / audio_event tokens are ignored

    flush(force=True)

    return {
        "text": full_text,
        "language": "en",
        "segments": segments,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", help="Path to the input video or audio file.")
    parser.add_argument(
        "--output", required=True,
        help="Path to write Whisper-shaped JSON (e.g. assets/captions/avatar_video.json).",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    if not input_path.exists():
        logger.error("Input not found: %s", input_path)
        return 1
    output_path.parent.mkdir(parents=True, exist_ok=True)

    api_key = _resolve_api_key()

    started = time.time()
    tmp_audio: Path | None = None
    try:
        tmp_audio = _extract_audio(input_path)
        scribe_json = _call_scribe(tmp_audio, api_key)
        whisper_shaped = _to_whisper_shape(scribe_json)
        output_path.write_text(json.dumps(whisper_shaped, indent=2))
        n_segments = len(whisper_shaped["segments"])
        n_words = sum(len(s["words"]) for s in whisper_shaped["segments"])
        elapsed = time.time() - started
        logger.info(
            "Wrote %s — %d segments, %d words, %.1fs total",
            output_path, n_segments, n_words, elapsed,
        )
        return 0
    finally:
        if tmp_audio and tmp_audio.parent.exists():
            try:
                shutil.rmtree(tmp_audio.parent)
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(main())
