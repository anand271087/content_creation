# ZeroHands VSL — 16:9 long-form

One-off job, **not** routed through the 9:16 viral-reel pipeline.

## Folder map

```
vsl/
├── inputs/                  source docs (do not edit in place — copy + modify if you want to tweak)
│   ├── VSL_Script.docx
│   └── VSL_Production_Bible.docx
├── assets/
│   ├── avatar/              HeyGen renders per segment, named <segment_id>.mp4
│   ├── screenrec/           YOU drop the 3 screen recordings here
│   │   ├── instagram_scroll.mp4       45–60s, slow scroll of @automatewithanand, silent
│   │   ├── heygen_walkthrough.mp4     60–90s, HeyGen avatar creation, silent
│   │   └── elevenlabs_walkthrough.mp4 60–90s, ElevenLabs voice clone, silent
│   ├── slides/              Hyperframes slide renders per slide_id, generated
│   └── captions/            Whisper word timestamps per segment, generated
├── scripts/                 build scripts (parse / extract_brand / heygen / compose)
├── output/                  final VSL mp4 lands here
├── segments.json            written by parse_script.py
├── brand.json               written by extract_brand.py (palette pulled from zerohands.co)
├── state.json               per-segment content hash (drives modular re-render)
└── README.md
```

## Avatar mapping

| Look | HeyGen avatar ID env | Used for |
|------|----------------------|----------|
| 1 (tight, hook) | `HEYGEN_AVATAR_ID_GREY` | `hook` and `objection` segments |
| 2 (medium, body) | `HEYGEN_AVATAR_ID_BLUE` | every other segment |

Voice: existing `HEYGEN_VOICE_ID` for both.

## Screen recording usage (read this before recording)

The avatar's voice is the audio source for every segment. Screen recordings play *visually* underneath the avatar narration — **record silently, no narration over the top.** Just do the actions on screen.

- **`instagram_scroll.mp4`** — 45–60s slow scroll of your IG profile on mobile. Used during the `proof` segment.
- **`heygen_walkthrough.mp4`** — 60–90s of: avatar creation page → upload footage → see generated avatar. Used during the first half of `value_step2_clone`.
- **`elevenlabs_walkthrough.mp4`** — 60–90s of: voice creation → upload audio → see trained clone. Used during the second half of `value_step2_clone`.

If a file is missing at compose-time, that segment falls back to a Hyperframes placeholder slide — you can re-render just that segment later by dropping the file in and re-running compose.

## Re-running after a script tweak

`state.json` stores a content hash per segment. Re-running the pipeline:
- Unchanged hash → reuses existing `avatar/<id>.mp4` (no HeyGen call)
- Changed hash → re-renders just that segment
- Compose always re-runs from current assets

## Build order

1. `python3 vsl/scripts/extract_brand.py` → writes `brand.json` from zerohands.co
2. `python3 vsl/scripts/parse_script.py` → writes `segments.json` from the docx
3. *Inspect `segments.json` — confirm visually before any HeyGen calls.*
4. `node vsl/scripts/render_slides.mjs` → renders all Hyperframes slides into `assets/slides/`
5. *Spot-check a few slides — confirm before HeyGen.*
6. `python3 vsl/scripts/heygen_render.py` → calls HeyGen per segment, writes to `assets/avatar/`
7. `python3 vsl/scripts/compose.py` → captions, PIP, concat → `output/zerohands_vsl_16x9.mp4`
