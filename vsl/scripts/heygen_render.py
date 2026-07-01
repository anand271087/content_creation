"""
vsl/scripts/heygen_render.py
Per-segment HeyGen avatar rendering for the ZeroHands VSL.

Steps:
  1. Upload vsl/assets/avatar_bg.png to HeyGen (asset upload) — cached in state.json.
  2. For each segment in vsl/segments.json:
       a. Compute content hash (= segment.hash + look + voice + bg_asset_id).
       b. If existing vsl/assets/avatar/<id>.mp4 matches the hash, SKIP (no credits burned).
       c. Otherwise submit HeyGen v2 generate with:
            - avatar_id: HEYGEN_AVATAR_ID_GREY (look1) | HEYGEN_AVATAR_ID_BLUE (look2)
            - voice: HEYGEN_VOICE_ID, input_text = segment.spoken
            - background: {type: "image", image_asset_id: <uploaded_id>}
            - dimension: 1920x1080
       d. Poll v1/video_status.get until completed, then download.

Usage:
  python3 vsl/scripts/heygen_render.py --dry-run    # estimate cost + show pre-flight, no API calls
  python3 vsl/scripts/heygen_render.py              # render only segments missing/changed
  python3 vsl/scripts/heygen_render.py --force      # re-render every segment
  python3 vsl/scripts/heygen_render.py hook gap     # render specific segment ids only

Env required: HEYGEN_API_KEY, HEYGEN_VOICE_ID, HEYGEN_AVATAR_ID_GREY, HEYGEN_AVATAR_ID_BLUE.
"""
from __future__ import annotations
import argparse, hashlib, json, logging, os, sys, time
from pathlib import Path

import requests
from dotenv import load_dotenv
from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent
SEGMENTS_FILE = ROOT / "segments.json"
STATE_FILE    = ROOT / "state.json"
AVATAR_BG_PNG = ROOT / "assets" / "avatar_bg.png"
AVATAR_OUTDIR = ROOT / "assets" / "avatar"
LOG_FILE      = ROOT.parent / "logs" / "vsl_heygen.log"

AVATAR_OUTDIR.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

HEYGEN_GENERATE_URL = "https://api.heygen.com/v2/video/generate"
HEYGEN_STATUS_URL   = "https://api.heygen.com/v1/video_status.get"
HEYGEN_UPLOAD_URL   = "https://upload.heygen.com/v1/asset"

POLL_INTERVAL_SEC = 20
TASK_TIMEOUT_SEC  = 1800
SCRIPT_MAX_CHARS  = 5000

# Logging
logger = logging.getLogger("vsl_heygen")
logger.setLevel(logging.DEBUG)
_fmt = logging.Formatter("%(asctime)s [vsl_heygen] %(levelname)s %(message)s")
_fh = logging.FileHandler(LOG_FILE); _fh.setFormatter(_fmt); logger.addHandler(_fh)
_sh = logging.StreamHandler(sys.stdout); _sh.setFormatter(_fmt); logger.addHandler(_sh)

# ── Env ────────────────────────────────────────────────────────────────────
def load_env() -> dict:
    load_dotenv(ROOT.parent / ".env")
    keys = {
        "HEYGEN_API_KEY":       os.getenv("HEYGEN_API_KEY", "").strip(),
        "HEYGEN_VOICE_ID":      os.getenv("HEYGEN_VOICE_ID", "").strip(),
        "HEYGEN_AVATAR_ID_GREY":os.getenv("HEYGEN_AVATAR_ID_GREY", "").strip(),
        "HEYGEN_AVATAR_ID_BLUE":os.getenv("HEYGEN_AVATAR_ID_BLUE", "").strip(),
    }
    missing = [k for k, v in keys.items() if not v]
    if missing:
        logger.error("Missing env vars: %s", ", ".join(missing))
        logger.error("Add them to .env at project root.")
        sys.exit(2)
    return keys

# ── State ──────────────────────────────────────────────────────────────────
def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text() or "{}")

def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))

# ── HeyGen helpers ─────────────────────────────────────────────────────────
def heygen_headers(api_key: str) -> dict:
    return {"X-Api-Key": api_key, "Content-Type": "application/json"}

