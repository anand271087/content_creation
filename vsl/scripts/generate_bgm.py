"""
Generate a short ambient BGM loop via ElevenLabs Music API (preferred) with a
fallback to the Sound-Generation endpoint. Saves to vsl/assets/music/bgm.mp3.

The Music API can produce up to 5 minutes of music in one call — enough for the
whole VSL — but it's beta. We try it first; if it fails we fall back to a 22s
sound-generation clip that compose.py will loop.

Reads ELEVENLABS_API_KEY from .env at the project root.
"""
from __future__ import annotations
import logging, os, sys, time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT     = Path(__file__).resolve().parent.parent
OUT_DIR  = ROOT / "assets" / "music"
OUT_FILE = OUT_DIR / "bgm.mp3"
LOG_FILE = ROOT.parent / "logs" / "vsl_bgm.log"

ELEVEN_MUSIC_URL = "https://api.elevenlabs.io/v1/music"
ELEVEN_SFX_URL   = "https://api.elevenlabs.io/v1/sound-generation"

BGM_PROMPT = (
    "calm hopeful ambient instrumental, soft piano arpeggio, light pad strings, "
    "warm tone, gentle breathing rhythm, NO drums, NO bass drops, no melody, "
    "minimal, expert teaching mood"
)

OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("vsl_bgm")
logger.setLevel(logging.DEBUG)
fmt = logging.Formatter("%(asctime)s [vsl_bgm] %(levelname)s %(message)s")
fh  = logging.FileHandler(LOG_FILE); fh.setFormatter(fmt); logger.addHandler(fh)
sh  = logging.StreamHandler(sys.stdout); sh.setFormatter(fmt); logger.addHandler(sh)


def load_env() -> str:
    load_dotenv(ROOT.parent / ".env")
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key:
        logger.error("ELEVENLABS_API_KEY not set in .env")
        sys.exit(2)
    return key


def try_music_api(api_key: str, prompt: str, length_ms: int = 180_000) -> bytes | None:
    """Hit ElevenLabs Music endpoint. Returns mp3 bytes or None on failure."""
    body = {"prompt": prompt, "music_length_ms": length_ms}
    headers = {"xi-api-key": api_key, "Content-Type": "application/json",
               "Accept": "audio/mpeg"}
    logger.info("Trying Music API — %d ms (%.1f min)…", length_ms, length_ms / 60_000)
    try:
        r = requests.post(ELEVEN_MUSIC_URL, headers=headers, json=body, timeout=300)
    except requests.RequestException as e:
        logger.warning("Music API network error: %s", e); return None
    if r.status_code in (200, 201) and r.headers.get("content-type", "").startswith("audio/"):
        logger.info("Music API responded with audio (%d KB)", len(r.content) // 1024)
        return r.content
    logger.warning("Music API not available (HTTP %d): %s",
                   r.status_code, r.text[:300])
    return None


def try_sfx_api(api_key: str, prompt: str, seconds: int = 22) -> bytes | None:
    """Hit ElevenLabs Sound-Generation endpoint. Returns mp3 bytes or None."""
    body = {"text": prompt, "duration_seconds": seconds, "prompt_influence": 0.3}
    headers = {"xi-api-key": api_key, "Content-Type": "application/json",
               "Accept": "audio/mpeg"}
    logger.info("Calling Sound-Generation API — %ds…", seconds)
    try:
        r = requests.post(ELEVEN_SFX_URL, headers=headers, json=body, timeout=120)
    except requests.RequestException as e:
        logger.error("SFX network error: %s", e); return None
    if r.status_code in (200, 201) and r.headers.get("content-type", "").startswith("audio/"):
        logger.info("SFX API responded with audio (%d KB)", len(r.content) // 1024)
        return r.content
    logger.error("SFX API failed (HTTP %d): %s", r.status_code, r.text[:500])
    return None


def main() -> int:
    if OUT_FILE.exists() and OUT_FILE.stat().st_size > 50_000:
        logger.info("BGM already exists at %s — skipping", OUT_FILE)
        return 0
    api_key = load_env()
    # Try Music API first (longer track = no loop seam)
    audio = try_music_api(api_key, BGM_PROMPT, length_ms=180_000)
    # Fall back to sound-generation (22s clip, will loop in compose.py)
    if audio is None:
        logger.info("Falling back to Sound-Generation endpoint…")
        audio = try_sfx_api(api_key, BGM_PROMPT, seconds=22)
    if audio is None:
        logger.error("Both ElevenLabs endpoints failed — no BGM generated")
        return 1
    OUT_FILE.write_bytes(audio)
    logger.info("Wrote %s (%d KB)", OUT_FILE, OUT_FILE.stat().st_size // 1024)
    return 0


if __name__ == "__main__":
    sys.exit(main())
