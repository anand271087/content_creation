"""
vsl/scripts/build_thumbnail.py
Generate a YouTube-ready VSL thumbnail (1920x1080) from the final composed mp4.

Approach:
  1. Extract a candidate frame from the final VSL during the hook avatar moment
     (around 0:14 — the reveal beat).
  2. Composite text overlay: bold "I HAVEN'T FILMED THIS" with brand-blue accent
     keyword + "AI · GENERATED" badge in the top-right.
  3. Save to vsl/output/thumbnail.png.

Reads brand colors from vsl/brand.json.
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT     = Path(__file__).resolve().parent.parent
FINAL    = ROOT / "output" / "zerohands_vsl_16x9.mp4"
OUT_PNG  = ROOT / "output" / "thumbnail.png"
brand    = json.loads((ROOT / "brand.json").read_text())

W, H = 1920, 1080

# Pick a frame around the hook reveal moment (last 4s of hook segment)
EXTRACT_SECONDS = 16.0


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


PRIMARY = hex_to_rgb(brand.get("primary", "#2979ff"))
ACCENT  = hex_to_rgb(brand.get("accent",  "#00e5ff"))
BG      = hex_to_rgb(brand.get("bg",      "#000000"))


def extract_frame() -> Image.Image:
    """Extract a frame from the final VSL and downsample to 1920×1080 if it's 4K.

    YouTube thumbnails are displayed at 1280×720 (and the upload spec is 1920×1080),
    so we don't need 4K — and the rest of the script's overlay math assumes 1920×1080.
    """
    if not FINAL.exists():
        print(f"missing {FINAL} — run compose.py first", file=sys.stderr)
        sys.exit(2)
    tmp = ROOT / "output" / "_thumb_extract.png"
    subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{EXTRACT_SECONDS:.2f}", "-i", str(FINAL),
         "-vf", f"scale={W}:{H}:flags=lanczos",
         "-frames:v", "1", "-q:v", "2", str(tmp)],
        check=True, capture_output=True,
    )
    img = Image.open(tmp).convert("RGB")
    tmp.unlink(missing_ok=True)
    return img


def load_font(size: int, weight: str = "bold") -> ImageFont.FreeTypeFont:
    candidates_bold = [
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    candidates_regular = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    pool = candidates_bold if weight == "bold" else candidates_regular
    for c in pool:
        if Path(c).exists():
            try:
                return ImageFont.truetype(c, size)
            except OSError:
                continue
    return ImageFont.load_default()


def main() -> int:
    img = extract_frame()

    # Slightly darken the bottom half so the headline text reads cleanly.
    darken = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(darken)
    for y in range(int(H * 0.45), H):
        alpha = int(min(170, (y - H * 0.45) / (H * 0.55) * 220))
        dd.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), darken)

    draw = ImageDraw.Draw(img)
    head_font = load_font(180, "bold")
    sub_font  = load_font(56, "bold")
    badge_font = load_font(28, "bold")

    # Title positions — bottom 40% area.
    line1 = "I HAVEN'T"
    line2 = "FILMED THIS."
    sub   = "AND YOU DIDN'T NOTICE."

    line1_y = int(H * 0.58)
    line2_y = int(H * 0.74)
    sub_y   = int(H * 0.88)

    def draw_text_with_stroke(text, y, font, fill, stroke=8):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        x = (W - text_w) // 2
        for dx in (-stroke, 0, stroke):
            for dy in (-stroke, 0, stroke):
                if dx == 0 and dy == 0:
                    continue
                draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 255))
        draw.text((x, y), text, font=font, fill=fill)

    draw_text_with_stroke(line1, line1_y, head_font, (255, 255, 255, 255))
    draw_text_with_stroke(line2, line2_y, head_font, PRIMARY + (255,))
    draw_text_with_stroke(sub,   sub_y,   sub_font,  ACCENT + (255,), stroke=4)

    # Top-right badge: "AI · GENERATED"
    badge_text = "AI · GENERATED"
    pad_x, pad_y = 22, 12
    bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
    bw = (bbox[2] - bbox[0]) + 2 * pad_x
    bh = (bbox[3] - bbox[1]) + 2 * pad_y
    bx = W - bw - 56
    by = 56
    # Rounded rectangle badge (PIL supports rounded_rectangle)
    draw.rounded_rectangle((bx, by, bx + bw, by + bh), radius=999,
                           fill=ACCENT + (255,))
    draw.text((bx + pad_x, by + pad_y - 4), badge_text, font=badge_font, fill=BG + (255,))

    img.convert("RGB").save(OUT_PNG, "PNG", optimize=True)
    print(f"Wrote {OUT_PNG} ({OUT_PNG.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
