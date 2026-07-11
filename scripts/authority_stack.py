"""
authority_stack.py — full-frame avatar reel with logo-pop overlays.

Reuses the existing avatar_video.mp4 (from pipeline.py Stage 3) and captions
(Stage 5). Produces a single-file output where:
  - avatar is chest-up cropped, full-frame the whole reel (no broll box)
  - Hormozi-style word-by-word captions burn in at the bottom
  - a branded logo card pops in near the top when each brand is spoken
    (auto-detected by matching Whisper word timestamps)

Usage:
    python3 scripts/authority_stack.py

Reads:
  assets/avatar/avatar_video.mp4
  assets/captions/avatar_video.json
  assets/script_data.json           (for tool_mentioned + tone only)

Writes:
  assets/final/authority_stack.mp4                (base)
  assets/final/authority_stack_with_thumb.mp4     (thumbnail appended)
"""
from __future__ import annotations
import json, logging, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Prefer the background-replaced avatar (scripts/replace_background.py) when present
_AVATAR_BG = ROOT / "assets" / "avatar" / "avatar_video_bg.mp4"
_AVATAR_RAW = ROOT / "assets" / "avatar" / "avatar_video.mp4"
AVATAR = _AVATAR_BG if _AVATAR_BG.exists() else _AVATAR_RAW
CAPS   = ROOT / "assets" / "captions" / "avatar_video.json"
FINAL  = ROOT / "assets" / "final" / "authority_stack.mp4"
LOGO_DIR = ROOT / "assets" / "logo_cards"
LOGO_DIR.mkdir(parents=True, exist_ok=True)
FINAL.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="[authority_stack] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("authority_stack")

# ── Layout constants ────────────────────────────────────────────────────────
W, H, FPS = 1080, 1920, 30

# Chest-up crop with generous headroom so the logo card sits fully above the
# face. Larger crop area = wider view of the source = face renders SMALLER and
# LOWER in the output. Aspect ratio is 9:16 (800/1422 ≈ 0.5625).
CROP_W, CROP_H, CROP_X, CROP_Y = 800, 1422, 140, 50

# Logo card overlay
CARD_W = 380
CARD_H = 480
CARD_X = (W - CARD_W) // 2   # centered horizontally
CARD_Y = 40                  # 40px from top

# Captions (Hormozi word-by-word)
CAPTION_FONT = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
CAPTION_SIZE = 88
CAPTION_Y_FRAC = 0.78        # ~78% down the frame
BRAND_BLUE = "#2979ff"

# ── Brand data ──────────────────────────────────────────────────────────────

TIER_COLORS = {
    "bad":   "#ef4444",
    "good":  "#facc15",
    "great": "#22c55e",
}
TIER_LABELS = {"bad": "BAD", "good": "GOOD", "great": "GREAT"}

