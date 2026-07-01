"""
Parse VSL_Script.docx -> vsl/segments.json.

Output schema (one record per segment, in script order):

  {
    "id": "hook",
    "label": "HOOK — the reveal",
    "time_label": "0:00 – 0:20",
    "look": "look1",                # look1 = HEYGEN_AVATAR_ID_GREY (tight, hook)
                                    # look2 = HEYGEN_AVATAR_ID_BLUE (medium, body)
    "visual_mode": "full_screen_text",
    "slide_ids": ["H1", "H2", "H3"],
    "screen_recording": null,       # or filename in vsl/assets/screenrec/
    "title_card_before": null,      # or "The Proof" / "The System" / "The Funnel"
    "spoken": "...",                # exact text to feed HeyGen
    "raw_cues": ["[Look 1, tight close-up. ...]", ...],   # bracketed editing notes, NOT spoken
    "hash": "sha256[...:12]"        # content hash for modular re-render
  }

Source of truth: the script's timestamped section headings (e.g. "0:00 – 0:20   HOOK — the reveal").
Editing cues in square brackets are preserved as `raw_cues` but stripped from `spoken`.
"""
from __future__ import annotations
import hashlib, json, re, sys
from pathlib import Path
from docx import Document

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DOCX = ROOT / "inputs" / "VSL_Script.docx"
OUT = ROOT / "segments.json"

# Visual-mode / look / slide / screen-rec / title-card classification per segment id.
# All segment ids here MUST appear as TIME_HEADING_RE matches in the docx in this order.
SEGMENT_RULES = {
    "hook": {
        "look": "look2",   # v8 — user wants Blue avatar everywhere (was Grey/look1)
        "visual_mode": "full_screen_text",
        "slide_ids": ["H1", "H2", "H3"],
        "title_card_before": None,
        "screen_recording": None,
    },
    "objection": {
        "look": "look2",   # v8 — Blue avatar everywhere
        "visual_mode": "full_screen_text",
        "slide_ids": ["H4"],
        "title_card_before": None,
        "screen_recording": None,
    },
    "soft_cta": {
        "look": "look2",
        "visual_mode": "pip_over_slide",
        "slide_ids": ["B1"],
        "title_card_before": "The Reveal",   # new — gives viewer a beat after the reveal moment
        "screen_recording": None,
    },
    "pain": {
        "look": "look2",
        "visual_mode": "pip_over_slide",
        "slide_ids": ["B2"],
        "title_card_before": None,
        "screen_recording": None,
    },
    "solution": {
        "look": "look2",
        "visual_mode": "pip_over_slide",
        "slide_ids": ["B3", "B4"],
        "title_card_before": "The System",
        "screen_recording": None,
    },
    "proof": {
        "look": "look2",
        "visual_mode": "screen_share_with_pip",
        "slide_ids": [],
        "title_card_before": "The Proof",
        "screen_recording": "instagram_scroll.mp4",
    },
    "value_step1_strategy": {
        "look": "look2",
        "visual_mode": "pip_over_slide",
        "slide_ids": ["B6", "B7", "B8"],
        "title_card_before": None,
        "screen_recording": None,
    },
    "value_step2_clone": {
        "look": "look2",
        "visual_mode": "screen_share_with_pip",
        "slide_ids": ["B9"],
        "title_card_before": None,
        # Played sped-up to fit avatar narration windows in compose.py.
        # Two HeyGen parts get stitched as one HeyGen window; then ElevenLabs window.
        "screen_recording": ["Heygen_part1.mov", "Heygen_part2.mov", "eleven_labs.mov"],
        "screen_recording_groups": [
            { "label": "heygen",     "files": ["Heygen_part1.mov", "Heygen_part2.mov"] },
            { "label": "elevenlabs", "files": ["eleven_labs.mov"] }
        ]
    },
    "value_step3_funnel": {
        "look": "look2",
        "visual_mode": "pip_over_slide",
        "slide_ids": ["B11"],
        "title_card_before": "The Funnel",
        "screen_recording": None,
    },
    "why_it_works": {
        "look": "look2",
        "visual_mode": "pip_over_slide",
        "slide_ids": ["B12"],
        "title_card_before": None,
        "screen_recording": None,
    },
    "gap": {
        "look": "look2",
        "visual_mode": "full_face",
        "slide_ids": [],
        "title_card_before": None,
        "screen_recording": None,
    },
    "offer": {
        "look": "look2",
        "visual_mode": "split_screen_left_avatar",   # avatar left half + WHAT WE BUILD list right half
        "slide_ids": ["O1"],
        "title_card_before": None,
        "screen_recording": None,
    },
    "risk_cta": {
        "look": "look2",
        "visual_mode": "split_screen_left_avatar",   # avatar left half + BOOK A CALL card right half
        "slide_ids": ["R1"],
        "title_card_before": None,
        "screen_recording": None,
    },
    "outro": {
        "look": "look2",
        "visual_mode": "full_face",
        "slide_ids": [],
        "title_card_before": None,
        "screen_recording": None,
    },
}

