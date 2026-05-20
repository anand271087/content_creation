"""
Stage 4 — Background Music Generation (Kie.ai ElevenLabs)
Submits Track 1 (tension, 35s) and Track 2 (warm, 25s) simultaneously,
polls both in parallel, downloads to assets/music/.
"""

import json
import logging
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from dotenv import load_dotenv
from tqdm import tqdm

SCRIPT_DATA_PATH = Path(__file__).parent.parent / "assets" / "script_data.json"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
MUSIC_DIR = ROOT / "assets" / "music"
LOG_FILE = ROOT / "logs" / "pipeline.log"

TRACK1_OUTPUT = MUSIC_DIR / "track1_tension.mp3"
TRACK2_OUTPUT = MUSIC_DIR / "track2_warm.mp3"
STING1_OUTPUT = MUSIC_DIR / "sting1.mp3"
STING2_OUTPUT = MUSIC_DIR / "sting2.mp3"
STING3_OUTPUT = MUSIC_DIR / "sting3.mp3"
HOOK_STING_OUTPUT = MUSIC_DIR / "hook_sting.mp3"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("stage4_music")
logger.setLevel(logging.DEBUG)

_fmt = logging.Formatter("%(asctime)s [stage4_music] %(levelname)s %(message)s")

_fh = logging.FileHandler(LOG_FILE)
_fh.setFormatter(_fmt)
logger.addHandler(_fh)

_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(_fmt)
logger.addHandler(_sh)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
KIE_CREATE_URL = "https://api.kie.ai/api/v1/jobs/createTask"
KIE_POLL_URL = "https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}"

POLL_INTERVAL_SEC = 15
TASK_TIMEOUT_SEC = 600       # 10 minutes per track
MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]   # seconds

# Tone → Track 1 prompt map (script-aware music)
_TRACK1_TONE_MAP = {
    "urgent": (
        "cinematic dark orchestral underscore, fast tempo driving tension, "
        "pounding sub bass, relentless urgency, no melody, no vocals, "
        "seamless loop point, exactly 35 seconds"
    ),
    "inspiring": (
        "cinematic uplifting orchestral underscore, slow confident build, "
        "deep bass with hopeful harmonic undertone, no melody, no vocals, "
        "seamless loop point, exactly 35 seconds"
    ),
    "neutral": (
        "cinematic dark orchestral underscore, deep sub bass rumble, "
        "tense thriller atmosphere, slow build from quiet dread to full tension, "
        "no melody, no vocals, seamless loop point, exactly 35 seconds"
    ),
}

# Tone → Track 2 prompt map
_TRACK2_TONE_MAP = {
    "urgent": (
        "warm uplifting piano with gentle strings, resolved tension, "
        "positive momentum, light percussion, no vocals, seamless loop, exactly 25 seconds"
    ),
    "inspiring": (
        "warm hopeful soft piano with gentle ambient pad, soaring resolution, "
        "light percussion, positive transformation energy, no vocals, "
        "seamless loop, exactly 25 seconds"
    ),
    "neutral": (
        "warm uplifting soft piano with gentle ambient pad, "
        "positive transformation feel, light percussion, hopeful resolution energy, "
        "no vocals, seamless loop, exactly 25 seconds"
    ),
}


def _load_script_tone() -> str:
    """Read tone from script_data.json. Falls back to 'neutral'."""
    if not SCRIPT_DATA_PATH.exists():
        return "neutral"
    try:
        with open(SCRIPT_DATA_PATH) as fh:
            data = json.load(fh)
        return data.get("tone", "neutral")
    except Exception:
        return "neutral"


