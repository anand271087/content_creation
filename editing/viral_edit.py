"""
viral_edit.py — Package A ("Dynamic Minimalism") post-processor.

Takes a captioned reel + its word-timing JSON, applies:
  1. Zoom punches on key words (numbers, brand names, punch verbs) — 0.35s snap-in
     from 1.0× to 1.08×, then snap back
  2. Slow ramp-in punch during a chosen "reveal" beat (auto-selected as the beat
     covering seconds 3–10 of the reel by default)

Output: assets/final/<basename>_edited.mp4

Usage:
    python3 scripts/viral_edit.py                                     # edits viral_15s
    python3 scripts/viral_edit.py --input assets/final/some.mp4 \
                                  --captions assets/captions/some.json
    python3 scripts/viral_edit.py --dry-run                           # prints picks, no encode
"""
from __future__ import annotations
import argparse, json, logging, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "assets" / "final" / "viral_15s.mp4"
DEFAULT_CAPS  = ROOT / "assets" / "captions" / "viral_15s.json"

FPS = 30
PUNCH_ZOOM   = 1.08          # zoom factor at peak of punch
PUNCH_HOLD   = 0.35          # seconds each punch is held
PUNCH_MIN_GAP = 1.8          # min seconds between two punches
MAX_PUNCHES  = 6             # cap to avoid gimmicky "everything is zoomed"

REVEAL_RAMP_ZOOM = 1.05      # gentle ramp during the reveal beat
REVEAL_BEAT_START = 3.0      # sec — default start of the reveal beat
REVEAL_BEAT_END   = 10.0     # sec — default end of the reveal beat

# Word scoring — pick words that DESERVE a punch (numbers, brand names, punch words)
NUMERIC_WORDS = {
    "zero","one","two","three","four","five","six","seven","eight","nine","ten",
    "eleven","twelve","thirteen","twenty","thirty","forty","fifty","hundred",
    "thousand","million","billion","half","double","triple","dozens","hundreds",
    "twenty-four","twenty-four","forty-two",
}
BRAND_WORDS = {
    "openai","gpt","terra","sol","luna","heygen","elevenlabs","claude","mythos",
    "anthropic","chatgpt","gemini","codex","cursor","copilot","perplexity",
}
PUNCH_WORDS = {
    "craziest","never","always","actually","exactly","every","single","real",
    "just","only","free","paid","fake","real","live","today","tonight","forever",
    "instantly","completely","immediately","zero","tons","massive","huge",
    "cheaper","cheapest","half","double","affordable","expensive",
    "hours","minutes","seconds","days","weeks","months","years",
    "family","freedom","business","money","time","life",
    "ai","avatar","agents","agent","automation","automated",
}
STOP_WORDS = {
    "a","an","the","and","or","but","if","of","for","to","in","on","at","by",
    "with","from","as","is","are","was","were","be","been","am","i","you","he",
    "she","it","we","they","this","that","these","those","my","your","his","her",
    "our","their","because","so","that's","it's","i'm","you're","gonna","going",
}


def clean_word(w: str) -> str:
    """Lowercase, strip punctuation."""
    return re.sub(r"[^a-z0-9\-]", "", w.lower())


def score_word(w: str) -> int:
    """Score a word by punch-worthiness. Higher = more likely to zoom-punch."""
    c = clean_word(w)
    if not c or c in STOP_WORDS: return 0
    score = 0
    if any(ch.isdigit() for ch in c): score += 8
    if c in NUMERIC_WORDS:  score += 6
    if c in BRAND_WORDS:    score += 7
    if c in PUNCH_WORDS:    score += 4
    if c.endswith("est"):   score += 2   # superlatives ("craziest", "biggest")
    if len(c) >= 8:         score += 1
    return score


def load_words(caps_json: Path) -> list[dict]:
    data = json.loads(caps_json.read_text())
    out = []
    for seg in data.get("segments", []):
        for w in seg.get("words", []) or []:
            t = (w.get("word") or w.get("text") or "").strip()
            if not t: continue
            try:
                out.append({"word": t, "start": float(w["start"]), "end": float(w["end"])})
            except (KeyError, TypeError, ValueError):
                continue
    return out


