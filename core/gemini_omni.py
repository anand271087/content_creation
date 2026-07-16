"""Gemini Omni Flash client — video hooks via Google's Interactions API.

Model: gemini-omni-flash-preview (public preview, launched 2026-06-30).
Docs: https://ai.google.dev/gemini-api/docs/omni
Pricing: ~$0.10/second of 720p video output. NO free tier. 10s max at launch.

Why it exists here: the Vaibhav Sisinty-style VIDEO HOOK (analysis
2026-07-16, reel DaqBTo1AcvY) — 4-6s of AI footage acting out the hook line
before the real face enters. Omni's conversational editing means a bad hook
gets fixed with "make the lighting warmer", not a blind re-roll.

Usage (needs GEMINI_API_KEY in .env — billing enabled):
    from core.gemini_omni import generate, edit
    r = generate("fisheye skit: ...", Path("hook.mp4"))     # r["id"] for edits
    edit(r["id"], "make the office brighter", Path("hook_v2.mp4"))
"""
from __future__ import annotations
import base64
import logging
import os
import subprocess
from pathlib import Path

import requests
from dotenv import load_dotenv

log = logging.getLogger("gemini_omni")
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

BASE = "https://generativelanguage.googleapis.com/v1beta/interactions"
MODEL = "gemini-omni-flash-preview"


def _key() -> str:
    k = os.getenv("GEMINI_API_KEY", "").strip()
    if not k:
        raise RuntimeError("GEMINI_API_KEY missing in .env — create one at "
                           "https://aistudio.google.com/apikey (billing required; "
                           "Omni has NO free tier, ~$0.10/sec of video)")
    return k


def _reencode(raw: Path, out: Path) -> Path:
    """H264 Baseline + 30fps + 1080x1920 — house delivery format."""
    subprocess.run([
        "ffmpeg", "-y", "-i", str(raw),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,"
               "crop=1080:1920,fps=30",
        "-c:v", "libx264", "-profile:v", "baseline", "-level", "3.1",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "192k", str(out),
    ], check=True, capture_output=True)
    return out


def _call(payload: dict, out: Path) -> dict:
    r = requests.post(f"{BASE}?key={_key()}", json=payload, timeout=900)
    if r.status_code != 200:
        raise RuntimeError(f"Omni API {r.status_code}: {r.text[:400]}")
    data = r.json()
    vid = (data.get("output_video") or {}).get("data")
    if not vid:
        raise RuntimeError(f"no output_video in response (keys: {list(data)}); "
                           f"possibly safety-blocked — rephrase the prompt")
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = out.with_suffix(".raw.mp4")
    raw.write_bytes(base64.b64decode(vid))
    _reencode(raw, out)
    raw.unlink()
    log.info("omni video → %s (interaction %s)", out.name, data.get("id"))
    return {"id": data.get("id"), "path": out}


def generate(prompt: str, out: Path, aspect: str = "9:16",
             first_frame: Path | None = None) -> dict:
    """Text (or image+text) → video. Returns {"id", "path"} — keep the id to
    iterate with edit(). first_frame uses the <FIRST_FRAME> tag convention."""
    if first_frame:
        img_b64 = base64.b64encode(Path(first_frame).read_bytes()).decode()
        payload_input = [
            {"type": "image", "data": img_b64, "mime_type": "image/png"},
            {"type": "text", "text": f"<FIRST_FRAME> {prompt}"},
        ]
    else:
        payload_input = prompt
    return _call({
        "model": MODEL,
        "input": payload_input,
        "response_format": {"type": "video", "aspect_ratio": aspect},
    }, out)


def edit(previous_id: str, instruction: str, out: Path) -> dict:
    """Conversational edit of a prior generation — ask for the delta only
    ('make the violin invisible'), never re-describe the scene."""
    return _call({
        "model": MODEL,
        "previous_interaction_id": previous_id,
        "input": instruction,
    }, out)
