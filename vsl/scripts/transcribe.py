"""
vsl/scripts/transcribe.py
Transcribe each rendered avatar segment with word-level timestamps, write JSON
(Whisper-shaped) to vsl/assets/captions/<segment>.json.

Provider routing:
  - ELEVENLABS_API_KEY set  → ElevenLabs Scribe (cloud, fast, accurate on proper nouns)
  - otherwise               → local Whisper (free, slower)

Used by compose.py to burn 2-line captions in long-form YouTube style.

Usage:
  python3 vsl/scripts/transcribe.py                  # transcribe all segments missing or stale
  python3 vsl/scripts/transcribe.py --force          # re-transcribe everything
  python3 vsl/scripts/transcribe.py hook outro       # specific segment ids only
"""
from __future__ import annotations
import argparse, hashlib, json, logging, os, subprocess, sys
from pathlib import Path

from dotenv import load_dotenv

ROOT       = Path(__file__).resolve().parent.parent
PROJECT    = ROOT.parent
AVATAR_DIR = ROOT / "assets" / "avatar"
CAPS_DIR   = ROOT / "assets" / "captions"
STATE_FILE = ROOT / "state.json"
LOG_FILE   = PROJECT / "logs" / "vsl_transcribe.log"

# Reuse the existing ElevenLabs Scribe adapter from the main project.
ELEVENLABS_SCRIPT = PROJECT / "scripts" / "transcribe_elevenlabs.py"

CAPS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("vsl_transcribe")
logger.setLevel(logging.DEBUG)
_fmt = logging.Formatter("%(asctime)s [vsl_transcribe] %(levelname)s %(message)s")
_fh = logging.FileHandler(LOG_FILE); _fh.setFormatter(_fmt); logger.addHandler(_fh)
_sh = logging.StreamHandler(sys.stdout); _sh.setFormatter(_fmt); logger.addHandler(_sh)


def file_hash(p: Path) -> str:
    h = hashlib.sha256()
    h.update(str(p.stat().st_size).encode())
    h.update(b"|")
    h.update(str(int(p.stat().st_mtime)).encode())
    return h.hexdigest()[:12]


def transcribe_via_elevenlabs(mp4: Path) -> dict:
    """Run the existing ElevenLabs Scribe adapter; returns Whisper-shaped JSON."""
    sid = mp4.stem
    json_out = CAPS_DIR / f"{sid}.json"
    if not ELEVENLABS_SCRIPT.exists():
        raise RuntimeError(f"ElevenLabs adapter not found: {ELEVENLABS_SCRIPT}")
    cmd = [
        sys.executable, str(ELEVENLABS_SCRIPT),
        str(mp4),
        "--output", str(json_out),
    ]
    logger.info("[%s] elevenlabs Scribe → %s", sid, json_out.name)
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        logger.error("[%s] Scribe failed:\n%s", sid, (res.stderr or res.stdout)[-1500:])
        raise RuntimeError(f"Scribe failed for {sid}")
    if not json_out.exists():
        raise RuntimeError(f"Scribe did not write {json_out}")
    return json.loads(json_out.read_text())


def transcribe_via_whisper(mp4: Path) -> dict:
    """Run local Whisper CLI; returns Whisper-shaped JSON."""
    sid = mp4.stem
    json_out = CAPS_DIR / f"{sid}.json"
    model = os.getenv("WHISPER_MODEL", "medium")
    logger.info("[%s] whisper model=%s", sid, model)
    cmd = [
        "whisper", str(mp4),
        "--model", model,
        "--output_format", "json",
        "--output_dir", str(CAPS_DIR),
        "--word_timestamps", "True",
        "--language", "en",
        "--fp16", "False",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        logger.error("[%s] whisper failed:\n%s", sid, res.stderr[-1500:])
        raise RuntimeError(f"whisper failed for {sid}")
    if not json_out.exists():
        raise RuntimeError(f"whisper did not write {json_out}")
    return json.loads(json_out.read_text())


def pick_provider() -> str:
    """Return 'elevenlabs' if ELEVENLABS_API_KEY is set, else 'whisper'."""
    load_dotenv(PROJECT / ".env")
    if os.getenv("ELEVENLABS_API_KEY", "").strip():
        return "elevenlabs"
    return "whisper"


def transcribe_one(mp4: Path, provider: str) -> dict:
    if provider == "elevenlabs":
        return transcribe_via_elevenlabs(mp4)
    return transcribe_via_whisper(mp4)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true")
    p.add_argument("targets", nargs="*")
    args = p.parse_args()

    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    state.setdefault("captions", {})

    provider = pick_provider()
    logger.info("STT provider: %s", provider)

    mp4s = sorted(AVATAR_DIR.glob("*.mp4"))
    if args.targets:
        mp4s = [p for p in mp4s if p.stem in args.targets]
    if not mp4s:
        logger.error("no avatar mp4s to transcribe in %s", AVATAR_DIR)
        return 2

    ok = skip = err = 0
    for mp4 in mp4s:
        sid = mp4.stem
        digest = file_hash(mp4)
        prev = state["captions"].get(sid)
        json_out = CAPS_DIR / f"{sid}.json"
        # also gate on provider — if user switches providers, re-transcribe
        if (not args.force) and json_out.exists() and prev and prev.get("hash") == digest and prev.get("provider") == provider:
            logger.info("[%s] unchanged — skipping", sid)
            skip += 1
            continue
        try:
            data = transcribe_one(mp4, provider)
            n_words = sum(len(s.get("words", [])) for s in data.get("segments", []))
            state["captions"][sid] = {"hash": digest, "words": n_words, "provider": provider}
            STATE_FILE.write_text(json.dumps(state, indent=2))
            logger.info("[%s] ✅ %d words", sid, n_words)
            ok += 1
        except Exception as e:
            logger.error("[%s] ❌ %s", sid, e)
            err += 1

    print(f"\nProvider: {provider}    Transcribed: {ok}    Skipped: {skip}    Failed: {err}")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
