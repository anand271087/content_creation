"""
Stage 2 — B-Roll Generation (Kie.ai: nano-banana-2 → Kling I2V)
Two-step pipeline:
  1. Generate a reference image via nano-banana-2 (Google Imagen on Kie.ai)
  2. Animate it into a 5s video via Kling image-to-video

Falls back to Kling text-to-video if image generation fails.
Set BROLL_MODEL=kling-2.6/text-to-video to force T2V mode.
"""

import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from dotenv import load_dotenv
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
SCRIPT_DATA_PATH = ROOT / "assets" / "script_data.json"
BROLL_DIR = ROOT / "assets" / "broll"
LOG_FILE = ROOT / "logs" / "pipeline.log"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("stage2_broll")
logger.setLevel(logging.DEBUG)

_fmt = logging.Formatter("%(asctime)s [stage2_broll] %(levelname)s %(message)s")

_fh = logging.FileHandler(LOG_FILE)
_fh.setFormatter(_fmt)
logger.addHandler(_fh)

_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(_fmt)
logger.addHandler(_sh)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
KIE_GENERATE_URL = "https://api.kie.ai/api/v1/jobs/createTask"
KIE_POLL_URL = "https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}"

POLL_INTERVAL_SEC = 15
TASK_TIMEOUT_SEC = 600       # 10 minutes per clip
IMAGE_TIMEOUT_SEC = 180      # 3 minutes for image generation
MAX_WORKERS = 5
MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]   # seconds

# Model names
IMAGE_MODEL = "nano-banana-2"         # Google Imagen via Kie.ai
I2V_MODEL = "kling-2.6/image-to-video"
T2V_MODEL = "kling-2.6/text-to-video"
SEEDANCE_MODEL = "bytedance/seedance-1.5-pro"  # Fallback when Kling is down

# ---------------------------------------------------------------------------
# Prompt enrichment constants
# ---------------------------------------------------------------------------
NEGATIVE_PROMPT = (
    "text, watermark, logo, blur, low quality, distorted faces, "
    "stock footage aesthetic, green screen, cartoon, animation, "
    "overexposed, washed out, talking head, subtitles, captions, "
    "title cards, UI elements, "
    "Chinese text, Chinese characters, Japanese text, Japanese kanji, "
    "Korean text, Korean hangul, Arabic script, Hindi script, Devanagari, "
    "any non-Latin script, any non-English text, foreign language text, "
    "non-English characters, Asian characters, CJK characters, "
    "gibberish text, unreadable text, random letters, nonsense writing, "
    "signs, banners, billboards, labels, annotations, writing on walls, "
    "writing on screen, writing on objects, any visible text whatsoever"
)

CINEMATIC_SUFFIX = (
    ", cinematic lighting, shallow depth of field, 8K hyperrealistic, "
    "shot on Sony A7IV, smooth camera motion, professional color grade, "
    "no text overlays, no watermarks, absolutely no subtitles, "
    "absolutely no foreign language text, no Chinese no Japanese no Korean no Arabic, "
    "English only if any text appears"
)

SECTION_STYLE_MAP = {
    "hook":          "extreme close-up, dramatic tension, fast cut energy, dark atmospheric",
    "context":       "medium shot, establishing environment, neutral cinematic",
    "trigger_1":     "extreme close-up, dramatic tension, red accent lighting",
    "body_1":        "medium shot, informational, clean blue-white light, professional",
    "trigger_2":     "tight shot, high contrast, tension spike, stark shadows",
    "body_2":        "medium close-up, personal and relatable, warm neutral tones",
    "trigger_3":     "over-shoulder POV, real-world proof, specific detail visible",
    "bridge":        "wide to medium pull, transitional mood, shifting from dark to warm",
    "grand_takeaway": "clean minimal composition, soft warm light, deliberate stillness",
    "emotion_save":  "warm golden light, approachable environment, hopeful atmosphere",
}

# Duration in seconds by section type (longer for content-heavy sections)
DURATION_MAP = {
    "hook":          "5",
    "context":       "5",
    "trigger_1":     "5",
    "body_1":        "5",
    "trigger_2":     "5",
    "body_2":        "5",
    "trigger_3":     "5",
    "bridge":        "5",
    "grand_takeaway": "5",
    "emotion_save":  "5",
}

