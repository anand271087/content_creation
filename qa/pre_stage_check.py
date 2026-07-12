"""
pre_stage_check.py — Gate checks before running each pipeline stage.

Encodes every past mistake as an enforced rule. Run before each stage:
  python3 scripts/pre_stage_check.py --stage 1
  python3 scripts/pre_stage_check.py --stage 2
  python3 scripts/pre_stage_check.py --screen
  python3 scripts/pre_stage_check.py --stage 5

Exits 0 if all checks pass, 1 if any fail (pipeline should not proceed).
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPT_DATA = ROOT / "assets" / "script_data.json"

PASS = "  ✅"
FAIL = "  ❌"
WARN = "  ⚠️ "

errors = []
warnings = []

def ok(msg): print(f"{PASS} {msg}")
def fail(msg): print(f"{FAIL} {msg}"); errors.append(msg)
def warn(msg): print(f"{WARN} {msg}"); warnings.append(msg)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

BLOCKED_URL_PATTERNS = [
    "claude.ai",
    "/dashboard",
    "/app/",
    "/login",
    "/signin",
    "/sign-in",
    "app.make.com",
    "app.n8n.cloud",
]

def is_blocked_url(url: str) -> bool:
    return any(p in url for p in BLOCKED_URL_PATTERNS)

def load_script_data():
    if not SCRIPT_DATA.exists():
        fail("assets/script_data.json not found")
        return None
    try:
        return json.loads(SCRIPT_DATA.read_text())
    except Exception as e:
        fail(f"script_data.json is invalid JSON: {e}")
        return None


# ---------------------------------------------------------------------------
# Stage 1 — Script generation
# ---------------------------------------------------------------------------

def check_stage1(args):
    print("\n── Stage 1 pre-checks ──────────────────────────────────────")

    # Transcript or topic provided
    if args.transcript:
        tp = Path(args.transcript)
        if not tp.exists():
            fail(f"Transcript file not found: {tp}")
        elif tp.stat().st_size < 100:
            fail(f"Transcript file looks empty or too short: {tp}")
        else:
            ok(f"Transcript file exists ({tp.stat().st_size} bytes)")

    # Warn if previous script exists with same hook (reuse risk)
    if SCRIPT_DATA.exists():
        data = load_script_data()
        if data:
            prev_hook = data.get("hook_used", "")
            prev_title = data.get("title", "")
            warn(f"Previous script exists: '{prev_title}' (hook {prev_hook}). "
                 f"Tell Claude to NOT reuse hook {prev_hook}.")

    # API key present
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        fail("ANTHROPIC_API_KEY not set in environment")
    else:
        ok("ANTHROPIC_API_KEY present")


# ---------------------------------------------------------------------------
# Stage 2 — Broll generation
# ---------------------------------------------------------------------------

def check_stage2():
    print("\n── Stage 2 pre-checks ──────────────────────────────────────")

    data = load_script_data()
    if not data:
        return

    # Check for stale broll from previous run
    broll_dir = ROOT / "assets" / "broll"
    existing = list(broll_dir.glob("*.mp4")) if broll_dir.exists() else []
    if existing:
        warn(f"{len(existing)} existing broll clips found. If this is a new topic, "
             "delete them first: rm assets/broll/*.mp4")
    else:
        ok("No stale broll clips")

    # Check all screen URLs are safe
    screen_sections = [s for s in data.get("sections", []) if s.get("broll_type") == "screen"]
    for s in screen_sections:
        url = s.get("screen_capture", {}).get("url", "")
        if not url:
            fail(f"[{s['id']}] screen section has no URL")
        elif is_blocked_url(url):
            fail(f"[{s['id']}] URL will trigger bot-detection: {url}. "
                 f"Use anthropic.com/claude-code or github.com/anthropics/claude-code instead")
        else:
            ok(f"[{s['id']}] URL is safe: {url}")

    # Hyperframes availability (replaces Kling for clip sections)
    import shutil, subprocess as _sub
    _clip_secs = [s for s in data.get("sections", []) if s.get("broll_type") == "clip"]
    if _clip_secs:
        try:
            _hf = _sub.run(["npx", "hyperframes@latest", "--version"],
                           capture_output=True, text=True, timeout=15)
            if _hf.returncode == 0:
                ok(f"Hyperframes {_hf.stdout.strip()} available ({len(_clip_secs)} clip sections to render)")
            else:
                fail("hyperframes not available — run: npm install -g hyperframes")
        except Exception as e:
            warn(f"Could not check Hyperframes: {e}")
    else:
        ok("No clip sections — Hyperframes not needed")


# ---------------------------------------------------------------------------
# Screen capture (screen_choreography + screen_broll)
# ---------------------------------------------------------------------------

def check_screen():
    print("\n── Screen capture pre-checks ───────────────────────────────")

    data = load_script_data()
    if not data:
        return

    screen_sections = [s for s in data.get("sections", []) if s.get("broll_type") == "screen"]
    if not screen_sections:
        ok("No screen sections — nothing to capture")
        return

    for s in screen_sections:
        url = s.get("screen_capture", {}).get("url", "")
        sid = s["id"]

        # URL safety
        if not url:
            fail(f"[{sid}] No URL set for screen section")
        elif is_blocked_url(url):
            fail(f"[{sid}] BLOCKED URL: {url}. Replace with a public page before capturing.")
        else:
            ok(f"[{sid}] URL safe: {url}")

        # Warn if screenshots already exist (might be stale)
        existing = list((ROOT / "assets" / "screen_screenshots").glob(f"{sid}_*.png"))
        if existing:
            warn(f"[{sid}] {len(existing)} existing screenshots found — will be skipped unless deleted first")


# ---------------------------------------------------------------------------
# Stage 5 — Render
# ---------------------------------------------------------------------------

def check_stage5():
    print("\n── Stage 5 (render) pre-checks ────────────────────────────")

    data = load_script_data()
    if not data:
        return

    all_clear = True

    for s in data.get("sections", []):
        sid = s["id"]
        btype = s.get("broll_type")

        if btype == "clip":
            path = ROOT / "assets" / "broll" / f"{sid}.mp4"
            if not path.exists():
                fail(f"[{sid}] Missing broll clip: {path}")
                all_clear = False
            elif path.stat().st_size < 1000:
                fail(f"[{sid}] Broll clip is suspiciously small: {path}")
                all_clear = False
            else:
                ok(f"[{sid}] Broll clip present ({path.stat().st_size // 1024}KB)")

        elif btype == "diagram":
            png = ROOT / "assets" / "diagrams" / f"{sid}.png"
            excalidraw = ROOT / "assets" / "diagrams" / f"{sid}.excalidraw"
            if not excalidraw.exists():
                fail(f"[{sid}] Missing diagram: {excalidraw}")
                all_clear = False
            elif not png.exists():
                fail(f"[{sid}] Excalidraw exists but PNG not rendered. "
                     f"Run: node scripts/render_diagram.mjs {sid}")
                all_clear = False
            else:
                ok(f"[{sid}] Diagram PNG present ({png.stat().st_size // 1024}KB)")

        elif btype == "screen":
            f0 = ROOT / "assets" / "screen_screenshots" / f"{sid}_f0.png"
            if not f0.exists():
                fail(f"[{sid}] Missing screen screenshot: {f0}. "
                     f"Run: node scripts/screen_broll.mjs")
                all_clear = False
            elif f0.stat().st_size < 5000:
                fail(f"[{sid}] Screenshot is suspiciously small ({f0.stat().st_size}B) — "
                     "may be a blank/error page")
                all_clear = False
            else:
                ok(f"[{sid}] Screen screenshots present ({f0.stat().st_size // 1024}KB)")

        elif btype == "text_card":
            # text_card renders as a static PNG in Remotion — check for {id}_card.png
            png = ROOT / "assets" / "diagrams" / f"{sid}_card.png"
            if not png.exists():
                fail(f"[{sid}] Missing text_card PNG: {png}. "
                     f"Run: python3 scripts/generate_text_cards.py")
                all_clear = False
            elif png.stat().st_size < 5000:
                fail(f"[{sid}] Text card PNG too small ({png.stat().st_size}B)")
                all_clear = False
            else:
                ok(f"[{sid}] Text card PNG present ({png.stat().st_size // 1024}KB)")

        elif btype == "terminal":
            f0 = ROOT / "assets" / "screen_screenshots" / f"{sid}_f0.png"
            if not f0.exists():
                fail(f"[{sid}] Missing terminal screenshot: {f0}. "
                     f"Run: node scripts/run_terminal_demo.mjs")
                all_clear = False
            elif f0.stat().st_size < 5000:
                fail(f"[{sid}] Terminal screenshot suspiciously small ({f0.stat().st_size}B) — "
                     "may be blank")
                all_clear = False
            else:
                ok(f"[{sid}] Terminal screenshots present ({f0.stat().st_size // 1024}KB)")

    # Avatar video
    avatar = ROOT / "assets" / "avatar" / "avatar_video.mp4"
    if not avatar.exists():
        fail("avatar_video.mp4 not found")
    elif avatar.stat().st_size < 1_000_000:
        fail(f"avatar_video.mp4 too small ({avatar.stat().st_size} bytes) — download may have failed")
    else:
        ok(f"avatar_video.mp4 present ({avatar.stat().st_size // (1024*1024)}MB)")

    # Captions
    captions = ROOT / "assets" / "captions" / "avatar_video.json"
    if not captions.exists():
        fail("Captions not found — run Whisper first: whisper assets/avatar/avatar_video.mp4 --model medium ...")
    else:
        # Captions must be newer than avatar
        if captions.stat().st_mtime < avatar.stat().st_mtime:
            fail("Captions are OLDER than avatar video — re-run Whisper on the new avatar")
        else:
            ok(f"Captions present and newer than avatar")

    # sync_broll_to_speech check — total_duration_sec should not be a round number
    planned = data.get("total_duration_sec", 0)
    if planned in (60, 90, 120) or str(planned).endswith(".0"):
        warn(f"total_duration_sec={planned} looks like a planned value, not a Whisper-synced one. "
             "Run: python3 scripts/sync_broll_to_speech.py")
    else:
        ok(f"total_duration_sec={planned}s (Whisper-synced)")

    # Music placeholders
    music_dir = ROOT / "assets" / "music"
    required_music = ["sting1.mp3", "sting2.mp3", "sting3.mp3"]
    for m in required_music:
        mp = music_dir / m
        if not mp.exists():
            fail(f"Missing music file: {m}. Create placeholder: "
                 f"ffmpeg -f lavfi -i 'sine=frequency=1:duration=2' -c:a libmp3lame -y assets/music/{m}")
        else:
            ok(f"Music: {m} present")

    if all_clear:
        print("\n  All assets verified — safe to render ✅")
    else:
        print("\n  Fix the above issues before rendering ❌")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    parser = argparse.ArgumentParser(description="Pre-stage gate checks")
    parser.add_argument("--stage", type=int, choices=[1, 2, 5], help="Stage number to check")
    parser.add_argument("--screen", action="store_true", help="Check before screen capture")
    parser.add_argument("--transcript", type=str, help="Transcript file path (for stage 1 check)")
    args = parser.parse_args()

    if args.stage == 1:
        check_stage1(args)
    elif args.stage == 2:
        check_stage2()
    elif args.stage == 5:
        check_stage5()
    elif args.screen:
        check_screen()
    else:
        parser.print_help()
        sys.exit(1)

    print()
    if errors:
        print(f"❌ {len(errors)} error(s) found — do not proceed until fixed.")
        sys.exit(1)
    elif warnings:
        print(f"⚠️  {len(warnings)} warning(s) — review before proceeding.")
        sys.exit(0)
    else:
        print("✅ All checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
