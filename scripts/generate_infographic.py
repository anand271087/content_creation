"""Generate a Signature Sketch Infographic via Nano Banana (Gemini 3.1 Flash Image).

DIRECT Google Gemini API call — no Kie.ai middleman.

Produces:
  - assets/infographic/linkedin.png    (4:5, 1080x1350)
  - assets/infographic/instagram.png   (9:16, 1080x1920)
  - assets/infographic/caption.md      (6-part LinkedIn caption per skill formula)
  - assets/infographic/prompts.json    (the prompts used, for debugging / re-runs)

The LinkedIn image is generated first; it is then passed as a REFERENCE image
to the Instagram run so the signature look stays consistent (the main lever
called out in SKILL_infography.md).

Usage:

  # From the most recent script_data.json (auto-derives title + sides + stack
  # from the script's title, grand_takeaway, and key beats):
  python3 scripts/generate_infographic.py

  # Ad-hoc — fully manual structure:
  python3 scripts/generate_infographic.py \\
      --topic "n8n isn't dead. The use cases are splitting." \\
      --left-header "Leaving n8n → AI agents" \\
      --left "Conversational,Adaptive logic,Single-user" \\
      --right-header "Staying in n8n" \\
      --right "Multi-system,On-premise,High-volume cron" \\
      --rule-left "Conversational, adaptive, single-user → AI agent" \\
      --rule-right "Deterministic, multi-system, high-volume → n8n" \\
      --stack "n8n — core,Claude Code — chat layer,Lindy — small teams"

Requires:
  - GEMINI_API_KEY in .env (get from https://aistudio.google.com/apikey)
  - pip install google-genai
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DATA = ROOT / "assets" / "script_data.json"
OUT_DIR = ROOT / "assets" / "infographic"

MODEL = "gemini-3.1-flash-image"  # Nano Banana 2

# ───────────────────────────────────────────────────────────────────────────────
# Style presets. The cream-paper canvas is LOCKED across all three — only the
# line work, lettering, ink palette, and background texture vary.
# Add new styles by appending an entry to STYLES.
# ───────────────────────────────────────────────────────────────────────────────
SHARED_LOCK = (
    "The boxes are clean and empty inside with no decorative icons or symbols. "
    "Cream paper background, soft paper grain, bright and airy, no photographs "
    "and no logos."
)

STYLES: dict[str, dict] = {
    "architect": {
        "ink_left": "warm terracotta-orange",
        "ink_right": "cool teal-blue",
        "style_block": (
            "drawn in the style of an architect's working drawing with "
            "ruler-guided pen lines and soft pencil shading. "
            "Ink-pen outlines with light pencil texture and subtle cross-hatch "
            "shading, a faint pencil grid in the background, neat printed "
            "hand-lettering, generous white space."
        ),
    },
    "field-journal": {
        "ink_left": "warm burnt-sienna",
        "ink_right": "dusty indigo",
        "style_block": (
            "drawn as a personal field-journal sketch with loose freehand ink "
            "lines, occasional ink bleed and uneven line thickness, slightly "
            "organic non-uniform box shapes, soft pencil shading inside contour "
            "lines, handwritten cursive labels in dark sepia ink with small "
            "mid-line correction marks, scattered tiny dot accents, occasional "
            "bracket marks in the margins. No pencil grid. More personal "
            "sketchbook feel than technical drawing, generous airy spacing."
        ),
    },
    "marker-board": {
        "ink_left": "vivid coral red-orange",
        "ink_right": "deep petrol teal",
        "style_block": (
            "drawn as if photographed from a kickoff whiteboard, with bold "
            "chisel-tip felt-marker strokes for box borders and titles, "
            "slightly thick uneven lines, deliberate hand-drawn imperfection. "
            "No pencil grid, no cross-hatch shading. Flat blocks of color used "
            "sparingly for one or two emphasis labels. Chunky bold sans-serif "
            "hand-lettering for the title and crisp marker lettering for body "
            "labels. High contrast against the cream background, generous "
            "white space."
        ),
    },
}

DEFAULT_STYLE = "architect"

LINKEDIN_COMPOSITION = (
    "laid out as a tall vertical poster with four sections stacked top to bottom "
    "and generous spacing between them"
)
INSTAGRAM_COMPOSITION = (
    "laid out as a full-height vertical story poster with four sections stacked "
    "top to bottom, large breathing room between sections, and the title and "
    "bottom row pulled slightly toward center so nothing sits at the extreme "
    "top or bottom edge"
)


def build_prompt(
    *,
    topic: str,
    title: str,
    left_header: str,
    left_boxes: list[str],
    right_header: str,
    right_boxes: list[str],
    rule_left: str,
    rule_right: str,
    stack: list[str],
    composition: str,
    style: str = DEFAULT_STYLE,
) -> str:
    """Build a single-paragraph Nano Banana prompt.

    Cream-paper canvas + four-zone layout are constant. Line work + lettering +
    ink palette vary per `style` (architect | field-journal | marker-board).
    """
    if style not in STYLES:
        raise ValueError(f"Unknown style {style!r}. Choices: {list(STYLES)}")
    spec = STYLES[style]
    left_a, left_b, left_c = (left_boxes + ["", "", ""])[:3]
    right_a, right_b, right_c = (right_boxes + ["", "", ""])[:3]
    stack_1, stack_2, stack_3 = (stack + ["", "", ""])[:3]
    return (
        f"A hand-drawn infographic on warm cream paper that explains {topic}, "
        f"{spec['style_block']} Laid out {composition}. "
        f'At the top, a hand-lettered title reading "{title}." '
        f"Below it, two columns side by side separated by a dashed pencil "
        f"center line. The left column is drawn in {spec['ink_left']} ink, "
        f'headed "{left_header}," with three clean rounded boxes labeled '
        f'"{left_a}," "{left_b}," and "{left_c}." The right column is drawn in '
        f'{spec["ink_right"]} ink, headed "{right_header}," with three boxes '
        f'labeled "{right_a}," "{right_b}," and "{right_c}." Beneath the '
        f"columns, a horizontal strip with two hand-drawn arrows reading "
        f'"{rule_left}" and "{rule_right}." At the bottom, a row of three '
        f'boxes labeled "{stack_1}," "{stack_2}," and "{stack_3}." '
        f"{SHARED_LOCK}"
    )


def derive_from_script_data() -> dict:
    """Auto-derive infographic fields from assets/script_data.json.

    Best-effort. Uses title + grand_takeaway + first 3 sections (excluding hook)
    as left/right/stack candidates. The user can always override on the CLI.
    """
    if not SCRIPT_DATA.exists():
        sys.exit(
            f"ERROR: {SCRIPT_DATA} not found. Run Stage 1 first, or pass --topic explicitly."
        )
    s = json.loads(SCRIPT_DATA.read_text())
    title = s.get("title", "Untitled").split(":")[0].strip()
    grand = s.get("grand_takeaway_line", "")
    sections = s.get("sections", [])
    # Heuristic split — labels come from on_screen_text of body_1/body_2/emotion_save.
    def osr(sid):
        for sec in sections:
            if sec["id"] == sid:
                return sec.get("on_screen_text") or []
        return []
    left_boxes = osr("body_1")[:3] or ["AI agents", "Adaptive logic", "Conversational"]
    right_boxes = osr("body_2")[:3] or ["Multi-system", "On-premise", "Scheduled"]
    stack = osr("emotion_save")[:3] or ["Core stack", "Chat layer", "Personal"]
    return {
        "topic": grand or title,
        "title": title,
        "left_header": "What's changing",
        "left_boxes": left_boxes,
        "right_header": "What's stable",
        "right_boxes": right_boxes,
        "rule_left": "If it's new / adaptive / single-user → agent",
        "rule_right": "If it's deterministic / multi-system → keep current stack",
        "stack": stack,
    }


def build_caption(fields: dict) -> str:
    """6-part LinkedIn caption per the skill formula."""
    title = fields["title"]
    left = " · ".join(fields["left_boxes"])
    right = " · ".join(fields["right_boxes"])
    stack = " + ".join(fields["stack"])
    return f"""# LinkedIn / Instagram caption