MANIFEST_PATH = BROLL_DIR / "manifest.json"


# ---------------------------------------------------------------------------
# Encoder helpers
# ---------------------------------------------------------------------------

def _h264_encoder_flags() -> list[str]:
    """Return ffmpeg video encoder flags. Uses h264_videotoolbox on macOS, libx264 elsewhere."""
    if platform.system() == "Darwin":
        return ["-c:v", "h264_videotoolbox", "-profile:v", "baseline", "-level:v", "3.1", "-q:v", "65"]
    return ["-c:v", "libx264", "-profile:v", "baseline", "-level", "3.1", "-preset", "fast", "-crf", "23"]


def _reencode_baseline(path: Path, section_id: str) -> None:
    """Re-encode broll clip to H264 Baseline level 3.1, yuv420p — required for Chromium/Remotion.
    Tries h264_videotoolbox on macOS first, falls back to libx264 if it fails."""
    tmp = path.with_suffix(".tmp.mp4")
    libx264_flags = ["-c:v", "libx264", "-profile:v", "baseline", "-level", "3.1", "-preset", "fast", "-crf", "23"]

    def _run_encode(encoder_flags: list[str], label: str) -> bool:
        cmd = [
            "ffmpeg", "-i", str(path),
            *encoder_flags,
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-y", str(tmp),
        ]
        logger.info("[%s] Re-encoding to H264 baseline (%s)", section_id, label)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            if tmp.exists():
                tmp.unlink()
            logger.warning("[%s] %s encode failed: %s", section_id, label, proc.stderr[-500:])
            return False
        return True

    success = False
    if platform.system() == "Darwin":
        success = _run_encode(
            ["-c:v", "h264_videotoolbox", "-profile:v", "baseline", "-level:v", "3.1", "-q:v", "65"],
            "h264_videotoolbox"
        )
    if not success:
        success = _run_encode(libx264_flags, "libx264")

    if not success:
        raise RuntimeError(f"[{section_id}] re-encode failed with both h264_videotoolbox and libx264")
    shutil.move(str(tmp), str(path))
    logger.info("[%s] Re-encoded to H264 baseline — %d bytes", section_id, path.stat().st_size)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enrich_prompt(section: dict) -> str:
    """
    Build the final Kling prompt for a section.
    Prepends a short spoken-context line so Kling generates footage
    that visually matches what Anand is saying at that moment.
    """
    base = section.get("broll_prompt", "")
    spoken = section.get("spoken", "").strip()
    style = SECTION_STYLE_MAP.get(section.get("id", ""), "")

    # Take first 80 chars of spoken text as scene context — enough for Kling
    # to understand the subject without overloading the prompt
    context = f"Scene depicts: {spoken[:80]}. " if spoken else ""

    if style:
        enriched = f"{context}{base}, {style}{CINEMATIC_SUFFIX}"
    else:
        enriched = f"{context}{base}{CINEMATIC_SUFFIX}"

    logger.debug("[%s] Enriched prompt: %s", section.get("id"), enriched)
    return enriched


def _enrich_image_prompt(section: dict) -> str:
    """
    Build a clean visual prompt for nano-banana-2 (Google Imagen).
    Strips cinematic camera specs — Imagen responds better to pure visual descriptions.
    """
    base = section.get("broll_prompt", "")
    spoken = section.get("spoken", "").strip()
    style = SECTION_STYLE_MAP.get(section.get("id", ""), "")

    # Remove camera/lens jargon that confuses image models
    # but keep mood, color, and subject
    context = f"{spoken[:60]}. " if spoken else ""
    no_text = (
        "absolutely no text of any kind, no Chinese characters, no Japanese characters, "
        "no Korean characters, no Arabic script, no foreign language text, "
        "no writing, no letters, no words, no signs, no watermarks, no subtitles, "
        "photorealistic, highly detailed"
    )
    if style:
        return f"{context}{base}, {style}, {no_text}, 9:16 vertical aspect ratio"
    return f"{context}{base}, {no_text}, 9:16 vertical aspect ratio"


