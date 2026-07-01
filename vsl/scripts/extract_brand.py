"""
Fetch zerohands.co, parse its CSS, and write the brand palette to vsl/brand.json.

Strategy:
  1. GET the HTML, find <link rel="stylesheet"> and any inline <style>.
  2. Fetch each external stylesheet (absolute or resolved-relative URL).
  3. Run a regex sweep across the concatenated CSS for:
       - hex colors (#abc / #aabbcc)
       - rgb()/rgba()/hsl()/hsla()
       - CSS custom properties (--primary, --accent, --bg, ...)
  4. Score & cluster: most-used non-white/black-ish colors become primary/accent,
     darkest background-ish goes to bg, white-ish becomes text.
  5. Write vsl/brand.json with primary / accent / bg / bg_secondary / text /
     and a `raw` list of every distinct color we saw so a human can override.

If anything fails (network, parse, empty palette), fall back to brand-bible defaults:
  bg=#1F3864, accent=#B7892B, text=#FFFFFF, bg_secondary=#0E1A33
"""
from __future__ import annotations
import json, re, sys
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://www.zerohands.co"
OUT = ROOT / "brand.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

FALLBACK = {
    "primary":      "#1F3864",   # navy
    "accent":       "#B7892B",   # gold
    "bg":           "#0E1A33",
    "bg_secondary": "#1F3864",
    "text":         "#FFFFFF",
    "text_muted":   "#B6BEC9",
    "source":       "fallback",
    "raw":          [],
}

HEX_RE = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
RGB_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*[\d.]+)?\s*\)")
HSL_RE = re.compile(r"hsla?\(\s*(\d+)\s*,\s*(\d+)%?\s*,\s*(\d+)%?\b", re.I)
CSS_VAR_RE = re.compile(r"--([a-z0-9_-]+)\s*:\s*([^;}\n]+?)\s*[;}]", re.I)


def _hex_norm(h: str) -> str:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h.lower()


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return "#{:02x}{:02x}{:02x}".format(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    s, l = s / 100.0, l / 100.0
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60.0) % 2 - 1))
    m = l - c / 2
    if   0   <= h < 60:  r, g, b = c, x, 0
    elif 60  <= h < 120: r, g, b = x, c, 0
    elif 120 <= h < 180: r, g, b = 0, c, x
    elif 180 <= h < 240: r, g, b = 0, x, c
    elif 240 <= h < 300: r, g, b = x, 0, c
    else:                r, g, b = c, 0, x
    return _rgb_to_hex(int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))


def _luma(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _saturation(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    mx, mn = max(r, g, b), min(r, g, b)
    return mx - mn  # rough chroma


def _fetch(url: str, timeout: int = 15) -> str:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text


def _gather_css(site_url: str) -> str:
    html = _fetch(site_url)
    blobs = [html]
    base = site_url
    # external stylesheets
    for m in re.finditer(r'<link[^>]+rel=["\']?stylesheet["\']?[^>]*>', html, re.I):
        tag = m.group(0)
        href_m = re.search(r'href=["\']([^"\']+)["\']', tag, re.I)
        if not href_m:
            continue
        href = href_m.group(1)
        try:
            url = href if urlparse(href).netloc else urljoin(base, href)
            blobs.append(_fetch(url))
        except Exception as e:
            print(f"  WARN stylesheet fetch failed {href}: {e}", file=sys.stderr)
    # inline <style>...
    for m in re.finditer(r"<style[^>]*>([\s\S]*?)</style>", html, re.I):
        blobs.append(m.group(1))
    return "\n".join(blobs)


def _extract_colors(css: str) -> Counter:
    counter: Counter = Counter()
    # CSS variables first — they're high-signal (designer-named)
    var_colors: dict[str, str] = {}
    for var_name, value in CSS_VAR_RE.findall(css):
        for hx in HEX_RE.findall(value):
            var_colors[var_name.lower()] = _hex_norm(hx)
        for r, g, b in RGB_RE.findall(value):
            var_colors[var_name.lower()] = _rgb_to_hex(int(r), int(g), int(b))
        for h, s, l in HSL_RE.findall(value):
            var_colors[var_name.lower()] = _hsl_to_hex(float(h), float(s), float(l))
    # flat color references (count by usage)
    for hx in HEX_RE.findall(css):
        counter[_hex_norm(hx)] += 1
    for r, g, b in RGB_RE.findall(css):
        counter[_rgb_to_hex(int(r), int(g), int(b))] += 1
    for h, s, l in HSL_RE.findall(css):
        counter[_hsl_to_hex(float(h), float(s), float(l))] += 1
    return counter, var_colors


def _pick(counter: Counter, var_colors: dict[str, str]) -> dict:
    """Greedy palette pick."""
    # candidate set: variables first (preferred), then by usage count
    palette = dict(FALLBACK)
    palette["source"] = "scraped"

    def by_name(*keys):
        for k in keys:
            v = var_colors.get(k)
            if v:
                return v
        return None

    primary = by_name("primary", "brand", "brand-primary", "color-primary", "accent-primary")
    accent  = by_name("accent", "brand-accent", "color-accent", "secondary", "highlight", "gold")
    bg      = by_name("bg", "background", "color-bg", "background-color", "surface", "color-background")
    text    = by_name("text", "fg", "color-text", "foreground", "color-fg")

    sorted_colors = [c for c, _ in counter.most_common()]
    dark = sorted([c for c in sorted_colors if _luma(c) < 60], key=_luma)
    light = sorted([c for c in sorted_colors if _luma(c) > 200], key=_luma, reverse=True)
    sat_mid = sorted([c for c in sorted_colors if 40 < _luma(c) < 220 and _saturation(c) > 0.18],
                     key=lambda c: -counter[c])

    if not bg     and dark:    bg = dark[0]
    if not text   and light:   text = light[0]
    if not primary and sat_mid: primary = sat_mid[0]
    if not accent  and len(sat_mid) > 1: accent = sat_mid[1]
    bg_secondary = dark[1] if len(dark) > 1 else (bg or FALLBACK["bg_secondary"])

    if primary:      palette["primary"] = primary
    if accent:       palette["accent"] = accent
    if bg:           palette["bg"] = bg
    if bg_secondary: palette["bg_secondary"] = bg_secondary
    if text:         palette["text"] = text
    palette["raw"] = sorted_colors[:40]
    palette["css_variables"] = var_colors
    return palette


def main() -> int:
    try:
        print(f"Fetching {SITE} ...")
        css = _gather_css(SITE)
        print(f"  CSS gathered: {len(css):,} chars")
        counter, var_colors = _extract_colors(css)
        print(f"  Distinct colors: {len(counter)} / CSS vars: {len(var_colors)}")
        palette = _pick(counter, var_colors)
    except Exception as e:
        print(f"  ! Extraction failed: {e} — using fallback palette.", file=sys.stderr)
        palette = FALLBACK
    OUT.write_text(json.dumps(palette, indent=2))
    summary = {k: palette[k] for k in ("primary", "accent", "bg", "bg_secondary", "text", "source")}
    print(f"\nWrote {OUT}")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