# Each brand: (tier, display_name, whisper-anchor words, svg mark)
# anchor_words: list of lowercase (alnum-only) Whisper words that trigger this brand.
BRANDS = {
    "chatgpt":    ("bad",   "ChatGPT",   ["gpt", "chatgpt"],
        '<path fill="#10A37F" d="M50 8c-9 0-17 5-21 13-9 0-16 7-16 16 0 4 1 8 4 11-3 3-4 7-4 11 0 9 7 16 16 16 4 8 12 13 21 13s17-5 21-13c9 0 16-7 16-16 0-4-1-8-4-11 3-3 4-7 4-11 0-9-7-16-16-16-4-8-12-13-21-13zm-2 20l14 8v16l-14 8-14-8V36l14-8zm2 4-9 5v11l9 5 9-5V37l-9-5z"/>'),
    "gemini":     ("good",  "Gemini",    ["gemini"],
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4285F4"/><stop offset=".45" stop-color="#9B72CB"/><stop offset=".85" stop-color="#D96570"/><stop offset="1" stop-color="#F19E39"/></linearGradient></defs><path fill="url(#g)" d="M50 6c1 20 18 38 44 44-26 6-43 24-44 44-1-20-18-38-44-44 26-6 43-24 44-44z"/>'),
    "claude":     ("great", "Claude",    ["claude"],
        '<g fill="#D97757"><path d="M50 6l6 20 20 6-20 6-6 20-6-20-20-6 20-6z"/><circle cx="50" cy="50" r="5"/></g>'),
    "sora":       ("bad",   "Sora",      ["sora"],
        '<defs><radialGradient id="s" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#000"/><stop offset="1" stop-color="#333"/></radialGradient></defs><circle cx="50" cy="50" r="42" fill="url(#s)"/><circle cx="50" cy="50" r="18" fill="none" stroke="#fff" stroke-width="4"/><circle cx="50" cy="50" r="4" fill="#fff"/>'),
    "synthesia":  ("good",  "Synthesia", ["synthesia"],
        '<defs><linearGradient id="sy" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#5B21B6"/><stop offset="1" stop-color="#8B5CF6"/></linearGradient></defs><path fill="url(#sy)" d="M50 10L86 30v40L50 90 14 70V30z"/><text x="50" y="62" text-anchor="middle" font-family="Arial Black" font-weight="900" font-size="34" fill="#fff">S</text>'),
    "heygen":     ("great", "HeyGen",    ["heygen", "heigen"],
        '<rect x="10" y="10" width="80" height="80" rx="18" fill="#2563EB"/><text x="50" y="66" text-anchor="middle" font-family="Arial Black" font-weight="900" font-size="52" fill="#fff">H</text><circle cx="76" cy="76" r="5" fill="#38BDF8"/>'),
    "free_clone": ("bad",   "Free Clone", ["clone"],
        '<g fill="#9CA3AF"><rect x="40" y="18" width="20" height="42" rx="10"/><path d="M28 50c0 12 10 22 22 22s22-10 22-22h-6c0 9-7 16-16 16s-16-7-16-16z"/><rect x="47" y="72" width="6" height="10"/><rect x="34" y="82" width="32" height="4" rx="2"/></g>'),
    "descript":   ("good",  "Descript",  ["descript"],
        '<rect x="10" y="10" width="80" height="80" rx="18" fill="#8B5CF6"/><g fill="#fff"><rect x="26" y="46" width="6" height="8" rx="2"/><rect x="36" y="38" width="6" height="24" rx="2"/><rect x="46" y="30" width="6" height="40" rx="2"/><rect x="56" y="38" width="6" height="24" rx="2"/><rect x="66" y="46" width="6" height="8" rx="2"/></g>'),
    "elevenlabs": ("great", "ElevenLabs", ["labs", "elevenlabs"],
        '<rect x="10" y="10" width="80" height="80" rx="18" fill="#111827"/><g fill="#fff"><rect x="30" y="30" width="14" height="40" rx="2"/><rect x="56" y="30" width="14" height="40" rx="2"/></g>'),
}


def build_svg_card(brand_key: str) -> str:
    tier, name, _anchors, mark_svg = BRANDS[brand_key]
    color = TIER_COLORS[tier]
    tier_label = TIER_LABELS[tier]
    winner_glow = ('<filter id="glow"><feGaussianBlur stdDeviation="6" result="c"/>'
                   '<feMerge><feMergeNode in="c"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
    winner_attr = 'filter="url(#glow)"' if tier == "great" else ""

    # Font stack that maps well after rsvg-convert (uses generic weights)
    font = 'Helvetica, Arial, sans-serif'
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CARD_W} {CARD_H}">
  <defs>{winner_glow}</defs>
  <rect x="8" y="8" width="{CARD_W-16}" height="{CARD_H-16}" rx="36" ry="36"
        fill="#ffffff" stroke="{color}" stroke-width="8" {winner_attr}/>
  <rect x="{(CARD_W-160)//2}" y="28" width="160" height="42" rx="21" fill="{color}"/>
  <text x="{CARD_W//2}" y="58" text-anchor="middle" font-family="{font}" font-weight="900"
        font-size="22" fill="#ffffff" letter-spacing="4">{tier_label}</text>
  <g transform="translate({(CARD_W-200)//2},110) scale(2)">
    {mark_svg}
  </g>
  <text x="{CARD_W//2}" y="{CARD_H-70}" text-anchor="middle" font-family="{font}" font-weight="900"
        font-size="42" fill="#111827">{name}</text>
  <text x="{CARD_W//2}" y="{CARD_H-32}" text-anchor="middle" font-family="{font}" font-weight="700"
        font-size="18" fill="{color}" letter-spacing="4">{'WINNER' if tier=='great' else ('OKAY' if tier=='good' else 'AVOID')}</text>
</svg>
"""


def render_logo_pngs() -> dict[str, Path]:
    """Render one PNG per brand via rsvg-convert. Returns {brand_key: path}."""
    out = {}
    for key in BRANDS:
        svg_path = LOGO_DIR / f"{key}.svg"
        png_path = LOGO_DIR / f"{key}.png"
        svg_path.write_text(build_svg_card(key), encoding="utf-8")
        r = subprocess.run(
            ["rsvg-convert", "-w", str(CARD_W), "-h", str(CARD_H),
             "-o", str(png_path), str(svg_path)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            log.error("rsvg-convert failed for %s: %s", key, r.stderr[:200])
            sys.exit(2)
        out[key] = png_path
    log.info("Rendered %d logo card PNGs to %s", len(out), LOGO_DIR)
    return out


# ── Whisper caption + brand-timestamp extraction ────────────────────────────

def load_words() -> list[dict]:
    data = json.loads(CAPS.read_text())
    out = []
    for seg in data.get("segments", []):
        for w in seg.get("words", []) or []:
            t = (w.get("word") or w.get("text") or "").strip()
            if not t: continue
            try:
                out.append({"word": t, "start": float(w["start"]), "end": float(w["end"])})
            except (KeyError, TypeError, ValueError): continue
    return out


# Whisper mishears + compound brand splits — normalize caption spelling.
WHISPER_FIXES = {
    "heigen": "HeyGen", "heigan": "HeyGen", "haygen": "HeyGen",
}
# Consecutive pairs merged into one caption word (a, b → merged).
COMPOUND_MERGES = [
    ("chat", "gpt", "ChatGPT"),
    ("eleven", "labs", "ElevenLabs"),
]


def normalize_words(words: list[dict]) -> list[dict]:
    """Fix Whisper mishears and merge split compound brand names."""
    fixed = []
    for w in words:
        c = clean(w["word"])
        if c in WHISPER_FIXES:
            fixed.append({**w, "word": WHISPER_FIXES[c]})
        else:
            fixed.append(w)

    merged: list[dict] = []
    i = 0
    while i < len(fixed):
        if i + 1 < len(fixed):
            a = clean(fixed[i]["word"])
            b = clean(fixed[i+1]["word"])
            hit = next(((m) for (x, y, m) in COMPOUND_MERGES if x == a and y == b), None)
            if hit:
                merged.append({"word": hit,
                               "start": fixed[i]["start"],
                               "end":   fixed[i+1]["end"]})
                i += 2
                continue
        merged.append(fixed[i])
        i += 1
    return merged


def clean(w: str) -> str:
    return re.sub(r"[^a-z]", "", w.lower())


def find_brand_windows(words: list[dict]) -> list[dict]:
    """Return chronological list of {key, name, tier, start, end, hold_until} entries."""
    anchor_map = {}   # anchor_word -> brand_key
    for key, (_tier, _name, anchors, _svg) in BRANDS.items():
        for a in anchors:
            anchor_map[a] = key

    windows: list[dict] = []
    seen_keys = set()
    for w in words:
        c = clean(w["word"])
        key = anchor_map.get(c)
        if not key or key in seen_keys: continue
        seen_keys.add(key)
        tier, name, _a, _s = BRANDS[key]
        # Overlay in slightly before the word is spoken; hold ~1.7s
        start = max(0.0, w["start"] - 0.30)
        end = start + 1.80
        windows.append({"key": key, "name": name, "tier": tier,
                        "start": start, "end": end,
                        "word": w["word"], "wstart": w["start"]})

    # Prevent overlap — if the next window starts before previous ends, clip previous.
    windows.sort(key=lambda x: x["start"])
    for i in range(len(windows) - 1):
        if windows[i]["end"] > windows[i+1]["start"] - 0.1:
            windows[i]["end"] = windows[i+1]["start"] - 0.1
    return windows


# ── ffmpeg build ────────────────────────────────────────────────────────────

def build_caption_filters(words: list[dict], tmp: Path) -> tuple[str, Path]:
    """Emit a drawtext filter chain for word-by-word Hormozi captions.
    Every 4th word highlighted brand-blue.
    """
    caps_tmp = tmp / "word_files"
    caps_tmp.mkdir(exist_ok=True)
    filters = []
    for i, w in enumerate(words):
        clean_t = re.sub(r"[.,!?;:]$", "", w["word"]).upper()
        fp = caps_tmp / f"w_{i:04d}.txt"
        fp.write_text(clean_t, encoding="utf-8")
        f_arg = str(fp).replace(":", "\\:").replace(",", "\\,").replace(" ", "\\ ")
        font = CAPTION_FONT.replace(":", "\\:").replace(" ", "\\ ")
        s = max(0.0, w["start"]); e = max(s + 0.08, w["end"])
        color = BRAND_BLUE if (i % 4 == 3) else "white"
        filters.append(
            f"drawtext=fontfile={font}:textfile={f_arg}"
            f":fontsize={CAPTION_SIZE}:fontcolor={color}"
            f":bordercolor=black:borderw=5"
            f":x=(w-text_w)/2:y=h*{CAPTION_Y_FRAC}"
            f":enable=between(t\\,{s:.2f}\\,{e:.2f})"
        )
    return ",".join(filters), caps_tmp


def run_ffmpeg(logo_paths: dict[str, Path], windows: list[dict],
               caption_chain: str, out_path: Path) -> None:
    """Compose the full video with crop, captions, and logo overlays."""
    # Build -i inputs for each brand PNG in a stable chronological order
    ordered_keys = [w["key"] for w in windows]
    inputs = ["-i", str(AVATAR)]
    for k in ordered_keys:
        inputs += ["-i", str(logo_paths[k])]

    # Filter chain:
    #   [0] crop+scale → [base]
    #   [base] drawtext... → [captioned]
    #   [captioned][1] overlay ... → [o1]
    #   [o1][2]     overlay ... → [o2]
    #   ...
    parts = []
    parts.append(f"[0:v]crop={CROP_W}:{CROP_H}:{CROP_X}:{CROP_Y},scale={W}:{H}[base]")
    parts.append(f"[base]{caption_chain}[captioned]" if caption_chain else "[base]null[captioned]")

    prev = "captioned"
    for i, win in enumerate(windows, 1):
        # Winner tier: add a slight bounce (scale animation via time-modulated scale)
        # Static overlay is simpler and reliable — keep it stable.
        s = win["start"]; e = win["end"]
        label = f"o{i}"
        parts.append(
            f"[{prev}][{i}:v]overlay=x={CARD_X}:y={CARD_Y}"
            f":enable='between(t\\,{s:.2f}\\,{e:.2f})'[{label}]"
        )
        prev = label

    filter_complex = ";".join(parts)

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filter_complex,
        "-map", f"[{prev}]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "slow", "-crf", "17",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(out_path),
    ]
    log.info("ffmpeg filter length: %d chars, %d overlays", len(filter_complex), len(windows))
    subprocess.run(cmd, check=True)


# ── main ────────────────────────────────────────────────────────────────────

def main() -> int:
    if not AVATAR.exists():
        log.error("Missing %s", AVATAR); return 2
    if not CAPS.exists():
        log.error("Missing %s", CAPS); return 2

    words = load_words()
    log.info("Loaded %d word timestamps", len(words))
    words = normalize_words(words)
    log.info("After normalization: %d words", len(words))

    windows = find_brand_windows(words)
    log.info("Detected %d brand windows:", len(windows))
    for w in windows:
        log.info("  %s   %.2fs → %.2fs   (word=%r at %.2fs, tier=%s)",
                 w["name"], w["start"], w["end"], w["word"], w["wstart"], w["tier"])

    logo_paths = render_logo_pngs()

    # Build caption filter chain
    tmp = ROOT / "assets" / "authority_stack_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    caption_chain, _ = build_caption_filters(words, tmp)

    run_ffmpeg(logo_paths, windows, caption_chain, FINAL)

    dur = float(subprocess.check_output([
        "ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1", str(FINAL)
    ]).decode().strip())
    mb = FINAL.stat().st_size / 1e6
    print(f"\n✅ authority_stack built — {dur:.1f}s / {mb:.1f} MB → {FINAL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