def _build_tracks() -> list[dict]:
    tone = _load_script_tone()
    logger.info("Script tone detected: '%s' — selecting music prompts accordingly", tone)

    track1_prompt = _TRACK1_TONE_MAP.get(tone, _TRACK1_TONE_MAP["neutral"])
    track2_prompt = _TRACK2_TONE_MAP.get(tone, _TRACK2_TONE_MAP["neutral"])

    return [
        {
            "id": "track1",
            "label": "Track 1 (tension)",
            "output": TRACK1_OUTPUT,
            "loop": True,
            "prompt_influence": 0.6,
            "output_format": "mp3_44100_128",
            "prompt": track1_prompt,
        },
        {
            "id": "track2",
            "label": "Track 2 (warm)",
            "output": TRACK2_OUTPUT,
            "loop": True,
            "prompt_influence": 0.6,
            "output_format": "mp3_44100_128",
            "prompt": track2_prompt,
        },
        {
            "id": "sting1",
            "label": "Sting 1 (trigger impact)",
            "output": STING1_OUTPUT,
            "loop": False,
            "prompt_influence": 0.9,
            "output_format": "mp3_44100_192",
            "prompt": (
                "dramatic cinematic impact sting, single deep sub bass hit, "
                "sharp attack fast decay, tension spike, heart-pounding, "
                "no melody, no loop, exactly 2 seconds"
            ),
        },
        {
            "id": "sting2",
            "label": "Sting 2 (trigger impact)",
            "output": STING2_OUTPUT,
            "loop": False,
            "prompt_influence": 0.9,
            "output_format": "mp3_44100_192",
            "prompt": (
                "cinematic whoosh impact, rising tension sweep into hard bass hit, "
                "thriller moment punctuation, sharp attack, no melody, no loop, exactly 2 seconds"
            ),
        },
        {
            "id": "sting3",
            "label": "Sting 3 (trigger impact)",
            "output": STING3_OUTPUT,
            "loop": False,
            "prompt_influence": 0.9,
            "output_format": "mp3_44100_192",
            "prompt": (
                "deep orchestral stab, low brass hit with sub bass, "
                "single dramatic beat, no decay tail, punchy, no melody, no loop, exactly 2 seconds"
            ),
        },
        {
            "id": "hook_sting",
            "label": "Hook intro SFX",
            "output": HOOK_STING_OUTPUT,
            "loop": False,
            "prompt_influence": 0.85,
            "output_format": "mp3_44100_192",
            "prompt": (
                "single cinematic boom hit, deep low-frequency sub bass impact, "
                "epic movie trailer opener, sharp attack fast decay, "
                "reverberant tail, no melody, no loop, exactly 3 seconds"
            ),
        },
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _kie_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _request_with_retry(method: str, url: str, *, headers: dict,
                         json_body: dict | None = None,
                         stream: bool = False,
                         label: str = "") -> requests.Response:
    """HTTP request with 3 retries and exponential backoff."""
    for attempt, wait in enumerate(RETRY_BACKOFF, start=1):
        try:
            resp = requests.request(
                method, url,
                headers=headers,
                json=json_body,
                stream=stream,
                timeout=60,
            )
            if resp.status_code < 500:
                return resp
            logger.warning("%s HTTP %s (attempt %d/%d) — retrying in %ds",
                           label, resp.status_code, attempt, MAX_RETRIES, wait)
        except requests.RequestException as exc:
            logger.warning("%s request error (attempt %d/%d): %s — retrying in %ds",
                           label, attempt, MAX_RETRIES, exc, wait)
        time.sleep(wait)

    # Final attempt
    try:
        return requests.request(
            method, url,
            headers=headers,
            json=json_body,
            stream=stream,
            timeout=60,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"{label} — all {MAX_RETRIES + 1} attempts failed: {exc}"
        ) from exc


def _submit_music_task(track: dict, api_key: str) -> str:
    """Submit a BGM generation task to Kie.ai ElevenLabs. Returns task_id."""
    body = {
        "model": "elevenlabs/sound-effect-v2",
        "callBackUrl": "",
        "input": {
            "text": track["prompt"],
            "loop": track.get("loop", False),
            "prompt_influence": track.get("prompt_influence", 0.7),
            "output_format": track.get("output_format", "mp3_44100_128"),
        },
    }

    logger.info("Submitting %s to Kie.ai ElevenLabs", track["label"])
    resp = _request_with_retry(
        "POST", KIE_CREATE_URL,
        headers=_kie_headers(api_key),
        json_body=body,
        label=f"submit[{track['id']}]",
    )

    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"[{track['id']}] Kie.ai submit failed — HTTP {resp.status_code}: {resp.text}"
        )

    data = resp.json()
    data_payload = data.get("data") or {}
    task_id = (
        data_payload.get("taskId")
        or data_payload.get("task_id")
        or data.get("taskId")
        or data.get("task_id")
    )
    if not task_id:
        raise RuntimeError(
            f"[{track['id']}] Could not find taskId in response: {data}"
        )

    logger.info("%s — task_id=%s", track["label"], task_id)
    return task_id


