# Editing Techniques Library

Distilled from 5 reference reels (2026-07-20). Per-reel deep dives with frames live in
`assets/reference_analysis/<code>/techniques.md`. Use this file to pick techniques;
use the per-reel files for exact mechanics.

| Code | Creator | What it is |
|------|---------|------------|
| DambEp1igDW | @realskytan | "Perfect scripting structure" — wireframe structure board, 35s |
| Da5JDSjv7zI | rrishijain | Pinterest→Gemini→Flow clone tutorial — before/after self-demo, 43s |
| DYpUDeCu9xV | @npcfaizan | "Viral formats: Yapping" — chaptered listicle masterclass, 125s |
| Dadfan2OglS | @max_v.v | "25 tools" category flash-list, 7.4s loop reel |
| DY2glqovla6 | @iamjoeanderson | Edits-app text-reveal tutorial — annotation stack, 36s |

Status: ✅ = existing machinery · 🔨 = small build (≤half day) · 🏗 = medium build

---

## 1. HOOKS / OPENS

| Technique | Source | Mechanics | Recipe | Status |
|---|---|---|---|---|
| **Before/after self-demo split** | Da5JDSjv7zI | Top half = SAME take AI-restyled into the effect being taught, bottom = raw, lip-synced; split exits on the promise word ("two minutes") | vstack via OverlayChain + one AI restyle pass of our own clip | 🔨 |
| Rapid-fire framework reveal | DambEp1igDW | 8 diagram elements pop word-synced in 4.6s — naming the parts IS the hook | tier_board reveal mechanics, no-hook rule | ✅ |
| Result-first cold open | DY2glqovla6 | Finished effect plays full-frame 0–2.5s before any explanation; frame 1 mid-motion | `formats/video_hook.py apply_hook()` / Format #8 addendum #1 | ✅ |
| Word-built title header | DYpUDeCu9xV | Title assembles word-by-word; emphasis word serif-italic inside red highlight bar | New PIL lockup style + OverlayChain windows | 🔨 |
| Scrolling thumbnail filmstrip | DYpUDeCu9xV | 2 rows of reel thumbnails sliding opposite directions under the hook title | GSAP x-tween chroma template or ffmpeg pan | 🔨 |
| Stacked title lockup | DY2glqovla6 | 3-line overlap: small white / huge yellow condensed / small white, hard shadows | One PIL function | 🔨 |
| Whole-board flash open | Dadfan2OglS | Frame 0 is already the full first board; swap entire board per category clause | OverlayChain enable windows | ✅ |

## 2. REVEALS / OVERLAY MECHANICS

| Technique | Source | Mechanics | Recipe | Status |
|---|---|---|---|---|
| **Person-occlusion text reveal** | DY2glqovla6 | Giant text sandwiched BETWEEN background and subject — wipes on as subject walks past | RVM matte (`editing/replace_background.py`) as alpha; composite text under it | 🏗 top steal |
| **Recurring agenda card w/ ghost rows** | DYpUDeCu9xV | Glassy card with N ghosted rows returns each chapter; active row un-blurs crisp on the spoken word | tier_stack unblur + checklist ghosting, new compositor pattern | 🏗 top steal |
| Whole-board hard swap | Dadfan2OglS | Header + all rows replaced in ONE frame at clause_start − 0.1s; ~1.4s per board | OverlayChain windows from Scribe | ✅ |
| Pop-blur logo card | (verdict_board, built) | Card pops center with blur-in, shrink-lands as tile | `motion/templates/pop_card.html` + verdict_board | ✅ |
| Sticker accumulation | Da5JDSjv7zI | Collage stickers (torn paper, tape, comic bursts, arrows) add one per beat on styled footage | motion.py spring pops + one-time collage PNG pack | 🏗 |
| Wireframe bar-group cards | DambEp1igDW | "Redacted text" colored bar groups as abstract framework elements | New small PIL builder | 🔨 |
| Evidence-grid build | DYpUDeCu9xV | Screenshot cards (shadow, slight rotation) pop into 2×2 grid; green ▲view pills stamp on as proof | tier_board land + proof pills | 🔨 |
| Phone-frame video pop | DYpUDeCu9xV | Example reel PLAYS inside rounded white phone card, overshoot pop at name-drop | Rounded-mask `add_video` helper + spring pop | 🔨 unlocks A<B compares |
| Device mockup demos | DY2glqovla6 | Screen recordings inside iPhone-frame PNG on cream backdrop, scale varies per beat | `device_frame()` compositor over capture stack | 🔨 |
| Annotation stack (arrows + tap-rings) | DY2glqovla6 | Hand-drawn arrow on the spoken VERB; white ring pulse on the tapped UI element | GSAP draw-on templates (motion.py chroma) | 🔨 |
| Profile-pill social proof | DYpUDeCu9xV | pfp + handle + follower-count pill pops at creator name-drop | spring_label + PIL | ✅ |
| Analytics receipt card | DYpUDeCu9xV | Dark stat card (views/watch-time rows) as claim proof | PIL card | 🔨 |
| Label carry-over across cut | DY2glqovla6 | Overlay outlives its cut by ~0.5s, sits on the incoming frame | OverlayChain window straddling the cut | ✅ |
| Typewriter w/ color tail | DambEp1igDW | Characters type in accent color, settle to white | New GSAP template | 🏗 |
| Letter blur-in section labels | DambEp1igDW | Big label letters blur in left→right stagger | GSAP per-char stagger template | 🔨 |
| Script-progress tracker | DambEp1igDW | Bottom segmented line (section names), active segment underlined, appends over time — retention meter | PIL state PNGs swapped by OverlayChain | 🏗 |

