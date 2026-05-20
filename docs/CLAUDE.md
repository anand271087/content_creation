# AI Reel Pipeline — Operating Guide

This file guides Claude Code when working inside the productized reel pipeline. It
describes the system at a working level: how a prompt becomes a finished vertical
video reel, where the moving parts are, and what to touch (or not) when extending it.

---

## What This System Does

Input  : a short topic, transcript, or content brief
Output : a 60–90 second vertical (9:16) video reel — talking-head avatar with motion
         graphic b-roll, burned-in captions, ambient audio, thumbnail card, and
         ready-to-post social copy.

The pipeline is deterministic, resumable, and runs end-to-end from a single command.

---

## Run the Pipeline

```bash
# End-to-end from a prompt-derived script
python3 pipeline.py --topic "<your topic line>"

# Resume from a transcript file
python3 pipeline.py --transcript path/to/transcript.txt

# Resume from an existing script (skips script generation)
python3 pipeline.py --script assets/script_data.json

# Skip individual stages (when re-using prior outputs)
python3 pipeline.py --topic "..." --skip-broll
python3 pipeline.py --topic "..." --skip-avatar
python3 pipeline.py --topic "..." --skip-music
```

The pipeline writes `pipeline_state.json` after each stage. Re-running the same
command auto-resumes from the last incomplete stage.

---

## Stages (What Each One Owns)

| # | Stage              | Owns                                                          | Output                                  |
|---|--------------------|----------------------------------------------------------------|------------------------------------------|
| 1 | Script Generation  | Topic / brief → structured script with 10 narrative sections   | `assets/script_data.json`                |
| 2 | B-Roll Generation  | Per-section motion-graphic / screen / diagram clips            | `assets/broll/*.mp4`                     |
| 3 | Avatar Generation  | Synthetic talking-head from the spoken script                  | `assets/avatar/avatar_video.mp4`         |
| 4 | Audio Generation   | Ambient bed tracks + impact stings at trigger moments          | `assets/music/*.mp3`                     |
| 5 | Compose & Render   | Transcript alignment + final 1080×1920 reel + 1.25× fast cut   | `assets/final/final_reel*.mp4`           |
| 6 | Quality Review     | Multi-image visual evaluation against design rubric            | `assets/analysis/video_analysis.json`    |
| 8 | Social Copy        | YouTube / Instagram / LinkedIn captions and hashtags           | `assets/social/*.txt`                    |

Stages 2, 3, and 4 run in parallel. Stage 5 runs after all three complete.

---

## Where The Client Prompt Goes

A client-supplied prompt template controls how Stage 1 turns the input topic into a
structured script. See `docs/PROMPT_TEMPLATE.md` for the slot. Anything pasted there
replaces the default prompt — the rest of the pipeline is template-agnostic and
picks up from the produced `script_data.json`.

---

## Data Contract Between Stages

Every stage downstream of Stage 1 reads `assets/script_data.json`. The schema is
fixed — do not rename fields without updating every consumer. Key fields:

- `total_duration_sec`   — final reel length target
- `bgm_dip_timestamps`   — when ambient music dips for impact stings
- `bgm_transition_sec`   — where tension track switches to warm track
- `full_spoken_script`   — exact text the avatar speaks
- `grand_takeaway_line`  — quotable line used in the takeaway template
- `sections[]`           — 10 objects with id, start_sec, end_sec, spoken,
                           on_screen_text, broll_prompt, expression_cue,
                           vocal_direction, bgm_dip, bgm_track, broll_type

`broll_type` values:
- `clip`     — motion-graphic clip rendered in browser, shows in rounded box
- `screen`   — screen recording of a real product UI
- `diagram`  — node-edge / knowledge-graph animation
- `terminal` — synthetic terminal demo

---

## Operating Rules

- All API keys live in `.env`. Never commit, never hardcode.
- Every download verifies non-zero filesize before marking complete.
- All API calls use exponential backoff (1s → 2s → 4s) over 3 attempts.
- Structured logs go to `logs/pipeline.log`. Use this to debug, not stdout.
- Stage return type is uniform: `{success: bool, output_path: str,
  duration_sec: float, error: str | None}`.
- Crash recovery is automatic via `pipeline_state.json`.
- Stale-asset guard: if `script_data.json` is newer than a downstream asset, that
  asset is deleted and its stage is reset on the next run.

---

## When You Are Asked To Change Behaviour

| Request                                           | File to edit                                        |
|---------------------------------------------------|------------------------------------------------------|
| Change the scripting style / prompt               | The client prompt template in `docs/PROMPT_TEMPLATE.md` |
| Change visual templates for b-roll                | `hyperframes-templates/*.html`                       |
| Change rhythm cuts, captions, layout              | `remotion/src/components/*.tsx`                      |
| Change avatar voice / face                        | `.env` (`HEYGEN_AVATAR_ID`, `HEYGEN_VOICE_ID`)       |
| Change music prompts                              | `stages/stage4_music.py`                             |
| Change parallelism or stage order                 | `pipeline.py`                                        |

---

## Linting & Verification

Before shipping any rendered reel:

```bash
npx hyperframes lint    # validate composition templates
```

Fix every error before treating a render as final. Warnings are informational only.

---

## Important: What Not To Do

- Do not edit `assets/script_data.json` by hand once a render has started — it
  breaks the broll/caption sync contract. Re-run from Stage 1 instead.
- Do not skip `sync_broll_to_speech` unless you have manually aligned timestamps
  to the actual avatar speech (use `SKIP_BROLL_SYNC=1` only when intentional).
- Do not commit generated assets — they are large and reproducible.
