"""Format #8 — editorial process walkthrough (nick_saraev Danc08PA0kz replica).

Visual grammar:
  - Layout alternates: SPLIT (demo card on cream top / tight face bottom)
    ↔ full-frame face
  - RED CROSS SLASH over the terminal demo at the negation phrase
    ("zero CODING skills")
  - Phrase-accumulating captions, serif-italic emphasis + bold sans
  - Real product demos (terminal, live site, logged-in Claude, QR, approval)
  - Quoted-keyword CTA ("APP" in yellow serif italic)

Script pattern: "You can now X with zero Y" → "Here's the full process" →
First/Next/Then/Once/Finally + demos → resource pitch → keyword CTA.
"""
from __future__ import annotations
import logging
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.brand import W, H, FONT_BLACK, CRF_FINAL
from core.grade import chain as grade_chain
from core.words import load_words, normalize, clean, duration_of

log = logging.getLogger("process_walkthrough")

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "assets" / "process_assets"
DEMO_DIR = ROOT / "assets" / "screen_demos"

SERIF_I = "/System/Library/Fonts/Supplemental/Georgia Italic.ttf"

# Face framings for the blueshrt window look (verified from the render)
CROP_FULL = None    # set by build() after verification — full chest framing
CROP_TIGHT = None   # tighter head framing for the split's bottom band

# ── Palette derives from the avatar's background (user rule 2026-07-15) ──
# Every edit color — base, card, captions, accent — keys off the look's bg so
# overlays read cleanly on that specific set instead of a fixed cream style.
PALETTES = {
    # nick_saraev bright editorial (blueshrt window / any light bg)
    "cream": {
        "base": (250, 249, 246), "panel": (255, 255, 255),
        "panel_outline": (224, 222, 216), "pad": (255, 255, 255),
        "cap_fill": (20, 20, 24), "cap_stroke": (255, 255, 255),
        "cta_fill": (255, 214, 40), "cta_stroke": (0, 0, 0),
        "slash": (225, 26, 26), "grade": "bright_sharp",
    },
    # black_couch: warm dark brick bg → dark base blends the letterbox seam,
    # cream text, warm amber-red accent picked from the brick tone
    "dark_brick": {
        "base": (22, 17, 13), "panel": (34, 27, 21),
        "panel_outline": (78, 60, 46), "pad": (26, 20, 15),
        "cap_fill": (245, 239, 230), "cap_stroke": (10, 8, 6),
        "cta_fill": (255, 214, 40), "cta_stroke": (0, 0, 0),
        "slash": (232, 80, 42), "grade": "sharp_4k",
    },
}
PAL = PALETTES["cream"]          # set by build()
CREAM = (250, 249, 246)
CARD_X, CARD_Y, CARD_W, CARD_H = 70, 120, 940, 760
VID_X, VID_Y, VID_W, VID_H = 80, 150, 920, 700
MINI_Y = 1210                      # tight face band top during splits
FULL_Y = 373                       # padded editorial fullface top
CAP_Y = 940                        # caption line between card and face

# (phase key, start anchor word, demo file or None, caption phrases)
PHASES = [
    ("hook",   None,      "rn_terminal.mp4", ["Zero", "Zero Coding", "Skills Required"]),
    ("bridge", "process", None,              ["here's the full process"]),
    ("step1",  "first",   "expo.mp4",        ["React Native + Expo"]),
    ("step2",  "next",    "rn_terminal.mp4", ["start with one screen"]),
    ("step3",  "scan",    "expo_qr.mp4",     ["test it live on your phone"]),
    ("step4",  "once",    "claude.mp4",      ["Claude writes the listing"]),
    ("step5",  "finally", "appstore.mp4",    ["submitted, then approved"]),
    ("cta",    "comment", None,              ['comment "APP"']),
]
SLASH_ANCHOR = "coding"            # red slash lands on this word


def cream_base() -> Path:
    img = Image.new("RGBA", (W, H), (*PAL["base"], 255))
    out = ASSET_DIR / "cream_base.png"
    img.save(out)
    return out


def cream_panel() -> Path:
    img = Image.new("RGBA", (W, H), (*PAL["base"], 255))
    d = ImageDraw.Draw(img)
    # soft vignette corners for depth
    d.rounded_rectangle([CARD_X, CARD_Y, CARD_X + CARD_W, CARD_Y + CARD_H],
                        radius=28, fill=(*PAL["panel"], 255),
                        outline=(*PAL["panel_outline"], 255), width=3)
    out = ASSET_DIR / "cream_panel.png"
    img.save(out)
    return out