## 3. TRANSITIONS / SEAMS / RHYTHM

| Technique | Source | Mechanics | Recipe | Status |
|---|---|---|---|---|
| Whip-blur / defocus-pull seam | DY2glqovla6 | Gaussian blur ramp ~0.2s out, next scene enters blurred, snaps sharp ~0.4s | ffmpeg gblur ramp in OverlayChain — 2nd seam flavor beside light-leak | 🔨 |
| Motion-blur stack wipe-out | DambEp1igDW | Whole overlay stack wipes up with blur before a title beat | GSAP y-tween + blur | 🔨 |
| Micro punch-ins per sentence | DYpUDeCu9xV | ~1.6→1.7× zoom pulses on sentence starts | `editing/viral_edit.py` punches | ✅ |
| Per-chapter light/dark palette inversion | DYpUDeCu9xV | Boards flip dark ↔ cream per chapter as macro pattern interrupt | Palette swap per phase | ✅ decision |
| Zoom-OUT payoff ending | DambEp1igDW | Avatar shrinks, full framework fills frame at the end | ffmpeg keyframe zoom-out (we only had zoom-in) | 🔨 |
| **NO light-leaks trend** | 3 of 5 reels | Overlay density + hard word-synced cuts carry rhythm; zero flashes | Make `flash_at` optional per format — not a default | ✅ decision |
| Voice-as-metronome | Dadfan2OglS | Identical 4-word chant per beat; visuals carry the content | Scripting pattern | ✅ |

## 4. CAPTIONS / TYPE

| Technique | Source | Mechanics | Recipe | Status |
|---|---|---|---|---|
| **Lowercase micro-captions (TREND)** | 4 of 5 reels | Single word or short phrase, lowercase, white, mid-frame, swap at word_start; NO all-caps karaoke, no stroke | Caption-style flag; 5th consecutive top-creator data point | 🔨 make it a mode |
| Keyword-only captions | DY2glqovla6 | ONE noun/verb per beat ("app", "drag", "mask"), filler skipped | Scribe words + keyword filter | 🔨 |
| Mixed-typography seam captions | Da5JDSjv7zI | Sans accumulate + yellow serif-italic emphasis words on the split seam | Format #8 addendum styles | ✅ |
| Serif editorial board header | Dadfan2OglS | Playfair-class serif centered top, swaps with board | PIL font class | 🔨 |
| Two-tone label | DY2glqovla6 | White word + yellow numeral, drop shadow | Accent glyph in pill builders | ✅ |
| Ghost-grey placeholder text | DambEp1igDW | 40%-opacity example text = "this is a template" | PIL opacity | ✅ |

## 5. LEGIBILITY / GRADE
- **Dark-grade-as-text-bed** (Dadfan2OglS): crush shadows + vignette so raw white text reads with NO pills — inverse of our dark-pill rule; use on dark/moody looks. 🔨
- **Top-gradient darkening** (DambEp1igDW): gradient instead of pills for top-anchored overlays. ✅ analog exists
- **Single-accent discipline** (DY2glqovla6): one accent color across every overlay class per reel — matches brand rule. ✅

## 6. CTA / ENDINGS
- **Blurred-payoff CTA** (DYpUDeCu9xV): the promised database/screenshot shown fully blurred + keyword — curiosity engine for lead magnets. 🔨
- **Loop-bait promise gap** (Dadfan2OglS): hard-cut mid-list (20 of 25 shown) → rewatch + comments. ✅ decision
- **CTA pill + shine sweep** (DY2glqovla6): glassy pill pops exactly on "follow", specular sweep. 🔨 polish
- **Quoted-keyword pop** (Da5JDSjv7zI): huge yellow serif-italic quoted keyword beside head, holds to end. ✅
- **Export-screen-as-proof** (DY2glqovla6): real render/progress UI as the receipt before the result. ✅ capture stack
- **Real-outcome ending / end on payoff**: 5 of 5 reels end within ~1s of the last payoff. ✅ house rule confirmed

## 7. CROSS-CUTTING LAWS (all 5 reels agree)
1. Every reveal is word-synced (word_start − 0.15s rule validated everywhere).
2. Lowercase small captions have replaced all-caps karaoke among top editors.
3. Rhythm comes from overlay density + hard cuts, not flashes/transitions.
4. Proof beats claims: receipts, view pills, export screens, self-referential demos.
5. End the instant the payoff lands.

## New format variants queued (build on request)
- **structure_board** (DambEp1igDW): teaches a STRUCTURE with named parts → wireframe board + progress tracker. Decision rule: "script names ordered parts of a whole".
- **category_flash** (Dadfan2OglS): many tools grouped by use-case, rapid-fire <15s loop. Decision rule: "N tools by category, no reasons".
- **chaptered listicle** (DYpUDeCu9xV): "three things" masterclass = Format #8 split + agenda card + evidence grids.
- **before/after self-demo** (Da5JDSjv7zI): Format #8 variant for any "AI restyles video" topic.
