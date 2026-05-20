"""
generate_text_cards.py — Generate animated text card brolls for text_card sections.

For each section with broll_type="text_card":
1. Uses Claude API to build an Excalidraw numbered-list card from card_lines
2. Renders card to PNG via render_diagram.mjs
3. Feeds PNG to Kling I2V via Kie.ai → animated .mp4
4. Saves to assets/broll/{section_id}.mp4 (same location as regular broll)
"""

import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import anthropic
import requests
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent
SCRIPT_DATA = ROOT / "assets" / "script_data.json"
DIAGRAMS_DIR = ROOT / "assets" / "diagrams"
BROLL_DIR = ROOT / "assets" / "broll"
LOG_FILE = ROOT / "logs" / "pipeline.log"

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
DIAGRAMS_DIR.mkdir(parents=True, exist_ok=True)
BROLL_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("generate_text_cards")
logger.setLevel(logging.DEBUG)
_fmt = logging.Formatter("%(asctime)s [generate_text_cards] %(levelname)s %(message)s")
_fh = logging.FileHandler(LOG_FILE); _fh.setFormatter(_fmt); logger.addHandler(_fh)
_sh = logging.StreamHandler(sys.stdout); _sh.setFormatter(_fmt); logger.addHandler(_sh)

KIE_GENERATE_URL = "https://api.kie.ai/api/v1/jobs/createTask"
KIE_POLL_URL = "https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}"
POLL_INTERVAL = 15
VIDEO_TIMEOUT = 600
IMAGE_TIMEOUT = 180

# Color palette — one per item slot (alternating)
ITEM_COLORS = [
    {"stroke": "#1971c2", "bg": "#e7f5ff"},   # blue
    {"stroke": "#2f9e44", "bg": "#d3f9d8"},   # green
    {"stroke": "#f59f00", "bg": "#fff9db"},   # yellow
    {"stroke": "#862e9c", "bg": "#f3d9fa"},   # purple
    {"stroke": "#c92a2a", "bg": "#ffe3e3"},   # red
]

# ---------------------------------------------------------------------------
# Excalidraw card builder
# ---------------------------------------------------------------------------

def _base_element(eid, etype, x, y, w, h):
    return {
        "id": eid, "type": etype,
        "x": x, "y": y, "width": w, "height": h,
        "angle": 0,
        "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
        "fillStyle": "hachure", "strokeWidth": 2, "strokeStyle": "solid",
        "roughness": 2, "opacity": 100, "groupIds": [], "frameId": None,
        "roundness": {"type": 3}, "boundElements": [], "updated": 1,
        "link": None, "locked": False,
    }


def build_card_excalidraw(section_id: str, title: str, card_lines: list[str]) -> dict:
    """Build a bold numbered-list Excalidraw card from card_lines."""
    elements = []

    # Items (no title — starts at top of card)
    item_y_start = 40
    item_row_height = 190
    circle_size = 90
    label_x = 160
    label_w = 680

    for i, line in enumerate(card_lines[:5]):
        col = ITEM_COLORS[i % len(ITEM_COLORS)]
        y = item_y_start + i * item_row_height
        idx = str(i + 1)

        # Number circle background
        circle = _base_element(f"circle_{i}", "ellipse", 40, y, circle_size, circle_size)
        circle.update({
            "strokeColor": col["stroke"],
            "backgroundColor": col["bg"],
            "strokeWidth": 3,
        })
        elements.append(circle)

        # Number text (centered in circle)
        num_el = _base_element(f"num_{i}", "text", 40, y + 14, circle_size, circle_size - 14)
        num_el.update({
            "strokeColor": col["stroke"],
            "text": idx,
            "fontSize": 52, "fontFamily": 1,
            "textAlign": "center", "verticalAlign": "top",
            "containerId": None, "originalText": idx, "lineHeight": 1.25,
        })
        elements.append(num_el)

        # Label text (right of circle)
        label_el = _base_element(f"label_{i}", "text", label_x, y + 22, label_w, 60)
        label_el.update({
            "strokeColor": "#1e1e1e",
            "text": line.upper(),
            "fontSize": 24, "fontFamily": 1,
            "textAlign": "left", "verticalAlign": "top",
            "containerId": None, "originalText": line.upper(), "lineHeight": 1.25,
        })
        elements.append(label_el)

    return {
        "type": "excalidraw",
        "version": 2,
        "source": "https://excalidraw.com",
        "elements": elements,
        "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
        "files": {},
    }


