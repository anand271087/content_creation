"""
pipeline.py — Master orchestrator for the Viral Reel Automation Pipeline.
@automatewithanand | automatewithanand
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.resolve()
STATE_FILE = PROJECT_ROOT / "pipeline_state.json"
LOG_FILE = PROJECT_ROOT / "logs" / "pipeline.log"

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging setup — both stdout and file
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("pipeline")

# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


VIDEO_DSSCL_PASS = 9.0        # stage6 threshold
MAX_PIPELINE_ITERATIONS = 3   # outer loop: script → render → analyse → repeat


def _new_state(topic: str | None, transcript: str | None) -> dict:
    return {
        "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "topic": topic or "",
        "transcript": transcript or "",
        "stage1_complete": False,
        "stage2_complete": False,
        "stage3_complete": False,
        "stage4_complete": False,
        "stage5_complete": False,
        "stage6_passed": False,
        "stage8_complete": False,
        "pipeline_iteration": 1,
        "script_path": "assets/script_data.json",
        "broll_paths": {},
        "avatar_path": None,
        "music_paths": {},
        "video_analysis": None,
        "error": None,
    }


def load_state() -> dict | None:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read pipeline_state.json: %s", exc)
    return None


def save_state(state: dict) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
    except OSError as exc:
        logger.error("Failed to save pipeline_state.json: %s", exc)


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

_current_state: dict | None = None


def _sigint_handler(signum, frame):  # noqa: ANN001
    logger.info("Received SIGINT — saving pipeline state before exit.")
    if _current_state is not None:
        save_state(_current_state)
    print("\nPipeline paused. Re-run to resume.")
    sys.exit(0)


signal.signal(signal.SIGINT, _sigint_handler)

# ---------------------------------------------------------------------------
# Stage runner helpers
# ---------------------------------------------------------------------------


def _run_stage(label: str, fn, **kwargs) -> dict:
    """
    Execute a stage function, measure elapsed time, and return a normalised
    result dict: {"success": bool, "output_path": str|None, "duration_sec": float, "error": str|None}
    """
    print(f"▶ {label}...")
    t0 = time.monotonic()
    try:
        result = fn(**kwargs) if kwargs else fn()
        elapsed = time.monotonic() - t0

        # Normalise result — stage functions must return a dict with at least
        # {"success": bool}.  We fill in missing keys gracefully.
        if not isinstance(result, dict):
            result = {"success": bool(result)}

        result.setdefault("output_path", None)
        result.setdefault("duration_sec", elapsed)
        result.setdefault("error", None)

        if result["success"]:
            print(f"✓ {label} ({result['duration_sec']:.1f}s)")
            logger.info("%s completed in %.1fs", label, result["duration_sec"])
        else:
            err = result.get("error") or "unknown error"
            print(f"✗ {label} failed — {err}")
            logger.error("%s failed: %s", label, err)

        return result

    except Exception as exc:  # noqa: BLE001
        elapsed = time.monotonic() - t0
        err = str(exc)
        print(f"✗ {label} failed — {err}")
        logger.exception("%s raised an exception", label)
        return {"success": False, "output_path": None, "duration_sec": elapsed, "error": err}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline.py",
        description="Viral Reel Automation Pipeline — @automatewithanand",
    )

    source = parser.add_mutually_exclusive_group()
    source.add_argument("--topic", metavar="TOPIC", help="Topic string for script generation")
    source.add_argument(
        "--transcript",
        metavar="FILE",
        help="Path to a transcript file (Stage 1 will adapt it into a script)",
    )
    source.add_argument(
        "--script",
        metavar="FILE",
        help="Path to an already-generated script_data.json (skips Stage 1)",
    )
    source.add_argument(
        "--research-json",
        metavar="FILE",
        help="Path to a research JSON (schema_version 1.0) — extracts topic, hook_angle, why, outlier_ref and feeds them to Stage 1",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run Stage 1 only, print the script JSON, then exit",
    )
    parser.add_argument(
        "--skip-broll",
        action="store_true",
        help="Skip Stage 2 — reuse existing b-roll assets",
    )
    parser.add_argument(
        "--skip-avatar",
        action="store_true",
        help="Skip Stage 3 — reuse existing avatar video",
    )
    parser.add_argument(
        "--skip-music",
        action="store_true",
        help="Skip Stage 4 — reuse existing music tracks",
    )
    parser.add_argument(
        "--skip-social",
        action="store_true",
        help="Skip Stage 8 — skip social media copy generation",
    )
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Skip Stage 6 (viral DSSCL video analysis) — needed for Authority/Conversion content",
    )

    return parser


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def main() -> int:
    global _current_state  # noqa: PLW0603

    parser = _build_parser()
    args = parser.parse_args()

    # At least one source is required (unless --script is provided)
    if not any([args.topic, args.transcript, args.script, args.research_json]):
        parser.error("Provide one of --topic, --transcript, --script, or --research-json.")

    # ------------------------------------------------------------------
    # Load research JSON if provided — extract topic + context
    # ------------------------------------------------------------------
    research_context: dict | None = None
    if args.research_json:
        rj_path = Path(args.research_json)
        if not rj_path.exists():
            print(f"Error: research JSON not found: {args.research_json}")
            return 1
        try:
            rj = json.loads(rj_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"Error: could not parse research JSON: {exc}")
            return 1
        # Extract topic — required field
        if not rj.get("topic"):
            print("Error: research JSON has no 'topic' field.")
            return 1
        args.topic = rj["topic"]
        # Build research context from optional enrichment fields
        research_context = {
            "hook_angle": rj.get("hook_angle"),
            "why": rj.get("why"),
            "outlier_ref": rj.get("outlier_ref"),
            "backup_topics": rj.get("backup_topics", []),
            "signal_strength": rj.get("signal_strength"),
        }
        logger.info("Loaded research JSON: topic=%r hook_angle=%s signal=%s",
                    args.topic, research_context["hook_angle"], research_context["signal_strength"])
        print(f"Research JSON loaded — topic: {args.topic}")

    # ------------------------------------------------------------------
    # Lazy imports — avoids paying the cost if dependencies aren't installed
    # ------------------------------------------------------------------
    try:
        from stages.stage1_script import run_stage1
        from stages.stage2_broll import run_stage2
        from stages.stage3_avatar import run_stage3
        from stages.stage4_music import run_stage4
        from stages.stage5_compose import run_stage5
        from stages.stage6_analyse import run_stage6
        from stages.stage7_learnings import run_stage7
        from stages.stage8_social import run_stage8
        from scripts.pre_evaluate_script import run_pre_evaluate
        from scripts.check_broll_quality import check_broll_quality
        from scripts.generate_diagrams import run_generate_diagrams
    except ImportError as exc:
        logger.error("Could not import stage module: %s", exc)
        print(f"Error: {exc}")
        return 1

    pipeline_start = time.monotonic()

    # ------------------------------------------------------------------
    # Determine effective topic/transcript for state matching
    # ------------------------------------------------------------------
    effective_topic: str = args.topic or ""
    effective_transcript: str = ""
    if args.transcript:
        tp = Path(args.transcript)
        if not tp.exists():
            print(f"Error: transcript file not found: {args.transcript}")
            return 1
        # Read file contents — stage1 expects the transcript TEXT, not the path
        effective_transcript = tp.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # Crash recovery — try to resume if topic matches
    # ------------------------------------------------------------------
    existing_state = load_state()
    if (
        existing_state
        and not args.script  # --script always starts fresh
        and (
            (effective_topic and existing_state.get("topic") == effective_topic)
            or (effective_transcript and existing_state.get("transcript") == effective_transcript)
        )
    ):
        state = existing_state
        logger.info("Resuming run_id=%s from previous state.", state["run_id"])
        print(f"Resuming pipeline run {state['run_id']} from saved state.")

        # ------------------------------------------------------------------
        # Stale-asset guard: if script_data.json is newer than avatar/broll,
        # the script was regenerated after those assets were built — they must
        # be re-generated to match the new script. Reset their stage flags.
        # ------------------------------------------------------------------
        script_file = Path(state.get("script_path", "assets/script_data.json"))
        if script_file.exists() and state.get("stage1_complete"):
            script_mtime = script_file.stat().st_mtime

            # Check avatar
            avatar_path = state.get("avatar_path")
            if avatar_path and Path(avatar_path).exists():
                if script_mtime > Path(avatar_path).stat().st_mtime:
                    logger.warning(
                        "script_data.json is newer than avatar_video.mp4 — deleting stale avatar and resetting Stage 3."
                    )
                    print("⚠ Avatar is stale — deleting and will re-generate.")
                    try:
                        Path(avatar_path).unlink()
                    except OSError as e:
                        logger.warning("Could not delete stale avatar: %s", e)
                    state["stage3_complete"] = False
                    state["avatar_path"] = None

            # Check broll — delete and reset any individual clip older than the script
            broll_paths = state.get("broll_paths", {})
            stale_broll = [
                (sid, p) for sid, p in broll_paths.items()
                if p and Path(p).exists() and script_mtime > Path(p).stat().st_mtime
            ]
            if stale_broll:
                stale_ids = [sid for sid, _ in stale_broll]
                logger.warning(
                    "script_data.json is newer than %d broll clip(s) — deleting stale clips and resetting Stage 2: %s",
                    len(stale_broll), stale_ids,
                )
                print(f"⚠ {len(stale_broll)} broll clip(s) are stale — deleting and will re-generate.")
                for sid, p in stale_broll:
                    try:
                        Path(p).unlink()
                        del state["broll_paths"][sid]
                    except OSError as e:
                        logger.warning("Could not delete stale broll %s: %s", sid, e)
                state["stage2_complete"] = False

            # Stage 5 (compose) must always re-run if avatar or broll were reset
            if not state.get("stage3_complete") or not state.get("stage2_complete"):
                state["stage5_complete"] = False
                state["stage6_passed"] = False

            save_state(state)
    else:
        state = _new_state(effective_topic, effective_transcript)
        logger.info("Starting new pipeline run_id=%s", state["run_id"])

    _current_state = state

    # ------------------------------------------------------------------
    # Override state with --skip-* flags
    # ------------------------------------------------------------------
    if args.skip_broll:
        state["stage2_complete"] = True
        logger.info("--skip-broll: marking Stage 2 as complete.")

    if args.skip_avatar:
        state["stage3_complete"] = True
        logger.info("--skip-avatar: marking Stage 3 as complete.")

    if args.skip_music:
        state["stage4_complete"] = True
        logger.info("--skip-music: marking Stage 4 as complete.")

    # ------------------------------------------------------------------
    # Stage 1 — Script Generation
    # ------------------------------------------------------------------
    if args.script:
        # User supplied a pre-generated script — skip Stage 1 entirely
        script_path = args.script
        if not Path(script_path).exists():
            print(f"Error: script file not found: {script_path}")
            return 1
        state["script_path"] = script_path
        state["stage1_complete"] = True
        logger.info("Using supplied script: %s", script_path)
        print(f"Using pre-generated script: {script_path}")
        save_state(state)

    elif not state["stage1_complete"]:
        stage1_kwargs: dict = {}
        if args.topic:
            stage1_kwargs["topic"] = args.topic
        elif args.transcript:
            stage1_kwargs["transcript"] = effective_transcript  # already file contents
        if research_context:
            stage1_kwargs["research_context"] = research_context

        result1 = _run_stage("Stage 1: Generating script", run_stage1, **stage1_kwargs)

        if not result1["success"]:
            state["error"] = result1["error"]
            save_state(state)
            logger.error("Stage 1 failed — aborting pipeline.")
            return 1

        state["stage1_complete"] = True
        if result1.get("output_path"):
            state["script_path"] = result1["output_path"]
        save_state(state)

    else:
        logger.info("Stage 1 already complete — skipping.")
        print("✓ Stage 1: Script already exists — skipping.")

    # ------------------------------------------------------------------
    # Script Pre-Evaluation — cheap text check BEFORE spending on HeyGen/Kie.ai
    # Loops Stage 1 up to MAX_PRE_EVAL_ITERATIONS if script doesn't pass.
    # ------------------------------------------------------------------
    if not args.script:  # skip pre-eval if user supplied a pre-built script
        MAX_PRE_EVAL_ITERATIONS = 3
        for pre_eval_iter in range(1, MAX_PRE_EVAL_ITERATIONS + 1):
            print(f"\n── Pre-Evaluation: Checking script before spending on broll/avatar (attempt {pre_eval_iter}/{MAX_PRE_EVAL_ITERATIONS}) ──")
            pre_result = _run_stage("Pre-Eval: Script quality check", run_pre_evaluate)

            if not pre_result["success"]:
                logger.warning("Pre-eval failed to run: %s — skipping and proceeding", pre_result.get("error"))
                break

            score = pre_result.get("score", 0)
            issues = pre_result.get("issues", [])
            print(f"  Pre-Eval Score: {score:.2f} | Issues: {len(issues)}")
            for issue in issues:
                print(f"    ✗ {issue}")

            if pre_result.get("passed"):
                print(f"  ✓ Script passed pre-evaluation ({score:.2f}) — proceeding to broll/avatar")
                break

            if pre_eval_iter >= MAX_PRE_EVAL_ITERATIONS:
                logger.warning("Script did not pass pre-eval after %d attempts (score %.2f) — proceeding anyway", MAX_PRE_EVAL_ITERATIONS, score)
                print(f"  ⚠ Pre-eval score {score:.2f} after {MAX_PRE_EVAL_ITERATIONS} attempts — proceeding with best script")
                break

            # Regenerate script with pre-eval feedback
            print(f"  Script needs improvement — regenerating (attempt {pre_eval_iter + 1})...")
            state["stage1_complete"] = False
            save_state(state)

            pre_eval_kwargs: dict = {"video_feedback": {
                "dsscl_scores": pre_result.get("dsscl_scores", {}),
                "script_feedback": pre_result.get("feedback", ""),
                "weaknesses": issues,
                "pipeline_iteration": pre_eval_iter,
            }}
            if args.topic:
                pre_eval_kwargs["topic"] = args.topic
            elif args.transcript:
                pre_eval_kwargs["transcript"] = effective_transcript
            if research_context:
                pre_eval_kwargs["research_context"] = research_context

            result1 = _run_stage(f"Stage 1 (pre-eval {pre_eval_iter + 1}): Regenerating script", run_stage1, **pre_eval_kwargs)
            if not result1["success"]:
                logger.error("Stage 1 re-run during pre-eval failed: %s", result1.get("error"))
                break
            state["stage1_complete"] = True
            state["script_path"] = result1.get("output_path", state["script_path"])
            save_state(state)

    # --dry-run: print script and exit
    if args.dry_run:
        script_path = state.get("script_path", "assets/script_data.json")
        try:
            with open(script_path, "r", encoding="utf-8") as fh:
                script_json = json.load(fh)
            print("\n" + "=" * 60)
            print("DRY RUN — Script JSON:")
            print("=" * 60)
            print(json.dumps(script_json, indent=2, ensure_ascii=False))
        except OSError:
            print(f"(Could not read script file: {script_path})")
        return 0

    # ------------------------------------------------------------------
    # Stage 2a — Text card generation (serial, before all other broll)
    # Generates Excalidraw numbered-list cards → PNG → Kling I2V → .mp4
    # for sections with broll_type="text_card"
    # ------------------------------------------------------------------
    import subprocess as _sp
    import json as _json
    _script_path = Path(state.get("script_path", "assets/script_data.json"))
    _script_data = _json.loads(_script_path.read_text()) if _script_path.exists() else {}
    _text_card_sections = [s for s in _script_data.get("sections", []) if s.get("broll_type") == "text_card"]
    if _text_card_sections:
        print(f"\n▶ Stage 2a: Generating {len(_text_card_sections)} text card(s)...")
        from scripts.generate_text_cards import run as _run_text_cards
        _tc_result = _run_text_cards(_script_data)
        if _tc_result.get("failed"):
            print(f"⚠ Stage 2a: {len(_tc_result['failed'])} text card(s) failed: {_tc_result['failed']}")
        else:
            print(f"✓ Stage 2a: {len(_tc_result.get('generated', []))} text card(s) generated")

    # ------------------------------------------------------------------
    # Stage 2b — Diagram generation (serial, before parallel stages)
    # Generates Excalidraw JSON + PNG for sections with broll_type="diagram"
    # ------------------------------------------------------------------
    _diagram_sections = [s for s in _script_data.get("sections", []) if s.get("broll_type") == "diagram"]
    if _diagram_sections:
        print(f"\n▶ Stage 2b: Generating {len(_diagram_sections)} diagram(s)...")
        _diag_result = run_generate_diagrams(_script_data)
        if _diag_result.get("generated"):
            # Render .excalidraw → PNG using Playwright
            _render_cmd = ["node", "render_diagram.mjs"]
            _render_result = _sp.run(_render_cmd, cwd=PROJECT_ROOT / "remotion", capture_output=True, text=True)
            if _render_result.returncode != 0:
                logger.warning("Diagram render failed: %s", _render_result.stderr[-500:])
                print(f"⚠ Diagram render failed — broll clips used as fallback")
            else:
                print(f"✓ Stage 2b: {len(_diag_result['generated'])} diagram(s) rendered")

    # ------------------------------------------------------------------
    # Stage 2b.5 — Choreography generation (serial, before screen capture)
    # Calls Claude API to auto-generate cursor_steps[] for broll_type="screen" sections
    # ------------------------------------------------------------------
    _screen_sections = [s for s in _script_data.get("sections", []) if s.get("broll_type") == "screen"]
    if _screen_sections:
        _needs_choreo = [s for s in _screen_sections if not s.get("screen_capture", {}).get("cursor_steps")]
        if _needs_choreo:
            print(f"\n▶ Stage 2b.5: Generating choreography for {len(_needs_choreo)} screen section(s)...")
            _choreo_result = _sp.run(
                ["node", "scripts/screen_choreography.mjs"],
                cwd=PROJECT_ROOT,
                capture_output=True, text=True,
                timeout=120,
            )
            if _choreo_result.returncode != 0:
                logger.warning("Choreography generation failed: %s", _choreo_result.stderr[-500:])
                print(f"⚠ Stage 2b.5: Choreography failed — screen sections use static screenshots")
            else:
                print(f"✓ Stage 2b.5: Choreography generated")
                # Reload script_data with freshly generated cursor_steps
                _script_data = _json.loads(_script_path.read_text()) if _script_path.exists() else _script_data

    # Stage 2c — Screen broll capture (serial, before parallel stages)
    # Playwright navigates through cursor_steps, saves clean PNGs + fallback video
    # ------------------------------------------------------------------
    _screen_sections = [s for s in _script_data.get("sections", []) if s.get("broll_type") == "screen"]
    if _screen_sections:
        print(f"\n▶ Stage 2c: Capturing {len(_screen_sections)} screen broll(s)...")
        _screen_result = _sp.run(
            ["node", "scripts/screen_broll.mjs"],
            cwd=PROJECT_ROOT,
            capture_output=True, text=True,
            timeout=300,
        )
        if _screen_result.returncode != 0:
            logger.warning("Screen broll capture failed: %s", _screen_result.stderr[-500:])
            print(f"⚠ Stage 2c: Screen capture failed — sections fall back to Kling generation")
        else:
            print(f"✓ Stage 2c: Screen broll captured")

    # Stage 2c.5 — Terminal broll capture (serial, Playwright renders local HTML terminal)
    # Playwright opens terminal_renderer.html, types command, streams output, saves 5 PNGs
    # ------------------------------------------------------------------
    _terminal_sections = [s for s in _script_data.get("sections", []) if s.get("broll_type") == "terminal"]
    if _terminal_sections:
        print(f"\n▶ Stage 2c.5: Rendering {len(_terminal_sections)} terminal broll(s)...")
        _terminal_result = _sp.run(
            ["node", "scripts/run_terminal_demo.mjs"],
            cwd=PROJECT_ROOT,
            capture_output=True, text=True,
            timeout=180,
        )
        if _terminal_result.returncode != 0:
            logger.warning("Terminal broll render failed: %s", _terminal_result.stderr[-500:])
            print(f"⚠ Stage 2c.5: Terminal render failed:\n{_terminal_result.stdout[-300:]}")
        else:
            print(f"✓ Stage 2c.5: Terminal broll rendered")
            if _terminal_result.stdout:
                for _line in _terminal_result.stdout.strip().split('\n')[-5:]:
                    print(f"  {_line}")

    # ------------------------------------------------------------------
    # Stage 2d — Hyperframes motion-graphic brolls for "clip" sections
    # Replaces Kling AI: renders animated motion graphics locally via GSAP/Chromium
    # Each clip section gets a template-driven MP4 (hook, trigger, body, bridge, etc.)
    # ------------------------------------------------------------------
    _clip_sections = [s for s in _script_data.get("sections", []) if s.get("broll_type") == "clip"]
    if _clip_sections and not state["stage2_complete"]:
        print(f"\n▶ Stage 2d: Rendering {len(_clip_sections)} Hyperframes broll(s)...")
        _hf_result = _sp.run(
            ["node", "scripts/generate_hyperframes_broll.mjs"],
            cwd=PROJECT_ROOT,
            timeout=600,
        )
        if _hf_result.returncode == 0:
            print(f"✓ Stage 2d: Hyperframes brolls rendered")
            state["stage2_complete"] = True
            save_state(state)
        else:
            print(f"⚠ Stage 2d: Hyperframes render failed (exit {_hf_result.returncode})")
    elif not _clip_sections and not state["stage2_complete"]:
        # No clip sections — mark Stage 2 done so Kling is not attempted
        state["stage2_complete"] = True
        save_state(state)

    # ------------------------------------------------------------------
    # Stages 2, 3, 4 — run in parallel (Kling Stage 2 skipped if Hyperframes ran)
    # ------------------------------------------------------------------
    parallel_tasks = []

    if not state["stage2_complete"]:
        # Fallback: Kling API for any clip sections Hyperframes couldn't handle
        parallel_tasks.append(("Stage 2: B-roll generation (Kling fallback)", run_stage2, "stage2_complete", "broll_paths"))
    else:
        logger.info("Stage 2 already complete — skipping.")
        print("✓ Stage 2: B-roll already exists — skipping.")

    if not state["stage3_complete"]:
        parallel_tasks.append(("Stage 3: Avatar generation", run_stage3, "stage3_complete", "avatar_path"))
    else:
        logger.info("Stage 3 already complete — skipping.")
        print("✓ Stage 3: Avatar already exists — skipping.")

    if not state["stage4_complete"]:
        parallel_tasks.append(("Stage 4: Music generation", run_stage4, "stage4_complete", "music_paths"))
    else:
        logger.info("Stage 4 already complete — skipping.")
        print("✓ Stage 4: Music already exists — skipping.")

    avatar_failed = False

    if parallel_tasks:
        logger.info("Running %d parallel stage(s).", len(parallel_tasks))

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_map = {
                executor.submit(_run_stage, label, fn): (label, state_key, output_key)
                for label, fn, state_key, output_key in parallel_tasks
            }

            for future in as_completed(future_map):
                label, state_key, output_key = future_map[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
                    result = {"success": False, "output_path": None, "duration_sec": 0.0, "error": str(exc)}
                    logger.exception("Unexpected error in %s", label)

                if result["success"]:
                    state[state_key] = True
                    # Store output path using the appropriate key shape
                    op = result.get("output_path")
                    if output_key == "avatar_path":
                        state["avatar_path"] = op
                    elif output_key in ("broll_paths", "music_paths"):
                        if isinstance(op, dict):
                            state[output_key] = op
                        elif op:
                            # stage returned a single path string — store as-is
                            state[output_key] = op
                else:
                    state["error"] = result.get("error")
                    if state_key == "stage3_complete":
                        avatar_failed = True
                        logger.error("Avatar generation failed — Stage 5 will be blocked.")

                save_state(state)

    # ------------------------------------------------------------------
    # Broll Quality Check — fix bad clips BEFORE the expensive Remotion render
    # ------------------------------------------------------------------
    # Broll quality check — only runs for Kling-generated clips.
    # Hyperframes clips are motion graphics (intentionally small files, brand-consistent)
    # and must never be flagged or regenerated via Kling.
    if state.get("stage2_complete") and not avatar_failed:
        import json as _json
        _sd = _json.loads(Path(args.script or "assets/script_data.json").read_text()) if Path(args.script or "assets/script_data.json").exists() else {}
        _clip_sections = {s["id"] for s in _sd.get("sections", []) if s.get("broll_type") == "clip"}
        _hf_dir = Path("hyperframes-templates")
        _hf_rendered = set()
        for sid in _clip_sections:
            mp4 = Path(f"assets/broll/{sid}.mp4")
            # Hyperframes clips are typically 100-800KB depending on section length; Kling clips are 1-3MB
            if mp4.exists() and mp4.stat().st_size < 900_000:
                _hf_rendered.add(sid)
        _kling_clips = _clip_sections - _hf_rendered
        if _kling_clips:
            print("\n── Broll Quality Check: Screening Kling clips for watermarks ──")
            try:
                from scripts.regenerate_broll import regenerate as regenerate_sections
                broll_check = check_broll_quality(section_ids=list(_kling_clips))
                if broll_check["success"]:
                    failed_clips = [s for s in broll_check.get("failed_sections", []) if s in _kling_clips]
                    print(f"  Broll check — {broll_check.get('pass_count', 0)} passed, {len(failed_clips)} failed")
                    if failed_clips:
                        print(f"  Failed Kling clips: {', '.join(failed_clips)} — regenerating...")
                        for sec_id in failed_clips:
                            print(f"    ↻ Regenerating {sec_id}...")
                            regenerate_sections([sec_id])
                        print("  ✓ Failed clips regenerated")
                    else:
                        print("  ✓ All Kling clips passed quality check")
                else:
                    logger.warning("Broll check failed to run: %s — skipping", broll_check.get("error"))
            except Exception as exc:
                logger.warning("Broll quality check error: %s — skipping", exc)
        else:
            print("\n── Broll Quality Check: All clips are Hyperframes — skipping Kling check ──")

    # ------------------------------------------------------------------
    # Stage 5 — Remotion Compose
    # ------------------------------------------------------------------
    if avatar_failed:
        logger.error("Skipping Stage 5: avatar generation failed (required for composition).")
        print("✗ Stage 5: Skipped — avatar generation failed (avatar is required for composition).")
        state["error"] = "Stage 5 skipped: avatar failed"
        save_state(state)
        return 1

    if not state["stage5_complete"]:
        result5 = _run_stage("Stage 5: Composing final reel", run_stage5)

        if result5["success"]:
            state["stage5_complete"] = True
            if result5.get("output_path"):
                state["final_path"] = result5["output_path"]
        else:
            state["error"] = result5.get("error")
            logger.error("Stage 5 failed: %s", result5.get("error"))

        save_state(state)
    else:
        logger.info("Stage 5 already complete — skipping.")
        print("✓ Stage 5: Final reel already exists — skipping.")

    if not state.get("stage5_complete"):
        total_elapsed = time.monotonic() - pipeline_start
        print()
        print("=" * 60)
        print(f"Pipeline failed at Stage 5 in {total_elapsed:.1f}s")
        if state.get("error"):
            print(f"Error: {state['error']}")
        print("=" * 60)
        return 1

    # ------------------------------------------------------------------
    # Stage 6 loop — Video DSSCL Analysis → regenerate if below threshold
    # ------------------------------------------------------------------
    pipeline_iteration = state.get("pipeline_iteration", 1)
    video_feedback = None

    if args.skip_analysis:
        print()
        print("── Stage 6: skipped (--skip-analysis) ──")
        logger.info("Stage 6 skipped via --skip-analysis flag.")
        state["stage6_passed"] = True
        state["video_analysis"] = None
        save_state(state)

    while not args.skip_analysis and pipeline_iteration <= MAX_PIPELINE_ITERATIONS:
        print()
        print(f"── Stage 6: Video Analysis (pipeline iteration {pipeline_iteration}/{MAX_PIPELINE_ITERATIONS}) ──")

        result6 = _run_stage("Stage 6: Analysing video", run_stage6)

        if not result6["success"]:
            logger.warning("Stage 6 analysis failed: %s — treating as passed to avoid infinite loop.", result6.get("error"))
            state["stage6_passed"] = True
            state["video_analysis"] = None
            save_state(state)
            break

        scores = result6.get("dsscl_scores", {})
        passed = result6.get("passed", False)
        final_score = scores.get("final", 0)

        state["video_analysis"] = {
            "iteration": pipeline_iteration,
            "dsscl_scores": scores,
            "passed": passed,
            "weaknesses": result6.get("weaknesses", []),
            "strengths": result6.get("strengths", []),
        }
        save_state(state)

        print(f"  Video DSSCL: D={scores.get('D',0)} Share={scores.get('Share',0)} Save={scores.get('Save',0)} C={scores.get('C',0)} L={scores.get('L',0)} → Final={final_score:.2f}")
        print(f"  Weaknesses: {', '.join(result6.get('weaknesses', [])) or 'none'}")

        if passed:
            print(f"  ✓ Video DSSCL passed ({final_score:.2f} ≥ {VIDEO_DSSCL_PASS})")
            state["stage6_passed"] = True
            save_state(state)
            break

        if pipeline_iteration >= MAX_PIPELINE_ITERATIONS:
            logger.warning(
                "Video DSSCL %.2f < %.1f after %d pipeline iterations — accepting best result.",
                final_score, VIDEO_DSSCL_PASS, MAX_PIPELINE_ITERATIONS,
            )
            print(f"  ⚠ Video DSSCL {final_score:.2f} below {VIDEO_DSSCL_PASS} after {MAX_PIPELINE_ITERATIONS} iterations — using best result.")
            state["stage6_passed"] = False
            save_state(state)
            break

        # Video didn't pass — regenerate script + avatar + broll + render
        pipeline_iteration += 1
        state["pipeline_iteration"] = pipeline_iteration
        print(f"\n  Video DSSCL {final_score:.2f} < {VIDEO_DSSCL_PASS} — regenerating script (pipeline iteration {pipeline_iteration})...")

        video_feedback = {
            "dsscl_scores": scores,
            "script_feedback": result6.get("script_feedback", ""),
            "weaknesses": result6.get("weaknesses", []),
            "pipeline_iteration": pipeline_iteration,
        }

        # Reset stages that depend on the script
        state["stage1_complete"] = False
        state["stage2_complete"] = False
        state["stage3_complete"] = False
        state["stage5_complete"] = False
        # Keep stage4 (music) — it doesn't depend on the script content
        save_state(state)

        # Stage 1 — regenerate script with video feedback
        stage1_kwargs = {"video_feedback": video_feedback}
        if args.topic:
            stage1_kwargs["topic"] = args.topic
        elif args.transcript:
            stage1_kwargs["transcript"] = effective_transcript  # already file contents

        result1 = _run_stage(
            f"Stage 1 (iteration {pipeline_iteration}): Regenerating script with video feedback",
            run_stage1, **stage1_kwargs,
        )
        if not result1["success"]:
            logger.error("Stage 1 re-run failed: %s", result1.get("error"))
            break
        state["stage1_complete"] = True
        state["script_path"] = result1.get("output_path", state["script_path"])
        save_state(state)

        # Stage 2d (re-run) — Hyperframes brolls with --force to replace previous iteration
        print(f"  Re-rendering Hyperframes brolls (iteration {pipeline_iteration})...")
        _hf_rerun = _sp.run(
            ["node", "scripts/generate_hyperframes_broll.mjs", "--force"],
            cwd=PROJECT_ROOT,
            timeout=600,
        )
        if _hf_rerun.returncode == 0:
            state["stage2_complete"] = True
            save_state(state)
        else:
            logger.warning("Hyperframes re-run failed on iteration %d", pipeline_iteration)

        # Stage 3 in parallel with nothing (avatar only — broll done above)
        print(f"  Running Avatar generation (iteration {pipeline_iteration})...")
        with ThreadPoolExecutor(max_workers=1) as executor:
            futures = {
                executor.submit(_run_stage, f"Stage 3 (iteration {pipeline_iteration}): Avatar", run_stage3, force=True): "stage3",
            }
            avatar_failed = False
            for future in as_completed(futures):
                stage_key = futures[future]
                r = future.result()
                if r["success"]:
                    state[f"{stage_key}_complete"] = True
                else:
                    logger.error("%s failed on iteration %d: %s", stage_key, pipeline_iteration, r.get("error"))
                    if stage_key == "stage3":
                        avatar_failed = True
            save_state(state)

        if avatar_failed:
            logger.error("Avatar failed on iteration %d — stopping loop.", pipeline_iteration)
            break

        # Stage 5 — re-render
        result5 = _run_stage(f"Stage 5 (iteration {pipeline_iteration}): Composing reel", run_stage5)
        if result5["success"]:
            state["stage5_complete"] = True
            if result5.get("output_path"):
                state["final_path"] = result5["output_path"]
        else:
            logger.error("Stage 5 re-run failed on iteration %d: %s", pipeline_iteration, result5.get("error"))
            state["error"] = result5.get("error")
            save_state(state)
            break

        save_state(state)
        # Loop back to Stage 6 analysis

    # ------------------------------------------------------------------
    # Stage 7 — Learning Capture (always runs, regardless of Stage 6 pass/fail)
    # ------------------------------------------------------------------
    print()
    _run_stage("Stage 7: Capturing learnings", run_stage7)

    # ------------------------------------------------------------------
    # Stage 8 — Social Media Copy
    # ------------------------------------------------------------------
    if not args.skip_social and not state.get("stage8_complete"):
        print()
        result8 = _run_stage("Stage 8: Generating social media copy", run_stage8)
        if result8["success"]:
            state["stage8_complete"] = True
            save_state(state)
    elif state.get("stage8_complete"):
        print("✓ Stage 8: Social copy already exists — skipping.")

    # ------------------------------------------------------------------
    # Final summary
    # ------------------------------------------------------------------
    total_elapsed = time.monotonic() - pipeline_start
    final_path = state.get("final_path", "assets/final/final_reel.mp4")
    video_analysis = state.get("video_analysis")

    print()
    print("=" * 60)
    if state.get("stage5_complete"):
        print(f"Pipeline complete in {total_elapsed:.1f}s")
        print(f"Output: {final_path}")
        if video_analysis:
            sc = video_analysis.get("dsscl_scores", {})
            print(f"Video DSSCL: {sc.get('final', '?'):.2f} | Passed: {video_analysis.get('passed', False)}")
        if state.get("stage8_complete"):
            print("Social copy: assets/social/ (instagram.txt, linkedin.txt, youtube.txt)")
    else:
        print(f"Pipeline finished with errors in {total_elapsed:.1f}s")
        if state.get("error"):
            print(f"Last error: {state['error']}")
    print("=" * 60)

    return 0 if state.get("stage5_complete") else 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
