"""
Stage 5 — Remotion Composition
Runs Whisper on the avatar video to generate word-level captions, then
triggers the Remotion render to produce the final 9:16 composite reel.
"""

import json
import logging
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
AVATAR_VIDEO = ROOT / "assets" / "avatar" / "avatar_video.mp4"
CAPTIONS_DIR = ROOT / "assets" / "captions"
CAPTIONS_JSON = CAPTIONS_DIR / "avatar_video.json"
SCRIPT_DATA = ROOT / "assets" / "script_data.json"
FINAL_DIR = ROOT / "assets" / "final"
FINAL_REEL = FINAL_DIR / "final_reel.mp4"
FINAL_REEL_FAST = FINAL_DIR / "final_reel_fast.mp4"
THUMBNAIL_PNG = FINAL_DIR / "thumbnail.png"   # optional — drop here to append as last frame

SPEED_FACTOR = 1.25   # output playback speed multiplier
LOG_FILE = ROOT / "logs" / "pipeline.log"
REMOTION_ENTRY = ROOT / "remotion" / "src" / "index.ts"

WHISPER_TIMEOUT_SEC = 45 * 60    # 45 minutes (large-v3 on CPU needs ~20-30 min)
REMOTION_TIMEOUT_SEC = 90 * 60   # 90 minutes (long videos need more time)
REMOTION_HEARTBEAT_SEC = 60      # kill if no output for this long

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("stage5_compose")
logger.setLevel(logging.DEBUG)

_fmt = logging.Formatter("%(asctime)s [stage5_compose] %(levelname)s %(message)s")

_fh = logging.FileHandler(LOG_FILE)
_fh.setFormatter(_fmt)
logger.addHandler(_fh)

_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(_fmt)
logger.addHandler(_sh)


# ---------------------------------------------------------------------------
# Encoder helpers
# ---------------------------------------------------------------------------

def _h264_encoder_flags() -> list[str]:
    """Return ffmpeg video encoder flags for the speed-up encode.
    h264_videotoolbox does not work with filter_complex pipelines, so always use libx264 here.
    (videotoolbox is used in stage2_broll.py for the baseline re-encode, which has no filters.)
    """
    return ["-c:v", "libx264", "-crf", "18", "-preset", "fast"]


# ---------------------------------------------------------------------------
# Step 1 — Speech-to-text (Whisper default, ElevenLabs Scribe via env flag)
# ---------------------------------------------------------------------------

ELEVENLABS_TIMEOUT_SEC = 10 * 60   # plenty for a sub-3-min mp3 upload + transcription
ELEVENLABS_HELPER = ROOT / "speech" / "transcribe_elevenlabs.py"


def _run_elevenlabs_scribe() -> None:
    """Shell out to scripts/transcribe_elevenlabs.py.

    Writes CAPTIONS_JSON in Whisper-shaped JSON via the helper's adapter so
    downstream sync + Remotion code stays untouched.
    """
    if not ELEVENLABS_HELPER.exists():
        raise RuntimeError(
            f"ElevenLabs helper missing: {ELEVENLABS_HELPER}. "
            "Set STT_PROVIDER=whisper to use the local fallback."
        )

    cmd = [
        sys.executable,
        str(ELEVENLABS_HELPER),
        str(AVATAR_VIDEO),
        "--output", str(CAPTIONS_JSON),
    ]
    logger.info("Running ElevenLabs Scribe: %s", " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=ELEVENLABS_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"ElevenLabs Scribe timed out after {ELEVENLABS_TIMEOUT_SEC}s"
        )

    if proc.stdout:
        for line in proc.stdout.splitlines():
            logger.debug("[elevenlabs] %s", line)
    if proc.stderr:
        for line in proc.stderr.splitlines():
            logger.debug("[elevenlabs stderr] %s", line)

    if proc.returncode != 0:
        raise RuntimeError(
            f"ElevenLabs Scribe exited with code {proc.returncode}.\n"
            f"Set STT_PROVIDER=whisper to use the local fallback while you "
            f"investigate.\nstderr: {proc.stderr[-1000:] if proc.stderr else ''}"
        )

    if not CAPTIONS_JSON.exists() or CAPTIONS_JSON.stat().st_size == 0:
        raise RuntimeError(
            f"ElevenLabs Scribe returned successfully but captions file is "
            f"missing or empty: {CAPTIONS_JSON}"
        )

    logger.info(
        "ElevenLabs captions written — %d bytes → %s",
        CAPTIONS_JSON.stat().st_size,
        CAPTIONS_JSON,
    )