def _enrich_motion_prompt(section: dict) -> str:
    """
    Minimal motion prompt for Kling I2V — describe the movement only.
    The image already sets the visual; we just need a gentle camera move.
    """
    section_id = section.get("id", "")
    spoken = section.get("spoken", "").strip()[:60]

    if section_id.startswith("trigger"):
        return f"slow dramatic zoom in, cinematic tension, {spoken}"
    if section_id in ("grand_takeaway", "emotion_save"):
        return f"gentle slow push forward, warm hopeful atmosphere, {spoken}"
    if section_id == "bridge":
        return f"smooth slow pan, transitional mood, {spoken}"
    return f"subtle Ken Burns zoom, smooth camera move, cinematic, {spoken}"


def _kie_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _request_with_retry(method: str, url: str, *, headers: dict, json_body: dict | None = None,
                         stream: bool = False, label: str = "") -> requests.Response:
    """HTTP request with 3 retries and exponential backoff."""
    last_exc: Exception | None = None
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
                # 4xx are caller errors — don't retry
                return resp
            logger.warning("%s HTTP %s (attempt %d/%d) — retrying in %ds",
                           label, resp.status_code, attempt, MAX_RETRIES, wait)
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("%s request error (attempt %d/%d): %s — retrying in %ds",
                           label, attempt, MAX_RETRIES, exc, wait)
        time.sleep(wait)

    # Final attempt (no sleep after)
    try:
        return requests.request(
            method, url,
            headers=headers,
            json=json_body,
            stream=stream,
            timeout=60,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"{label} — all {MAX_RETRIES + 1} attempts failed: {exc}") from exc


def _poll_task_for_image(task_id: str, section_id: str, api_key: str,
                          timeout: int = IMAGE_TIMEOUT_SEC) -> str:
    """
    Poll a Kie.ai jobs task until success. Returns the first URL from resultUrls.
    Used for both image and video tasks.
    """
    url = KIE_POLL_URL.format(task_id=task_id)
    deadline = time.time() + timeout

    while time.time() < deadline:
        time.sleep(POLL_INTERVAL_SEC)

        resp = _request_with_retry(
            "GET", url,
            headers=_kie_headers(api_key),
            label=f"poll_img[{section_id}]",
        )

        if resp.status_code != 200:
            logger.warning("[%s] Image poll HTTP %s — will retry", section_id, resp.status_code)
            continue

        data = resp.json()
        payload = data.get("data") or data
        status = (payload.get("state") or payload.get("status") or "").lower()
        logger.debug("[%s] image poll state=%s", section_id, status)

        if status == "success":
            result_json_str = payload.get("resultJson")
            if result_json_str:
                try:
                    result = json.loads(result_json_str)
                    urls = result.get("resultUrls") or []
                    if urls:
                        logger.info("[%s] Image ready — url=%s", section_id, urls[0])
                        return urls[0]
                except (json.JSONDecodeError, TypeError):
                    pass
            raise RuntimeError(f"[{section_id}] Image task succeeded but no URL in resultJson: {payload}")

        if status in ("fail", "failed", "error"):
            raise RuntimeError(f"[{section_id}] Kie.ai image task failed — payload: {payload}")

    raise TimeoutError(f"[{section_id}] Image task {task_id} timed out after {timeout}s")


def _submit_image_task(section: dict, api_key: str) -> str:
    """Submit nano-banana-2 image generation job. Returns task_id."""
    section_id = section["id"]
    prompt = _enrich_image_prompt(section)

    body = {
        "model": IMAGE_MODEL,
        "callBackUrl": "",
        "input": {
            "prompt": prompt,
            "image_input": [],
            "aspect_ratio": "9:16",
            "resolution": "1K",
            "output_format": "png",
        },
    }

    logger.info("[%s] Submitting nano-banana-2 image task", section_id)
    resp = _request_with_retry(
        "POST", KIE_GENERATE_URL,
        headers=_kie_headers(api_key),
        json_body=body,
        label=f"submit_img[{section_id}]",
    )

    if resp.status_code != 200:
        raise RuntimeError(
            f"[{section_id}] nano-banana-2 submit failed — HTTP {resp.status_code}: {resp.text}"
        )

    data = resp.json()
    data_payload = data.get("data") or {}
    task_id = data_payload.get("taskId") or data_payload.get("task_id")
    if not task_id:
        raise RuntimeError(f"[{section_id}] No taskId in nano-banana-2 response: {data}")

    logger.info("[%s] nano-banana-2 task_id=%s", section_id, task_id)
    return task_id