def pick_punches(words: list[dict]) -> list[tuple[float, float]]:
    """Return list of (start, end) time ranges for each punch."""
    scored = [(score_word(w["word"]), w) for w in words]
    scored.sort(key=lambda x: -x[0])
    picks: list[dict] = []
    for score, w in scored:
        if score <= 0: continue
        # respect min gap from any already-picked word
        if any(abs(w["start"] - p["start"]) < PUNCH_MIN_GAP for p in picks): continue
        picks.append(w)
        if len(picks) >= MAX_PUNCHES: break
    picks.sort(key=lambda p: p["start"])
    # convert to (start, end) with fixed hold
    return [(p["start"], p["start"] + PUNCH_HOLD, p["word"]) for p in picks]


def build_zoompan_expr(punches: list[tuple[float, float, str]],
                       reveal_start: float, reveal_end: float) -> str:
    """Build a per-frame zoom expression combining punches + reveal ramp.

    Frames use `on` (frame index). We convert to seconds via on/FPS.
    """
    t = f"(on/{FPS})"
    # Punches: each punch is a discrete rectangle (1.08 zoom during window, else 1.0)
    parts = []
    for s, e, _ in punches:
        parts.append(f"between({t}\\,{s:.2f}\\,{e:.2f})*{PUNCH_ZOOM - 1:.4f}")
    punch_bump = " + ".join(parts) if parts else "0"

    # Reveal ramp: gentle linear 1.0 → 1.05 across the reveal beat, then hold, then release
    ramp_slope = REVEAL_RAMP_ZOOM - 1  # 0.05
    reveal_bump = (
        f"if(between({t}\\,{reveal_start:.2f}\\,{reveal_end:.2f})\\,"
        f"({ramp_slope:.4f}*({t}-{reveal_start:.2f})/{reveal_end - reveal_start:.2f})\\,0)"
    )

    return f"1.0 + ({punch_bump}) + ({reveal_bump})"


def run_ffmpeg(input_mp4: Path, out_mp4: Path, zoom_expr: str,
               width: int, height: int) -> None:
    # zoompan with d=1 = single-frame duration per input frame — needed for per-frame zoom
    # s=WxH keeps output size stable; x/y expressions keep zoom centred
    filt = (
        f"zoompan="
        f"z='{zoom_expr}':"
        f"d=1:"
        f"x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':"
        f"s={width}x{height}:"
        f"fps={FPS}"
    )
    logging.info("ffmpeg filter length: %d chars", len(filt))
    subprocess.run([
        "ffmpeg", "-y", "-i", str(input_mp4),
        "-vf", filt,
        "-c:v", "libx264", "-preset", "slow", "-crf", "17",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",   # audio is unchanged — no re-encode needed
        str(out_mp4),
    ], check=True)


def probe_dims(mp4: Path) -> tuple[int, int]:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-of", "csv=p=0", str(mp4)],
    ).decode().strip().split(",")
    return int(out[0]), int(out[1])


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input",    type=Path, default=DEFAULT_INPUT,
                   help="Captioned reel to edit (default: assets/final/viral_15s.mp4)")
    p.add_argument("--captions", type=Path, default=DEFAULT_CAPS,
                   help="Word-timing JSON (default: assets/captions/viral_15s.json)")
    p.add_argument("--reveal-start", type=float, default=REVEAL_BEAT_START,
                   help="Second where the reveal beat begins (default: 3.0)")
    p.add_argument("--reveal-end", type=float, default=REVEAL_BEAT_END,
                   help="Second where the reveal beat ends (default: 10.0)")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the punch picks + expr; do not encode")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="[viral_edit] %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout)])

    if not args.input.exists():
        logging.error("input missing: %s", args.input); return 2
    if not args.captions.exists():
        logging.error("captions missing: %s", args.captions); return 2

    words = load_words(args.captions)
    logging.info("Loaded %d words from captions", len(words))

    punches = pick_punches(words)
    logging.info("Picked %d punch moments:", len(punches))
    for s, e, w in punches:
        logging.info("  %.2fs → %.2fs   %s", s, e, w)

    W, H = probe_dims(args.input)
    zoom_expr = build_zoompan_expr(punches, args.reveal_start, args.reveal_end)
    logging.info("Reveal ramp: %.2fs → %.2fs (peak zoom %.2f)",
                 args.reveal_start, args.reveal_end, REVEAL_RAMP_ZOOM)

    if args.dry_run:
        print(f"\nZoom expression:\n  {zoom_expr}\n")
        return 0

    out = args.input.with_name(args.input.stem + "_edited.mp4")
    run_ffmpeg(args.input, out, zoom_expr, W, H)
    dur = float(subprocess.check_output([
        "ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1", str(out)
    ]).decode().strip())
    mb = out.stat().st_size / 1e6
    print(f"\n✅ viral_edit built — {dur:.1f}s / {mb:.1f} MB → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
