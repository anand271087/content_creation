"""
countdown_reel.py — Dan Martell countdown + screen-demo replica (ref: Dak4_ygAPXc
"5 AI Tools I Use Everyday", 103K plays).

Visual grammar from the reference:
  - Short credibility hook with big "5 AI TOOLS" text
  - Reverse countdown: big "NUMBER 5" … "NUMBER 1" text top-of-frame per item
  - Per tool, a browser-mockup demo card takes the lower half while he talks
  - Spoken keyword CTA at the end ("Comment STACK") + CTA pill on screen
  - Countdown crescendo lands on the strongest tool (#1 = HeyGen = the reveal)

Reads  assets/avatar/avatar_video_bg.mp4    (studio background version)
       assets/captions/countdown.json       (Scribe word timestamps)
Writes assets/final/countdown.mp4

Usage:
    python3 scripts/countdown_reel.py
"""
from __future__ import annotations
import json, logging, re, subprocess, sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
AVATAR = ROOT / "assets" / "avatar" / "avatar_video_bg.mp4"
CAPS = ROOT / "assets" / "captions" / "countdown.json"
FINAL = ROOT / "assets" / "final" / "countdown.mp4"
ASSET_DIR = ROOT / "assets" / "countdown_assets"
LOGO_DIR = ROOT / "assets" / "tier_cards" / "real_logos"
ASSET_DIR.mkdir(parents=True, exist_ok=True)
FINAL.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="[countdown] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("countdown")

W, H = 1080, 1920
FONT_BLACK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

# Blue-avatar framing (face sits lower/left vs grey) — 1.83× crop tuned so the
# chin (≈1126 out) clears the demo card top (1160)
CROP = "crop=591:1050:179:250,scale=1080:1920"

HOOK_TEXT = "5 AI TOOLS"
NUM_Y = 120                 # big NUMBER N text top
CARD_W, CARD_H = 760, 740
CARD_X, CARD_Y = (W - CARD_W) // 2, 1160
CTA_TEXT = "COMMENT: STACK"

# Items in countdown order: (number word, anchor word(s), logo key, name, domain, brand color)
ITEMS = [
    ("five",  ["perplexity"],           "perplexity", "Perplexity", "perplexity.ai", "#20B8CD"),
    ("four",  ["n8n", "nadn", "naden"], "n8n",        "n8n",        "n8n.io",        "#FF6D5A"),
    ("three", ["elevenlabs", "eleven"], "elevenlabs", "ElevenLabs", "elevenlabs.io", "#111827"),
    ("two",   ["claude"],               "claude",     "Claude",     "claude.ai",     "#D97757"),
    ("one",   ["heygen", "heigen"],     "heygen",     "HeyGen",     "heygen.com",    "#2563EB"),
]


# ── Assets ──────────────────────────────────────────────────────────────────

