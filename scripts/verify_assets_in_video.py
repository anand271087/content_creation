"""Verify which b-roll/diagram/screen/text_card assets were created and used in the final video.

Run after Stage 2 (or any later stage) to see a manifest like:

  ┌─────────────────┬──────────┬──────────────────────────────────────┬─────────┬────────┐
  │ section_id      │ type     │ path                                 │ size    │ status │
  ├─────────────────┼──────────┼──────────────────────────────────────┼─────────┼────────┤
  │ hook            │ clip     │ assets/broll/hook.mp4                │ 248 KB  │ OK     │
  │ context         │ diagram  │ assets/diagrams/context.mp4          │  ---    │ MISSING│
  │ body_1          │ screen   │ assets/screen_screenshots/body_1.mp4 │  4 KB   │ TINY⚠  │
  └─────────────────┴──────────┴──────────────────────────────────────┴─────────┴────────┘

Status rules:
  OK       — file exists and size >= MIN_OK_BYTES (15 KB)
  TINY⚠    — file exists but smaller than MIN_OK_BYTES (likely empty / Cloudflare verify / loading error)
  MISSING  — file does not exist
  IN_PROPS — section is referenced in assets/remotion_props.json (post-Stage 5)
  NOT_REF  — file exists but never referenced in the latest remotion_props.json (orphan)

Usage:
  python3 scripts/verify_assets_in_video.py
  python3 scripts/verify_assets_in_video.py --strict   # exit 1 if any TINY/MISSING
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DATA = ROOT / "assets" / "script_data.json"
REMOTION_PROPS = ROOT / "assets" / "remotion_props.json"

# All rendered section MP4s land in assets/broll/{section_id}.mp4 regardless of broll_type.
# (assets/diagrams/, assets/screen_screenshots/, assets/screen_timelines/ are SOURCE asset dirs —
# the rendered videos derived from them are placed back into assets/broll/.)
BROLL_DIR = ROOT / "assets" / "broll"
TYPE_DIR = {
    "clip":      BROLL_DIR,
    "diagram":   BROLL_DIR,
    "screen":    BROLL_DIR,
    "terminal":  BROLL_DIR,
    "text_card": BROLL_DIR,
}

MIN_OK_BYTES = 15 * 1024  # below this = suspect (Cloudflare verify, empty file, etc.)


def fmt_size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n} B"


def find_file(section_id: str, broll_type: str) -> Path | None:
    base = TYPE_DIR.get(broll_type, ROOT / "assets" / "broll")
    for ext in (".mp4", ".mov", ".webm"):
        p = base / f"{section_id}{ext}"
        if p.exists():
            return p
    return None


def load_props_refs() -> set[str]:
    """Return set of section IDs referenced in the latest Remotion props (if any)."""
    if not REMOTION_PROPS.exists():
        return set()
    try:
        props = json.loads(REMOTION_PROPS.read_text())
        sections = props.get("scriptData", {}).get("sections", [])
        return {s["id"] for s in sections}
    except Exception:
        return set()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 if any section is MISSING or TINY")
    args = parser.parse_args()

    if not SCRIPT_DATA.exists():
        print(f"ERROR: {SCRIPT_DATA} not found. Run Stage 1 first.")
        return 1

    script = json.loads(SCRIPT_DATA.read_text())
    sections = script.get("sections", [])
    props_refs = load_props_refs()
    have_props = bool(props_refs)

    print(f"\n  Script: {script.get('title', '(untitled)')}")
    print(f"  Duration: {script.get('total_duration_sec')}s | Sections: {len(sections)}")
    print(f"  Remotion props: {'present (Stage 5 ran)' if have_props else 'absent (pre-Stage 5)'}\n")

    counts = {"OK": 0, "TINY": 0, "MISSING": 0, "ORPHAN": 0}
    rows: list[tuple[str, str, str, str, str, str]] = []
    rows.append(("section_id", "type", "path", "size", "status", "in_props"))

    for sec in sections:
        sid = sec["id"]
        btype = sec.get("broll_type", "clip")
        path = find_file(sid, btype)
        in_props = "yes" if sid in props_refs else ("—" if not have_props else "NO")

        if path is None:
            rows.append((sid, btype, "—", "—", "MISSING", in_props))
            counts["MISSING"] += 1
            continue

        size = path.stat().st_size
        rel = path.relative_to(ROOT).as_posix()
        if size < MIN_OK_BYTES:
            status = "TINY⚠"
            counts["TINY"] += 1
        else:
            status = "OK"
            counts["OK"] += 1
        rows.append((sid, btype, rel, fmt_size(size), status, in_props))

    # also flag orphans: section IDs referenced in props but missing in script_data
    if have_props:
        script_ids = {s["id"] for s in sections}
        for orphan in props_refs - script_ids:
            rows.append((orphan, "?", "—", "—", "ORPHAN", "yes"))
            counts["ORPHAN"] += 1

    # render the table
    widths = [max(len(str(r[i])) for r in rows) for i in range(6)]
    for i, row in enumerate(rows):
        line = "  " + " │ ".join(str(c).ljust(widths[j]) for j, c in enumerate(row))
        print(line)
        if i == 0:
            print("  " + "─┼─".join("─" * w for w in widths))

    print()
    print(f"  Summary: OK={counts['OK']}  TINY⚠={counts['TINY']}  MISSING={counts['MISSING']}  ORPHAN={counts['ORPHAN']}")

    if args.strict and (counts["TINY"] or counts["MISSING"]):
        print(f"\n  STRICT: failing because {counts['TINY']} TINY + {counts['MISSING']} MISSING.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