def _submit_i2v_task(section: dict, image_url: str, api_key: str) -> str:
    """Submit Kling image-to-video task. Returns task_id."""
    section_id = section["id"]
    motion_prompt = _enrich_motion_prompt(section)
    duration = DURATION_MAP.get(section_id, "5")

    body = {
        "model": I2V_MODEL,
        "callBackUrl": "",
        "input": {
            "prompt": motion_prompt,
            "negative_prompt": NEGATIVE_PROMPT,
            "image_url": image_url,
            "duration": duration,
            "aspect_ratio": "9:16",
            "sound": False,
        },
    }

    logger.info("[%s] Submitting Kling I2V task (image_url=%s)", section_id, image_url[:80])
    resp = _request_with_retry(
        "POST", KIE_GENERATE_URL,
        headers=_kie_headers(api_key),
        json_body=body,
        label=f"submit_i2v[{section_id}]",
    )

    if resp.status_code != 200:
        raise RuntimeError(
            f"[{section_id}] Kling I2V submit failed — HTTP {resp.status_code}: {resp.text}"
        )

    data = resp.json()
    data_payload = data.get("data") or {}
    task_id = data_payload.get("taskId") or data_payload.get("task_id")
    if not task_id:
        raise RuntimeError(f"[{section_id}] No taskId in Kling I2V response: {data}")

    logger.info("[%s] Kling I2V task_id=%s", section_id, task_id)
    return task_id


def _submit_seedance_task(section: dict, api_key: str) -> str:
    """Submit to Seedance 1.5 Pro (ByteDance via Kie.ai). Returns task_id."""
    section_id = section["id"]
    prompt = _enrich_prompt(section)
    # Seedance duration options: 4, 8, 12 — map our 5s clips to 8s (closest)
    body = {
        "model": SEEDANCE_MODEL,
        "callBackUrl": "",
        "input": {
            "prompt": prompt,
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "duration": "8",
            "generate_audio": False,
        },
    }
    logger.info("[%s] Submitting to Seedance 1.5 Pro (Kling fallback)", section_id)
    resp = _request_with_retry(
        "POST", KIE_GENERATE_URL,
        headers=_kie_headers(api_key),
        json_body=body,
        label=f"seedance[{section_id}]",
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"[{section_id}] Seedance submit failed — HTTP {resp.status_code}: {resp.text}"
        )
    data = resp.json()
    data_payload = data.get("data") or {}
    task_id = data_payload.get("taskId") or data_payload.get("task_id")
    if not task_id:
        raise RuntimeError(f"[{section_id}] No taskId in Seedance response: {data}")
    logger.info("[%s] Seedance task_id=%s", section_id, task_id)
    return task_id


def _submit_seedance_i2v_task(section: dict, image_url: str, api_key: str) -> str:
    """Submit nano-banana-2 image to Seedance 1.5 Pro for I2V animation. Returns task_id."""
    section_id = section["id"]
    prompt = _enrich_motion_prompt(section)

    body = {
        "model": SEEDANCE_MODEL,
        "callBackUrl": "",
        "input": {
            "prompt": prompt,
            "input_urls": [image_url],
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "duration": "8",
            "generate_audio": False,
        },
    }

    logger.info("[%s] Submitting Seedance I2V task (image_url=%s)", section_id, image_url[:80])
    resp = _request_with_retry(
        "POST", KIE_GENERATE_URL,
        headers=_kie_headers(api_key),
        json_body=body,
        label=f"seedance_i2v[{section_id}]",
    )

    if resp.status_code != 200:
        raise RuntimeError(
            f"[{section_id}] Seedance I2V submit failed — HTTP {resp.status_code}: {resp.text}"
        )

    data = resp.json()
    data_payload = data.get("data") or {}
    task_id = data_payload.get("taskId") or data_payload.get("task_id")
    if not task_id:
        raise RuntimeError(f"[{section_id}] No taskId in Seedance I2V response: {data}")

    logger.info("[%s] Seedance I2V task_id=%s", section_id, task_id)
    return task_id


