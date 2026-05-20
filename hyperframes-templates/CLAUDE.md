# HyperFrames Composition Project

## Skills — USE THESE FIRST

**Always invoke the relevant skill before writing or modifying compositions.** Skills encode framework-specific patterns (e.g., `window.__timelines` registration, `data-*` attribute semantics, shader-compatible CSS rules) that are NOT in generic web docs. Skipping them produces broken compositions.

| Skill                      | Command                   | When to use                                                                                       |
| -------------------------- | ------------------------- | ------------------------------------------------------------------------------------------------- |
| **hyperframes**            | `/hyperframes`            | Creating or editing HTML compositions, captions, TTS, audio-reactive animation, marker highlights |
| **hyperframes-cli**        | `/hyperframes-cli`        | CLI commands: init, lint, preview, render, transcribe, tts                                        |
| **hyperframes-registry**   | `/hyperframes-registry`   | Installing blocks and components via `hyperframes add`                                            |
| **website-to-hyperframes** | `/website-to-hyperframes` | Capturing a URL and turning it into a video — full website-to-video pipeline                      |
| **gsap**                   | `/gsap`                   | GSAP animations for HyperFrames — tweens, timelines, easing, performance                          |

> **Skills not available?** Ask the user to run `npx hyperframes skills` and restart their
> agent session, or install manually: `npx skills add heygen-com/hyperframes`.

---

## Commands

```bash
npx hyperframes preview          # preview in browser (studio editor)
npx hyperframes render           # render to MP4 (standard quality, CRF 18)
npx hyperframes render --crf 28  # draft quality (fast preview)
npx hyperframes render --crf 15  # high quality (final delivery)
npx hyperframes lint             # validate compositions (errors + warnings)
npx hyperframes lint --verbose   # include info-level findings
npx hyperframes lint --json      # machine-readable output for CI
npx hyperframes docs <topic>     # reference docs in terminal
```

**Render quality presets:**
| Preset | Flag | CRF | Use for |
|--------|------|-----|---------|
| Draft | `--crf 28` | 28 | Quick preview, iteration |
| Standard | *(default)* | 18 | Pipeline output |
| High | `--crf 15` | 15 | Final delivery |

---

## Non-Negotiable Rules

These 5 rules must be followed in every composition — linter will reject violations.

### 1. Register the timeline on `window.__timelines`

```js
window.__timelines = window.__timelines || {};
window.__timelines["main"] = gsap.timeline({ paused: true });
// Use the composition id as the key (matches data-composition-id on root element)
```

### 2. `class="clip"` on every timed element

The renderer uses this class for visibility control — elements without it are always visible (breaks timing):

```html
<!-- CORRECT -->
<div class="clip" data-start="0" data-duration="3" data-track-index="0">Hello</div>

<!-- WRONG — missing class="clip" -->
<div data-start="0" data-duration="3" data-track-index="0">Hello</div>
```

### 3. No non-deterministic logic during timeline setup

Never use these during GSAP timeline setup — renderer replays the timeline frame-by-frame:

```js
// BANNED during setup:
Math.random()    // breaks determinism
Date.now()       // breaks determinism
fetch()          // async = crashes renderer
setTimeout()     // no async during setup
```

Pre-compute random values outside the timeline if needed.

### 4. Video elements must be `muted` with separate `<audio>`

```html
<video class="clip" src="clip.mp4" muted playsinline ...></video>
<audio src="clip.mp4"></audio>  <!-- audio tracked separately -->
```

### 5. Synchronous timeline only — no `async`/`await`

All GSAP `.to()`, `.from()`, `.fromTo()` calls must be synchronous within the timeline setup function. No `await` inside the setup block.

---

## Root Element Schema

The root `<div>` of each composition requires these `data-*` attributes:

```html
<div
  data-composition-id="my-comp"    <!-- unique ID, matches window.__timelines key -->
  data-start="0"                   <!-- start time in seconds (usually 0) -->
  data-width="1080"                <!-- composition width in pixels -->
  data-height="1920"               <!-- composition height in pixels -->
  data-duration="__DURATION__"     <!-- total duration in seconds (use __DURATION__ placeholder) -->
  style="width:1080px;height:1920px;position:relative;overflow:hidden;"
>
```

`__DURATION__` is replaced by the pipeline at render time based on `section.end_sec - section.start_sec`.

---

## Sub-Composition Pattern

Reference another HTML file inside a composition:

```html
<div
  class="clip"
  data-composition-src="compositions/lower-third.html"
  data-start="2"
  data-duration="5"
  data-track-index="1"
></div>
```

---

## GSAP Ease Vocabulary

Use these named aliases consistently across templates:

| Mood | Ease string | Use for |
|------|-------------|---------|
| smooth | `power2.out` | Most body text, card reveals |
| snappy | `power4.out` | Stats, numbers popping in |
| bouncy | `back.out(1.7)` | Icon/emoji entrances |
| springy | `elastic.out(1, 0.3)` | Logo bounces, CTA buttons |
| dramatic | `expo.out` | Hook slams, trigger flashes |
| dreamy | `sine.inOut` | Grand takeaway fades |