def big_text(text: str, name: str, size: int = 76) -> Path:
    f = ImageFont.truetype(FONT_BLACK, size)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = int(tmp.textlength(text, font=f))
    stroke, pad = 6, 16
    img = Image.new("RGBA", (tw + (pad + stroke) * 2, size + (pad + stroke) * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((pad + stroke, pad), text, font=f, fill=(255, 255, 255, 255),
           stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    out = ASSET_DIR / f"{name}.png"
    img.save(out)
    return out


# Live screen recordings (scripts/record_tool_demos.mjs) shown inside the card.
DEMO_DIR = ROOT / "assets" / "screen_demos"
VID_W, VID_H = 744, 636
VID_X, VID_Y = (W - VID_W) // 2, CARD_Y + 92
# per-key crop of the raw recording before scaling (removes e.g. Wayback toolbar)
DEMO_TOP_CROP = {"elevenlabs": 70}


def build_card_frame(idx: int, domain: str) -> Path:
    """White browser-chrome frame — the live demo video overlays inside it."""
    card = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, CARD_W - 1, CARD_H - 1], radius=26, fill=(250, 250, 250, 252))
    d.rounded_rectangle([0, 0, CARD_W - 1, 84], radius=26, fill=(235, 235, 238, 255))
    d.rectangle([0, 44, CARD_W - 1, 84], fill=(235, 235, 238, 255))
    for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        d.ellipse([28 + i * 34, 32, 48 + i * 34, 52], fill=c)
    d.rounded_rectangle([150, 24, CARD_W - 40, 62], radius=19, fill=(255, 255, 255, 255))
    fu = ImageFont.truetype(FONT_BOLD, 24)
    d.text((172, 30), domain, font=fu, fill=(90, 90, 96, 255))
    out = ASSET_DIR / f"frame_{idx}.png"
    card.save(out)
    return out


def build_lightleak() -> Path:
    """Full-frame warm light-leak flash (baked alpha) shown ~0.25s at each cut.
    Learned from Dan Martell's b-roll reel: color-wash flash bridges cuts."""
    import numpy as np
    yy, xx = np.mgrid[0:H, 0:W]
    d1 = np.sqrt(((yy - H * 0.25) / (H * 0.7)) ** 2 + ((xx - W * 0.85) / (W * 0.7)) ** 2)
    d2 = np.sqrt(((yy - H * 0.75) / (H * 0.8)) ** 2 + ((xx - W * 0.1) / (W * 0.8)) ** 2)
    glow = np.clip(1 - d1, 0, 1) * 0.85 + np.clip(1 - d2, 0, 1) * 0.45
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[:, :, 0] = 255
    rgba[:, :, 1] = np.clip(150 + glow * 80, 0, 255).astype(np.uint8)
    rgba[:, :, 2] = np.clip(60 + glow * 60, 0, 255).astype(np.uint8)
    rgba[:, :, 3] = np.clip(glow * 150, 0, 150).astype(np.uint8)
    out = ASSET_DIR / "lightleak.png"
    Image.fromarray(rgba).save(out)
    return out


def build_cta_pill() -> Path:
    f = ImageFont.truetype(FONT_BLACK, 52)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = int(tmp.textlength(CTA_TEXT, font=f))
    pw, ph = tw + 90, 110
    pill = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(pill)
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=22, fill=(41, 121, 255, 255))
    d.text((45, (ph - 66) / 2), CTA_TEXT, font=f, fill=(255, 255, 255, 255))
    out = ASSET_DIR / "cta_pill.png"
    pill.save(out)
    return out


# ── Timing ──────────────────────────────────────────────────────────────────

