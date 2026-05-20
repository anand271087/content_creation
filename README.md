# Viral Reel Automation Pipeline — `@automatewithanand`

End-to-end automation that takes a **topic or transcript** and produces a fully edited **9:16 vertical reel** (Instagram / YouTube Shorts) — script, b-roll, AI avatar, music, captions, on-screen text, BGM ducking, DSSCL virality scoring, and platform-specific social copy — all written to `assets/final/`.

Built around four AI services (Claude API, HeyGen, Kie.ai, OpenAI Whisper) plus a [Remotion](https://www.remotion.dev/) composition for the final render.

---

## Quick start (60 seconds)

```bash
# 1. Install deps (one-time)
pip install -r requirements.txt
cd remotion && npm install && cd ..
brew install ffmpeg                # macOS

# 2. Fill in API keys
cp .env.example .env                # then edit .env

# 3. Run the pipeline
python3 pipeline.py --topic "AI agents explained in 3 steps"
# OR
python3 pipeline.py --transcript path/to/transcript.txt
```

Output: `assets/final/final_reel.mp4` (1×) and `assets/final/final_reel_fast.mp4` (1.25× sped-up — usually the deliverable).

---

## What it does

```
Topic / Transcript
   └──► Stage 1  Script (Claude API + GOAT framework, DSSCL ≥ 9.5)
   └──► Stage 2  B-roll per section (Hyperframes motion graphics + Kie.ai fallback)
   └──► Stage 3  Avatar talking-head (HeyGen)
   └──► Stage 4  BGM tracks + impact stings (Kie.ai ElevenLabs)
   └──► Stage 5  Whisper captions → sync timestamps → Remotion render
   └──► Stage 6  DSSCL virality scoring on the rendered video (Claude vision)
   └──► Stage 7  Capture learnings (decisions + lessons → memory)
   └──► Stage 8  Platform-specific social copy (Instagram / LinkedIn / YouTube)

Final: assets/final/final_reel.mp4 + final_reel_fast.mp4
```

Stages 2, 3, 4 run **in parallel** via `ThreadPoolExecutor`. Stage 5 waits on all three. Crash-resume is automatic via `pipeline_state.json`.

---

## Setup in detail

### 1. System dependencies

```bash
brew install ffmpeg              # macOS — verify: ffmpeg -version
sudo apt install ffmpeg          # Ubuntu/Debian
```

### 2. Python dependencies

```bash
pip install -r requirements.txt
```

Includes `anthropic`, `requests`, `openai-whisper`, `torch`, `python-dotenv`, `tqdm`.

### 3. Node / Remotion dependencies

```bash
cd remotion && npm install && cd ..
```

### 4. API keys (`.env`)

Copy `.env.example` to `.env` and fill in:

| Variable | Used by | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | Stage 1 (script), Stage 6 (video scoring) | https://console.anthropic.com |
| `KIE_API_KEY` | Stage 2 (b-roll fallback), Stage 4 (BGM) | https://kie.ai |
| `HEYGEN_API_KEY` | Stage 3 (avatar) | https://app.heygen.com → API |
| `HEYGEN_VOICE_ID` | Stage 3 | HeyGen voice library |
| `HEYGEN_AVATAR_ID` | Stage 3 | HeyGen avatar library |
| `WHISPER_MODEL` | Stage 5 (captions) | Use `medium` (default) or `large-v3` for best accuracy on proper nouns |
| `BROLL_MODEL` | Stage 2 fallback | Default: `kling-2.6/text-to-video` |

---

## Run the pipeline — every option

```bash
# Full run from a topic
python3 pipeline.py --topic "How to use Claude /goal"

# From a transcript file (recommended — gives Stage 1 more context)
python3 pipeline.py --transcript assets/transcript.txt

# From an existing script (skips Stage 1 entirely)
python3 pipeline.py --script assets/script_data.json

# From a research JSON (output of a topic-research step)
python3 pipeline.py --research-json path/to/research.json

# Dry run — Stage 1 only, prints script JSON, no external API calls past Claude
python3 pipeline.py --topic "..." --dry-run

# Skip individual stages (reuses existing assets in assets/)
python3 pipeline.py --topic "..." --skip-broll
python3 pipeline.py --topic "..." --skip-avatar
python3 pipeline.py --topic "..." --skip-music
python3 pipeline.py --topic "..." --skip-social
```

---

## Generate ONE reel — the recommended workflow

This is the workflow I use most often. It gives you a checkpoint between the cheap text-only stages and the expensive HeyGen render, so you can edit the script before burning credits.

### Step 1 — Write a transcript brief

Drop a `transcript.txt` into `assets/`. It can be a YouTube transcript, a rough idea, or a structured brief. Stage 1 reads this and converts it into a polished 10-section reel script.

For best results, your brief should include:
- The **core angle / emphasis** in one sentence
- **Hard constraints** (audience, ideal length, what NOT to say)
- **Key proof moments** — specific numbers, real examples, named tools
- **Grand takeaway** — the quotable climax line
- **CTA hook** — the comment-trigger and DM-offer

See [assets/transcript.txt](assets/transcript.txt) (if present after a run) for an example.

### Step 2 — Generate the script alone

```bash
python3 stages/stage1_script.py --transcript assets/transcript.txt
```

This:
1. Loads `scripts/reference_scripts/english-hooks.md` (200 hook templates) and `content-formats.md` (47 formats)
2. Calls Claude with the GOAT framework prompt
3. Iterates on the script until DSSCL ≥ 9.5 (max 5 attempts)
4. Writes `assets/script_data.json` and prints a preview

Open `assets/heygen_input.txt` to see the clean spoken-script paste-into-HeyGen text.

### Step 3 — Sanity-check the script

```bash
# What the section structure looks like + total word count
python3 -c "
import json
s=json.load(open('assets/script_data.json'))
for sec in s['sections']:
    w=len(sec.get('spoken','').split())
    print(f\"  {sec['id']:<18} {sec['broll_type']:<10} {w:>3}w\")
print(f'total: {sum(len(s.get(\"spoken\",\"\").split()) for s in s[\"sections\"])} words')
"
```

**Word-count calibration:** ~4 words/sec final-cut speed after 1.25× speed-up. For a **90-second** 1.25× cut, target **~360 spoken words** total. For a 60-second cut, target **~240 words**.

### Step 4 — Pre-flight checks (highly recommended)

The script generator sometimes emits `broll_type: "screen"` with `screen_capture.url` pointing at `claude.ai` / `openai.com`. Those URLs hit Cloudflare verify pages and the b-roll generator records the verify page. **Patch them to `clip`:**

```bash
python3 -c "
import json
with open('assets/script_data.json') as f: s = json.load(f)
patched = 0
for sec in s['sections']:
    if sec.get('broll_type') == 'screen':
        sec['broll_type'] = 'clip'
        if 'screen_capture' in sec:
            sec['_disabled_screen_capture'] = sec.pop('screen_capture')
        patched += 1
with open('assets/script_data.json', 'w') as f: json.dump(s, f, indent=2)
print(f'Patched {patched} screen sections -> clip')
"
```

### Step 5 — Generate the avatar (HeyGen)

Two options:

**Option A — Automated (HeyGen API, costs credits):**

Run the full pipeline with `--skip-music` (music placeholders already exist). HeyGen call costs credits; budget accordingly.

```bash
python3 pipeline.py --transcript assets/transcript.txt --skip-music
```

**Option B — Manual (zero API cost):**

1. Open HeyGen UI → pick your avatar + voice
2. Paste the text from `assets/heygen_input.txt`
3. Render 9:16, black background `#000000`
4. Save the file as `assets/avatar/avatar_video.mp4`
5. Seed `pipeline_state.json` to skip Stage 3:

```bash
python3 -c "
import json
state = {
    'stage1_complete': True, 'stage2_complete': False, 'stage3_complete': True,
    'stage4_complete': True, 'stage5_complete': False, 'stage6_passed': False,
    'stage8_complete': False, 'pipeline_iteration': 3,
    'avatar_path': 'assets/avatar/avatar_video.mp4',
    'script_path': 'assets/script_data.json', 'broll_paths': {},
    'music_paths': {k: f'assets/music/{f}' for k, f in [
        ('track1','track1_tension.mp3'),('track2','track2_warm.mp3'),
        ('sting1','sting1.mp3'),('sting2','sting2.mp3'),('sting3','sting3.mp3'),
        ('hook_sting','hook_sting.mp3')]},
    'video_analysis': None, 'error': None, 'run_id': 'manual', 'transcript': '',
}
json.dump(state, open('pipeline_state.json','w'), indent=2)
print('state seeded')
"
python3 pipeline.py --transcript assets/transcript.txt --skip-music
```

> `pipeline_iteration: 3` disables the iteration retry loop. Set to `1` if you want the loop to retry on DSSCL < 9.0.

### Step 6 — Append the thumbnail card (optional)

After Stage 5 finishes, append the auto-generated thumbnail PNG as a 1.5-second card at the end of both reels:

```bash
python3 scripts/append_thumbnail.py
```

Writes `final_reel_with_thumb.mp4` and `final_reel_fast_with_thumb.mp4` alongside the originals.

### Step 7 — Verify every section made it into the render

```bash
python3 scripts/verify_assets_in_video.py
```

Per-section manifest with status: `OK / TINY⚠ / MISSING / ORPHAN`. Confirms zero screen captures, zero broken clips, and every section is referenced in the Remotion props.

---

## Output files

| Path | What it is |
|---|---|
| `assets/script_data.json` | 10-section structured script + DSSCL scores + on-screen text + b-roll prompts |
| `assets/heygen_input.txt` | Clean spoken script to paste into HeyGen UI |
| `assets/broll/*.mp4` | Per-section b-roll clips (Hyperframes motion graphics or Kling fallback) |
| `assets/diagrams/*.png` | Source PNGs for `broll_type: diagram` sections |
| `assets/avatar/avatar_video.mp4` | HeyGen-rendered talking-head video |
| `assets/music/*.mp3` | BGM tracks + impact stings |
| `assets/captions/avatar_video.json` | Whisper word-level timestamps |
| `assets/final/final_reel.mp4` | 1× full-quality render |
| `assets/final/final_reel_fast.mp4` | 1.25× sped-up cut (this is usually the deliverable) |
| `assets/final/final_reel_with_thumb.mp4` | 1× cut + 1.5s thumbnail card appended at end |
| `assets/final/final_reel_fast_with_thumb.mp4` | 1.25× cut + 1.5s thumbnail card |
| `assets/final/thumbnail.png` | Auto-generated thumbnail (9:16) |
| `assets/analysis/video_analysis.json` | Stage 6 DSSCL scores + strengths + weaknesses + per-frame feedback |
| `assets/social/instagram.txt` | IG caption + 10 hashtags |
| `assets/social/linkedin.txt` | LinkedIn post copy |
| `assets/social/youtube.txt` | YouTube Shorts title + description |

---

## Hard rules I learned the hard way

### 1. NEVER `broll_type: "screen"` on `claude.ai`, `chatgpt.com`, `openai.com`, or any login-walled URL

The screen-broll generator opens those URLs in a headless browser → Cloudflare "verify you are human" page → that page gets recorded as the b-roll → kills retention. **Patch every `"screen"` section to `"clip"` before running Stage 2.** See [Step 4](#step-4--pre-flight-checks-highly-recommended).

### 2. NEVER drop first-person identity claims for the avatar

The avatar is **Anand**. The source YouTube videos often contain personal claims from the source creator (religion, family size, company size, location). Without explicit guardrails, Stage 1 will copy those into Anand's first-person script. Always include hard constraints in your brief:

> The avatar is ANAND. NEVER write first-person claims about religion, family, nationality, marital status, scale ("250-person company"), or any identity trait that is not established for Anand. Frame all claims as a hands-on operator: "I ran this test", "I tried this last night".

### 3. NEVER let stale assets linger between runs

The pipeline has a stale-asset guard that compares `script_data.json` mtime vs each asset's mtime. If the script is newer, the asset is deleted and the stage is reset. But this only catches assets in `assets/avatar/` and `assets/broll/`. Manually wipe everything between unrelated runs:

```bash
find assets/broll assets/avatar assets/captions assets/final assets/analysis assets/screen_screenshots assets/screen_timelines assets/diagrams assets/social -mindepth 1 -type f -delete 2>/dev/null
rm -f assets/script_data.json assets/script_data.json.bak assets/heygen_input.txt assets/remotion_props.json assets/remotion_debug_props.json assets/transcript.txt pipeline_state.json logs/pipeline.log
```

### 4. Single-pass vs iteration loop

By default, Stage 6 scores the video on DSSCL. If `final < 9.0`, the pipeline regenerates Stage 1 with feedback and re-runs Stages 2–6. This burns HeyGen credits fast and rarely passes 9.0 on a second try. **To force single-pass, seed `pipeline_iteration: 3` in `pipeline_state.json` before running.**

### 5. HeyGen ≠ deterministic

HeyGen sometimes returns `MOVIO_PAYMENT_INSUFFICIENT_CREDIT` (you're out of credits) or `workflow internal error: Queue is closed` (their server bug). On the latter, retry — usually works second time. On the former, top up.

---

## Architecture deep-dive

See [CLAUDE.md](CLAUDE.md) for the full architecture document, including:
- Per-stage data contracts
- The DSSCL virality framework (D × 0.30 + S × 0.25 + Save × 0.25 + C × 0.10 + L × 0.10)
- The 10-section reel structure (HOOK → CONTEXT → TRIGGER 1 → BODY 1 → ... → EMOTION_SAVE)
- Remotion composition layout (avatar bottom 50%, b-roll top 50%, Hormozi-style captions)
- BGM ducking + sting trigger timing
- Whisper-aligned section timestamp resync (`scripts/sync_broll_to_speech.py`)
- The GOAT framework writing rules

---

## Utility scripts

```bash
# Align b-roll section timestamps to actual Whisper speech (Stage 5 internal)
python3 scripts/sync_broll_to_speech.py --dry-run    # preview
python3 scripts/sync_broll_to_speech.py              # apply

# Regenerate specific b-roll clips
python3 scripts/regenerate_broll.py body_1 emotion_save

# Pre-evaluate script quality (cheap text-only check) — auto-runs after Stage 1
python3 scripts/pre_evaluate_script.py

# Check b-roll clip quality (watermarks, generic stock) — auto-runs before Stage 5
python3 scripts/check_broll_quality.py

# Append thumbnail card at end of both renders
python3 scripts/append_thumbnail.py

# Verify every section's b-roll is present and referenced in the final render
python3 scripts/verify_assets_in_video.py
python3 scripts/verify_assets_in_video.py --strict    # exit 1 if any MISSING/TINY
```

---

## Folder map

```
/
├── CLAUDE.md                    architecture spec (read this)
├── README.md                    this file
├── pipeline.py                  master orchestrator
├── .env.example                 API key template
├── requirements.txt
├── package.json                 root npm metadata
│
├── stages/
│   ├── stage1_script.py         GOAT framework + DSSCL loop
│   ├── stage2_broll.py          Hyperframes + Kling fallback
│   ├── stage3_avatar.py         HeyGen
│   ├── stage4_music.py          Kie.ai ElevenLabs
│   ├── stage5_compose.py        Whisper → sync → Remotion render
│   ├── stage6_analyse.py        Claude vision DSSCL scoring
│   ├── stage7_learnings.py      capture decisions + lessons
│   └── stage8_social.py         platform-specific copy
│
├── remotion/                    Remotion composition (Next.js + React)
│   └── src/
│       ├── Root.tsx             calculateMetadata for dynamic duration
│       ├── ReelComposition.tsx  main 9:16 composition
│       └── components/          BrollPanel, AvatarPanel, HormoziCaptions, ...
│
├── hyperframes-templates/       motion-graphics b-roll templates
│
├── scripts/
│   ├── reference_scripts/       english-hooks.md (200) + content-formats.md (47)
│   ├── sync_broll_to_speech.py
│   ├── regenerate_broll.py
│   ├── pre_evaluate_script.py
│   ├── check_broll_quality.py
│   ├── append_thumbnail.py
│   └── verify_assets_in_video.py
│
├── assets/                      generated outputs (gitignored)
│   ├── broll/  avatar/  music/  captions/
│   ├── final/  analysis/  social/  diagrams/
│   └── script_data.json  heygen_input.txt  transcript.txt
│
└── logs/
    └── pipeline.log
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Remotion MEDIA_ELEMENT_ERROR Code 4` on b-roll | Kling generates H264 High/Main profile, Chromium rejects it | Stage 2 re-encodes every clip after download (baseline profile). If you see this, manually `ffmpeg -i in.mp4 -c:v libx264 -profile:v baseline -level 3.1 -pix_fmt yuv420p out.mp4` |
| Video abruptly cuts at 60s | `sync_broll_to_speech.py` not run, OR `durationInFrames` hardcoded | Stage 5 auto-syncs and Root.tsx uses `calculateMetadata`. Re-run Stage 5. |
| Old avatar reused in a new topic's video | Stale-asset guard didn't trip | `rm assets/avatar/avatar_video.mp4` and re-run |
| Whisper misidentifies proper nouns ("Claude" → "clot") | `small.en` model is inaccurate | Set `WHISPER_MODEL=large-v3` in `.env` (downloads ~1.5 GB first run) |
| Stage 4 music API failed | Kie.ai transient | Pre-baked silent placeholders + ffmpeg sub-bass stings work as fallback. Run pipeline with `--skip-music` and pre-place them. |
| Caption shows "FOLLOW -UPS" split | Whisper splits hyphenated words | `HormoziCaptions.tsx` already merges these. If it still leaks, check `extractWords()` |
| HeyGen `MOVIO_PAYMENT_INSUFFICIENT_CREDIT` | Out of credits | Top up at app.heygen.com |
| HeyGen `workflow internal error: Queue is closed` | HeyGen server bug | Retry — usually works second time |
| Pipeline retries Stage 3 even though avatar exists | Script mtime is newer than avatar mtime | `touch -t <past-time> assets/script_data.json` to backdate it |

---

## License & credits

- Pipeline orchestration + Remotion composition: original
- AI services: Anthropic Claude, OpenAI Whisper, HeyGen, Kie.ai
- Frameworks: GOAT (script writing), DSSCL (virality scoring), Hormozi-style captions

Built for [@automatewithanand](https://www.youtube.com/@automatewithanand) — AI automation for Indian builders.