def upload_bg_asset(api_key: str, png_path: Path) -> str:
    """Upload the gradient PNG to HeyGen, return asset_id."""
    if not png_path.exists():
        logger.error("avatar background not found: %s — run build_avatar_bg.py first", png_path)
        sys.exit(2)
    logger.info("Uploading background asset %s (%d KB) → HeyGen", png_path.name, png_path.stat().st_size // 1024)
    with open(png_path, "rb") as fh:
        resp = requests.post(
            HEYGEN_UPLOAD_URL,
            headers={"X-Api-Key": api_key, "Content-Type": "image/png"},
            data=fh.read(),
            timeout=120,
        )
    if resp.status_code not in (200, 201):
        logger.error("HeyGen asset upload failed HTTP %d: %s", resp.status_code, resp.text[:500])
        sys.exit(1)
    body = resp.json()
    asset_id = (body.get("data") or {}).get("id") or body.get("id")
    if not asset_id:
        logger.error("HeyGen upload response missing id: %s", body)
        sys.exit(1)
    logger.info("Background asset uploaded — asset_id=%s", asset_id)
    return asset_id

def submit_segment(api_key: str, avatar_id: str, voice_id: str,
                   spoken: str, bg_asset_id: str) -> str:
    body = {
        "video_inputs": [{
            "character": {
                "type": "avatar",
                "avatar_id": avatar_id,
                "avatar_style": "normal",
            },
            "voice": {
                "type": "text",
                "input_text": spoken,
                "voice_id": voice_id,
            },
            "background": {
                "type": "image",
                "image_asset_id": bg_asset_id,
            },
        }],
        "dimension": {"width": 1920, "height": 1080},
    }
    resp = requests.post(HEYGEN_GENERATE_URL, headers=heygen_headers(api_key),
                         json=body, timeout=60)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"HeyGen submit HTTP {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    vid = (data.get("data") or {}).get("video_id") or data.get("video_id")
    if not vid:
        raise RuntimeError(f"Missing video_id in response: {data}")
    return vid

def poll_segment(api_key: str, video_id: str, label: str) -> str:
    deadline = time.time() + TASK_TIMEOUT_SEC
    last_status = ""
    with tqdm(desc=f"[{label}] poll", unit="poll", leave=False) as bar:
        while time.time() < deadline:
            time.sleep(POLL_INTERVAL_SEC)
            bar.update(1)
            try:
                resp = requests.get(HEYGEN_STATUS_URL, headers=heygen_headers(api_key),
                                    params={"video_id": video_id}, timeout=30)
            except requests.RequestException as e:
                logger.warning("[%s] poll network error: %s", label, e)
                continue
            if resp.status_code != 200:
                logger.warning("[%s] poll HTTP %d", label, resp.status_code)
                continue
            payload = resp.json().get("data", resp.json())
            status = (payload.get("status") or "").lower()
            if status != last_status:
                logger.info("[%s] status=%s", label, status)
                last_status = status
            bar.set_postfix(status=status)
            if status == "completed":
                url = payload.get("video_url")
                if not url:
                    raise RuntimeError(f"completed but no video_url: {payload}")
                return url
            if status == "failed":
                raise RuntimeError(f"HeyGen failed for {label}: {payload}")
    raise RuntimeError(f"poll timeout for {label}")

def download(url: str, dest: Path) -> None:
    logger.info("Downloading → %s", dest)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    sz = dest.stat().st_size
    if sz < 50_000:
        raise RuntimeError(f"download too small: {sz} bytes")

# ── Main flow ─────────────────────────────────────────────────────────────
def hash_for_segment(seg: dict, look_avatar_id: str, voice_id: str, bg_asset_id: str) -> str:
    h = hashlib.sha256()
    h.update(seg["spoken"].encode("utf-8"))
    h.update(b"|"); h.update(look_avatar_id.encode())
    h.update(b"|"); h.update(voice_id.encode())
    h.update(b"|"); h.update(bg_asset_id.encode())
    return h.hexdigest()[:12]

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true", help="re-render all segments")
    p.add_argument("--dry-run", action="store_true", help="estimate cost without API calls")
    p.add_argument("targets", nargs="*", help="specific segment ids to render")
    args = p.parse_args()

    if not SEGMENTS_FILE.exists():
        logger.error("missing %s — run vsl/scripts/parse_script.py first", SEGMENTS_FILE)
        return 2
    segments = json.loads(SEGMENTS_FILE.read_text())

    if args.targets:
        segments = [s for s in segments if s["id"] in args.targets]
        if not segments:
            logger.error("No matching segment ids: %s", ", ".join(args.targets))
            return 2

    # Pre-flight: total words, estimated cost
    total_words = sum(len(s["spoken"].split()) for s in segments)
    total_chars = sum(len(s["spoken"]) for s in segments)
    est_minutes = total_words / 150            # 150 wpm conservative
    est_cost_low  = est_minutes * 0.30
    est_cost_high = est_minutes * 0.60

    print("\n── Pre-flight ──────────────────────────────────")
    print(f"  Segments queued: {len(segments)}")
    print(f"  Total words:     {total_words}")
    print(f"  Estimated runtime: {est_minutes:.1f} min")
    print(f"  Estimated cost:  ${est_cost_low:.2f} – ${est_cost_high:.2f}  (very rough)")
    for s in segments:
        print(f"    {s['id']:25s}  {s['look']:5s}  words={len(s['spoken'].split()):4d}  chars={len(s['spoken']):5d}")
    print("─────────────────────────────────────────────────\n")

    over = [s for s in segments if len(s["spoken"]) > SCRIPT_MAX_CHARS]
    if over:
        logger.error("Segments exceeding %d chars: %s", SCRIPT_MAX_CHARS, ", ".join(s["id"] for s in over))
        return 2

    if args.dry_run:
        print("Dry run — no API calls.")
        return 0

    env = load_env()
    state = load_state()
    state.setdefault("avatars", {})

    # Upload background image (once, cached)
    bg_asset_id = (state.get("heygen") or {}).get("bg_asset_id")
    if not bg_asset_id:
        bg_asset_id = upload_bg_asset(env["HEYGEN_API_KEY"], AVATAR_BG_PNG)
        state.setdefault("heygen", {})["bg_asset_id"] = bg_asset_id
        save_state(state)
    else:
        logger.info("Re-using background asset_id from state: %s", bg_asset_id)

    look_to_avatar = {
        "look1": env["HEYGEN_AVATAR_ID_GREY"],   # tight, hook
        "look2": env["HEYGEN_AVATAR_ID_BLUE"],   # medium, body
    }

    rendered, skipped, failed = 0, 0, 0
    for seg in segments:
        sid    = seg["id"]
        look   = seg["look"]
        avatar = look_to_avatar.get(look)
        if not avatar:
            logger.error("[%s] unknown look %r — skipping", sid, look)
            failed += 1
            continue

        spoken = seg["spoken"].strip()
        if not spoken:
            logger.warning("[%s] empty spoken text — skipping", sid)
            skipped += 1
            continue

        out = AVATAR_OUTDIR / f"{sid}.mp4"
        digest = hash_for_segment(seg, avatar, env["HEYGEN_VOICE_ID"], bg_asset_id)
        prev = state["avatars"].get(sid)
        if (not args.force) and out.exists() and out.stat().st_size > 50_000 and prev and prev.get("hash") == digest:
            logger.info("[%s] unchanged — skipping (%d KB)", sid, out.stat().st_size // 1024)
            skipped += 1
            continue

        # Persist the text we're about to render so the user can review
        (AVATAR_OUTDIR / f"{sid}.txt").write_text(spoken)

        logger.info("[%s] submitting %s (%s, %d chars)", sid, look, avatar, len(spoken))
        try:
            vid_id = submit_segment(env["HEYGEN_API_KEY"], avatar, env["HEYGEN_VOICE_ID"],
                                    spoken, bg_asset_id)
            logger.info("[%s] video_id=%s", sid, vid_id)
            url = poll_segment(env["HEYGEN_API_KEY"], vid_id, sid)
            download(url, out)
            state["avatars"][sid] = {
                "hash": digest, "video_id": vid_id, "size": out.stat().st_size,
                "spoken_chars": len(spoken), "rendered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            save_state(state)
            logger.info("[%s] ✅ %d KB", sid, out.stat().st_size // 1024)
            rendered += 1
        except Exception as e:
            logger.error("[%s] ❌ %s", sid, e)
            failed += 1
            save_state(state)
            # Continue with next segment instead of aborting — partial progress is useful
            continue

    print("\n── Summary ─────────────────────────────────────")
    print(f"  Rendered: {rendered}")
    print(f"  Skipped:  {skipped}")
    print(f"  Failed:   {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
