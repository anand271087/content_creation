"""
Scan the final VSL and every per-segment avatar mp4 for silence gaps,
report any > 0.3s. Used to diagnose "voice dropouts" in the composed video
and identify whether the gap is in HeyGen's output (fix at render time)
or introduced during compose (fix in compose.py).
"""
from __future__ import annotations
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AVATAR_DIR = ROOT / "assets" / "avatar"
FINAL = ROOT / "output" / "zerohands_vsl_16x9.mp4"
THRESHOLD_DB = -40
MIN_GAP_SEC = 0.3


def silencedetect(mp4: Path) -> list[tuple[float, float]]:
    """Return list of (start, end) silence intervals."""
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(mp4),
           "-af", f"silencedetect=noise={THRESHOLD_DB}dB:d={MIN_GAP_SEC}",
           "-f", "null", "-"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    # ffmpeg writes to stderr
    out = res.stderr
    starts = [float(m) for m in re.findall(r"silence_start: (-?\d+\.?\d*)", out)]
    ends   = [float(m) for m in re.findall(r"silence_end: (-?\d+\.?\d*)",   out)]
    return list(zip(starts, ends))


def fmt_t(t: float) -> str:
    m, s = divmod(int(t), 60)
    cs = int((t - int(t)) * 100)
    return f"{m:02d}:{s:02d}.{cs:02d}"


def main() -> int:
    print("=" * 70)
    print("SILENCE AUDIT — gaps >= %.1fs at < %d dB" % (MIN_GAP_SEC, THRESHOLD_DB))
    print("=" * 70)

    # Per-segment avatar mp4s
    print("\n[Per-segment HeyGen avatar mp4s]")
    inherent_gaps: dict[str, list[tuple[float, float]]] = {}
    for mp4 in sorted(AVATAR_DIR.glob("*.mp4")):
        gaps = silencedetect(mp4)
        if gaps:
            inherent_gaps[mp4.stem] = gaps
            for s, e in gaps:
                dur = e - s
                print(f"  {mp4.stem:25s}  {fmt_t(s)} → {fmt_t(e)}   ({dur:.2f}s)")
        else:
            print(f"  {mp4.stem:25s}  clean")

    # Final composed video
    if not FINAL.exists():
        print(f"\nFinal video missing: {FINAL}", file=sys.stderr)
        return 1
    print(f"\n[Final composed VSL: {FINAL.name}]")
    fgaps = silencedetect(FINAL)
    if not fgaps:
        print("  no silence gaps detected")
    else:
        for s, e in fgaps:
            print(f"  {fmt_t(s)} → {fmt_t(e)}   ({e - s:.2f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
