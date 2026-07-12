#!/usr/bin/env python3
"""reel — one entrypoint for the short-form production system.

Usage:
    reel.py list                                  # formats + status + slots
    reel.py decide "For scripting: X is bad..."   # which format fits this script
    reel.py make <format> --avatar A.mp4 [--captions C.json] [--out O.mp4] [--no-finish]
    reel.py finish <video.mp4>                    # 1.3x speed + thumbnail end-card
    reel.py bg <style>                            # background replace (studio|warm|blue|teal|image)
    reel.py transcribe <video> <out.json>         # ElevenLabs Scribe words
    reel.py capture <demo-keys...>                # public-page screen demos
    reel.py analyze <instagram-url>               # download + frames + transcript of a reference reel

The long-form 10-section pipeline stays `python3 pipeline.py ...`.
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
PY = sys.executable


def cmd_list(_args) -> int:
    from formats.registry import REGISTRY
    print(f"{'format':<14} {'status':<11} {'type':<11} {'slot':<16} script pattern")
    for f in REGISTRY.values():
        print(f"{f.key:<14} {f.status:<11} {f.content_type:<11} {f.calendar_slot:<16} {f.script_pattern}")
    return 0


def cmd_decide(args) -> int:
    from formats.registry import decide, REGISTRY
    ranked = decide(args.text)
    if not ranked:
        print("no board/list shape detected → talking-head: viral_15s (short) or pipeline.py (long-form)")
        return 0
    for key, hits in ranked:
        f = REGISTRY[key]
        print(f"{key}  (shape hits: {hits})  — {f.description}")
    return 0


def cmd_make(args) -> int:
    from formats.registry import get_builder, REGISTRY
    if args.format not in REGISTRY:
        print(f"unknown format {args.format!r} — see `reel.py list`")
        return 2
    avatar = Path(args.avatar)
    captions = Path(args.captions) if args.captions else None
    out = Path(args.out) if args.out else ROOT / "assets" / "final" / f"{args.format}.mp4"
    build = get_builder(args.format)
    build(avatar, captions, out)
    print(f"composited → {out}")
    if not args.no_finish:
        from core.finish import finish
        final = finish(out)
        print(f"finished  → {final}")
    return 0


def cmd_finish(args) -> int:
    from core.finish import finish
    print(finish(Path(args.video)))
    return 0


def cmd_bg(args) -> int:
    cmd = [PY, str(ROOT / "editing" / "replace_background.py"), "--style", args.style]
    if args.bg_image:
        cmd += ["--bg-image", args.bg_image]
    return subprocess.call(cmd)


def cmd_transcribe(args) -> int:
    return subprocess.call([PY, str(ROOT / "speech" / "transcribe_elevenlabs.py"),
                            args.video, "--output", args.out])


def cmd_capture(args) -> int:
    return subprocess.call(["node", str(ROOT / "capture" / "record_tool_demos.mjs"), *args.keys])


def cmd_capture_url(args) -> int:
    cmd = ["node", str(ROOT / "capture" / "record_url.mjs"), args.url,
           "--name", args.name, "--secs", str(args.secs)]
    if args.login:
        cmd.append("--login")
    if args.actions:
        cmd += ["--actions", args.actions]
    return subprocess.call(cmd)


def cmd_analyze(args) -> int:
    return subprocess.call([PY, str(ROOT / "capture" / "analyze_reference.py"), args.url])


def cmd_looks(_args) -> int:
    from core.looks import LOOKS
    print(f"{'look':<24} {'angle':<6} {'crop':<10} setting / formats")
    for l in LOOKS.values():
        crop = l.crop or "UNVERIFIED"
        print(f"{l.key:<24} {l.angle:<6} {crop:<10} {l.setting}")
        print(f"{'':<42} → {', '.join(l.formats)}")
    return 0


def cmd_render(args) -> int:
    """HeyGen render with a registered look. COSTS CREDITS — requires --yes."""
    if not args.yes:
        print("HeyGen renders cost credits. Re-run with --yes to confirm the spend.")
        return 2
    from core.looks import get as get_look
    from formats.viral_15s import submit_heygen, poll_heygen, download, env
    look = get_look(args.look)
    text = Path(args.script_file).read_text() if args.script_file else args.text
    if not text:
        print("need --text or --script-file")
        return 2
    api_key = env("HEYGEN_API_KEY")
    voice = env("HEYGEN_VOICE_ID")
    vid = submit_heygen(text, api_key, look.avatar_id, voice)
    url = poll_heygen(vid, api_key)
    out = Path(args.out) if args.out else ROOT / "assets" / "avatar" / "avatar_video.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    bg = out.with_name("avatar_video_bg.mp4")
    if bg.exists():
        bg.unlink()          # stale-guard: force fresh background pass
    download(url, out)
    print(f"rendered look={look.key} → {out}")
    if look.crop is None:
        print("NOTE: this look's crop is UNVERIFIED — extract a test frame and add "
              "a preset to core/framing.py + core/looks.py before compositing.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="reel", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list").set_defaults(fn=cmd_list)

    d = sub.add_parser("decide"); d.add_argument("text"); d.set_defaults(fn=cmd_decide)

    m = sub.add_parser("make")
    m.add_argument("format")
    m.add_argument("--avatar", required=True)
    m.add_argument("--captions")
    m.add_argument("--out")
    m.add_argument("--no-finish", action="store_true")
    m.set_defaults(fn=cmd_make)

    f = sub.add_parser("finish"); f.add_argument("video"); f.set_defaults(fn=cmd_finish)

    b = sub.add_parser("bg")
    b.add_argument("style", choices=["studio", "warm", "blue", "teal", "image"])
    b.add_argument("--bg-image")
    b.set_defaults(fn=cmd_bg)

    t = sub.add_parser("transcribe")
    t.add_argument("video"); t.add_argument("out"); t.set_defaults(fn=cmd_transcribe)

    c = sub.add_parser("capture")
    c.add_argument("keys", nargs="*"); c.set_defaults(fn=cmd_capture)

    cu = sub.add_parser("capture-url")
    cu.add_argument("url")
    cu.add_argument("--name", default="demo")
    cu.add_argument("--secs", type=float, default=10)
    cu.add_argument("--login", action="store_true")
    cu.add_argument("--actions", default="")
    cu.set_defaults(fn=cmd_capture_url)

    a = sub.add_parser("analyze"); a.add_argument("url"); a.set_defaults(fn=cmd_analyze)

    lk = sub.add_parser("looks"); lk.set_defaults(fn=cmd_looks)

    r = sub.add_parser("render")
    r.add_argument("look")
    r.add_argument("--text")
    r.add_argument("--script-file")
    r.add_argument("--out")
    r.add_argument("--yes", action="store_true", help="confirm HeyGen credit spend")
    r.set_defaults(fn=cmd_render)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