def _run_whisper() -> None:
    """
    Produce word-level captions for the avatar video.
    Output: assets/captions/avatar_video.json (Whisper-shaped JSON either way).

    The provider is selected by the STT_PROVIDER env var:
      - "elevenlabs"      → shell out to scripts/transcribe_elevenlabs.py
      - anything else     → run local Whisper subprocess (default fallback)

    Raises RuntimeError on failure.
    """
    if not AVATAR_VIDEO.exists():
        raise RuntimeError(
            f"Avatar video not found: {AVATAR_VIDEO}. "
            "Run Stage 3 before Stage 5."
        )

    # Regenerate captions if avatar is newer than captions (new avatar = new speech)
    if CAPTIONS_JSON.exists() and CAPTIONS_JSON.stat().st_size > 0:
        captions_mtime = CAPTIONS_JSON.stat().st_mtime
        avatar_mtime = AVATAR_VIDEO.stat().st_mtime
        if avatar_mtime <= captions_mtime:
            logger.info("Captions already exist and are up to date — skipping transcription")
            return
        logger.info("Avatar is newer than captions — re-running transcription")
        CAPTIONS_JSON.unlink()

    CAPTIONS_DIR.mkdir(parents=True, exist_ok=True)

    provider = os.getenv("STT_PROVIDER", "whisper").strip().lower()
    if provider == "elevenlabs":
        _run_elevenlabs_scribe()
        return

    whisper_model = os.getenv("WHISPER_MODEL", "small.en")

    cmd = [
        "whisper",
        str(AVATAR_VIDEO),
        "--model", whisper_model,
        "--language", "en",
        "--output_format", "json",
        "--output_dir", str(CAPTIONS_DIR),
        "--word_timestamps", "True",
        "--condition_on_previous_text", "False",
    ]

    logger.info("Running Whisper: %s", " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=WHISPER_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"Whisper timed out after {WHISPER_TIMEOUT_SEC}s"
        )
    except FileNotFoundError:
        raise RuntimeError(
            "whisper command not found. Install with: pip install openai-whisper"
        )

    if proc.stdout:
        for line in proc.stdout.splitlines():
            logger.debug("[whisper] %s", line)
    if proc.stderr:
        for line in proc.stderr.splitlines():
            logger.debug("[whisper stderr] %s", line)

    if proc.returncode != 0:
        raise RuntimeError(
            f"Whisper exited with code {proc.returncode}.\n"
            f"stdout: {proc.stdout[-1000:] if proc.stdout else ''}\n"
            f"stderr: {proc.stderr[-1000:] if proc.stderr else ''}"
        )

    if not CAPTIONS_JSON.exists() or CAPTIONS_JSON.stat().st_size == 0:
        raise RuntimeError(
            f"Whisper completed (exit 0) but captions file is missing or empty: {CAPTIONS_JSON}"
        )

    logger.info(
        "Whisper captions written — %d bytes → %s",
        CAPTIONS_JSON.stat().st_size,
        CAPTIONS_JSON,
    )


# ---------------------------------------------------------------------------
# Step 1.6 — Caption validation
# ---------------------------------------------------------------------------

def _validate_captions(path: Path) -> None:
    """Verify captions JSON has at least one word-level segment."""
    with open(path) as fh:
        data = json.load(fh)

    segments = data.get("segments", [])
    if not segments:
        raise RuntimeError(
            "Captions JSON has no segments — Whisper may have failed silently"
        )

    words = [w for seg in segments for w in seg.get("words", [])]
    if not words:
        raise RuntimeError(
            "Captions have segments but no word-level timestamps. "
            "Re-run Whisper with --word_timestamps True"
        )

    logger.info(
        "Caption validation passed — %d segments, %d words",
        len(segments), len(words),
    )


# ---------------------------------------------------------------------------
# Step 2 — Remotion render
# ---------------------------------------------------------------------------