# ---------------------------------------------------------------------------
# Kie.ai helpers (shared pattern with stage2_broll.py)
# ---------------------------------------------------------------------------

def _kie_headers(api_key):
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _poll(task_id: str, section_id: str, api_key: str, timeout: int) -> str:
    url = KIE_POLL_URL.format(task_id=task_id)
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        resp = requests.get(url, headers=_kie_headers(api_key), timeout=30)
        if resp.status_code != 200:
            continue
        payload = resp.json().get("data") or resp.json()
        status = (payload.get("state") or payload.get("status") or "").lower()
        logger.debug("[%s] poll state=%s", section_id, status)
        if status == "success":
            result_str = payload.get("resultJson", "")
            urls = json.loads(result_str).get("resultUrls", []) if result_str else []
            if urls:
                return urls[0]
            raise RuntimeError(f"[{section_id}] Task succeeded but no URL: {payload}")
        if status in ("fail", "failed", "error"):
            raise RuntimeError(f"[{section_id}] Task failed: {payload}")
    raise TimeoutError(f"[{section_id}] Task {task_id} timed out after {timeout}s")


def _reencode(src: Path, dst: Path):
    """Re-encode to H264 baseline for Remotion/Chromium compatibility."""
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", str(src),
            "-c:v", "h264_videotoolbox",
            "-profile:v", "baseline",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(dst),
        ], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        subprocess.run([
            "ffmpeg", "-y", "-i", str(src),
            "-c:v", "libx264", "-profile:v", "baseline",
            "-level", "3.1", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(dst),
        ], check=True, capture_output=True)


# ---------------------------------------------------------------------------
# Main card generation
# ---------------------------------------------------------------------------