def _poll_music_task(task_id: str, track: dict, api_key: str) -> str:
    """Poll until the music task completes. Returns audio download URL."""
    url = KIE_POLL_URL.format(task_id=task_id)
    deadline = time.time() + TASK_TIMEOUT_SEC
    poll_count = 0

    with tqdm(desc=f"Polling {track['label']}", unit="poll", leave=True) as bar:
        while time.time() < deadline:
            time.sleep(POLL_INTERVAL_SEC)
            poll_count += 1
            bar.update(1)

            resp = _request_with_retry(
                "GET", url,
                headers=_kie_headers(api_key),
                label=f"poll[{track['id']}]",
            )

            if resp.status_code != 200:
                logger.warning("[%s] Poll HTTP %s — will retry", track["id"], resp.status_code)
                continue

            data = resp.json()
            payload = data.get("data", data)
            # Kie.ai jobs uses "state": waiting | queuing | generating | success | fail
            status = (payload.get("state") or payload.get("status") or "").lower()
            bar.set_postfix(status=status)

            logger.debug("[%s] poll #%d — state=%s", track["id"], poll_count, status)

            if status == "success":
                # resultJson is a JSON string containing {"resultUrls": ["https://..."]}
                result_json_str = payload.get("resultJson") or "{}"
                try:
                    result_data = json.loads(result_json_str)
                except json.JSONDecodeError:
                    result_data = {}
                result_urls = result_data.get("resultUrls") or []
                audio_url = result_urls[0] if result_urls else None
                if not audio_url:
                    raise RuntimeError(
                        f"[{track['id']}] Task completed but no audio URL found: {payload}"
                    )
                logger.info("[%s] Task complete — url=%s", track["id"], audio_url)
                return audio_url

            if status in ("fail", "failed", "error"):
                reason = payload.get("failMsg") or payload.get("error") or str(payload)
                raise RuntimeError(f"[{track['id']}] Kie.ai task failed: {reason}")

    raise TimeoutError(
        f"[{track['id']}] Task {task_id} did not complete within {TASK_TIMEOUT_SEC}s"
    )


