# ZeroHands VSL — creative direction (baked into the build)

These are the deliberate departures from the literal Bible spec, made to maximise YouTube watch-time and call-booking rate. The Bible is the floor, not the ceiling.

## 1. The reveal is the single most important moment
- During hook lines 1–3, a tiny pulsing **"AI · GENERATED"** badge sits in the top-right corner. Barely noticeable consciously. The brain registers it subconsciously.
- At the reveal sentence ("That was my AI avatar. And you didn't even notice."):
  - Hard audio cut → 0.4s silence
  - Badge flashes full-screen for 12 frames
  - Zoom-punch on avatar face from 100% → 108% over 6 frames
  - Then return to clean Look 1 frame for the rest of the reveal beat
- This is the moment that earns the next 12 minutes of attention.

## 2. Hook cut rate: 1.8–2.5s, not 3–5s
- YouTube's first-30s retention curve rewards aggressive opens harder than the Bible's reference VSLs (which were 2023-era).
- Cuts every ~2s during 0:00–0:20; calm to the Bible's 1–2 min/slide from 1:05 onward.

## 3. Four title cards, not three
- The Reveal (between `objection` and `soft_cta`) — new
- The Proof (existing, before `proof`)
- The System (existing, before `solution`)
- The Funnel (existing, before `value_step3_funnel`)
- 1.2s each, hard cut in/out, no transitions.

## 4. Captions: long-form YouTube style, not Hormozi reel
- 2 lines max, ~6 words per line
- Inter Bold sans-serif, 56pt, white with 3px black stroke
- One brand-blue (#2979ff) keyword highlight per line (whichever noun carries the most weight)
- Bottom-third safe zone (y = 850, 9-pixel margin from PIP if PIP is bottom-left)
- Whisper-aligned word timestamps; no single-word zoom (reads as frantic over 13 min)

## 5. Micro-cuts during value-give (drop-off prevention)
- During `value_step1_strategy`, `value_step2_clone`, `value_step3_funnel`:
- Every ~10s, a keyword + icon pops up next to the avatar PIP for ~2.5s, then disappears (no transition)
- Example keywords: "NICHE", "PILLARS", "HOOK · BODY · CTA", "HEYGEN", "ELEVENLABS", "CLAUDE", "MANYCHAT", "n8n", "BOOKED CALL"
- Small (180×60px), brand-blue background, white text, top-right corner

## 6. Pitch-pivot at 9:15
- Hard cut all visuals (per Bible)
- Plus: hard audio cut → 0.6s of literal silence
- Then re-enter on clean Look 2 full-face frame
- The silence makes the viewer lean forward exactly when the offer starts

## 7. Thumbnail
- Extract the most expressive frame from Look 1 (preferably mid-reveal)
- Overlay: bold "I HAVEN'T FILMED THIS" (or close variant) in brand blue with black stroke
- Tiny "AI · GENERATED" badge top-right (echo of the in-video badge)
- Output: `vsl/output/thumbnail.png` at 1920×1080

## 8. Loop-bait outro
- Final 1.5s of the outro: smash-cut back to the hook's H1 slide ("Never film another video again")
- Increases YouTube session-time signal — viewers hesitate, some restart
- Avatar audio ends cleanly before the cut; the loop is pure visual

## 9. What I'm NOT changing
- Spoken script text — Bible-sanctioned, leave it
- Single offer path — one CTA only
- No music — voice only with light compression + EQ
- Hard cuts only — no whooshes/wipes/crossfades
- Two looks (Grey hook / Blue body)
- 16:9, 1920×1080, ~12:00 runtime

## Quality bar
- The avatar should never be the centre of attention for more than 8 consecutive seconds without a visual cutaway, keyword pop, or PIP shift. The Bible covers why — small lip-sync issues compound over a long-form runtime.
- Every slide must work as a freeze-frame screenshot (someone WILL screenshot the framework diagrams).
- The reveal at 0:14 and the pitch pivot at 9:15 are the two moments where retention either holds or breaks. Both engineered above.