---

## Performance Anti-Patterns (Avoid)

These cause dropped frames during render:

- `backdrop-filter: blur(>32px)` — use `blur(16px)` max
- `filter: blur()` on large animated elements — pre-blur as a static layer
- `box-shadow` on elements that are being animated — remove or use `drop-shadow` filter
- Animating `width`/`height` — use `scaleX`/`scaleY` instead
- Multiple stacked `backdrop-filter` layers — flatten to one

---

## Available Catalog Blocks

Install via `npx hyperframes add <name>` in the hyperframes project directory.

### Social Overlays
| Block | Install | Use in pipeline |
|-------|---------|-----------------|
| `macos-notification` | `npx hyperframes add macos-notification` | Automation triggers, webhook events |
| `instagram-follow` | `npx hyperframes add instagram-follow` | emotion_save CTA section |
| `spotify-card` | `npx hyperframes add spotify-card` | Music/audio content hooks |
| `reddit-post` | `npx hyperframes add reddit-post` | Social proof, comments |
| `yt-lower-third` | `npx hyperframes add yt-lower-third` | Channel branding, lower thirds |

### Data / Info
| Block | Install | Use in pipeline |
|-------|---------|-----------------|
| `data-chart` | `npx hyperframes add data-chart` | Cost comparisons (₹200 vs ₹40K), ROI stats |
| `flowchart` | `npx hyperframes add flowchart` | Automation workflow steps, pipelines |

### VFX / 3D
| Block | Install | Use in pipeline |
|-------|---------|-----------------|
| `vfx-liquid-background` | `npx hyperframes add vfx-liquid-background` | Premium body/bridge sections |
| `vfx-iphone-device` | `npx hyperframes add vfx-iphone-device` | App showcases, mobile demos |
| `vfx-liquid-glass` | `npx hyperframes add vfx-liquid-glass` | Glassmorphism card backgrounds |
| `vfx-text-cursor` | `npx hyperframes add vfx-text-cursor` | Code/typing reveals |
| `vfx-portal` | `npx hyperframes add vfx-portal` | Transformation scenes |
| `vfx-shatter` | `npx hyperframes add vfx-shatter` | Breaking/disruption hooks |
| `vfx-magnetic` | `npx hyperframes add vfx-magnetic` | Interactive-feel demos |
| `ui-3d-reveal` | `npx hyperframes add ui-3d-reveal` | UI/dashboard showcases |

### Shader Transitions
| Block | Install | Use in pipeline |
|-------|---------|-----------------|
| `transitions-grid` | `npx hyperframes add transitions-grid` | Section-to-section cuts |
| `transitions-light` | `npx hyperframes add transitions-light` | Bridge → grand_takeaway |
| `transitions-mechanical` | `npx hyperframes add transitions-mechanical` | Industrial/tech transitions |
| `transitions-push` | `npx hyperframes add transitions-push` | Lateral scene pushes |
| `transitions-radial` | `npx hyperframes add transitions-radial` | Radial reveals |
| `transitions-scale` | `npx hyperframes add transitions-scale` | Zoom transitions |
| `chromatic-radial-split` | `npx hyperframes add chromatic-radial-split` | Glitch/hype moments |
| `cinematic-zoom` | `npx hyperframes add cinematic-zoom` | Hook dramatic zoom |
| `glitch` | `npx hyperframes add glitch` | Tech disruption scenes |
| `flash-through-white` | `npx hyperframes add flash-through-white` | Trigger flash cuts |
| `ripple-waves` | `npx hyperframes add ripple-waves` | Emotional transitions |
| `sdf-iris` | `npx hyperframes add sdf-iris` | Eye/focus reveals |
| `swirl-vortex` | `npx hyperframes add swirl-vortex` | Transformation vortex |
| `light-leak` | `npx hyperframes add light-leak` | Cinematic light flare |

### Components (copy-paste snippets)
| Component | Install | Use |
|-----------|---------|-----|
| `grain-overlay` | `npx hyperframes add grain-overlay` | Cinematic warmth on grand_takeaway |
| `shimmer-sweep` | `npx hyperframes add shimmer-sweep` | AI/premium feel on any template |
| `grid-pixelate-wipe` | `npx hyperframes add grid-pixelate-wipe` | Scene wipes |

### Media
| Block | Install | Use |
|-------|---------|-----|
| `nyc-paris-flight` | `npx hyperframes add nyc-paris-flight` | Travel/global reach scenes |
| `north-korea-locked-down` | `npx hyperframes add north-korea-locked-down` | "Locked out" / restricted scenes |
| `app-showcase` | `npx hyperframes add app-showcase` | Mobile app demos |

---

## Template Inventory

Templates in `hyperframes-templates/` — used by `generate_hyperframes_broll.mjs`:

