---
name: signature-sketch-infographic
description: Turn any post script, idea, or framework into a one-page hand-sketched infographic for LinkedIn and Instagram, generated with Nano Banana (Gemini 3.1 Flash Image). Use this skill whenever the user wants to create a social infographic, carousel cover, visual post, "make this into a graphic", reel cover, or wants to turn a script/hook/framework into a shareable image. Always use this when the user mentions LinkedIn posts, Instagram posts, infographics, visual content, or asks for a Nano Banana image prompt — even if they don't say the word "infographic". This skill locks a consistent signature visual style so every post looks like it came from the same creator.
---

# Signature Sketch Infographic

This project has the skill wired up to a direct Nano Banana call (no Kie.ai middleman).
When the user asks for an infographic, run:

```bash
# From the most recent script_data.json (auto-derives all fields):
python3 scripts/generate_infographic.py

# Or, fully manual:
python3 scripts/generate_infographic.py \
  --topic "<one-line topic>" \
  --title "<hook title>" \
  --left-header "<left header>" --left "<A,B,C>" \
  --right-header "<right header>" --right "<D,E,F>" \
  --rule-left "<arrow left>" --rule-right "<arrow right>" \
  --stack "<tool1,tool2,tool3>"

# Pick a signature style (cream paper stays locked across all):
python3 scripts/generate_infographic.py --style auto            # let the recommender pick
python3 scripts/generate_infographic.py --style architect       # default — calm authority
python3 scripts/generate_infographic.py --style field-journal   # warmer, freehand, personal-story
python3 scripts/generate_infographic.py --style marker-board    # bold, contrarian, decision-framework

# Just see what the recommender would pick without generating:
python3 scripts/recommend_infographic_style.py
python3 scripts/recommend_infographic_style.py --json    # machine-readable

# Generate just a LinkedIn preview without burning the IG render:
python3 scripts/generate_infographic.py --linkedin-only --style marker-board

# Save under a suffix so you can compare:
python3 scripts/generate_infographic.py --style marker-board --out-suffix _v2
# → assets/infographic/linkedin_v2.png + instagram_v2.png
```

Outputs land in `assets/infographic/`:
- `linkedin.png` (4:5, 1080×1350)
- `instagram.png` (9:16, 1080×1920) — uses LinkedIn image as reference for consistency
- `caption.md` (the 6-part LinkedIn caption per the skill formula)
- `prompts.json` (the actual prompts used, for debugging or re-runs)

## Requirements

- `GEMINI_API_KEY` in `.env` (from https://aistudio.google.com/apikey)
- `pip install google-genai pillow`
- Costs ~$0.13 per post (LinkedIn 4:5 + Instagram 9:16 at 1K)

## The signature canvas (LOCKED — never change)

**Cream paper background + four-zone vertical composition + clean empty boxes + two-color ink meaning** are constant across every post. Only the line work, lettering, and ink hues vary by `--style`.

## Three signature styles

### `architect` (default)
- **Inks:** warm terracotta-orange (changing) + cool teal-blue (stable)
- **Lines:** ruler-guided ink-pen outlines, light pencil cross-hatch shading
- **Background:** faint pencil grid
- **Lettering:** neat printed hand-lettering
- **Best for:** thought-leadership, frameworks, calm-authority takes

### `field-journal`
- **Inks:** warm burnt-sienna (changing) + dusty indigo (stable)
- **Lines:** loose freehand, occasional ink bleed, organic box shapes
- **Background:** no grid
- **Lettering:** handwritten cursive with mid-line correction marks, corner brackets, scattered dot accents
- **Best for:** personal stories, reflections, "figuring this out with you" content

### `marker-board`
- **Inks:** vivid coral red-orange (changing) + deep petrol teal (stable)
- **Lines:** bold chisel-tip felt-marker strokes, deliberate hand-drawn imperfection
- **Background:** no grid, no shading
- **Lettering:** chunky bold sans-serif title, crisp marker labels, **flat solid-color pills for one or two emphasis labels**
- **Best for:** contrarian takes, decision frameworks, "this is the answer" posts — highest scroll-stop power

This exact style block is reused verbatim in every prompt (handled by `build_prompt` in `scripts/generate_infographic.py`):

```
The boxes are clean and empty inside with no decorative icons or symbols. The
style is a warm, inviting hand-sketched diagram on cream paper: ink-pen outlines
with light pencil texture and subtle cross-hatch shading, soft paper grain, a
faint pencil grid in the background, neat hand-lettering, generous white space,
bright and airy, no photographs and no logos.
```

The line about boxes being **clean and empty inside with no decorative icons** is critical — without it Nano Banana fills boxes with meaningless glyph doodles that look AI-generated. The script keeps it in every time.

## How the prompt is built

A Nano Banana prompt is a single flowing **paragraph**, not a keyword list — the model has deep language understanding and a paragraph produces a far better image. The script builds it in this order (subject → action → composition → zones → style):

1. **Subject + action**: what the graphic is and what it explains.
2. **Composition**: vertical, four zones top to bottom — title, two columns, divider strip with arrows, bottom row. Aspect ratio is set via **config parameter**, NEVER in the prompt text.
3. **The content of each zone**, with exact short labels (1–3 words where possible).
4. **The LOCKED style block** verbatim at the end.

The four standard zones:

- **Title**: the hook line.
- **Left column** (terracotta ink): the "changing / moving" category + 3 short boxes.
- **Right column** (teal ink): the "stable / keep" category + 3 short boxes.
- **Middle strip**: two arrows summarizing the decision rule.
- **Bottom row**: 3 boxes for the recommended tool stack or takeaways.

## Aspect ratio handling

Aspect ratio is set in the API config, NOT in the prompt text:

- **LinkedIn → 4:5** (1080×1350). LinkedIn feed crops anything taller than 4:5.
- **Instagram → 9:16** (1080×1920). Full-height story/reel cover.

The two prompts are nearly identical. The 9:16 version adds one composition instruction so the taller canvas doesn't strand content at the edges (handled by `LINKEDIN_COMPOSITION` vs `INSTAGRAM_COMPOSITION` in the script).

## Consistency lever

Per the skill spec, the LinkedIn image is generated **first**. The script then passes that PNG as a reference image to the Instagram run — this is the main consistency lever, far more reliable than words alone.

## Caption formula

The script writes `caption.md` with the 6-part LinkedIn caption:

1. **Hook (first 2 lines)** — contrarian or surprising. LinkedIn hides everything after ~2–3 lines behind "see more".
2. **The reframe** — one or two lines flipping the hook into the real insight.
3. **The framework** — the split from the image, in short arrow lines.
4. **A proof point** — concrete result or personal example with a number.
5. **The line** — a memorable one-sentence takeaway.
6. **CTA** — comment-to-DM hook.

## Where this fits in the project

- The standard pipeline produces `assets/final/final_reel_fast_with_thumb.mp4` for posting.
- This infographic skill is an **alternative** posting format — use when the script is more "framework-y" than "story-y", or when you want to A/B against the reel.
- It does NOT replace the reel — both can be posted (reel on the day, infographic in the carousel slot or LinkedIn post).