def _download_audio(url: str, dest: Path, track_id: str) -> None:
    """Stream-download an audio file and verify non-zero filesize."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    for attempt, wait in enumerate(RETRY_BACKOFF + [0], start=1):
        try:
            logger.info("[%s] Downloading %s → %s", track_id, url, dest)
            resp = requests.get(url, stream=True, timeout=120)
            resp.raise_for_status()

            total = int(resp.headers.get("content-length", 0))
            with open(dest, "wb") as fh, tqdm(
                total=total or None,
                unit="B",
                unit_scale=True,
                desc=dest.name,
                leave=False,
            ) as bar:
                for chunk in resp.iter_content(chunk_size=8192):
                    fh.write(chunk)
                    bar.update(len(chunk))

            size = dest.stat().st_size
            if size == 0:
                raise RuntimeError(f"[{track_id}] Downloaded audio file is empty: {dest}")

            logger.info("[%s] Download complete — %d bytes → %s", track_id, size, dest)
            return

        except Exception as exc:
            logger.warning("[%s] Download attempt %d failed: %s", track_id, attempt, exc)
            if dest.exists():
                dest.unlink()
            if wait:
                time.sleep(wait)

    raise RuntimeError(f"[{track_id}] All download attempts failed for {url}")


# ---------------------------------------------------------------------------
# Audio validation
# ---------------------------------------------------------------------------

def _validate_audio(path: Path, track_id: str) -> None:
    """Verify audio file is valid and has sufficient duration using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                str(path),
            ],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")

        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
        if duration < 0.5:
            raise RuntimeError(f"Audio duration too short: {duration:.2f}s")

        logger.info("[%s] Audio valid — duration=%.2fs", track_id, duration)

    except FileNotFoundError:
        logger.warning("[%s] ffprobe not found — skipping audio validation", track_id)
    except RuntimeError:
        raise
    except Exception as exc:
        logger.warning("[%s] Audio validation error (non-fatal): %s", track_id, exc)


# ---------------------------------------------------------------------------
# Per-track worker (submit → poll → download)
# ---------------------------------------------------------------------------

def _process_track(track: dict, api_key: str) -> tuple[str, Path]:
    """Full lifecycle for one BGM track. Returns (track_id, local_path)."""
    dest: Path = track["output"]

    # Crash recovery — skip if already present
    if dest.exists() and dest.stat().st_size > 0:
        logger.info("[%s] Already exists — skipping", track["id"])
        return track["id"], dest

    task_id = _submit_music_task(track, api_key)
    audio_url = _poll_music_task(task_id, track, api_key)
    _download_audio(audio_url, dest, track["id"])
    _validate_audio(dest, track["id"])

    return track["id"], dest


# ---------------------------------------------------------------------------
# Public stage entrypoint
# ---------------------------------------------------------------------------

def run_stage4() -> dict:
    """
    Run Stage 4 — Background Music Generation.

    Returns:
        {
            "success": bool,
            "output_path": dict[str, str],   # track_id → abs file path
            "duration_sec": float,
            "error": str | None,
        }
    """
    start = time.time()
    load_dotenv(ROOT / ".env")

    api_key = os.getenv("KIE_API_KEY", "")
    if not api_key:
        return {
            "success": False,
            "output_path": {},
            "duration_sec": 0.0,
            "error": "KIE_API_KEY not set in environment",
        }

    tracks = _build_tracks()
    logger.info("Starting BGM generation for %d tracks", len(tracks))
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)

    results: dict[str, str] = {}
    errors: list[str] = []

    # Submit and poll all tracks in parallel
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(_process_track, track, api_key): track["id"]
            for track in tracks
        }

        with tqdm(total=len(futures), desc="BGM tracks", unit="track") as bar:
            for future in as_completed(futures):
                track_id = futures[future]
                try:
                    tid, path = future.result()
                    results[tid] = str(path)
                    logger.info("[%s] Done — %s", tid, path)
                except Exception as exc:
                    errors.append(f"{track_id}: {exc}")
                    logger.error("[%s] Failed: %s", track_id, exc)
                finally:
                    bar.update(1)

    duration = time.time() - start

    if errors:
        error_msg = f"{len(errors)} track(s) failed: " + "; ".join(errors)
        logger.error("Stage 4 completed with errors in %.1fs — %s", duration, error_msg)
        return {
            "success": False,
            "output_path": results,
            "duration_sec": round(duration, 2),
            "error": error_msg,
        }

    logger.info("Stage 4 complete in %.1fs — %d tracks downloaded", duration, len(results))
    return {
        "success": True,
        "output_path": results,
        "duration_sec": round(duration, 2),
        "error": None,
    }


# ---------------------------------------------------------------------------
# Standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = run_stage4()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["success"] else 1)
