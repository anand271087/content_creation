"""PIL asset builders shared by all formats: title pills, dark-pill labels,
float labels, brand logo cards, light-leak flash.

Standing rules baked in (memory: feedback_tier_timeline_format):
  - landed text ALWAYS sits on a dark pill (raw white drowns in the warm bg)
  - float labels = white + 5px black stroke (they sit over the hoodie)
"""
from __future__ import annotations
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from core.brand import W, H, FONT_BLACK, FONT_BOLD, DARK_PILL

# Stylized brand SVG marks (fallback when no real logo PNG exists).
# Real logos preferred: assets/tier_cards/real_logos/{key}.png
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
    "elevenlabs": ("great", "ElevenLabs", ["labs", "elevenlabs", "eleven"],
        '<rect x="10" y="10" width="80" height="80" rx="18" fill="#111827"/><g fill="#fff"><rect x="30" y="30" width="14" height="40" rx="2"/><rect x="56" y="30" width="14" height="40" rx="2"/></g>'),
    "perplexity": ("good",  "Perplexity", ["perplexity"],
        '<path fill="#20B8CD" d="M50 8 L58 30 L82 30 L63 44 L70 68 L50 54 L30 68 L37 44 L18 30 L42 30 Z"/>'),
    "n8n":        ("good",  "n8n",        ["n8n"],
        '<g fill="#FF6D5A"><circle cx="22" cy="50" r="10"/><circle cx="50" cy="30" r="10"/><circle cx="50" cy="70" r="10"/><circle cx="78" cy="50" r="10"/><rect x="28" y="46" width="20" height="8"/><rect x="52" y="34" width="22" height="8" transform="rotate(30 52 38)"/><rect x="52" y="58" width="22" height="8" transform="rotate(-30 52 62)"/></g>'),
}

REAL_LOGO_DIR = Path(__file__).resolve().parent.parent / "assets" / "tier_cards" / "real_logos"


def logo_image(key: str, px: int, workdir: Path) -> Image.Image:
    """Real downloaded logo if present, else rasterized stylized SVG mark.
    Non-square logos are letterboxed into a px x px transparent box."""
    real = REAL_LOGO_DIR / f"{key}.png"
    if real.exists():
        logo = Image.open(real).convert("RGBA")
    else:
        _t, _n, _a, mark = BRANDS[key]
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" '
               f'width="{px}" height="{px}">{mark}</svg>')
        svg_p = workdir / f"_{key}.svg"
        png_p = workdir / f"_{key}.png"
        svg_p.write_text(svg, encoding="utf-8")
        subprocess.run(["rsvg-convert", "-w", str(px), "-h", str(px),
                        "-o", str(png_p), str(svg_p)], check=True, capture_output=True)
        logo = Image.open(png_p).convert("RGBA")
    scale = min(px / logo.width, px / logo.height)
    nw, nh = max(1, round(logo.width * scale)), max(1, round(logo.height * scale))
    logo = logo.resize((nw, nh), Image.LANCZOS)
    box = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    box.paste(logo, ((px - nw) // 2, (px - nh) // 2), logo)
    return box


def title_pill(lines: list[str], out: Path, size: int = 38) -> Path:
    """White rounded pill, 1-2 bold black lines — the persistent top title."""
    f = ImageFont.truetype(FONT_BLACK, size)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = max(tmp.textlength(t, font=f) for t in lines)
    line_h = size + 18
    pw, ph = int(tw + 80), 18 * 2 + line_h * len(lines)
    pill = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(pill)
    d.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=20, fill=(255, 255, 255, 248))
    for i, t in enumerate(lines):
        lw = d.textlength(t, font=f)
        d.text(((pw - lw) / 2, 18 + i * line_h), t, font=f, fill=(10, 10, 10, 255))
    pill.save(out)
    return out


def float_label(text: str, out: Path, size: int = 42) -> Path:
    """Big white + black-stroke label (the 'being evaluated' floater)."""
    f = ImageFont.truetype(FONT_BLACK, size)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = int(tmp.textlength(text, font=f))
    pad, stroke = 14, 5
    img = Image.new("RGBA", (tw + (pad + stroke) * 2, size + (pad + stroke) * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((pad + stroke, pad), text, font=f, fill=(255, 255, 255, 255),
           stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    img.save(out)
    return out


def dark_label(text: str, out: Path, size: int = 28, font: str = FONT_BOLD) -> Path:
    """White text on a dark rounded pill — the ONLY approved landed-label style."""
    f = ImageFont.truetype(font, size)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = int(tmp.textlength(text, font=f))
    pad_x, pad_y = 18, 10
    img = Image.new("RGBA", (tw + pad_x * 2, size + pad_y * 2 + 6), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=12, fill=DARK_PILL)
    d.text((pad_x, pad_y), text, font=f, fill=(255, 255, 255, 255))
    img.save(out)
    return out


def light_leak(out: Path) -> Path:
    """Warm light-leak flash frame (~0.22s at cuts/reveals) — Dan Martell polish."""
    yy, xx = np.mgrid[0:H, 0:W]
    d1 = np.sqrt(((yy - H * 0.25) / (H * 0.7)) ** 2 + ((xx - W * 0.85) / (W * 0.7)) ** 2)
    d2 = np.sqrt(((yy - H * 0.75) / (H * 0.8)) ** 2 + ((xx - W * 0.1) / (W * 0.8)) ** 2)
    glow = np.clip(1 - d1, 0, 1) * 0.85 + np.clip(1 - d2, 0, 1) * 0.45
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[:, :, 0] = 255
    rgba[:, :, 1] = np.clip(150 + glow * 80, 0, 255).astype(np.uint8)
    rgba[:, :, 2] = np.clip(60 + glow * 60, 0, 255).astype(np.uint8)
    rgba[:, :, 3] = np.clip(glow * 150, 0, 150).astype(np.uint8)
    Image.fromarray(rgba).save(out)
    return out