# Heading match: "0:00 – 0:20   HOOK — the reveal" or "9:45 – 11:15   The offer (single path)".
# Tolerant of regular hyphen, en-dash, em-dash and varying whitespace.
TIME_HEADING_RE = re.compile(
    r"^\s*"
    r"(\d{1,2}:\d{2})\s*[–—-]\s*(\d{1,2}:\d{2})"     # start - end times
    r"\s+(.+?)\s*$"                                    # label after
)

# Sub-heading inside the value-give block, e.g. "Step 1 — Content Strategy".
STEP_HEADING_RE = re.compile(r"^\s*Step\s*([123])\s*[—–-]\s*(.+?)\s*$", re.I)

# Bracketed editing cues — never spoken.
BRACKET_RE = re.compile(r"\[[^\]]*\]")


def _strip_cues(text: str) -> tuple[str, list[str]]:
    cues = BRACKET_RE.findall(text)
    cleaned = BRACKET_RE.sub("", text).strip()
    return cleaned, cues


def _hash(text: str, look: str) -> str:
    h = hashlib.sha256()
    h.update(text.encode("utf-8"))
    h.update(b"|")
    h.update(look.encode("utf-8"))
    return h.hexdigest()[:12]


def parse() -> list[dict]:
    doc = Document(SCRIPT_DOCX)
    # Flatten paragraphs to strings so we can scan with a single index.
    paras = [p.text.rstrip() for p in doc.paragraphs]

    # First pass: find each timestamped section's heading line index + label/time.
    headings = []   # [(idx, time_label, label_raw)]
    for i, line in enumerate(paras):
        m = TIME_HEADING_RE.match(line)
        if m:
            start, end, rest = m.groups()
            headings.append({
                "idx":   i,
                "time_label": f"{start} – {end}",
                "label": rest,
            })

    # Inside the 3:30 - 8:30 "value give" block we split by Step headings into 3 sub-segments.
    # First identify the big-block boundaries from headings list.
    seg_ids_in_order = list(SEGMENT_RULES.keys())
    label_to_segid = {
        "HOOK — the reveal":                    "hook",
        "Objection handle":                     "objection",
        "Soft CTA + promise":                   "soft_cta",
        "Pain block + villain":                 "pain",
        "Solution — the system":                "solution",
        "Proof":                                "proof",
        "The value give (the body)":            "_value_block_",       # gets sub-divided
        "Why it works":                         "why_it_works",
        "The gap — pitch pivot":                "gap",
        "The offer (single path)":              "offer",
        "Risk reversal + CTA":                  "risk_cta",
        "Outro":                                "outro",
    }

    # Build segments by walking heading-to-heading and slicing paras between them.
    segments: list[dict] = []
    for h_i, h in enumerate(headings):
        end_idx = headings[h_i + 1]["idx"] if h_i + 1 < len(headings) else len(paras)
        body_lines = paras[h["idx"] + 1: end_idx]
        block_text = "\n".join(line for line in body_lines if line.strip())

        seg_id = label_to_segid.get(h["label"].strip())
        if seg_id is None:
            # heuristic match (in case of small label drift)
            label_lc = h["label"].lower()
            if   "hook" in label_lc:      seg_id = "hook"
            elif "objection" in label_lc: seg_id = "objection"
            elif "soft cta" in label_lc:  seg_id = "soft_cta"
            elif "pain" in label_lc:      seg_id = "pain"
            elif "solution" in label_lc:  seg_id = "solution"
            elif "proof" in label_lc:     seg_id = "proof"
            elif "value give" in label_lc or "body" in label_lc: seg_id = "_value_block_"
            elif "why it works" in label_lc: seg_id = "why_it_works"
            elif "gap" in label_lc or "pitch pivot" in label_lc: seg_id = "gap"
            elif "offer" in label_lc:     seg_id = "offer"
            elif "risk" in label_lc or "cta" in label_lc: seg_id = "risk_cta"
            elif "outro" in label_lc:     seg_id = "outro"
            else:
                print(f"  WARN: unrecognised section heading: {h['label']!r}", file=sys.stderr)
                continue

        if seg_id == "_value_block_":
            # Find Step 1 / Step 2 / Step 3 sub-headings inside this block and split.
            step_starts: list[tuple[int, str, str]] = []   # (line_idx_within_body, step_num, step_title)
            for li, ln in enumerate(body_lines):
                ms = STEP_HEADING_RE.match(ln)
                if ms:
                    step_starts.append((li, ms.group(1), ms.group(2).strip()))
            if len(step_starts) != 3:
                print(f"  WARN: value-block has {len(step_starts)} Step headings, expected 3", file=sys.stderr)
            # Intro line(s) before Step 1 - we drop them, they were already covered in the Solution beat.
            for k, (li, n, title) in enumerate(step_starts):
                next_li = step_starts[k + 1][0] if k + 1 < len(step_starts) else len(body_lines)
                step_body_lines = body_lines[li + 1: next_li]
                step_text = "\n".join(line for line in step_body_lines if line.strip())
                sub_id = {
                    "1": "value_step1_strategy",
                    "2": "value_step2_clone",
                    "3": "value_step3_funnel",
                }[n]
                spoken, cues = _strip_cues(step_text)
                rule = SEGMENT_RULES[sub_id]
                segments.append({
                    "id":               sub_id,
                    "label":            f"Step {n} — {title}",
                    "time_label":       h["time_label"],     # the parent's time range
                    "look":             rule["look"],
                    "visual_mode":      rule["visual_mode"],
                    "slide_ids":        rule["slide_ids"],
                    "screen_recording": rule["screen_recording"],
                    "screen_recording_groups": rule.get("screen_recording_groups"),
                    "title_card_before":rule["title_card_before"],
                    "spoken":           spoken,
                    "raw_cues":         cues,
                    "hash":             _hash(spoken, rule["look"]),
                })
            continue

        spoken, cues = _strip_cues(block_text)
        rule = SEGMENT_RULES.get(seg_id)
        if rule is None:
            print(f"  WARN: no SEGMENT_RULES entry for {seg_id}", file=sys.stderr)
            continue
        segments.append({
            "id":               seg_id,
            "label":            h["label"],
            "time_label":       h["time_label"],
            "look":             rule["look"],
            "visual_mode":      rule["visual_mode"],
            "slide_ids":        rule["slide_ids"],
            "screen_recording": rule["screen_recording"],
            "screen_recording_groups": rule.get("screen_recording_groups"),
            "title_card_before":rule["title_card_before"],
            "spoken":           spoken,
            "raw_cues":         cues,
            "hash":             _hash(spoken, rule["look"]),
        })

    # Sanity: order should match SEGMENT_RULES key order.
    expected = list(SEGMENT_RULES.keys())
    actual = [s["id"] for s in segments]
    missing = [s for s in expected if s not in actual]
    extra   = [s for s in actual if s not in expected]
    if missing:
        print(f"  WARN: missing segments: {missing}", file=sys.stderr)
    if extra:
        print(f"  WARN: unexpected segments: {extra}", file=sys.stderr)
    return segments


def main() -> int:
    if not SCRIPT_DOCX.exists():
        print(f"VSL_Script.docx not found at {SCRIPT_DOCX}", file=sys.stderr)
        return 1
    segments = parse()
    OUT.write_text(json.dumps(segments, indent=2, ensure_ascii=False))
    total_words = sum(len(s["spoken"].split()) for s in segments)
    print(f"Wrote {OUT}")
    print(f"  Segments: {len(segments)}")
    print(f"  Total words: {total_words}  (~{total_words / 150:.1f} min at 150 wpm)")
    for s in segments:
        wc = len(s["spoken"].split())
        rec = s["screen_recording"]
        rec_str = f"  rec={rec}" if rec else ""
        tc = f"  title={s['title_card_before']!r}" if s["title_card_before"] else ""
        slides = ",".join(s["slide_ids"]) if s["slide_ids"] else "—"
        print(f"  {s['id']:25s} {s['time_label']:14s} {s['look']} {s['visual_mode']:24s} slides={slides:10s} words={wc:4d}{rec_str}{tc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