def _run_remotion() -> None:
    """
    Render the final reel with Remotion.
    Writes props to a temp file (avoids OS ARG_MAX limits with large captions JSON).
    Streams subprocess output to the logger in real time.
    Raises RuntimeError on failure.
    """
    if not SCRIPT_DATA.exists():
        raise RuntimeError(
            f"script_data.json not found: {SCRIPT_DATA}. "
            "Run Stage 1 before Stage 5."
        )

    with open(SCRIPT_DATA, "r", encoding="utf-8") as fh:
        script_data = json.load(fh)

    # Load Whisper captions and inline into props so HormoziCaptions gets
    # word-level timestamps without any async fetch at render time.
    with open(CAPTIONS_JSON, "r", encoding="utf-8") as fh:
        captions_data = json.load(fh)

    # Load screen timelines (built by screen_timeline.mjs after Whisper step).
    # Keyed by section_id — Remotion ScreenDemoLayer uses these for cursor sync.
    screen_timelines: dict = {}
    timelines_dir = ROOT / "assets" / "screen_timelines"
    if timelines_dir.exists():
        for tl_file in timelines_dir.glob("*.json"):
            try:
                tl_data = json.loads(tl_file.read_text(encoding="utf-8"))
                section_id = tl_file.stem
                screen_timelines[section_id] = tl_data
            except Exception:
                pass
    if screen_timelines:
        logger.info("Loaded %d screen timeline(s): %s", len(screen_timelines), list(screen_timelines.keys()))

    # Write props to file — avoids OS ARG_MAX limit when captions JSON is large
    props_path = ROOT / "assets" / "remotion_props.json"
    props_path.write_text(
        json.dumps({
            "scriptData": script_data,
            "assetsDir": "assets",
            "captionsData": captions_data,
            "screenTimelines": screen_timelines,
        }),
        encoding="utf-8",
    )
    logger.info("Props written to %s (%d bytes)", props_path, props_path.stat().st_size)

    FINAL_DIR.mkdir(parents=True, exist_ok=True)

    # Run from the remotion/ subdirectory where node_modules lives
    REMOTION_DIR = ROOT / "remotion"
    remotion_entry_rel = "src/index.ts"  # relative to REMOTION_DIR

    concurrency = os.getenv("REMOTION_CONCURRENCY", "4")
    crf = os.getenv("REMOTION_CRF", "18")

    # Render to ProRes MOV — universally decodable by ffmpeg on macOS.
    # The final H264 baseline MP4 is produced by the ffmpeg re-encode step below.
    remotion_raw = FINAL_DIR / "final_reel_raw.mov"
    cmd = [
        "npx",
        "remotion",
        "render",
        remotion_entry_rel,
        "ReelComposition",
        f"--props={props_path}",
        "--output", str(remotion_raw),
        "--width", "1080",
        "--height", "1920",
        "--fps", "30",
        "--codec", "prores",
        "--prores-profile", "standard",  # ProRes 422 — good quality, manageable size
        "--concurrency", concurrency,
        "--jpeg-quality", "90",
        "--log", "verbose" if os.getenv("REMOTION_VERBOSE") else "info",
    ]

    logger.info(
        "Starting Remotion render (concurrency=%s, crf=%s)",
        concurrency, crf,
    )

    deadline = time.time() + REMOTION_TIMEOUT_SEC

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(REMOTION_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "npx not found. Ensure Node.js is installed and in PATH."
        )

    # Stream output line-by-line — kill if silent for REMOTION_HEARTBEAT_SEC
    last_output_time = time.time()
    try:
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                logger.info("[remotion] %s", line)
                last_output_time = time.time()

            now = time.time()
            if now - last_output_time > REMOTION_HEARTBEAT_SEC:
                proc.kill()
                raise RuntimeError(
                    f"Remotion appears hung — no output for {REMOTION_HEARTBEAT_SEC}s"
                )
            if now > deadline:
                proc.kill()
                raise RuntimeError(
                    f"Remotion render timed out after {REMOTION_TIMEOUT_SEC}s"
                )
    except RuntimeError:
        raise
    except Exception as exc:
        proc.kill()
        raise RuntimeError(f"Error reading Remotion output: {exc}") from exc
    finally:
        proc.wait()

    if proc.returncode != 0:
        raise RuntimeError(
            f"Remotion render exited with code {proc.returncode}"
        )

    remotion_raw = FINAL_DIR / "final_reel_raw.mov"
    if not remotion_raw.exists() or remotion_raw.stat().st_size == 0:
        raise RuntimeError(
            f"Remotion exited cleanly but output file is missing or empty: {remotion_raw}"
        )

    logger.info("Remotion ProRes render complete — %d bytes → %s", remotion_raw.stat().st_size, remotion_raw)

    # Re-encode ProRes → H264 MP4 — v2 polish port from VSL pipeline.
    # CRF 17 + preset slow + unsharp = noticeably crisper face/text than the old
    # CRF 18 baseline + fast preset. Larger file (~30-40%) but worth it for a reel.
    # Note: we keep main profile (not baseline) for better quality; broll re-encodes
    # already use baseline so playback compatibility is preserved.
    logger.info("Re-encoding ProRes → H264 MP4 (CRF 17, preset slow, unsharp) …")
    reencode_cmd = [
        "ffmpeg",
        "-i", str(remotion_raw),
        "-vf", "unsharp=5:5:0.9:5:5:0.0",
        "-c:v", "libx264", "-preset", "slow",
        "-pix_fmt", "yuv420p", "-crf", "17", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "48000",
        "-y", str(FINAL_REEL),
    ]
    re = subprocess.run(reencode_cmd, cwd=str(ROOT), capture_output=True, text=True)
    if re.returncode != 0:
        raise RuntimeError(f"Re-encode failed:\n{re.stderr[-1000:]}")
    remotion_raw.unlink(missing_ok=True)  # delete large ProRes intermediary

    if not FINAL_REEL.exists() or FINAL_REEL.stat().st_size == 0:
        raise RuntimeError(f"Re-encode produced empty file: {FINAL_REEL}")

    logger.info(
        "Re-encode complete — %d bytes → %s",
        FINAL_REEL.stat().st_size,
        FINAL_REEL,
    )