def red_slash() -> Path:
    """Thick accent diagonal across the demo card — the 'X, cancelled' mark."""
    c = (*PAL["slash"], 235)
    img = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([(CARD_W - 60, 40), (60, CARD_H - 40)], fill=c, width=34)
    for (x, y) in [(CARD_W - 60, 40), (60, CARD_H - 40)]:
        d.ellipse([x - 17, y - 17, x + 17, y + 17], fill=c)
    out = ASSET_DIR / "red_slash.png"
    img.save(out)
    return out


def caption(text: str, idx: int, yellow: bool = False) -> Path:
    """Serif-italic phrase caption with a soft white stroke halo."""
    size = 54
    font = ImageFont.truetype(SERIF_I, size)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = int(tmp.textlength(text, font=font))
    pad = 18
    img = Image.new("RGBA", (tw + pad * 2 + 12, size + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fill = (*PAL["cta_fill"], 255) if yellow else (*PAL["cap_fill"], 255)
    stroke = (*PAL["cta_stroke"], 235) if yellow else (*PAL["cap_stroke"], 235)
    d.text((pad, pad - 6), text, font=font, fill=fill, stroke_width=4, stroke_fill=stroke)
    out = ASSET_DIR / f"cap_{idx}.png"
    img.save(out)
    return out


def compute_windows(words, duration):
    """Phase windows from anchor words (hook starts at 0)."""
    starts = {}
    for key, anchor, _demo, _caps in PHASES:
        if anchor is None:
            starts[key] = 0.0
            continue
        t = next((w["start"] for w in words if clean(w["word"]) == anchor
                  and w["start"] > starts.get("hook", 0)), None)
        starts[key] = t
    # fill missing by even spacing between neighbours
    keys = [k for k, *_ in PHASES]
    for i, k in enumerate(keys):
        if starts[k] is None:
            prev_t = starts[keys[i - 1]] or 0
            starts[k] = prev_t + 4.0
            log.warning("anchor for %s missing — estimated %.1fs", k, starts[k])
    windows = {}
    for i, k in enumerate(keys):
        end = starts[keys[i + 1]] if i + 1 < len(keys) else duration
        windows[k] = (max(0.0, starts[k] - 0.15), end)
    return windows


def build(avatar: Path, captions: Path, out: Path,
          crop_full: str = "crop=560:608:250:656,scale=1080:1174",
          crop_tight: str = "crop=608:400:226:664,scale=1080:710",
          phases=None, slash_anchor: str | None = None,
          palette: str = "cream", blur_base: bool = False,
          band_crop: str | None = None,
          full_y: int | None = None, mini_y: int | None = None) -> Path:
    global PHASES, SLASH_ANCHOR, PAL
    if phases is not None:
        PHASES = phases
    if slash_anchor is not None:
        SLASH_ANCHOR = slash_anchor
    PAL = PALETTES[palette]
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    duration = duration_of(avatar)
    words = normalize(load_words(captions))
    win = compute_windows(words, duration)
    for k, (s, e) in win.items():
        log.info("%-7s %6.2f → %6.2f", k, s, e)

    slash_t = next((w["start"] - 0.1 for w in words if clean(w["word"]) == SLASH_ANCHOR), 1.0)
    grade = grade_chain(PAL["grade"])

    panel = cream_panel()
    slash = red_slash()

    base_hex = "0x%02X%02X%02X" % PAL["base"]
    pad_hex = "0x%02X%02X%02X" % PAL["pad"]
    # base as a REAL video stream — a still-PNG main input silently
    # breaks timed overlays drawn on top of it
    cream_src = f"color={base_hex}:s={W}x{H}:r=30:d={duration:.3f}"
    inputs = ["-i", str(avatar), "-f", "lavfi", "-i", cream_src,
              "-i", str(panel), "-i", str(slash)]
    n_in = 4
    FY = FULL_Y if full_y is None else full_y
    MY = MINI_Y if mini_y is None else mini_y
    # split windows = phases with a demo
    split_phases = [(k, d) for k, _a, d, _c in PHASES if d]
    split_enable = "+".join(f"between(t\\,{win[k][0]:.2f}\\,{win[k][1]:.2f})"
                            for k, _ in split_phases)

    if blur_base:
        # Base = blurred scale-to-fill of the avatar's own background band, so
        # the whole frame carries the set's ambient color (palette-from-bg rule)
        # and the letterbox seam disappears. Darken so overlays/captions pop.
        bc = (band_crop + ",") if band_crop else ""
        parts = [
            f"[0:v]split=3[fa][fb][fc]",
            f"[fc]{bc}scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,gblur=sigma=30,eq=brightness=-0.06:saturation=1.15[bg]",
            f"[fa]{crop_full},{grade}[full]",
            f"[fb]{crop_tight},{grade}[mini]",
            f"[bg][full]overlay=x=(W-w)/2:y={FY}:enable='not({split_enable})'[p1]",
            f"[p1][2:v]overlay=x=0:y=0:enable='{split_enable}'[p2]",
            f"[p2][mini]overlay=x=(W-w)/2:y={MY}:enable='{split_enable}'[p3]",
        ]
    else:
        parts = [
            f"[0:v]split=2[fa][fb]",
            # editorial padded fullface: wide in-band crop on cream (arms never cut)
            f"[fa]{crop_full},{grade}[full]",
            f"[fb]{crop_tight},{grade}[mini]",
            # cream base canvas for every frame
            f"[1:v][full]overlay=x=0:y={FY}:enable='not({split_enable})'[p1]",
            # card panel + tight face band during splits
            f"[p1][2:v]overlay=x=0:y=0:enable='{split_enable}'[p2]",
            f"[p2][mini]overlay=x=0:y={MY}:enable='{split_enable}'[p3]",
        ]
    prev = "p3"

    # demo videos inside the card per phase
    for k, demo in split_phases:
        s, e = win[k]
        demo_p = DEMO_DIR / demo
        if not demo_p.exists():
            log.warning("missing demo %s", demo)
            continue
        inputs += ["-i", str(demo_p)]
        parts.append(f"[{n_in}:v]scale={VID_W}:{VID_H}:force_original_aspect_ratio=decrease,"
                     f"pad={VID_W}:{VID_H}:(ow-iw)/2:(oh-ih)/2:color={pad_hex},"
                     f"setpts=PTS-STARTPTS+{s:.2f}/TB[d{n_in}]")
        parts.append(f"[{prev}][d{n_in}]overlay=x={VID_X}:y={VID_Y}"
                     f":enable='between(t\\,{s:.2f}\\,{e:.2f})'[o{n_in}]")
        prev = f"o{n_in}"
        n_in += 1

    # red slash over the hook card, from the negation word to hook end
    hs, he = win["hook"]
    parts.append(f"[{prev}][3:v]overlay=x={CARD_X}:y={CARD_Y}"
                 f":enable='between(t\\,{slash_t:.2f}\\,{he:.2f})'[oslash]")
    prev = "oslash"

    # phrase captions: accumulate inside their phase window
    cap_idx = 0
    for k, _a, _d, caps in PHASES:
        s, e = win[k]
        span = (e - s)
        step = min(1.2, span * 0.3)
        starts = [s + 0.2 + j * step for j in range(len(caps))]
        ends = starts[1:] + [e - 0.1]           # each phrase ENDS at the next
        for j, text in enumerate(caps):
            yellow = (k == "cta")
            cp = caption(text, cap_idx, yellow=yellow)
            cw, ch = Image.open(cp).size
            y = CAP_Y if _d else 1620           # split: between card and face; fullface: cream below
            inputs += ["-i", str(cp)]
            parts.append(f"[{prev}][{n_in}:v]overlay=x={(W - cw) // 2}:y={y}"
                         f":enable='between(t\\,{starts[j]:.2f}\\,{ends[j]:.2f})'[c{n_in}]")
            prev = f"c{n_in}"
            n_in += 1
            cap_idx += 1

    subprocess.run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", ";".join(parts),
        "-map", f"[{prev}]", "-map", "0:a",
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "slow", "-crf", str(CRF_FINAL),
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(out),
    ], check=True)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build(ROOT / "assets/avatar/avatar_video.mp4",
          ROOT / "assets/captions/process.json",
          ROOT / "assets/final/process_walkthrough.mp4")
