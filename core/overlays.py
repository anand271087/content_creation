"""OverlayChain — the ffmpeg composite engine every format shares.

Encapsulates all the hard-won gotchas:
  - default eof_action (repeat) — NEVER 'pass': it kills single-frame PNG
    overlays after 1 frame and drops demos that end mid-window
  - `-t duration` clamp — time-shifted (setpts) video overlays otherwise
    extend the render with a frozen tail
  - light-leak flash + brightness pulse at declared beat times
"""
from __future__ import annotations
import logging
import subprocess
from pathlib import Path

from core.brand import CRF_FINAL
from core.cards import light_leak
from core.framing import crop as crop_chain
from core.grade import chain as grade_chain

log = logging.getLogger("overlays")


class OverlayChain:
    def __init__(self, base_video: Path, crop_preset: str, workdir: Path,
                 grade: str = "videographer"):
        self.base = Path(base_video)
        # grade the BASE avatar (videographer: "increase the saturation");
        # overlays/cards render on top ungraded so brand colors stay exact
        self.crop = crop_chain(crop_preset) + "," + grade_chain(grade)
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.inputs: list[str] = ["-i", str(self.base)]
        self.items: list[tuple[int, int, int, float, float, str | None]] = []
        self.flash_times: list[float] = []
        self._n_inputs = 1

    def add_image(self, png: Path, x: int, y: int, start: float, end: float) -> None:
        self.inputs += ["-i", str(png)]
        self.items.append((self._n_inputs, x, y, start, end, None))
        self._n_inputs += 1

    def add_video(self, mp4: Path, x: int, y: int, start: float, end: float,
                  w: int, h: int, top_crop: int = 0) -> None:
        """Overlay a video clip scaled to cover w×h, time-shifted to `start`."""
        pre = ((f"crop=iw:ih-{top_crop}:0:{top_crop}," if top_crop else "")
               + f"scale={w}:{h}:force_original_aspect_ratio=increase,"
               + f"crop={w}:{h},setpts=PTS-STARTPTS+{start:.2f}/TB")
        self.inputs += ["-i", str(mp4)]
        self.items.append((self._n_inputs, x, y, start, end, pre))
        self._n_inputs += 1

    def flash_at(self, *times: float) -> None:
        self.flash_times.extend(times)

    def render(self, out: Path, duration: float, preset: str = "fast") -> Path:
        parts = [f"[0:v]{self.crop}[base]"]
        prev = "base"
        for n, (i, x, y, s, e, pre) in enumerate(self.items):
            src = f"{i}:v"
            if pre:
                parts.append(f"[{i}:v]{pre}[d{n}]")
                src = f"d{n}"
            lab = f"o{n}"
            parts.append(f"[{prev}][{src}]overlay=x={x}:y={y}"
                         f":enable='between(t\\,{s:.2f}\\,{e:.2f})'[{lab}]")
            prev = lab

        if self.flash_times:
            leak = light_leak(self.workdir / "lightleak.png")
            self.inputs += ["-i", str(leak)]
            fe = "+".join(f"between(t\\,{t:.2f}\\,{t + 0.22:.2f})" for t in self.flash_times)
            parts.append(f"[{prev}][{self._n_inputs}:v]overlay=x=0:y=0:enable='{fe}'[fl]")
            ee = "+".join(f"between(t\\,{t:.2f}\\,{t + 0.14:.2f})" for t in self.flash_times)
            parts.append(f"[fl]eq=brightness=0.13:enable='{ee}'[final]")
            prev = "final"
            self._n_inputs += 1

        log.info("%d overlays, %d flashes", len(self.items), len(self.flash_times))
        subprocess.run([
            "ffmpeg", "-y", *self.inputs,
            "-filter_complex", ";".join(parts),
            "-map", f"[{prev}]", "-map", "0:a",
            "-t", f"{duration:.3f}",
            "-c:v", "libx264", "-preset", preset, "-crf", str(CRF_FINAL),
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(out),
        ], check=True)
        return out
