---
name: motion-design
description: >-
  Adds animated motion-graphic overlays (spring-land pills, count-up numbers,
  underline draws, logo pops) ON TOP of avatar footage in any reel format.
  Renders GSAP scenes on magenta via the hyperframes CLI, then chroma-keys
  them transparent at composite time through OverlayChain. Use when a reel
  needs animated labels/stats/reveals instead of static PNG pops, when the
  user says "animate", "motion design", "make it move", or when upgrading an
  existing format's reveals.
---

# Motion design — animated overlays on avatar footage

## What this is

`core/motion.py` renders a small GSAP animation on a solid **magenta**
(#FF00FF) background using the same `npx hyperframes` CLI as the b-roll
generator, and `OverlayChain.add_video(..., chroma=MAGENTA)` keys the magenta
out → real motion graphics on top of the avatar, positioned and timed like any
overlay. Proven end-to-end 2026-07-16 (spring pill + count-up over the
black_couch look, zero fringe).

```python
from core.motion import spring_label, countup, MAGENTA
from core.overlays import OverlayChain

clip = spring_label("SKILL 1 — SCRIPT WRITER", ASSET_DIR/"m1.mp4", duration=3.5)
chain.add_video(clip, x=60, y=1560, start=t, end=t+3.5, w=960, h=240, chroma=MAGENTA)
```

## Templates (motion/templates/*.html)

| Template | Helper | Canvas | Motion |
|----------|--------|--------|--------|
| `spring_label` | `spring_label(text, out, accent, pill_bg, text_color, duration)` | 960×240 | dark pill drops in with back.out(2.2) overshoot + dot pulse |
| `countup` | `countup(target, caption, out, prefix, suffix, accent, text_color, duration)` | 760×300 | number rolls 0→N (power3.out), scale pop, underline bar draws |

Default colors are the dark_brick palette (amber #FFB02E accent, cream text).
**Always re-color per the palette-from-background rule** — pass accent/text
colors derived from the look's set.

## Template authoring rules (hard requirements — renders fail otherwise)

1. Root div MUST carry `data-composition-id="main"`, `data-start="0"`,
   `data-duration="__DURATION__"`, `data-width`, `data-height` matching the
   viewport meta.
2. Timeline MUST be `gsap.timeline({ paused: true })` and registered as
   `window.__timelines["main"] = tl` — an unregistered timeline = "zero
   duration" error.
3. Static HTML for all visible elements (no createElement), placeholders as
   `__KEY__`, pad the timeline to full `data-duration` with a no-op tween.
4. Background stays pure #FF00FF; never use magenta/pink content colors
   (they'd be keyed out). Avoid soft glows fading toward magenta.
5. No `repeat: -1` anywhere (breaks duration inference).
6. Register new templates in `core/motion.py` SIZES + add a typed helper.

## House motion rules (mentor/user-approved grammar)

- Motion decorates the reveal, it does not replace the format's reveal
  grammar. Hard cuts + one flash still beat fancy transitions.
- One motion element on screen at a time; sync entrances to Scribe word
  timestamps (`word_start − 0.15s`), same as static reveals.
- Entrances: back/elastic eases. Exits: power2/power3. (HyperFrames ease
  table, see feedback_hyperframes_docs memory.)
- Dark pills behind text on warm/bright sets — the spring_label pill already
  is one; keep it dark even when re-coloring the accent.
- Chroma edges: `colorkey=0xFF00FF:0.26:0.08` is baked into add_video; if a
  new template shows fringe, increase blend 0.08→0.12 before touching colors.
- 4K/sharpness: motion overlays render at native size; the finish chain's
  `upscale_4k` pass covers them — don't pre-upscale.

## When to use vs alternatives

- Animated label/stat ON the avatar → this skill.
- Full-frame animated card/cutaway (b-roll slot) → hyperframes-templates/
  via `broll/generate_hyperframes_broll.mjs` (no chroma needed).
- Static pill that just appears → core/cards.py PNG (cheaper; fine for board
  rows that accumulate).

Use `python3.11` for all Python in this repo.