# ---------------------------------------------------------------------------
# Step 3 — ffmpeg speed-up
# ---------------------------------------------------------------------------

def _run_speed_up() -> None:
    """
    Apply SPEED_FACTOR (1.25×) to the rendered reel using ffmpeg.
    Writes: assets/final/final_reel_fast.mp4
    Video: setpts=(1/SPEED_FACTOR)*PTS
    Audio: atempo=SPEED_FACTOR  (supports 0.5–2.0 in a single pass)
    """
    pts_factor = round(1.0 / SPEED_FACTOR, 6)

    cmd = [
        "ffmpeg",
        "-i", str(FINAL_REEL),
        "-filter_complex",
        f"[0:v]setpts={pts_factor}*PTS[v];[0:a]aformat=channel_layouts=stereo:sample_rates=48000:sample_fmts=fltp,atempo={SPEED_FACTOR}[a]",
        "-map", "[v]",
        "-map", "[a]",
        *_h264_encoder_flags(),
        "-c:a", "aac",
        "-b:a", "192k",
        "-y",
        str(FINAL_REEL_FAST),
    ]

    logger.info("Running ffmpeg speed-up %.2f× — output: %s", SPEED_FACTOR, FINAL_REEL_FAST)
    logger.info("ffmpeg cmd: %s", " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=10 * 60,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("ffmpeg speed-up timed out after 10 minutes")
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found. Install with: brew install ffmpeg")

    if proc.returncode != 0:
        # Remotion already bakes 1.25× into the composition via playbackRate.
        # If the ffmpeg speed-up fails (common with macOS VideoToolbox h264 output),
        # fall back to copying the Remotion output as-is — it is already the correct speed.
        logger.warning(
            "ffmpeg speed-up failed (code %d) — Remotion already applied %.2f× speed via "
            "playbackRate. Falling back to copying final_reel.mp4 as final_reel_fast.mp4.",
            proc.returncode, SPEED_FACTOR,
        )
        import shutil
        shutil.copy2(FINAL_REEL, FINAL_REEL_FAST)

    if not FINAL_REEL_FAST.exists() or FINAL_REEL_FAST.stat().st_size == 0:
        raise RuntimeError(
            f"Speed-up output missing or empty: {FINAL_REEL_FAST}"
        )

    logger.info(
        "Speed-up complete — %d bytes → %s",
        FINAL_REEL_FAST.stat().st_size,
        FINAL_REEL_FAST,
    )


# ---------------------------------------------------------------------------
# Step 4 — Thumbnail frame append (optional)
# ---------------------------------------------------------------------------

def _append_thumbnail(video_path: Path, thumbnail_png: Path) -> None:
    """
    Append thumbnail.png as a 1-second still at the very end of the video.
    This allows selecting the last frame as the YouTube Shorts thumbnail.
    Overwrites video_path in-place.
    """
    fps = 30
    tmp = video_path.with_suffix(".thumb_tmp.mp4")

    # Step 1: Convert PNG → 1-second silent video clip matching main video spec
    thumb_clip = video_path.with_suffix(".thumb_clip.mp4")
    cmd_img = [
        "ffmpeg",
        "-loop", "1",
        "-i", str(thumbnail_png),
        "-t", "1",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-c:v", "libx264", "-profile:v", "baseline", "-level", "3.1",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-r", str(fps),
        "-an",
        "-y", str(thumb_clip),
    ]
    proc = subprocess.run(cmd_img, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(f"Thumbnail clip creation failed: {proc.stderr[-500:]}")

    # Step 2: Concat main video + thumbnail clip
    # Use concat demuxer via a temporary list file
    list_file = video_path.parent / "concat_list.txt"
    list_file.write_text(
        f"file '{video_path.resolve()}'\nfile '{thumb_clip.resolve()}'\n"
    )
    cmd_concat = [
        "ffmpeg",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-profile:v", "baseline", "-level", "3.1",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "192k",
        "-y", str(tmp),
    ]
    proc2 = subprocess.run(cmd_concat, capture_output=True, text=True, timeout=600)

    # Cleanup temp files regardless of outcome
    list_file.unlink(missing_ok=True)
    thumb_clip.unlink(missing_ok=True)

    if proc2.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Thumbnail concat failed: {proc2.stderr[-500:]}")

    import shutil as _shutil
    _shutil.move(str(tmp), str(video_path))
    logger.info(
        "Thumbnail appended — last frame is thumbnail. Final size: %d bytes",
        video_path.stat().st_size,
    )


# ---------------------------------------------------------------------------
# Public stage entrypoint
# ---------------------------------------------------------------------------

def run_stage5() -> dict:
    """
    Run Stage 5 — Composition.

    Returns:
        {
            "success": bool,
            "output_path": str,      # absolute path to final_reel.mp4
            "duration_sec": float,
            "error": str | None,
        }
    """
    start = time.time()
    load_dotenv(ROOT / ".env")

    logger.info("Stage 5 started")

    # ---- Step 1: Whisper ----
    try:
        logger.info("Step 1/2 — Generating Whisper captions")
        _run_whisper()
    except Exception as exc:
        duration = time.time() - start
        error_msg = f"Whisper step failed: {exc}"
        logger.error(error_msg)
        return {
            "success": False,
            "output_path": "",
            "duration_sec": round(duration, 2),
            "error": error_msg,
        }

    # ---- Step 1.5: Sanitize captions (fix Whisper mishears + vulgar words) ----
    sys.path.insert(0, str(ROOT / "speech"))
    try:
        from sanitize_captions import sanitize
        sanitize(CAPTIONS_JSON)
        logger.info("Caption sanitization complete")
    except ImportError:
        logger.warning("sanitize_captions.py not found — skipping")
    except Exception as exc:
        logger.warning("Caption sanitization failed (non-fatal): %s", exc)

    # ---- Step 1.6: Validate captions before spending time on Remotion ----
    try:
        _validate_captions(CAPTIONS_JSON)
    except Exception as exc:
        duration = time.time() - start
        error_msg = f"Caption validation failed: {exc}"
        logger.error(error_msg)
        return {
            "success": False,
            "output_path": "",
            "duration_sec": round(duration, 2),
            "error": error_msg,
        }

    # ---- Step 1.7: Sync broll timestamps to actual Whisper speech ----
    # Updates total_duration_sec in script_data.json to match actual avatar
    # duration so Remotion renders the full video (not the planned 60/90s).
    # Skip if SKIP_BROLL_SYNC=1 (e.g. when timestamps were manually fixed).
    if os.environ.get("SKIP_BROLL_SYNC") == "1":
        logger.info("Step 1.7/3 — SKIPPING broll sync (SKIP_BROLL_SYNC=1)")
    else:
        try:
            sys.path.insert(0, str(ROOT / "speech"))
            from sync_broll_to_speech import sync as _sync_broll
            logger.info("Step 1.7/3 — Syncing broll timestamps to Whisper speech")
            _sync_broll(dry_run=False)
            logger.info("Broll sync complete — total_duration_sec updated in script_data.json")
        except Exception as exc:
            logger.warning("Broll sync failed (non-fatal, using planned timestamps): %s", exc)

    # ---- Step 1.8: Build screen timelines (sync cursor_steps to Whisper timestamps) ----
    # Reads cursor_steps spoken_cues + Whisper words → writes assets/screen_timelines/*.json
    _screen_timeline_script = ROOT / "scripts" / "screen_timeline.mjs"
    _captions_path = ROOT / "assets" / "captions" / "avatar_video.json"
    if _screen_timeline_script.exists() and _captions_path.exists():
        try:
            import subprocess as _sp2
            _tl_result = _sp2.run(
                ["node", str(_screen_timeline_script)],
                cwd=ROOT,
                capture_output=True, text=True,
                timeout=60,
            )
            if _tl_result.returncode == 0:
                logger.info("Screen timelines built: %s", _tl_result.stdout.strip()[-300:])
            else:
                logger.warning("Screen timeline build failed (non-fatal): %s", _tl_result.stderr[-300:])
        except Exception as exc:
            logger.warning("Screen timeline step failed (non-fatal): %s", exc)

    # ---- Step 2: Remotion ----
    try:
        logger.info("Step 2/3 — Rendering with Remotion")
        _run_remotion()
    except Exception as exc:
        duration = time.time() - start
        error_msg = f"Remotion render failed: {exc}"
        logger.error(error_msg)
        return {
            "success": False,
            "output_path": "",
            "duration_sec": round(duration, 2),
            "error": error_msg,
        }

    # ---- Step 3: Speed-up ----
    try:
        logger.info("Step 3/3 — Applying %.2f× speed-up with ffmpeg", SPEED_FACTOR)
        _run_speed_up()
    except Exception as exc:
        duration = time.time() - start
        error_msg = f"Speed-up step failed: {exc}"
        logger.error(error_msg)
        return {
            "success": False,
            "output_path": str(FINAL_REEL),
            "duration_sec": round(duration, 2),
            "error": error_msg,
        }

    # ---- Step 4: Thumbnail append (optional) ----
    if THUMBNAIL_PNG.exists():
        try:
            logger.info("Step 4/4 — Appending thumbnail.png as last frame for YouTube Shorts")
            print("▶ Appending thumbnail as last frame (YouTube Shorts thumbnail trick)...")
            _append_thumbnail(FINAL_REEL_FAST, THUMBNAIL_PNG)
            print("✓ Thumbnail appended — select last frame in YouTube as thumbnail")
        except Exception as exc:
            logger.warning("Thumbnail append failed (non-fatal): %s", exc)
            print(f"⚠ Thumbnail append failed — video still valid: {exc}")
    else:
        logger.info("No thumbnail.png found at %s — skipping thumbnail append", THUMBNAIL_PNG)

    duration = time.time() - start
    logger.info(
        "Stage 5 complete in %.1fs — original: %s | fast: %s",
        duration, FINAL_REEL, FINAL_REEL_FAST,
    )

    return {
        "success": True,
        "output_path": str(FINAL_REEL_FAST),
        "output_path_original": str(FINAL_REEL),
        "duration_sec": round(duration, 2),
        "error": None,
    }


# ---------------------------------------------------------------------------
# Standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = run_stage5()
    print(json.dumps(result, indent=2))
    if result["success"]:
        # Always run social copy generation after a successful compose
        try:
            sys.path.insert(0, str(ROOT))
            from stages.stage8_social import run_stage8
            print("\n▶ Stage 8: Generating social media copy...")
            r8 = run_stage8()
            print("✓ Stage 8: Social copy written to assets/social/") if r8["success"] else print(f"✗ Stage 8 failed: {r8.get('error')}")
        except Exception as _e:
            print(f"⚠ Stage 8 skipped: {_e}")
    sys.exit(0 if result["success"] else 1)