> Hook (first 2 lines — everything below this hides under "see more"):

Everyone's calling it dead.
The truth: the use cases are splitting — and most operators are about to get caught flat-footed.

> The reframe:

This isn't a tool fight. It's a job-to-be-done split.
Different work needs different runtimes.

> The framework:

Moving → {left}
Staying → {right}

> Proof:

I rebuilt 6 of my old workflows last week.
3 moved cleanly to the agent layer. 3 stayed exactly where they were.
The retainer my client pays went up — because I could *show them* the split.

> The line:

{title}.

> CTA:

Comment STACK and I'll DM you the 6-task audit I run on every legacy workflow — keep, migrate, or replace. Recommended starter stack: {stack}.
"""


def generate(
    fields: dict,
    *,
    api_key: str,
    out_dir: Path,
    skip_instagram: bool = False,
    style: str = DEFAULT_STYLE,
    out_suffix: str = "",
) -> dict:
    """Call Gemini API. Returns dict of file paths written."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        sys.exit(
            "ERROR: google-genai not installed. Run:\n  pip install google-genai"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    client = genai.Client(api_key=api_key)
    written = {}

    # ── LinkedIn (4:5) ─────────────────────────────────────────────────────────
    li_prompt = build_prompt(**fields, composition=LINKEDIN_COMPOSITION, style=style)
    print("  → LinkedIn 4:5 — calling Nano Banana...")
    li_resp = client.models.generate_content(
        model=MODEL,
        contents=li_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="4:5", image_size="1K"),
        ),
    )
    li_path = out_dir / f"linkedin{out_suffix}.png"
    _save_first_image(li_resp, li_path)
    print(f"    ✓ {li_path.name} ({li_path.stat().st_size / 1024:.0f} KB)")
    written["linkedin"] = li_path

    if skip_instagram:
        return written

    # ── Instagram (9:16) — uses LinkedIn image as reference for consistency ────
    ig_prompt = build_prompt(**fields, composition=INSTAGRAM_COMPOSITION, style=style)
    print("  → Instagram 9:16 — calling Nano Banana with LinkedIn image as reference...")
    try:
        from PIL import Image  # google-genai ships pillow as a transitive dep
    except ImportError:
        sys.exit("ERROR: Pillow not installed. Run:\n  pip install pillow")
    ref_image = Image.open(li_path)
    ig_resp = client.models.generate_content(
        model=MODEL,
        contents=[ref_image, ig_prompt],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="9:16", image_size="1K"),
        ),
    )
    ig_path = out_dir / f"instagram{out_suffix}.png"
    _save_first_image(ig_resp, ig_path)
    print(f"    ✓ {ig_path.name} ({ig_path.stat().st_size / 1024:.0f} KB)")
    written["instagram"] = ig_path

    # ── Caption + prompts.json ─────────────────────────────────────────────────
    caption_path = out_dir / f"caption{out_suffix}.md"
    caption_path.write_text(build_caption(fields))
    written["caption"] = caption_path
    print(f"    ✓ {caption_path.name}")

    prompts_path = out_dir / f"prompts{out_suffix}.json"
    prompts_path.write_text(
        json.dumps(
            {
                "model": MODEL,
                "fields": fields,
                "linkedin_prompt": li_prompt,
                "instagram_prompt": ig_prompt,
            },
            indent=2,
        )
    )
    written["prompts"] = prompts_path
    print(f"    ✓ {prompts_path.name}")

    return written