def _submit_broll_task(section: dict, api_key: str) -> str:
    """Submit a single broll_prompt to Kie.ai. Supports Kling and Seedance models."""
    section_id = section["id"]
    prompt = _enrich_prompt(section)
    model_name = os.getenv("BROLL_MODEL", T2V_MODEL)
    duration = DURATION_MAP.get(section_id, "5")

    is_seedance = "seedance" in model_name

    if is_seedance:
        # Seedance API — duration must be string "4"/"8"/"12", no negative_prompt/sound
        input_body = {
            "prompt": prompt,
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "duration": "8",
            "generate_audio": False,
        }
    else:
        # Kling API
        input_body = {
            "prompt": prompt,
            "negative_prompt": NEGATIVE_PROMPT,
            "sound": False,
            "aspect_ratio": "9:16",
            "duration": duration,
        }

    body = {
        "model": model_name,
        "callBackUrl": "",
        "input": input_body,
    }

    logger.info("Submitting broll task for section '%s'", section_id)
    resp = _request_with_retry(
        "POST", KIE_GENERATE_URL,
        headers=_kie_headers(api_key),
        json_body=body,
        label=f"submit[{section_id}]",
    )

    if resp.status_code != 200:
        raise RuntimeError(
            f"[{section_id}] Kie.ai submit failed — HTTP {resp.status_code}: {resp.text}"
        )

    data = resp.json()
    logger.debug("[%s] Submit response: %s", section_id, data)
    data_payload = data.get("data") or {}
    task_id = data_payload.get("taskId") or data_payload.get("task_id")
    if not task_id:
        raise RuntimeError(
            f"[{section_id}] Could not find taskId in response: {data}"
        )

    logger.info("Section '%s' — task_id=%s", section_id, task_id)
    return task_id


def _poll_broll_task(task_id: str, section_id: str, api_key: str) -> str:
    """Poll until status == 'completed'. Returns video URL."""
    url = KIE_POLL_URL.format(task_id=task_id)
    deadline = time.time() + TASK_TIMEOUT_SEC

    while time.time() < deadline:
        time.sleep(POLL_INTERVAL_SEC)

        resp = _request_with_retry(
            "GET", url,
            headers=_kie_headers(api_key),
            label=f"poll[{section_id}]",
        )

        if resp.status_code != 200:
            logger.warning("[%s] Poll HTTP %s — will retry", section_id, resp.status_code)
            continue

        data = resp.json()
        payload = data.get("data") or data
        # Jobs API state values: waiting, queuing, generating, success, fail
        status = (payload.get("state") or payload.get("status") or "").lower()

        logger.debug("[%s] poll state=%s", section_id, status)

        if status == "success":
            # Jobs API returns video URL inside resultJson (a JSON string)
            video_url = None
            result_json_str = payload.get("resultJson")
            if result_json_str:
                try:
                    result = json.loads(result_json_str)
                    # Kling uses resultUrls[0]; fallback to video_url key
                    urls = result.get("resultUrls") or []
                    video_url = urls[0] if urls else None
                    if not video_url:
                        video_url = result.get("video_url") or result.get("videoUrl")
                except (json.JSONDecodeError, TypeError):
                    pass
            # Fallback: direct fields
            if not video_url:
                video_url = payload.get("video_url") or payload.get("videoUrl")
            if not video_url:
                raise RuntimeError(
                    f"[{section_id}] Task completed but no video URL found: {payload}"
                )
            logger.info("[%s] Task completed — url=%s", section_id, video_url)
            return video_url

        if status in ("fail", "failed", "error"):
            raise RuntimeError(
                f"[{section_id}] Kie.ai task failed — payload: {payload}"
            )

    raise TimeoutError(
        f"[{section_id}] Task {task_id} did not complete within {TASK_TIMEOUT_SEC}s"
    )