def generate_text_card(section: dict, kie_key: str) -> Path:
    """Full pipeline for one text_card section. Returns path to .mp4."""
    sid = section["id"]
    card_lines = section.get("card_lines", [])
    title = section.get("label", sid.replace("_", " ").title())
    dest = BROLL_DIR / f"{sid}.mp4"

    if not card_lines:
        logger.warning("[%s] No card_lines — skipping text_card generation", sid)
        return dest

    # Step 1: Build Excalidraw JSON
    card_json = build_card_excalidraw(sid, title, card_lines)
    excalidraw_path = DIAGRAMS_DIR / f"{sid}_card.excalidraw"
    excalidraw_path.write_text(json.dumps(card_json, indent=2, ensure_ascii=False))
    logger.info("[%s] Excalidraw card written → %s", sid, excalidraw_path)

    # Step 2: Render PNG via render_diagram.mjs
    png_path = DIAGRAMS_DIR / f"{sid}_card.png"
    scripts_dir = ROOT / "scripts"
    result = subprocess.run(
        ["node", "render_diagram.mjs", f"{sid}_card"],
        cwd=scripts_dir, capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0 or not png_path.exists():
        raise RuntimeError(f"[{sid}] render_diagram.mjs failed:\n{result.stderr}")
    logger.info("[%s] PNG rendered → %s (%dKB)", sid, png_path, png_path.stat().st_size // 1024)

    # Step 3: Upload PNG to Kie.ai nano-banana-2 to get a hosted URL
    # We use nano-banana-2 with a prompt that describes the card style,
    # so the image is uploaded and we get a Kie.ai CDN URL back
    # Actually: Kling I2V needs a public URL — upload via nano-banana-2 with image_input
    # Better: submit the PNG as image_input to nano-banana-2 to get a CDN URL first
    logger.info("[%s] Uploading card PNG to get CDN URL via nano-banana-2...", sid)
    import base64
    png_b64 = base64.b64encode(png_path.read_bytes()).decode()
    img_body = {
        "model": "nano-banana-2",
        "callBackUrl": "",
        "input": {
            "prompt": f"Clean infographic card showing numbered list, bold typography, white background, professional design, no changes",
            "image_input": [{"type": "base64", "data": png_b64, "media_type": "image/png"}],
            "aspect_ratio": "9:16",
            "resolution": "1K",
            "output_format": "png",
        },
    }
    resp = requests.post(KIE_GENERATE_URL, headers=_kie_headers(kie_key), json=img_body, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"[{sid}] nano-banana-2 upload failed: {resp.status_code} {resp.text}")
    img_task_id = (resp.json().get("data") or {}).get("taskId")
    if not img_task_id:
        raise RuntimeError(f"[{sid}] No taskId in nano-banana-2 response: {resp.json()}")
    logger.info("[%s] nano-banana-2 task_id=%s", sid, img_task_id)

    image_url = _poll(img_task_id, sid, kie_key, IMAGE_TIMEOUT)
    logger.info("[%s] Card image URL: %s", sid, image_url[:80])

    # Step 4: Kling I2V — animate the card with subtle zoom
    motion_prompt = (
        "slow gentle zoom in, cards appearing one by one from top, "
        "clean minimal motion, professional presentation style, no camera shake"
    )
    i2v_body = {
        "model": "kling-2.6/image-to-video",
        "callBackUrl": "",
        "input": {
            "prompt": motion_prompt,
            "negative_prompt": (
                "shaky camera, fast movement, distortion, blur, "
                "Chinese text, Japanese text, Korean text, Arabic text, "
                "any non-English text, watermark, logo"
            ),
            "image_url": image_url,
            "duration": "5",
            "aspect_ratio": "9:16",
            "sound": False,
        },
    }
    resp = requests.post(KIE_GENERATE_URL, headers=_kie_headers(kie_key), json=i2v_body, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"[{sid}] Kling I2V submit failed: {resp.status_code} {resp.text}")
    video_task_id = (resp.json().get("data") or {}).get("taskId")
    if not video_task_id:
        raise RuntimeError(f"[{sid}] No taskId in Kling I2V response: {resp.json()}")
    logger.info("[%s] Kling I2V task_id=%s", sid, video_task_id)

    video_url = _poll(video_task_id, sid, kie_key, VIDEO_TIMEOUT)
    logger.info("[%s] Video URL: %s", sid, video_url[:80])

    # Step 5: Download and re-encode
    raw = BROLL_DIR / f"{sid}_raw.mp4"
    with requests.get(video_url, stream=True, timeout=120) as r:
        r.raise_for_status()
        raw.write_bytes(r.content)
    logger.info("[%s] Downloaded %dKB", sid, raw.stat().st_size // 1024)

    _reencode(raw, dest)
    raw.unlink(missing_ok=True)
    logger.info("[%s] Re-encoded → %s (%dKB)", sid, dest, dest.stat().st_size // 1024)
    return dest


def run(script_data: dict | None = None) -> dict:
    if script_data is None:
        if not SCRIPT_DATA.exists():
            return {"success": False, "error": "script_data.json not found"}
        script_data = json.loads(SCRIPT_DATA.read_text())

    sections = [s for s in script_data.get("sections", []) if s.get("broll_type") == "text_card"]
    if not sections:
        logger.info("No text_card sections — skipping")
        return {"success": True, "generated": []}

    kie_key = os.getenv("KIE_API_KEY", "")
    if not kie_key:
        return {"success": False, "error": "KIE_API_KEY not set"}

    generated, failed = [], []
    for s in sections:
        sid = s["id"]
        dest = BROLL_DIR / f"{sid}.mp4"
        if dest.exists() and dest.stat().st_size > 10000:
            logger.info("[%s] Already exists — skipping", sid)
            generated.append(sid)
            continue
        try:
            generate_text_card(s, kie_key)
            generated.append(sid)
        except Exception as e:
            logger.error("[%s] Failed: %s", sid, e)
            failed.append(sid)

    return {"success": len(failed) == 0, "generated": generated, "failed": failed}


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