| File | Section fit | What it shows |
|------|-------------|---------------|
| `tpl_hook_slam.html` | hook, trigger_1/2/3 | Bold slam text, dark bg, red accent |
| `tpl_stat_card.html` | body_1, body_2, trigger_2 | Single big stat/number |
| `tpl_two_col.html` | body_1, body_2 | Two-column fact comparison |
| `tpl_vs_split.html` | body_2, bridge | Left vs Right split screen |
| `tpl_flow_steps.html` | body_1, body_2 | Vertical 3-step flow |
| `tpl_quote_card.html` | grand_takeaway | Quote with attribution |
| `tpl_cta_card.html` | emotion_save | CTA with handle + follow prompt |
| `tpl_terminal.html` | body_1, body_2 | Typewriter terminal output |
| `tpl_checklist.html` | body_1, body_2, emotion_save | Animated check items |
| `tpl_timeline.html` | body_1, body_2 | Horizontal event timeline |
| `tpl_metric_grid.html` | trigger_2, body_2 | 2×2 metric grid |
| `tpl_callout_box.html` | trigger_1/2/3 | Colored callout/alert box |
| `tpl_persona_card.html` | context | Audience persona card |
| `tpl_before_after.html` | bridge | Before → After reveal |
| `tpl_data_chart.html` | body_1, body_2, trigger_2 | Animated bar chart for cost/ROI stats |
| `tpl_notification_stack.html` | trigger_1/2/3, body_1 | Stacked macOS notification banners |
| `tpl_flowchart_h.html` | body_1, body_2, bridge | Horizontal 3-step pipeline flow |
| `tpl_ig_cta.html` | emotion_save | Instagram-style follow CTA card |
| `tpl_ui_mockup.html` | `broll_type:"screen"` | Animated browser/app frame — replaces real screen recordings |
| `tpl_diagram_flow.html` | `broll_type:"diagram"` | Node-edge architecture diagram, builds component by component |
| `tpl_knowledge_graph.html` | `broll_type:"diagram"` + graph keyword | Central node + satellite nodes with animated connection lines |

---

## Documentation

```bash
npx hyperframes docs <topic>
# Topics: data-attributes, gsap, compositions, rendering, examples, troubleshooting
```

Full docs index (machine-readable, do NOT guess URLs):
```
https://hyperframes.heygen.com/llms.txt
```

---

## Linting — ALWAYS RUN AFTER CHANGES

```bash
npx hyperframes lint
```

Fix all **errors** before presenting the result. Warnings are informational.

---

## Project Structure

```
hyperframes-templates/
├── CLAUDE.md                    ← this file
├── tpl_hook_slam.html
├── tpl_stat_card.html
├── tpl_vs_split.html
├── tpl_flow_steps.html
├── tpl_quote_card.html
├── tpl_cta_card.html
├── tpl_terminal.html
├── tpl_checklist.html
├── tpl_timeline.html
├── tpl_metric_grid.html
├── tpl_callout_box.html
├── tpl_persona_card.html
├── tpl_before_after.html
├── tpl_two_col.html
├── tpl_data_chart.html          ← bar chart for cost/ROI stats
├── tpl_notification_stack.html  ← macOS notification banners for automation
├── tpl_flowchart_h.html         ← horizontal 3-step pipeline flow
├── tpl_ig_cta.html              ← Instagram follow CTA card
├── tpl_ui_mockup.html           ← animated browser/app frame (broll_type:"screen")
├── tpl_diagram_flow.html        ← architecture diagram, builds node by node (broll_type:"diagram")
└── tpl_knowledge_graph.html     ← knowledge graph with central + satellite nodes (broll_type:"diagram")
```

## broll_type Routing

Stage 1 script JSON controls which template family runs:

| `broll_type` in section JSON | Template selected | How to use |
|------------------------------|-------------------|------------|
| `"clip"` *(default)* | ID/content-based auto-select | Normal content sections |
| `"screen"` | `tpl_ui_mockup.html` | Add when section shows a tool UI — generator detects tool name from `spoken`/`tool_mentioned` and injects color + workflow steps automatically |
| `"diagram"` | `tpl_diagram_flow.html` or `tpl_knowledge_graph.html` | Add when section explains architecture/process — generator picks knowledge_graph if "graph/wiki/brain/connect" in spoken, else flow diagram. Items from `card_lines` become nodes. |

**Example Stage 1 JSON fields:**
```json
{
  "id": "body_1",
  "broll_type": "screen",
  "tool_mentioned": "n8n",
  "card_lines": ["Webhook trigger", "Claude processes", "Gmail sends"],
  "spoken": "In n8n, you connect a webhook to Claude, and it sends the output to Gmail automatically."
}
```

```json
{
  "id": "body_2",
  "broll_type": "diagram",
  "card_lines": ["Raw Folder", "Codex AI processes", "Wiki Pages created", "Cross-links formed"],
  "spoken": "The knowledge graph connects everything you've ever saved into an interconnected wiki."
}
```
