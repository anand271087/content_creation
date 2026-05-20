"""
Regenerate specific broll clips by section ID.
Usage: python3 scripts/regenerate_broll.py body_1 emotion_save

Reads broll_prompt from assets/script_data.json for each section,
deletes the existing file, and re-generates via Kie.ai Runway.
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

ROOT = Path(__file__).parent.parent
SCRIPT_DATA_PATH = ROOT / "assets" / "script_data.json"
BROLL_DIR = ROOT / "assets" / "broll"
LOG_FILE = ROOT / "logs" / "pipeline.log"

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [regen_broll] %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(LOG_FILE)],
)
logger = logging.getLogger("regen_broll")

KIE_GENERATE_URL = "https://api.kie.ai/api/v1/jobs/createTask"
KIE_POLL_URL = "https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}"
POLL_INTERVAL_SEC = 15
TASK_TIMEOUT_SEC = 600


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _submit(section: dict, api_key: str) -> str:
    model = os.getenv("BROLL_MODEL", "kling-2.6/text-to-video")
    # I2V models require an image_url — regen script does T2V only, so downgrade
    if "image-to-video" in model:
        model = "kling-2.6/text-to-video"
    is_seedance = "seedance" in model
    if is_seedance:
        input_body = {
            "prompt": section["broll_prompt"],
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "duration": "8",
            "generate_audio": False,
        }
    else:
        input_body = {
            "prompt": section["broll_prompt"],
            "sound": False,
            "aspect_ratio": "9:16",
            "duration": "5",
        }
    body = {
        "model": model,
        "callBackUrl": "",
        "input": input_body,
    }
    resp = requests.post(KIE_GENERATE_URL, headers=_headers(api_key), json=body, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"Submit failed HTTP {resp.status_code}: {resp.text}")
    data = resp.json()
    dp = data.get("data") or {}
    task_id = dp.get("taskId") or dp.get("task_id")
    if not task_id:
        raise RuntimeError(f"No taskId in response: {data}")
    logger.info("[%s] submitted — task_id=%s", section["id"], task_id)
    return task_id


def _poll(task_id: str, section_id: str, api_key: str) -> str:
    url = KIE_POLL_URL.format(task_id=task_id)
    deadline = time.time() + TASK_TIMEOUT_SEC
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL_SEC)
        resp = requests.get(url, headers=_headers(api_key), timeout=60)
        if resp.status_code != 200:
            logger.warning("[%s] poll HTTP %s", section_id, resp.status_code)
            continue
        payload = resp.json().get("data") or resp.json()
        status = (payload.get("state") or payload.get("status") or "").lower()
        logger.info("[%s] state=%s", section_id, status)
        if status == "success":
            result = json.loads(payload.get("resultJson") or "{}")
            urls = result.get("resultUrls") or []
            url_out = urls[0] if urls else result.get("video_url")
            if not url_out:
                raise RuntimeError(f"[{section_id}] No video URL in resultJson: {payload}")
            return url_out
        if status in ("fail", "failed", "error"):
            raise RuntimeError(f"[{section_id}] Task failed: {payload}")
    raise TimeoutError(f"[{section_id}] Timed out after {TASK_TIMEOUT_SEC}s")


def _download(url: str, dest: Path, section_id: str) -> None:
    logger.info("[%s] downloading → %s", section_id, dest)
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(8192):
            fh.write(chunk)
    size = dest.stat().st_size
    if size == 0:
        raise RuntimeError(f"[{section_id}] Empty file: {dest}")
    logger.info("[%s] done — %d bytes", section_id, size)


def _reencode_baseline(path: Path, section_id: str) -> None:
    """Re-encode to H264 Baseline 3.1 — required for Chromium/Remotion."""
    tmp = path.with_suffix(".tmp.mp4")
    libx264 = ["-c:v", "libx264", "-profile:v", "baseline", "-level", "3.1", "-preset", "fast", "-crf", "23"]

    def _try(flags, label):
        cmd = ["ffmpeg", "-i", str(path), *flags, "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-y", str(tmp)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            if tmp.exists(): tmp.unlink()
            return False
        return True

    success = False
    if platform.system() == "Darwin":
        success = _try(["-c:v", "h264_videotoolbox", "-profile:v", "baseline", "-level:v", "3.1", "-q:v", "65"], "videotoolbox")
    if not success:
        success = _try(libx264, "libx264")
    if not success:
        raise RuntimeError(f"[{section_id}] re-encode failed")
    shutil.move(str(tmp), str(path))
    logger.info("[%s] re-encoded to H264 baseline — %d bytes", section_id, path.stat().st_size)


def regenerate(section_ids: list[str]) -> None:
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("KIE_API_KEY", "")
    if not api_key:
        sys.exit("KIE_API_KEY not set")

    with open(SCRIPT_DATA_PATH) as f:
        script = json.load(f)

    section_map = {s["id"]: s for s in script["sections"]}

    missing = [sid for sid in section_ids if sid not in section_map]
    if missing:
        sys.exit(f"Unknown section IDs: {missing}")

    BROLL_DIR.mkdir(parents=True, exist_ok=True)

    def process(sid: str) -> None:
        section = section_map[sid]
        dest = BROLL_DIR / f"{sid}.mp4"
        # Delete existing so it gets re-generated
        if dest.exists():
            dest.unlink()
            logger.info("[%s] deleted existing file", sid)
        task_id = _submit(section, api_key)
        video_url = _poll(task_id, sid, api_key)
        _download(video_url, dest, sid)
        _reencode_baseline(dest, sid)

    with ThreadPoolExecutor(max_workers=len(section_ids)) as pool:
        futures = {pool.submit(process, sid): sid for sid in section_ids}
        for future in as_completed(futures):
            sid = futures[future]
            try:
                future.result()
                logger.info("[%s] regenerated successfully", sid)
            except Exception as exc:
                logger.error("[%s] FAILED: %s", sid, exc)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/regenerate_broll.py <section_id> [section_id ...]")
        print("Example: python3 scripts/regenerate_broll.py body_1 emotion_save")
        sys.exit(1)
    regenerate(sys.argv[1:])