def _download_video(url: str, dest: Path, section_id: str) -> None:
    """Stream-download a video file and verify non-zero filesize."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    for attempt, wait in enumerate(RETRY_BACKOFF + [0], start=1):
        try:
            logger.info("[%s] Downloading %s → %s", section_id, url, dest)
            resp = requests.get(url, stream=True, timeout=120)
            resp.raise_for_status()

            total = int(resp.headers.get("content-length", 0))
            with open(dest, "wb") as fh, tqdm(
                total=total or None,
                unit="B",
                unit_scale=True,
                desc=f"broll/{section_id}",
                leave=False,
            ) as bar:
                for chunk in resp.iter_content(chunk_size=8192):
                    fh.write(chunk)
                    bar.update(len(chunk))

            size = dest.stat().st_size
            if size == 0:
                raise RuntimeError(f"[{section_id}] Downloaded file is empty: {dest}")

            logger.info("[%s] Download complete — %d bytes", section_id, size)
            return

        except Exception as exc:
            logger.warning("[%s] Download attempt %d failed: %s", section_id, attempt, exc)
            if dest.exists():
                dest.unlink()
            if wait:
                time.sleep(wait)

    raise RuntimeError(f"[{section_id}] All download attempts failed for {url}")


# ---------------------------------------------------------------------------
# Per-section worker (submit → poll → download)
# ---------------------------------------------------------------------------

def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_manifest_entry(section_id: str, task_id: str, video_url: str, dest: Path) -> None:
    manifest = _load_manifest()
    manifest[section_id] = {"task_id": task_id, "url": video_url, "path": str(dest)}
    BROLL_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))


def _process_section(section: dict, api_key: str, force: bool = False) -> tuple[str, Path]:
    """
    Full lifecycle for one section. Returns (section_id, local_path).

    Pipeline (two-step when USE_I2V is enabled):
      1. Generate reference image via nano-banana-2
      2. Animate image → video via Kling I2V
      Fallback: Kling T2V if either step fails
    """
    section_id = section["id"]
    dest = BROLL_DIR / f"{section_id}.mp4"

    # Diagram sections don't need a Kling clip — handled by generate_diagrams.py
    if section.get("broll_type") == "diagram":
        logger.info("[%s] broll_type=diagram — skipping Kling generation", section_id)
        return section_id, dest  # dest won't exist; Remotion uses the PNG instead

    # Text card sections — handled by scripts/generate_text_cards.py (Excalidraw card → Kling I2V)
    if section.get("broll_type") == "text_card":
        if dest.exists() and dest.stat().st_size > 10000:
            logger.info("[%s] broll_type=text_card — already generated (%dKB)",
                        section_id, dest.stat().st_size // 1024)
            return section_id, dest
        logger.info("[%s] broll_type=text_card — will be generated by generate_text_cards.py", section_id)
        return section_id, dest

    # Screen sections are handled by scripts/screen_broll.mjs (Playwright screenshot → Ken Burns MP4)
    if section.get("broll_type") == "screen":
        if dest.exists() and dest.stat().st_size > 10000:
            logger.info("[%s] broll_type=screen — screenshot broll already captured (%dKB)",
                        section_id, dest.stat().st_size // 1024)
            return section_id, dest
        logger.info("[%s] broll_type=screen — will be captured by screen_broll.mjs (run Stage 2c)", section_id)
        return section_id, dest  # screen_broll.mjs runs before stage2 in pipeline.py

    # Terminal sections are handled by scripts/run_terminal_demo.mjs (Playwright terminal renderer)
    if section.get("broll_type") == "terminal":
        if dest.exists() and dest.stat().st_size > 10000:
            logger.info("[%s] broll_type=terminal — terminal broll already captured (%dKB)",
                        section_id, dest.stat().st_size // 1024)
            return section_id, dest
        logger.info("[%s] broll_type=terminal — will be captured by run_terminal_demo.mjs (Stage 2c.5)", section_id)
        return section_id, dest

    # Skip if already downloaded (crash recovery) — unless force=True
    if dest.exists() and dest.stat().st_size > 0 and not force:
        logger.info("[%s] Already exists — skipping", section_id)
        return section_id, dest

    if dest.exists():
        dest.unlink()

    broll_model = os.getenv("BROLL_MODEL", T2V_MODEL)
    use_seedance = "seedance" in broll_model
    force_t2v = broll_model.endswith("text-to-video")

    video_url: str | None = None
    task_id: str = ""

    if use_seedance:
        # Pipeline: nano-banana-2 (T2I) → Seedance I2V
        try:
            img_task_id = _submit_image_task(section, api_key)
            image_url = _poll_task_for_image(img_task_id, section_id, api_key, IMAGE_TIMEOUT_SEC)
            logger.info("[%s] Image generated — animating with Seedance I2V", section_id)

            i2v_task_id = _submit_seedance_i2v_task(section, image_url, api_key)
            video_url = _poll_broll_task(i2v_task_id, section_id, api_key)
            task_id = i2v_task_id
            logger.info("[%s] Seedance I2V complete", section_id)

        except Exception as exc:
            logger.warning("[%s] Seedance I2V failed (%s) — falling back to Seedance T2V", section_id, exc)
            video_url = None

        if not video_url:
            # Seedance T2V fallback
            logger.info("[%s] Using Seedance T2V fallback", section_id)
            task_id = _submit_seedance_task(section, api_key)
            video_url = _poll_broll_task(task_id, section_id, api_key)

    else:
        if not force_t2v:
            # Default pipeline: nano-banana-2 → Kling I2V
            try:
                img_task_id = _submit_image_task(section, api_key)
                image_url = _poll_task_for_image(img_task_id, section_id, api_key, IMAGE_TIMEOUT_SEC)
                logger.info("[%s] Image generated — proceeding to Kling I2V", section_id)

                i2v_task_id = _submit_i2v_task(section, image_url, api_key)
                video_url = _poll_task_for_image(i2v_task_id, section_id, api_key, TASK_TIMEOUT_SEC)
                task_id = i2v_task_id
                logger.info("[%s] Kling I2V complete", section_id)

            except Exception as exc:
                logger.warning("[%s] Kling I2V failed (%s) — falling back to T2V", section_id, exc)
                video_url = None

        if not video_url:
            # Kling T2V fallback
            logger.info("[%s] Using Kling T2V fallback", section_id)
            try:
                task_id = _submit_broll_task(section, api_key)
                video_url = _poll_broll_task(task_id, section_id, api_key)
            except Exception as exc:
                logger.warning("[%s] Kling T2V failed (%s) — trying Seedance fallback", section_id, exc)
                video_url = None

        if not video_url:
            # Last resort: Seedance T2V
            logger.info("[%s] Using Seedance 1.5 Pro as last resort", section_id)
            task_id = _submit_seedance_task(section, api_key)
            video_url = _poll_broll_task(task_id, section_id, api_key)

    _download_video(video_url, dest, section_id)
    _reencode_baseline(dest, section_id)
    _save_manifest_entry(section_id, task_id, video_url, dest)

    return section_id, dest


# ---------------------------------------------------------------------------
# Public stage entrypoint
# ---------------------------------------------------------------------------

def run_stage2(force: bool = False) -> dict:
    """
    Run Stage 2 — B-Roll Generation.

    Returns:
        {
            "success": bool,
            "output_path": dict[str, str],   # section_id → abs file path
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

    # Load script data
    if not SCRIPT_DATA_PATH.exists():
        return {
            "success": False,
            "output_path": {},
            "duration_sec": 0.0,
            "error": f"script_data.json not found at {SCRIPT_DATA_PATH}",
        }

    with open(SCRIPT_DATA_PATH) as fh:
        script_data = json.load(fh)

    sections = script_data.get("sections", [])
    if not sections:
        return {
            "success": False,
            "output_path": {},
            "duration_sec": 0.0,
            "error": "No sections found in script_data.json",
        }

    logger.info("Starting B-Roll generation for %d sections", len(sections))
    BROLL_DIR.mkdir(parents=True, exist_ok=True)

    results: dict[str, str] = {}
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(_process_section, section, api_key, force): section["id"]
            for section in sections
        }

        with tqdm(total=len(futures), desc="B-Roll sections", unit="clip") as bar:
            for future in as_completed(futures):
                section_id = futures[future]
                try:
                    sid, path = future.result()
                    results[sid] = str(path)
                    logger.info("[%s] Done — %s", sid, path)
                except Exception as exc:
                    errors.append(f"{section_id}: {exc}")
                    logger.error("[%s] Failed: %s", section_id, exc)
                finally:
                    bar.update(1)

    duration = time.time() - start

    if errors:
        error_msg = f"{len(errors)} section(s) failed: " + "; ".join(errors)
        logger.error("Stage 2 completed with errors in %.1fs — %s", duration, error_msg)
        return {
            "success": False,
            "output_path": results,
            "duration_sec": round(duration, 2),
            "error": error_msg,
        }

    logger.info("Stage 2 complete in %.1fs — %d clips downloaded", duration, len(results))
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
    result = run_stage2()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["success"] else 1)