def clean(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def load_words() -> list[dict]:
    data = json.loads(CAPS.read_text())
    out = []
    for seg in data.get("segments", []):
        for w in seg.get("words", []) or []:
            t = (w.get("word") or w.get("text") or "").strip()
            if t:
                out.append({"word": t, "start": float(w["start"]), "end": float(w["end"])})
    return out


def compute_timings(words: list[dict], duration: float) -> tuple[list[dict], float, float]:
    """Item windows from 'number <count>' markers; hook = 0 → first marker;
    CTA = 'comment' → end."""
    markers = []
    for i, w in enumerate(words):
        if clean(w["word"]) == "number" and i + 1 < len(words):
            nxt = clean(words[i + 1]["word"])
            markers.append((nxt, w["start"]))
    cta_t = next((w["start"] for w in words if clean(w["word"]) == "comment"), duration - 5)

    out = []
    for k, (numword, anchors, logo, name, domain, color) in enumerate(ITEMS):
        start = next((t for n, t in markers if n == numword), None)
        if start is None:
            log.warning("marker 'number %s' not found — skipping", numword)
            continue
        nxt_starts = [t for _, t in markers if t > start + 0.5]
        end = min(nxt_starts) if nxt_starts else cta_t
        end = min(end, cta_t)
        out.append({"numword": numword, "logo": logo, "name": name,
                    "domain": domain, "color": color,
                    "start": max(0.0, start - 0.10), "end": end, "n": 5 - k})
    hook_end = out[0]["start"] if out else 4.0
    return out, hook_end, cta_t


# ── Compose ─────────────────────────────────────────────────────────────────

def main() -> int:
    if not AVATAR.exists():
        log.error("missing %s", AVATAR); return 2
    if not CAPS.exists():
        log.error("missing %s", CAPS); return 2

    duration = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(AVATAR)]).decode().strip())

    words = load_words()
    items, hook_end, cta_t = compute_timings(words, duration)
    for it in items:
        log.info("NUMBER %d %-12s %5.2f → %5.2f", it["n"], it["name"], it["start"], it["end"])
    log.info("hook 0→%.2f | CTA %.2f→%.2f", hook_end, cta_t, duration)

    hook_png = big_text(HOOK_TEXT, "hook", 84)
    cta_png = build_cta_pill()
    hw = Image.open(hook_png).width
    cw = Image.open(cta_png).width

    inputs = ["-i", str(AVATAR), "-i", str(hook_png), "-i", str(cta_png)]
    # overlays: (input_idx, x, y, start, end, prefilter_or_None)
    overlays = [
        (1, (W - hw) // 2, NUM_Y, 0.0, hook_end, None),           # hook text
        (2, (W - cw) // 2, 1520, cta_t, duration, None),          # CTA pill
    ]
    idx = 3

    for k, it in enumerate(items):
        num_png = big_text(f"NUMBER {it['n']}", f"num_{it['n']}", 76)
        nw = Image.open(num_png).width
        inputs += ["-i", str(num_png)]
        overlays.append((idx, (W - nw) // 2, NUM_Y, it["start"], it["end"], None))
        idx += 1

        demo_start = it["start"] + 1.2
        frame_png = build_card_frame(k, it["domain"])
        inputs += ["-i", str(frame_png)]
        overlays.append((idx, CARD_X, CARD_Y, demo_start, it["end"], None))
        idx += 1

        demo_mp4 = DEMO_DIR / f"{it['logo']}.mp4"
        if demo_mp4.exists():
            top = DEMO_TOP_CROP.get(it["logo"], 0)
            pre = (f"crop=iw:ih-{top}:0:{top}," if top else "") + \
                  f"scale={VID_W}:{VID_H}:force_original_aspect_ratio=increase," \
                  f"crop={VID_W}:{VID_H},setpts=PTS-STARTPTS+{demo_start:.2f}/TB"
            inputs += ["-i", str(demo_mp4)]
            overlays.append((idx, VID_X, VID_Y, demo_start, it["end"], pre))
            idx += 1
        else:
            log.warning("no screen demo for %s — frame only", it["logo"])

    # Light-leak flash at each item start + demo card entry (Dan Martell cut style)
    leak = build_lightleak()
    inputs += ["-i", str(leak)]
    leak_idx = idx
    flash_times = []
    for it in items:
        flash_times.append(it["start"])
        flash_times.append(it["start"] + 1.2)   # demo card entry

    parts = [f"[0:v]{CROP}[base]"]
    prev = "base"
    for n, (i, x, y, s, e, pre) in enumerate(overlays):
        src = f"{i}:v"
        if pre:
            parts.append(f"[{i}:v]{pre}[d{n}]")
            src = f"d{n}"
        lab = f"o{n}"
        # NOTE: default eof_action=repeat — required. 'pass' kills single-frame
        # PNG overlays after 1 frame and drops a demo that ends mid-window.
        parts.append(f"[{prev}][{src}]overlay=x={x}:y={y}"
                     f":enable='between(t\\,{s:.2f}\\,{e:.2f})'[{lab}]")
        prev = lab

    # Flash overlays on top of everything + brightness pulse
    flash_enable = "+".join(f"between(t\\,{t:.2f}\\,{t + 0.22:.2f})" for t in flash_times)
    parts.append(f"[{prev}][{leak_idx}:v]overlay=x=0:y=0:enable='{flash_enable}'[flashed]")
    eq_enable = "+".join(f"between(t\\,{t:.2f}\\,{t + 0.14:.2f})" for t in flash_times)
    parts.append(f"[flashed]eq=brightness=0.13:enable='{eq_enable}'[final]")
    prev = "final"

    subprocess.run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", ";".join(parts),
        "-map", f"[{prev}]", "-map", "0:a",
        "-t", f"{duration:.3f}",   # clamp: time-shifted demo inputs outlast the avatar
        "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", str(FINAL),
    ], check=True)

    mb = FINAL.stat().st_size / 1e6
    print(f"\n✅ countdown built — {duration:.1f}s / {mb:.1f} MB → {FINAL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