def _save_first_image(resp, path: Path) -> None:
    """Pull the first image out of the response and write it to disk."""
    for part in getattr(resp, "parts", []) or []:
        img = part.as_image() if hasattr(part, "as_image") else None
        if img is not None:
            # google-genai's Image type has a .save() helper
            if hasattr(img, "save"):
                img.save(str(path))
            else:
                # Fallback: assume PIL-compatible
                img.save(path)
            return
    # Older response shape — walk candidates
    for cand in getattr(resp, "candidates", []) or []:
        for part in getattr(cand, "content", {}).get("parts", []) or []:
            inline = part.get("inline_data") if isinstance(part, dict) else getattr(part, "inline_data", None)
            if inline:
                import base64
                data = inline.get("data") if isinstance(inline, dict) else getattr(inline, "data", None)
                if data:
                    path.write_bytes(base64.b64decode(data) if isinstance(data, str) else data)
                    return
    raise RuntimeError("No image found in Gemini response.")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--topic", help="One-line topic. Overrides script_data.json.")
    p.add_argument("--title", help="Hook title for the top of the infographic.")
    p.add_argument("--left-header", help='e.g. "Leaving n8n → AI agents"')
    p.add_argument("--left", help="3 comma-separated short labels for left column.")
    p.add_argument("--right-header", help='e.g. "Staying in n8n"')
    p.add_argument("--right", help="3 comma-separated short labels for right column.")
    p.add_argument("--rule-left", help='Arrow text for left rule.')
    p.add_argument("--rule-right", help='Arrow text for right rule.')
    p.add_argument("--stack", help="3 comma-separated bottom-row stack labels.")
    p.add_argument("--linkedin-only", action="store_true",
                   help="Skip Instagram (saves ~$0.07).")
    p.add_argument("--style", choices=list(STYLES.keys()) + ["auto"],
                   default=DEFAULT_STYLE,
                   help=f"Signature style (default: {DEFAULT_STYLE}). "
                        f"Use 'auto' to let scripts/recommend_infographic_style.py "
                        f"pick based on script tone + Stage 6 signals. "
                        f"Cream paper canvas is locked across all styles.")
    p.add_argument("--out-suffix", default="",
                   help="Append a suffix to output filenames "
                        "(e.g. '--out-suffix _marker' → linkedin_marker.png).")
    args = p.parse_args()

    # Resolve fields ───────────────────────────────────────────────────────────
    fields = derive_from_script_data() if not args.topic else {
        "topic": args.topic,
        "title": args.title or args.topic,
        "left_header": args.left_header or "What's changing",
        "left_boxes": (args.left or "").split(",") if args.left else [],
        "right_header": args.right_header or "What's stable",
        "right_boxes": (args.right or "").split(",") if args.right else [],
        "rule_left": args.rule_left or "",
        "rule_right": args.rule_right or "",
        "stack": (args.stack or "").split(",") if args.stack else [],
    }
    # Apply CLI overrides on top of derived fields
    if args.title: fields["title"] = args.title
    if args.left_header: fields["left_header"] = args.left_header
    if args.left: fields["left_boxes"] = [s.strip() for s in args.left.split(",")]
    if args.right_header: fields["right_header"] = args.right_header
    if args.right: fields["right_boxes"] = [s.strip() for s in args.right.split(",")]
    if args.rule_left: fields["rule_left"] = args.rule_left
    if args.rule_right: fields["rule_right"] = args.rule_right
    if args.stack: fields["stack"] = [s.strip() for s in args.stack.split(",")]

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Try .env fallback
        env_path = ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not api_key:
        print(
            "ERROR: GEMINI_API_KEY not set.\n"
            "  1. Get a key: https://aistudio.google.com/apikey\n"
            "  2. Add to .env:  GEMINI_API_KEY=AIza...",
            file=sys.stderr,
        )
        return 1

    # Resolve --style auto via recommender
    style = args.style
    if style == "auto":
        try:
            from scripts.recommend_infographic_style import recommend
        except ImportError:
            # script run as standalone — import sibling directly
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from recommend_infographic_style import recommend
        va_path = ROOT / "assets" / "analysis" / "video_analysis.json"
        va = json.loads(va_path.read_text()) if va_path.exists() else None
        sd = json.loads(SCRIPT_DATA.read_text())
        rec = recommend(sd, va)
        style = rec["style"]
        print(f"\n  --style auto → {style}")
        print(f"    {rec['reason']}")

    print(f"\n  Generating infographic with {MODEL} (style: {style})...")
    print(f"  Title:  {fields['title']}")
    print(f"  Left:   {fields['left_boxes']}")
    print(f"  Right:  {fields['right_boxes']}")
    print(f"  Stack:  {fields['stack']}\n")

    written = generate(
        fields, api_key=api_key, out_dir=OUT_DIR,
        skip_instagram=args.linkedin_only, style=style,
        out_suffix=args.out_suffix,
    )
    print("\n  Outputs:")
    for k, v in written.items():
        print(f"    {k:<10} → {v.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
