"""
replace_background.py — swap the filmed backdrop for a studio gradient using
RobustVideoMatting (no green screen needed).

Reads  assets/avatar/avatar_video.mp4   (raw HeyGen avatar, curtain backdrop)
Writes assets/avatar/avatar_video_bg.mp4 (same video, warm-studio gradient bg)

The matting model runs with recurrent temporal state → no frame flicker.
Frames stream through ffmpeg pipes; audio is copied from the source.

Usage:
    python3 scripts/replace_background.py                 # warm studio (default)
    python3 scripts/replace_background.py --style blue    # brand-blue gradient
    python3 scripts/replace_background.py --style teal    # teal-cyan gradient
"""
from __future__ import annotations
import argparse, logging, subprocess, sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "models" / "rvm_mobilenetv3_fp32.torchscript"
SRC = ROOT / "assets" / "avatar" / "avatar_video.mp4"
DST = ROOT / "assets" / "avatar" / "avatar_video_bg.mp4"

logging.basicConfig(level=logging.INFO, format="[replace_bg] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("replace_bg")

# style → (top_rgb, bottom_rgb, glow_color, glow_strength)
STYLES = {
    "warm": ((26, 20, 16), (10, 8, 7),   (255, 150, 60), 0.28),
    "blue": ((11, 18, 32), (21, 60, 140), (41, 121, 255), 0.35),
    "teal": ((6, 26, 30),  (4, 12, 16),  (45, 212, 191), 0.30),
}
# "studio" is built procedurally (bokeh lamps + furniture silhouettes + vignette)
# and "image" composites onto a user-supplied backdrop photo via --bg-image.


def probe(src: Path) -> tuple[int, int, float, int]:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
        "-of", "csv=p=0", str(src)]).decode().strip().split(",")
    w, h = int(out[0]), int(out[1])
    num, den = out[2].split("/")
    fps = float(num) / float(den)
    frames = int(out[3]) if out[3] not in ("N/A", "") else 0
    return w, h, fps, frames


def build_background(w: int, h: int, style: str) -> np.ndarray:
    top, bot, glow_c, glow_s = STYLES[style]
    t = np.linspace(0, 1, h)[:, None, None]
    bg = (np.array(top, np.float32)[None, None, :] * (1 - t)
          + np.array(bot, np.float32)[None, None, :] * t)
    bg = np.broadcast_to(bg, (h, w, 3)).copy()
    cy, cx, radius = h * 0.30, w * 0.5, w * 0.90
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt(((yy - cy) / radius) ** 2 + ((xx - cx) / radius) ** 2)
    glow = np.clip(1 - d, 0, 1)[:, :, None] * glow_s
    bg = bg * (1 - glow) + np.array(glow_c, np.float32)[None, None, :] * glow
    return bg.astype(np.float32)


def build_studio_background(w: int, h: int) -> np.ndarray:
    """Procedural 'blurred studio' backdrop: warm wall wash, clustered lamp
    bokeh, furniture silhouettes, vignette + grain. Seeded → deterministic."""
    rng = np.random.default_rng(11)

    t = np.linspace(0, 1, h)[:, None, None]
    top = np.array([30, 23, 18], np.float32)
    bot = np.array([10, 8, 7], np.float32)
    bg = np.broadcast_to(top[None, None, :] * (1 - t) + bot[None, None, :] * t,
                         (h, w, 3)).copy()
    img = Image.fromarray(bg.astype(np.uint8))

    # Soft warm wall wash upper-right
    wash = Image.new("RGB", (w, h), (0, 0, 0))
    dw = ImageDraw.Draw(wash)
    dw.ellipse([w * 0.5, -h * 0.08, w * 1.4, h * 0.38], fill=(70, 42, 18))
    wash = wash.filter(ImageFilter.GaussianBlur(240))
    img = Image.fromarray(np.clip(np.asarray(img).astype(np.int32)
                                  + np.asarray(wash).astype(np.int32), 0, 255).astype(np.uint8))

    # Small dim bokeh clustered like two background lamps
    bokeh = Image.new("RGB", (w, h), (0, 0, 0))
    db = ImageDraw.Draw(bokeh)
    for cx, cy in [(w * 0.16, h * 0.16), (w * 0.82, h * 0.24)]:
        for _ in range(6):
            r = int(rng.integers(10, 30))
            x = int(cx + rng.normal(0, w * 0.07)); y = int(cy + rng.normal(0, h * 0.05))
            warm = (int(rng.integers(150, 220)), int(rng.integers(85, 130)), int(rng.integers(30, 60)))
            a = float(rng.uniform(0.25, 0.55))
            db.ellipse([x - r, y - r, x + r, y + r], fill=tuple(int(v * a) for v in warm))
    db.ellipse([int(w * 0.06) - 70, int(h * 0.34) - 70,
                int(w * 0.06) + 70, int(h * 0.34) + 70], fill=(46, 28, 12))
    bokeh = bokeh.filter(ImageFilter.GaussianBlur(18))
    img = Image.fromarray(np.clip(np.asarray(img).astype(np.int32)
                                  + np.asarray(bokeh).astype(np.int32), 0, 255).astype(np.uint8))

    # Furniture silhouettes at the edges (blurred dark shapes = depth)
    sil = Image.new("L", (w, h), 0)
    ds = ImageDraw.Draw(sil)
    ds.rectangle([0, int(h * 0.05), int(w * 0.09), int(h * 0.62)], fill=90)
    ds.rectangle([int(w * 0.91), int(h * 0.10), w, int(h * 0.66)], fill=80)
    for _ in range(7):
        x = int(w * 0.05 + rng.integers(-40, 80)); y = int(h * 0.60 + rng.integers(0, 240))
        ds.ellipse([x - 38, y - 14, x + 38, y + 14], fill=110)
    sil = sil.filter(ImageFilter.GaussianBlur(34))
    dark = np.asarray(sil).astype(np.float32)[:, :, None] / 255.0
    arr = np.asarray(img).astype(np.float32) * (1 - 0.55 * dark)

    # Vignette + grain
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt(((yy - h * 0.42) / (h * 0.78)) ** 2 + ((xx - w * 0.5) / (w * 0.88)) ** 2)
    vig = np.clip(1 - 0.5 * np.clip(d - 0.5, 0, 1) * 2, 0.5, 1.0)[:, :, None]
    arr = arr * vig + rng.normal(0, 2.4, (h, w, 3))
    return np.clip(arr, 0, 255).astype(np.float32)


