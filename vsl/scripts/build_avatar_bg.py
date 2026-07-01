"""
Generate a 1920x1080 PNG to use as the HeyGen avatar background.

Design:
  - Base: deep black tinted with brand bg_secondary
  - Center radial bloom: subtle blue-cyan glow at the avatar's chest/head zone
  - Top-right haze: faint cyan wash for asymmetric depth
  - Light vignette: slightly darker corners so the avatar reads as the focal point
  - No grid, no text, no edges, no logo — clean cinematic backdrop

Reads colors from vsl/brand.json. Writes vsl/assets/avatar_bg.png.
"""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
brand = json.loads((ROOT / "brand.json").read_text())

W, H = 1920, 1080
OUT = ROOT / "assets" / "avatar_bg.png"
OUT.parent.mkdir(parents=True, exist_ok=True)


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


PRIMARY = hex_to_rgb(brand.get("primary", "#2979ff"))
ACCENT  = hex_to_rgb(brand.get("accent",  "#00e5ff"))
BG      = hex_to_rgb(brand.get("bg",      "#000000"))
BG2     = hex_to_rgb(brand.get("bg_secondary", "#020203"))


def lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def main() -> int:
    # Base: gradient from BG2 (top) → BG (bottom), gives subtle vertical separation.
    img = Image.new("RGB", (W, H), BG)
    base = Image.new("RGB", (W, H))
    for y in range(H):
        # Slightly lighter at top to feel "skyboxy"
        t = (y / H) * 0.85
        col = lerp(BG2, BG, t)
        for x in range(W):
            base.putpixel((x, y), col)
    img = base

    # Center radial bloom — soft blue glow centered slightly above middle (avatar's chest/face zone)
    bloom = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bloom)
    cx, cy = W // 2, int(H * 0.52)
    # Stronger bloom in tight inner area
    for r in range(900, 0, -8):
        # Brightness falls off with r; primary tint near center, accent further out
        falloff = max(0.0, 1.0 - r / 900)
        alpha = int(170 * (falloff ** 1.6))
        if alpha <= 0:
            continue
        # blend primary <-> accent depending on radius (closer = primary, farther = accent hint)
        tint_t = max(0.0, min(1.0, (r / 900) ** 0.6))
        tint = lerp(PRIMARY, ACCENT, tint_t)
        bd.ellipse((cx - r, cy - r, cx + r, cy + r),
                   fill=(tint[0], tint[1], tint[2], alpha))
    bloom = bloom.filter(ImageFilter.GaussianBlur(radius=240))
    img = Image.alpha_composite(img.convert("RGBA"), bloom)

    # Top-right cyan haze for asymmetric depth
    haze = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(haze)
    hx, hy = int(W * 0.86), int(H * 0.18)
    for r in range(700, 0, -10):
        falloff = max(0.0, 1.0 - r / 700)
        alpha = int(90 * (falloff ** 1.8))
        if alpha <= 0:
            continue
        hd.ellipse((hx - r, hy - r, hx + r, hy + r),
                   fill=(ACCENT[0], ACCENT[1], ACCENT[2], alpha))
    haze = haze.filter(ImageFilter.GaussianBlur(radius=200))
    img = Image.alpha_composite(img, haze)

    # Light vignette — darken corners so the avatar reads as the focal point
    vignette = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    max_r = int((W ** 2 + H ** 2) ** 0.5 / 2)
    for r in range(max_r, 0, -20):
        falloff = (r / max_r)
        # darken increases toward edges
        alpha = int(200 * (falloff ** 3.5))
        if alpha <= 0:
            continue
        vd.ellipse((W // 2 - r, H // 2 - r, W // 2 + r, H // 2 + r),
                   fill=(0, 0, 0, alpha))
    # Invert so the vignette darkens the OUTSIDE (the loop drew progressively smaller darker ellipses on top)
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=140))
    img = Image.alpha_composite(img, vignette)

    img = img.convert("RGB")
    img.save(OUT, "PNG", optimize=True)
    print(f"Wrote {OUT}")
    print(f"  Size:    {W}x{H}")
    print(f"  Primary: rgb{PRIMARY}    Accent: rgb{ACCENT}    BG: rgb{BG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
