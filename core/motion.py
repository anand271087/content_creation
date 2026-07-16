"""Motion overlays — GSAP scenes rendered as chroma-key video for OverlayChain.

The gap this fills: OverlayChain items were static PNGs that blink on/off.
This renders a small GSAP animation (spring-land pills, count-up numbers, …)
on a solid MAGENTA background via the same `npx hyperframes` CLI the b-roll
generator uses, then OverlayChain.add_video(..., chroma=MAGENTA) keys the
magenta out at composite time → real motion graphics ON the avatar footage.

House rules (motion = seasoning, not the meal):
  - one motion element on screen at a time, synced to Scribe word_start − 0.15s
  - spring/back eases for entrances, power eases for exits (HyperFrames table)
  - never magenta/pink content colors in templates (they'd get keyed out)
  - hard cuts still beat fancy transitions — motion decorates reveals, it does
    not replace the reveal grammar of the format

Templates live in motion/templates/*.html — static HTML elements + GSAP
timeline + `data-duration="__DURATION__"` (same conventions as
hyperframes-templates/, see feedback_hyperframes_blank_template memory).
"""
from __future__ import annotations
import logging
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger("motion")

ROOT = Path(__file__).resolve().parent.parent
TPL_DIR = ROOT / "motion" / "templates"
HF_DIR = ROOT / "hyperframes-templates"
MAGENTA = "0xFF00FF"

# template → canvas size (must match the html viewport)
SIZES = {
    "spring_label": (960, 240),
    "countup": (760, 300),
}


def render_motion(template: str, out: Path, subs: dict[str, str],
                  duration: float = 3.0) -> Path:
    """Render motion/templates/<template>.html with __KEY__ substitutions to
    an mp4 on magenta. Returns `out`. Composite with add_video(chroma=MAGENTA).
    """
    tpl = TPL_DIR / f"{template}.html"
    if not tpl.exists():
        raise FileNotFoundError(f"unknown motion template {template!r} "
                                f"({', '.join(p.stem for p in TPL_DIR.glob('*.html'))})")
    html = tpl.read_text()
    subs = {"DURATION": f"{duration:.2f}", **subs}
    for k, v in subs.items():
        html = html.replace(f"__{k}__", str(v))
    if "__" in html.replace("__proto__", ""):
        log.warning("possibly unfilled placeholders remain in %s", template)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"motion-{template}-") as td:
        proj = Path(td)
        # local GSAP — no CDN fetch during render (same guard as b-roll gen)
        gsap = HF_DIR / "gsap.min.js"
        if gsap.exists():
            import re
            html = re.sub(r"https?://[^\"']*gsap[^\"']*\.js", "./gsap.min.js", html)
            (proj / "gsap.min.js").write_bytes(gsap.read_bytes())
        (proj / "index.html").write_text(html)
        (proj / "hyperframes.json").write_bytes((HF_DIR / "hyperframes.json").read_bytes())
        meta = (HF_DIR / "meta.json").read_text().replace(
            "hyperframes-templates", f"motion-{template}")
        (proj / "meta.json").write_text(meta)

        r = subprocess.run(
            ["npx", "hyperframes@latest", "render", str(proj),
             "-o", str(out), "-f", "30", "-q", "standard", "--quiet"],
            timeout=180)
        if r.returncode != 0 or not out.exists() or out.stat().st_size < 5000:
            raise RuntimeError(f"motion render failed for {template} → {out}")
    log.info("motion %s → %s (%.1fs)", template, out.name, duration)
    return out


def spring_label(text: str, out: Path, accent: str = "#FFB02E",
                 pill_bg: str = "rgba(20,15,11,0.92)", text_color: str = "#F5EFE6",
                 duration: float = 3.0) -> Path:
    """Dark pill that spring-lands with overshoot. Default palette = dark_brick."""
    return render_motion("spring_label", out, {
        "TEXT": text, "ACCENT": accent, "PILL_BG": pill_bg,
        "TEXT_COLOR": text_color}, duration)


def countup(target: float, caption: str, out: Path, prefix: str = "",
            suffix: str = "", accent: str = "#FFB02E",
            text_color: str = "#F5EFE6", duration: float = 3.0) -> Path:
    """Number counts 0→target with a pop + underline bar."""
    return render_motion("countup", out, {
        "TARGET": str(target), "CAPTION": caption, "PREFIX": prefix,
        "SUFFIX": suffix, "ACCENT": accent, "TEXT_COLOR": text_color}, duration)
