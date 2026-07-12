"""Transition + cut library.

House rule (from Dan Martell's own view data): hard cuts + one flash beat
fancy transitions — reach for xfade/shader effects only when the format
explicitly calls for them. Default = restraint.

Provides:
  - xfade_join(clips, transition, dur):    join clips with any of ffmpeg's
    ~50 xfade transitions ("fade", "wipeleft", "circleopen", "pixelize",
    "radial", "slideleft", "zoomin", "dissolve", "hblur", ...)
  - hard_join(clips):                       plain concat (the default)
  - two_cam_cut(a_video, b_video, words, out):  the two-camera jump cut for
    front/side look pairs — alternates angles at sentence boundaries using
    Scribe word timestamps (render the SAME script on both looks first)
  - Light-leak flash lives in core/overlays.OverlayChain.flash_at()
"""
from __future__ import annotations
import subprocess
import tempfile
from pathlib import Path

from core.words import clean

XFADE_TRANSITIONS = [
    "fade", "dissolve", "wipeleft", "wiperight", "wipeup", "wipedown",
    "slideleft", "slideright", "slideup", "slidedown", "circleopen",
    "circleclose", "radial", "pixelize", "hblur", "zoomin", "smoothleft",
    "smoothright", "smoothup", "smoothdown", "circlecrop", "rectcrop",
    "distance", "fadeblack", "fadewhite", "vertopen", "vertclose",
    "horzopen", "horzclose", "diagtl", "diagtr", "diagbl", "diagbr",
]


def hard_join(clips: list[Path], out: Path) -> Path:
    with tempfile.TemporaryDirectory() as td:
        lst = Path(td) / "c.txt"
        lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-c:v", "libx264", "-preset", "fast", "-crf", "17",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                        str(out)], check=True)
    return out


def xfade_join(clips: list[Path], out: Path, transition: str = "fade",
               dur: float = 0.4) -> Path:
    """Join clips with an xfade transition between each pair."""
    if transition not in XFADE_TRANSITIONS:
        raise KeyError(f"unknown xfade {transition!r}")
    from core.words import duration_of
    inputs, parts = [], []
    offsets = []
    total = 0.0
    for c in clips:
        inputs += ["-i", str(c)]
        offsets.append(total)
        total += duration_of(c) - dur
    prev_v, prev_a = "0:v", "0:a"
    for i in range(1, len(clips)):
        off = offsets[i]
        parts.append(f"[{prev_v}][{i}:v]xfade=transition={transition}:"
                     f"duration={dur}:offset={off:.3f}[v{i}]")
        parts.append(f"[{prev_a}][{i}:a]acrossfade=d={dur}[a{i}]")
        prev_v, prev_a = f"v{i}", f"a{i}"
    subprocess.run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(parts),
                    "-map", f"[{prev_v}]", "-map", f"[{prev_a}]",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "17",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    str(out)], check=True)
    return out


def sentence_boundaries(words: list[dict]) -> list[float]:
    """Cut points = end of sentence-final words (., !, ?)."""
    cuts = []
    for w in words:
        if w["word"].rstrip().endswith((".", "!", "?")):
            cuts.append(w["end"] + 0.05)
    return cuts


def two_cam_cut(a_video: Path, b_video: Path, words: list[dict], out: Path,
                min_seg: float = 2.0) -> Path:
    """Dan Martell two-camera jump cut: alternate A/B angle per sentence.

    a_video/b_video = the SAME script rendered on a front look and its side
    look (see core/looks.py pairs()). Audio comes from A throughout (identical
    script, but keeps one clean track). Segments shorter than min_seg merge
    with the next so cuts never feel jittery.
    """
    from core.words import duration_of
    dur = min(duration_of(a_video), duration_of(b_video))
    cuts = [t for t in sentence_boundaries(words) if 0.5 < t < dur - 0.5]
    merged = []
    last = 0.0
    for t in cuts:
        if t - last >= min_seg:
            merged.append(t)
            last = t
    bounds = [0.0] + merged + [dur]

    # Build select expressions: even segments from A, odd from B
    a_ranges, b_ranges = [], []
    for i in range(len(bounds) - 1):
        (a_ranges if i % 2 == 0 else b_ranges).append((bounds[i], bounds[i + 1]))
    def expr(ranges):
        return "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in ranges)

    fc = (
        f"[0:v]select='{expr(a_ranges)}',setpts=N/FRAME_RATE/TB[va];"
        f"[1:v]select='{expr(b_ranges)}',setpts=N/FRAME_RATE/TB[vb];"
        # interleave: overlay B segments onto A timeline is complex — instead
        # cut both and concat in order
    )
    # Simpler + frame-accurate: trim every segment, concat in order.
    inputs = ["-i", str(a_video), "-i", str(b_video)]
    parts, labels = [], []
    for i in range(len(bounds) - 1):
        src = 0 if i % 2 == 0 else 1
        s, e = bounds[i], bounds[i + 1]
        parts.append(f"[{src}:v]trim=start={s:.3f}:end={e:.3f},"
                     f"setpts=PTS-STARTPTS[s{i}]")
        labels.append(f"[s{i}]")
    parts.append(f"{''.join(labels)}concat=n={len(labels)}:v=1:a=0[v]")
    parts.append(f"[0:a]atrim=start=0:end={dur:.3f},asetpts=PTS-STARTPTS[a]")
    subprocess.run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(parts),
                    "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "17",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    str(out)], check=True)
    return out