def grade_person(frame: np.ndarray) -> np.ndarray:
    """Warm the subject toward the studio tone + gentle contrast (matches bg)."""
    g = frame.astype(np.float32).copy()
    g[:, :, 0] = np.clip(g[:, :, 0] * 1.04, 0, 255)
    g[:, :, 2] = np.clip(g[:, :, 2] * 0.97, 0, 255)
    return np.clip((g - 128) * 1.04 + 130, 0, 255)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--style", choices=list(STYLES) + ["studio", "image"], default="warm")
    p.add_argument("--bg-image", type=Path, default=None,
                   help="Backdrop photo for --style image (scaled to cover the frame)")
    p.add_argument("--input", type=Path, default=SRC)
    p.add_argument("--output", type=Path, default=DST)
    args = p.parse_args()

    if not MODEL.exists():
        log.error("Missing model: %s", MODEL); return 2
    if not args.input.exists():
        log.error("Missing input: %s", args.input); return 2

    w, h, fps, total = probe(args.input)
    log.info("Source: %dx%d @ %.2ffps, ~%d frames", w, h, fps, total)

    model = torch.jit.load(str(MODEL)).eval()
    device = "cpu"   # torchscript RVM is most reliable on CPU; MPS is flaky with jit
    model = model.to(device)

    if args.style == "studio":
        bg = build_studio_background(w, h)
    elif args.style == "image":
        if not args.bg_image or not args.bg_image.exists():
            log.error("--style image requires --bg-image <photo>"); return 2
        pic = Image.open(args.bg_image).convert("RGB")
        # scale-to-cover then center-crop
        scale = max(w / pic.width, h / pic.height)
        pic = pic.resize((round(pic.width * scale), round(pic.height * scale)))
        left, top_ = (pic.width - w) // 2, (pic.height - h) // 2
        bg = np.asarray(pic.crop((left, top_, left + w, top_ + h))).astype(np.float32)
    else:
        bg = build_background(w, h, args.style)
    grade = args.style in ("studio", "image", "warm")
    frame_bytes = w * h * 3

    dec = subprocess.Popen([
        "ffmpeg", "-v", "error", "-i", str(args.input),
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE, bufsize=frame_bytes * 4)
    enc = subprocess.Popen([
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", f"{fps}",
        "-i", "-", "-i", str(args.input),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p",
        "-c:a", "copy", str(args.output)],
        stdin=subprocess.PIPE)

    rec = [None] * 4
    n = 0
    with torch.no_grad():
        while True:
            raw = dec.stdout.read(frame_bytes)
            if len(raw) < frame_bytes:
                break
            frame = np.frombuffer(raw, np.uint8).reshape(h, w, 3)
            src_t = (torch.from_numpy(frame.copy()).permute(2, 0, 1)
                     .float().div(255).unsqueeze(0).to(device))
            fgr, pha, *rec = model(src_t, *rec, downsample_ratio=0.25)
            alpha = pha[0, 0].cpu().numpy()[:, :, None]
            person = grade_person(frame) if grade else frame.astype(np.float32)
            comp = person * alpha + bg * (1 - alpha)
            enc.stdin.write(comp.astype(np.uint8).tobytes())
            n += 1
            if n % 100 == 0:
                log.info("  %d/%d frames (%.0f%%)", n, total, 100 * n / max(total, 1))

    dec.stdout.close()
    enc.stdin.close()
    enc.wait()
    dec.wait()

    if not args.output.exists() or args.output.stat().st_size < 100_000:
        log.error("Output missing or too small"); return 1
    mb = args.output.stat().st_size / 1e6
    print(f"\n✅ background replaced ({args.style}) — {n} frames / {mb:.1f} MB → {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
