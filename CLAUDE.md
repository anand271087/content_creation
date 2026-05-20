# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# Viral Reel Automation Pipeline — @automatewithanand

---

## Bootstrap (run once on a fresh clone)

```bash
# Python dependencies
pip install -r requirements.txt

# Node/Remotion dependencies
cd remotion && npm install && cd ..

# System dependency
brew install ffmpeg          # macOS only — verify with: ffmpeg -version

# Copy and fill in .env before running anything
cp .env.example .env
```

## Active Claude Code Skills

Skills installed for this project — activate before the relevant work:

| Skill | Install | When to use |
|-------|---------|-------------|
| Skill Creator | `/plugin install skill-creator@claude-plugins-official` | Create `viral-reel` skill (one-time) |
| Superpowers | `/plugin install superpowers@claude-plugins-official` | Before editing any stage file — `/plan` first |
| GSD | `npx get-shit-done-cc --claude --global` ✅ installed | Isolated stage runs / debug sessions without polluting main context |
| /review | Built-in (Claude Code 2.1.86+) | After editing stage files before pipeline run |
| Context Mode | `/plugin marketplace add mksglu/context-mode` + `/plugin install context-mode@context-mode` | Hyperframes template debug cycles — `/context-mode on` |
| Claude Mem | `/plugin marketplace add thedotmack/claude-mem` + `/plugin install claude-mem` | End of each session — `/mem save` |
| Frontend Design | `/plugin install frontend-design@claude-plugins-official` | Before editing Remotion components or Hyperframes templates |

**GSD is already installed.** The other 6 require `/plugin install` commands run inside the Claude Code CLI (not in terminal).

---

## Running the Pipeline

```bash
# Full run from topic → final_reel.mp4
python pipeline.py --topic "AI agents explained in 3 steps"

# From a transcript file
python pipeline.py --transcript path/to/transcript.txt

# Skip stage 1 (use existing script)
python pipeline.py --script assets/script_data.json

# From a research JSON (output of the topic-research pipeline)
# Extracts topic + hook_angle + why + outlier_ref and feeds them into Stage 1
python pipeline.py --research-json path/to/research_output.json

# Dry run — generate script only, print JSON, do not call external APIs
python pipeline.py --topic "..." --dry-run

# Skip individual stages (reuse existing assets)
python pipeline.py --topic "..." --skip-broll
python pipeline.py --topic "..." --skip-avatar
python pipeline.py --topic "..." --skip-music
```

## Running Individual Stages

```bash
# Stage 1 only — script generation (reads reference files, calls Claude API, writes assets/script_data.json)
python3 stages/stage1_script.py --topic "..."

# Stage 2 only — B-roll (reads assets/script_data.json, calls Kie.ai Runway, writes assets/broll/)
python3 stages/stage2_broll.py

# Stage 3 only — avatar (reads assets/script_data.json, calls HeyGen, writes assets/avatar/avatar_video.mp4)
python3 stages/stage3_avatar.py

# Stage 4 only — BGM + stings (calls Kie.ai ElevenLabs, writes assets/music/)
# Generates: track1_tension.mp3, track2_warm.mp3, sting1/2/3.mp3, hook_sting.mp3
python3 stages/stage4_music.py

# Stage 5 only — compose (runs Whisper → sync timestamps → Remotion render)
python3 stages/stage5_compose.py

# Stage 6 only — analyse rendered video and score on DSSCL
python3 stages/stage6_analyse.py
python3 stages/stage6_analyse.py assets/final/final_reel.mp4   # custom path

# Remotion preview (hot-reload during component development)
cd remotion && npx remotion studio
```

## Utility Scripts

```bash
# Align broll section timestamps to actual Whisper speech — run after stage5 Whisper step,
# before Remotion render, whenever you have a new avatar video.
# Updates: start_sec/end_sec per section, bgm_dip_timestamps, bgm_transition_sec, total_duration_sec
python3 scripts/sync_broll_to_speech.py
python3 scripts/sync_broll_to_speech.py --dry-run   # preview without writing

# Regenerate specific broll clips (watermark, wrong scene, etc.)
python3 scripts/regenerate_broll.py body_1 emotion_save

# Generate DSSCL analysis doc with per-score commentary
# Writes: scripts/generated/script_analysis.md + script_data_snapshot.json
python3 -c "exec(open('scripts/generate_analysis.py').read())"  # (inline, see section below)

# Pre-evaluate script quality BEFORE spending on HeyGen/Kie.ai (cheap text-only check)
# Returns DSSCL score + issues list + go/no-go — runs automatically in pipeline after Stage 1
python3 scripts/pre_evaluate_script.py
python3 scripts/pre_evaluate_script.py assets/script_data.json   # explicit path

# Check broll clip quality AFTER Stage 2 — screens for watermarks and generic stock footage
# Returns failed section IDs — runs automatically in pipeline before Stage 5 render
python3 scripts/check_broll_quality.py
python3 scripts/check_broll_quality.py hook body_1 trigger_2     # check specific clips
```

## Architecture Overview

**Execution flow:** Stage 1 runs first (serial). Stages 2, 3, 4 run in parallel via `ThreadPoolExecutor`. Stage 5 runs last after all three complete. After stage 5 Whisper step, run `sync_broll_to_speech.py` before the Remotion render to align timestamps.

**Crash recovery:** `pipeline_state.json` tracks which stages have completed. Re-running `pipeline.py` auto-resumes from the last incomplete stage.

**Stale-asset guard:** On resume, pipeline compares `script_data.json` mtime against `avatar_video.mp4` and each broll clip. If the script is newer than an asset (i.e. script was regenerated after that asset was built), the stale file is **deleted** and its stage is reset. This prevents old avatar/broll from being composited against a new script. Stage 5 is also reset if either Stage 2 or Stage 3 was reset.

**Data contract between stages:** All stages communicate through `assets/script_data.json` (written by Stage 1, read by all others). The schema is defined in the Stage 1 section below — do not change field names without updating all consumers.

**Remotion data flow:** Stage 5 reads `assets/script_data.json` AND `assets/captions/avatar_video.json`, inlines both as `--props` to Remotion. `ReelComposition.tsx` receives `scriptData` + `captionsData` as props. `captionsData` is passed directly to `HormoziCaptions` — no async fetch at render time. No stage writes directly into the `remotion/` directory at runtime.

**BGM timing:** `bgm_dip_timestamps` in script JSON are Whisper-aligned by `sync_broll_to_speech.py` (actual trigger speech timestamps, not planned). Converted to frames inside Remotion's `<Audio>` volume callback. BGM files are short (~1.5s) — `loop={true}` on the `<Audio>` elements fills the full duration. Track switch at `bgm_transition_sec` uses `delay={bgm_transition_sec * fps}`.

**Caption sync:** Whisper runs on `assets/avatar/avatar_video.mp4` with `--word_timestamps True`. Output lands in `assets/captions/avatar_video.json`. `HormoziCaptions.tsx` flattens segments into a flat word list, post-processes to merge hyphen-continuation tokens and strip trailing punctuation, then shows a 3-word sliding window with the active word highlighted in `#FFD700`. No `fetch()` or `delayRender` — all data passes via props.

**Broll-speech sync:** HeyGen avatar video runs longer than the planned script (e.g. 76s vs 60s planned). `sync_broll_to_speech.py` matches first 3–4 words of each section's `spoken` text against the Whisper word list, extracts actual start timestamps, and rewrites section `start_sec`/`end_sec` in `script_data.json`. Also updates `bgm_dip_timestamps`, `bgm_transition_sec`, and `total_duration_sec`. The Remotion composition duration is set dynamically via `calculateMetadata` reading `total_duration_sec`.

After syncing, the script prints a match summary: `10/10 sections matched` or lists which sections fell back to interpolated timestamps. Fallback sections may be slightly out of sync. Using `WHISPER_MODEL=large-v3` minimises fallbacks.

**Composition duration:** `Root.tsx` uses `calculateMetadata` to compute `durationInFrames = Math.ceil(total_duration_sec * 30)`. This means the render covers the full avatar video — no abrupt cuts.

---

## What This Project Does

End-to-end automation pipeline that takes a topic or transcript and produces a fully
edited 60-second vertical reel (9:16) ready to post on Instagram / YouTube Shorts.

```
Topic / Transcript
    → Script (Claude API + GOAT Framework, DSSCL loop until ≥ 9.5)
    → B-Roll videos per section (Kie.ai — Kling or Runway)
    → Avatar talking-head video (HeyGen API)
    → Background music tracks x2 (Kie.ai — ElevenLabs sound-effect-v2)
    → Final composite (Remotion): B-roll top 50% | Avatar bottom 50%
    → Hormozi-style captions burned in (Whisper → @remotion/captions)
    → On-screen text overlays per section timestamp
    → BGM mixed with dips at trigger points
    → Output: final_reel.mp4 (9:16, 1080x1920)
```

---

## Skills This Project Uses

Three skills power this project. Bootstrap before building:

```bash
# 1. Video editing / composition layer (Remotion)
npx claude-code-templates@latest --skill video/remotion

# 2. Backend API orchestration layer
npx claude-code-templates@latest --skill development/senior-backend

# 3. Viral Script Generator (GOAT Framework)
#    Fully embedded in this CLAUDE.md — see Stage 1 section below.
#    Reference files live in scripts/reference_scripts/
```

---

## Project Structure

```
/
├── CLAUDE.md                        ← this file
├── .env                             ← API keys (never commit)
├── requirements.txt                 ← Python deps
├── package.json                     ← Node deps (Remotion)
├── pipeline.py                      ← master orchestrator (run this)
│
├── stages/
│   ├── stage1_script.py             ← Claude API + GOAT framework + DSSCL loop
│   ├── stage2_broll.py              ← Kie.ai b-roll generation per section
│   ├── stage3_avatar.py             ← HeyGen avatar video generation
│   ├── stage4_music.py              ← Kie.ai ElevenLabs BGM generation
│   ├── stage5_compose.py            ← Triggers Remotion render
│   └── stage6_analyse.py            ← Claude vision DSSCL video scorer
│
├── remotion/                        ← Remotion project (video/remotion skill)
│   ├── src/
│   │   ├── Root.tsx                 ← calculateMetadata for dynamic duration
│   │   ├── ReelComposition.tsx      ← Main 9:16 composition
│   │   ├── components/
│   │   │   ├── BrollPanel.tsx       ← Top 50% b-roll layer (Ken Burns zoom, crossfade)
│   │   │   ├── AvatarPanel.tsx      ← Bottom 50% avatar layer (cover, beauty filter)
│   │   │   ├── OnScreenText.tsx     ← Per-section timed text overlays
│   │   │   ├── HormoziCaptions.tsx  ← Prop-fed caption component (no fetch)
│   │   │   └── Divider.tsx          ← 4px white line at y=960
│   │   └── types.ts
│   ├── remotion.config.ts
│   └── package.json
│
├── scripts/
│   ├── reference_scripts/           ← GOAT framework reference files
│   │   ├── english-hooks.md         ← 200 hook templates
│   │   └── content-formats.md       ← 47 format structures
│   ├── sync_broll_to_speech.py      ← Align section timestamps to Whisper output
│   ├── regenerate_broll.py          ← Re-submit specific broll clips to Kie.ai
│   └── generated/                   ← Auto-generated DSSCL analysis docs
│       └── script_analysis.md
│
├── assets/
│   ├── broll/                       ← hook.mp4, context.mp4, trigger_1.mp4 ...
│   ├── avatar/                      ← avatar_video.mp4
│   ├── music/                       ← track1_tension.mp3, track2_warm.mp3,
│   │                                   sting1.mp3, sting2.mp3, sting3.mp3,
│   │                                   hook_sting.mp3
│   ├── captions/                    ← avatar_video.json (Whisper word timestamps)
│   ├── analysis/                    ← video_analysis.json (Stage 6 output)
│   └── final/                       ← final_reel.mp4
│
├── logs/
│   └── pipeline.log
└── pipeline_state.json              ← crash recovery state
```

---

## Environment Variables (.env)

```env
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Kie.ai (b-roll via Kling + BGM via ElevenLabs)
KIE_API_KEY=...

# Kling b-roll model. Default: text-to-video.
# Set to kling-2.6/image-to-video to use nano-banana-2 → I2V two-step pipeline.
BROLL_MODEL=kling-2.6/text-to-video

# HeyGen
HEYGEN_API_KEY=...
HEYGEN_VOICE_ID=...

# Avatar pool — set HEYGEN_AVATAR_ID to whichever you want for the run
HEYGEN_AVATAR_ID=98ad52735e614741beab2b011da90f99   # Grey (default/preferred)
HEYGEN_AVATAR_ID_BLACK=3b385e40f2fb46af9ac5c1a836d8dece
HEYGEN_AVATAR_ID_GREY=98ad52735e614741beab2b011da90f99
HEYGEN_AVATAR_ID_BLUE=cb3a77d6beee47cfb85fe381f13b813b
HEYGEN_AVATAR_ID_WHITE=6174316859e34fd4801d13fe64afc177
HEYGEN_AVATAR_ID_BKSHRT=dfffaf1a2186437abca5ca54c57b0c6c

# Whisper model for captions + broll sync. medium is the default (fast, good accuracy).
# large-v3 gives best accuracy but takes 12-15 min; medium takes ~3 min.
# small.en misidentifies proper nouns (Claude → "clot", n8n → "n 8 n").
WHISPER_MODEL=medium

# Optional: webhook for Kie.ai async callbacks (leave blank = polling)
CALLBACK_URL=
```

---

## ═══════════════════════════════════════════
## STAGE 1 — VIRAL SCRIPT GENERATOR (GOAT FRAMEWORK)
## ═══════════════════════════════════════════

**File:** `stages/stage1_script.py`

This is the complete viral script generator embedded directly in this project.
Claude Code must implement Stage 1 using this framework exactly as specified.

---

### Your Role as Script Generator

You are an Instagram scriptwriting expert who creates viral short-form video scripts
(30–90 seconds) that maximize retention, hook people instantly, and deliver the most
value per second. You write for @automatewithanand targeting AI automation content.

**Core audience:** Entrepreneurs, coaches, creators, and business owners who want
to grow faster, earn more, and break free from limitations.

---

### Non-Negotiable Writing Rules

- **Hook in the first 3 seconds** — bold statement, open loop, surprising fact,
  emotional trigger. Stop the scroll immediately.
- **No filler** — no welcome intros, no wasted sentences. Every word earns its place.
- **Conversational language** — spoken on camera, 8th-grade readability.
- **Active voice only** — never passive.
- **Single core idea** — one script, one message, maximum clarity.
- **Deep research** — real examples, real numbers. No generic claims.
- **Originality** — fresh angle every time. Never reuse prior examples.
- **Emotional drivers** — desire, fear, urgency, identity, transformation.
- **Shareability test** — "Will viewer send this to 3 friends right now?" If not → rewrite.
- **Build to a climax** — end with a "I need to act NOW" moment.

---

### STEP 0 — Load Reference Files First (MANDATORY)

Before generating any script content, read both files:

```
scripts/reference_scripts/english-hooks.md    ← 200 hook templates with blanks
scripts/reference_scripts/content-formats.md  ← 47 content format structures
```

**Hook selection:**
1. Scan all 200 hooks in `english-hooks.md`
2. Pick 2–3 best-fit hooks for the topic
3. Fill blanks with AI/automation-specific language
4. Pick the strongest → use as HOOK (0–5 sec)
5. Store chosen hook number in `hook_used` field of JSON output

**Format selection:**
1. Use the goal→format lookup table at the bottom of `content-formats.md`
2. Pick format that best matches content goal
3. Use that format's structure as backbone for CONTEXT → TRIGGER → TAKEAWAY
4. Store chosen format number in `format_used` field of JSON output

---

### STEP 1 — Audience Persona (Default for this channel)

```
WHO:      Age 22–45, working professionals in India
PAIN:     Job insecurity, wasting time, missing out, wanting more income
LANGUAGE: Conversational English
FEARS:    Being replaced by AI, being left behind
WANTS:    Income freedom, leverage, time back, status as an expert
```

The hook must speak to the LARGEST possible slice of this audience (big TAM).
Broader hook = more people stop scrolling.

---

### STEP 2 — DSSCL Virality Filter

Score the script on 5 signals before saving. D + S + S are non-negotiable.

| Signal | Priority | What drives it |
|--------|----------|----------------|
| **D — Double Watch** | 🔴 Highest | Info density, curiosity loops, emotional trigger, rewatch value |
| **S — Share** | 🔴 High | Quotable lines, identity signal, "be first to share this" |
| **S — Save** | 🔴 High | Concrete takeaway, tool name, FOMO, bookmark-worthy |
| **C — Comment** | 🟡 Medium | Debate trigger, relatable frustration, opinion bait |
| **L — Like** | 🟢 Low | General quality — follows naturally if above are strong |

**Scoring formula:**
```
Final = (D × 0.30) + (Share × 0.25) + (Save × 0.25) + (C × 0.10) + (L × 0.10)
```

**Pass thresholds:**
- D ≥ 9.0, Share ≥ 9.0, Save ≥ 9.0, C ≥ 7.0
- **Final ≥ 9.5** ← pipeline will not proceed until this is met

**If score < 9.5**, send this feedback prompt to Claude and regenerate:
```
Script scored {score}/10. Pipeline requires ≥ 9.5. Iteration {n}/5.
Weakest signals: {lowest_two_dimensions}

Required fixes:
- Hook: needs stronger pattern interrupt + broader TAM
- Grand Takeaway: must be more quotable (people screenshot this line)
- Save trigger: must name a specific tool OR give a time estimate

Rewrite keeping same 10-section structure. Return only the JSON object.
```

**Max 5 iterations.** If still < 9.5 after 5 tries → log warning, use best score achieved, continue pipeline.

---

### STEP 3 — The 60-Second Reel Structure

All 10 sections are MANDATORY. Do not skip or merge any.

```
┌─────────────────────────────────────────────────────────┐
│  0  – 5 sec   │  HOOK           pattern interrupt       │
│  5  – 10 sec  │  CONTEXT        bridge hook to content  │
│  10 – 12 sec  │  TRIGGER 1      spike — BGM dip         │
│  12 – 20 sec  │  BODY 1         develop the loop        │
│  20 – 25 sec  │  TRIGGER 2      spike — stat/contrast   │
│  25 – 30 sec  │  BODY 2         make it personal        │
│  30 – 32 sec  │  TRIGGER 3      spike — real story/nums │
│  32 – 35 sec  │  BRIDGE         emotional pivot         │
│  35 – 40 sec  │  GRAND TAKEAWAY quotable line           │
│  40 – 60 sec  │  EMOTION + SAVE CTA + specific tool     │
└─────────────────────────────────────────────────────────┘
```

**HOOK (0–5 sec):**
- From `english-hooks.md` — blanks filled with AI/automation language
- Pattern interrupt — say something the viewer did NOT expect
- Open a loop, NEVER close it in the hook (Zeigarnik effect)
- Big TAM — broad enough to stop anyone in the target audience
- ❌ Weak: "AI is changing everything."
- ✅ Strong: "Your competitor just replaced you with a ₹2,000/month tool. And you don't even know it yet."

**TRIGGERS (all 3):**
- Tease ONLY — never explain at the trigger point
- Each trigger = BGM dip (micro-silence, marks `bgm_dip: true` in JSON)
- Trigger 3 must include a real-world example with specific numbers
  (city, tool name, rupee/dollar amount, time saved)

**GRAND TAKEAWAY (35–40 sec):**
- 1–2 sentences, spoken slowly and clearly
- Must be QUOTABLE — this is the screenshot line people share
- BGM hard-transitions here: tension track → warm piano track
- Mark `bgm_transition_here: true` in JSON

**EMOTION + SAVE (40–60 sec):**
- Warm friend-to-friend energy, not corporate
- MUST name ONE specific tool (n8n / ChatGPT / Zapier / etc.)
  OR give ONE specific time estimate ("takes 20 minutes to set up")
- CTA last — only after delivering value

---

### STEP 4 — Production Specs Per Section

Each section in the JSON must include:

**`broll_prompt`** — cinematic scene for Kie.ai to generate:
```
Pattern: {subject}, {motion}, {color_palette}, cinematic, no text, no faces, 9:16 vertical, {mood}

Mood by section type:
- hook / triggers:      dark, tension, red accent, dramatic
- body sections:        neutral cinematic, blue accent, informational  
- bridge:               transitional, shifting from dark to warm
- grand_takeaway:       clean, minimal, warm
- emotion_save:         warm, hopeful, golden light
```

**`on_screen_text`** — array of strings, each max 3–5 words:
```json
["CALCULATOR.", "TOOL.", "EMPLOYEE."]
```

**`expression_cue`** — how the avatar should look:
- "dead serious, eyes locked into camera"
- "raised eyebrow, slight smirk"
- "leans in hard, drops voice"
- "warm smile, friend-to-friend energy"

**`vocal_direction`** — how the avatar should sound:
- "slow and deliberate, one word at a time"
- "drops voice at end of sentence"
- "building energy, faster pace"

---

### STEP 5 — Script JSON Output Schema

Stage 1 outputs `assets/script_data.json`. Exact schema:

```json
{
  "title": "Your AI Is An Employee. You Just Don't Know It Yet.",
  "hook_used": "#21",
  "format_used": "Format 4 — Common vs Elite",
  "total_duration_sec": 60,
  "dsscl_scores": {
    "D": 9.5,
    "Share": 9.5,
    "Save": 9.5,
    "C": 8.0,
    "L": 8.5,
    "final": 9.43
  },
  "dsscl_iteration": 2,
  "bgm_transition_sec": 35,
  "bgm_dip_timestamps": [10, 20, 30],
  "full_spoken_script": "Your ChatGPT is a calculator. Your AI workflow is a tool...",
  "grand_takeaway_line": "Most people will spend their career asking AI for help. The ones who win build AI that works while they sleep.",
  "tool_mentioned": "n8n",
  "sections": [
    {
      "id": "hook",
      "label": "HOOK",
      "start_sec": 0,
      "end_sec": 5,
      "spoken": "Your ChatGPT is a calculator. Your AI workflow is a tool. Your AI agent is an employee. I'll explain.",
      "on_screen_text": ["CALCULATOR.", "TOOL.", "EMPLOYEE."],
      "broll_prompt": "dark digital calculator morphing into a humanoid robot, slow dramatic zoom, black and red, cinematic, no text, no faces, 9:16 vertical, tension",
      "expression_cue": "dead serious, eyes locked into camera, slight lean forward",
      "vocal_direction": "slow and deliberate, pause between each word",
      "bgm_dip": false,
      "bgm_track": 1,
      "bgm_transition_here": false,
      "broll_type": "clip"
    },
    {
      "id": "context",
      "label": "CONTEXT",
      "start_sec": 5,
      "end_sec": 10,
      "spoken": "...",
      "on_screen_text": ["..."],
      "broll_prompt": "...",
      "expression_cue": "...",
      "vocal_direction": "...",
      "bgm_dip": false,
      "bgm_track": 1,
      "bgm_transition_here": false,
      "broll_type": "clip"
    },
    {
      "id": "trigger_1",
      "label": "TRIGGER 1",
      "start_sec": 10,
      "end_sec": 12,
      "spoken": "...",
      "on_screen_text": ["..."],
      "broll_prompt": "...",
      "expression_cue": "leans in hard, drops voice",
      "vocal_direction": "near whisper, maximum intensity",
      "bgm_dip": true,
      "bgm_track": 1,
      "bgm_transition_here": false,
      "broll_type": "clip",
      "flash_before": true
    },
    { "id": "body_1",    "label": "BODY 1",    "start_sec": 12, "end_sec": 20, "bgm_dip": false, "bgm_track": 1, "bgm_transition_here": false, "broll_type": "clip", "...": "..." },
    { "id": "trigger_2", "label": "TRIGGER 2", "start_sec": 20, "end_sec": 25, "bgm_dip": true,  "bgm_track": 1, "bgm_transition_here": false, "broll_type": "clip", "flash_before": true, "...": "..." },
    { "id": "body_2",    "label": "BODY 2",    "start_sec": 25, "end_sec": 30, "bgm_dip": false, "bgm_track": 1, "bgm_transition_here": false, "broll_type": "clip", "...": "..." },
    { "id": "trigger_3", "label": "TRIGGER 3", "start_sec": 30, "end_sec": 32, "bgm_dip": true,  "bgm_track": 1, "bgm_transition_here": false, "broll_type": "clip", "flash_before": true, "...": "..." },
    { "id": "bridge",    "label": "BRIDGE",    "start_sec": 32, "end_sec": 35, "bgm_dip": false, "bgm_track": 1, "bgm_transition_here": false, "broll_type": "clip", "...": "..." },
    {
      "id": "grand_takeaway",
      "label": "GRAND TAKEAWAY",
      "start_sec": 35,
      "end_sec": 40,
      "spoken": "Most people will spend their career asking AI for help. The ones who win build AI that works while they sleep.",
      "on_screen_text": ["ASKING FOR HELP", "vs", "BUILDING WHAT WORKS"],
      "broll_prompt": "clean minimal warm desk setup, soft golden light, person relaxed not working, hopeful, 9:16 vertical",
      "expression_cue": "calm, deliberate, full frame, direct eye contact",
      "vocal_direction": "slow, clear, each word landing with weight",
      "bgm_dip": false,
      "bgm_track": 2,
      "bgm_transition_here": true,
      "broll_type": "clip"
    },
    {
      "id": "emotion_save",
      "label": "EMOTION + SAVE",
      "start_sec": 40,
      "end_sec": 60,
      "spoken": "If you want to build your first AI agent — start with n8n. Free to self-host. Pick one repetitive task. Give it a goal, not a prompt. Save this — you'll want it. Follow for more builds every week.",
      "on_screen_text": ["START WITH: n8n", "GOAL, NOT A PROMPT", "SAVE THIS 🔖"],
      "broll_prompt": "n8n workflow interface on screen, automation nodes connecting, warm blue glow, person looking satisfied, 9:16 vertical",
      "expression_cue": "warm smile, leaning toward camera, friend-to-friend energy",
      "vocal_direction": "conversational, warm, relaxed pace",
      "bgm_dip": false,
      "bgm_track": 2,
      "bgm_transition_here": false,
      "broll_type": "clip",
      "tool_mentioned": "n8n"
    }
  ]
}
```

---

### STEP 6 — Virality Self-Check (run before saving JSON)

```
[ ] Hook is from english-hooks.md — blanks filled, not generic
[ ] Format from content-formats.md is clearly reflected in structure
[ ] Hook is a pattern interrupt — viewer did NOT expect this
[ ] Hook targets big TAM — broad enough to stop anyone in audience
[ ] Exactly 3 triggers at correct timestamps with bgm_dip: true
[ ] Grand Takeaway is 1–2 quotable, screenshot-worthy sentences
[ ] emotion_save section names ONE specific tool OR time estimate
[ ] bgm_transition_here: true on grand_takeaway section only
[ ] All on_screen_text entries: max 3–5 words each
[ ] broll_prompt present in every section (cinematic, no text, no faces, 9:16)
[ ] expression_cue and vocal_direction present in every section
[ ] DSSCL final score ≥ 9.5
```

---

### GOAT Virality Formula

```
character + delivery + content = virality

TAM × Curiosity × Relevance = Attention + Dopamine

good TAM + unique content     = viral + credibility      ✅
good TAM + average content    = no reach, no credibility  ❌
small TAM + unique + trigger  = good reach + credibility  ✅
small TAM + average + trigger = no reach, no credibility  ❌
```

Growth milestones:
- 0–10k:    Virality alone
- 10k–30k:  Virality + strong on-screen person
- 30k–70k:  Virality + person + positioning
- 70k–100k: Virality + person + positioning + credibility

You only need 6–10 viral videos to reach 100K.
Build every script like it's one of those 10.

---

## ═══════════════════════════════════════════
## API REFERENCE — ALL SERVICES
## ═══════════════════════════════════════════

### Claude API (Stage 1)
```
POST https://api.anthropic.com/v1/messages
Headers:
  x-api-key: $ANTHROPIC_API_KEY
  anthropic-version: 2023-06-01
  Content-Type: application/json
Body:
  model: claude-sonnet-4-20250514
  max_tokens: 8000
  messages: [{role: "user", content: "<goat framework prompt>"}]
```

### Kie.ai — Kling Text-to-Video (Stage 2 — B-Roll, T2V mode)
```
POST https://api.kie.ai/api/v1/jobs/createTask
Headers:
  Authorization: Bearer $KIE_API_KEY
  Content-Type: application/json
Body:
  {
    "model": "kling-2.6/text-to-video",
    "callBackUrl": "",
    "input": {
      "prompt": "<section.broll_prompt>",
      "duration": 5,
      "aspect_ratio": "9:16"
    }
  }

Poll: GET https://api.kie.ai/api/v1/jobs/task/{taskId}
Response: task.output.works[0].resource.resource   ← video URL
Poll interval: 15s | Timeout: 10 min per clip
IMPORTANT: 200 OK = task CREATED, not completed. Always poll.
```

### Kie.ai — nano-banana-2 Image Generation (Stage 2 — I2V step 1)
```
POST https://api.kie.ai/api/v1/jobs/createTask
Body:
  {
    "model": "nano-banana-2",
    "callBackUrl": "",
    "input": {
      "prompt": "<visual scene description>",
      "image_input": [],
      "aspect_ratio": "9:16",
      "resolution": "1K",
      "output_format": "png"
    }
  }

Response: resultJson.resultUrls[0]   ← PNG URL
```

### Kie.ai — Kling Image-to-Video (Stage 2 — I2V step 2)
```
POST https://api.kie.ai/api/v1/jobs/createTask
Body:
  {
    "model": "kling-2.6/image-to-video",
    "callBackUrl": "",
    "input": {
      "image_url": "<PNG URL from nano-banana-2>",
      "prompt": "<camera motion description only>",
      "duration": 5,
      "aspect_ratio": "9:16"
    }
  }
```

### Kie.ai — ElevenLabs BGM (Stage 4)
```
POST https://api.kie.ai/api/v1/jobs/createTask
Headers:
  Authorization: Bearer $KIE_API_KEY
  Content-Type: application/json
Body:
  {
    "model": "elevenlabs/sound-effect-v2",
    "callBackUrl": "",
    "input": {
      "text": "<bgm_prompt>",
      "loop": true,
      "prompt_influence": 0.7,
      "output_format": "mp3_44100_128"
    }
  }

Poll: GET https://api.kie.ai/api/v1/jobs/task/{taskId}

Track 1 prompt: "cinematic dark orchestral impact, deep sub bass, tense thriller underscore, heart-pounding dramatic atmosphere, builds suspense, no melody, 35 seconds"
Track 2 prompt: "warm hopeful soft piano melody, uplifting gentle beat, positive transformation, 25 seconds"
Sting prompt: "dramatic cinematic impact sting, single deep sub bass hit, tension spike moment, heart-pounding, no melody, 2 seconds"
Hook sting prompt: "dramatic cinematic orchestral boom, powerful low frequency hit, epic movie trailer opening, thunder crack, reverberant impact, no melody, 3 seconds"
```

### HeyGen API (Stage 3 — Avatar)
```
POST https://api.heygen.com/v2/video/generate
Headers:
  X-Api-Key: $HEYGEN_API_KEY
  Content-Type: application/json
Body:
  {
    "video_inputs": [{
      "character": {
        "type": "avatar",
        "avatar_id": "<HEYGEN_AVATAR_ID>",
        "avatar_style": "normal"
      },
      "voice": {
        "type": "text",
        "input_text": "<script_data.full_spoken_script>",
        "voice_id": "<HEYGEN_VOICE_ID>"
      },
      "background": { "type": "color", "value": "#000000" }
    }],
    "dimension": { "width": 540, "height": 960 }
  }

Poll: GET https://api.heygen.com/v1/video_status.get?video_id={id}
Status flow: pending → processing → completed | failed
Download from: response.data.video_url
Poll interval: 20s | Timeout: 15 min
Input text max: 5000 characters
```

---

## ═══════════════════════════════════════════
## STAGE 2 — B-ROLL GENERATION (Kie.ai)
## ═══════════════════════════════════════════

**File:** `stages/stage2_broll.py`

Two-step pipeline: nano-banana-2 (Imagen) → Kling I2V. Falls back to T2V if either step fails.

1. Read `assets/script_data.json`
2. For each section:
   - Submit `broll_prompt` to nano-banana-2 (Imagen) via Kie.ai jobs API → get reference PNG
   - Submit PNG + motion prompt to Kling I2V → get cinematic video
   - If either step fails → fall back to Kling T2V directly
3. Poll every 15 seconds until `completed`
4. Download MP4 to `assets/broll/{section.id}.mp4`
5. **Re-encode to H264 Baseline** immediately after download (Chromium/Remotion rejects High/Main profile):
   `ffmpeg -i input.mp4 -c:v libx264 -profile:v baseline -level 3.1 -pix_fmt yuv420p -movflags +faststart -y output.mp4`
6. Verify non-zero filesize before marking complete
7. Force T2V for all sections: set `BROLL_MODEL=kling-2.6/text-to-video` in `.env`

---

## ═══════════════════════════════════════════
## STAGE 3 — AVATAR GENERATION (HeyGen)
## ═══════════════════════════════════════════

**File:** `stages/stage3_avatar.py`

1. Read `full_spoken_script` from `assets/script_data.json`
2. Submit to HeyGen v2/video/generate
3. Poll every 20 seconds
4. Download to `assets/avatar/avatar_video.mp4`
5. Black background (#000000) enables clean compositing

---

## ═══════════════════════════════════════════
## STAGE 4 — BACKGROUND MUSIC (Kie.ai)
## ═══════════════════════════════════════════

**File:** `stages/stage4_music.py`

Generates **6 audio files** in parallel (ThreadPoolExecutor max_workers=5):

1. Submit all 6 tasks simultaneously to Kie.ai ElevenLabs
2. Poll all in parallel
3. Download to `assets/music/`:
   - `track1_tension.mp3` — dark orchestral underscore, fills 0→bgm_transition_sec
   - `track2_warm.mp3` — warm piano, fills bgm_transition_sec→end
   - `sting1.mp3` — impact hit at trigger 1 timestamp
   - `sting2.mp3` — impact hit at trigger 2 timestamp
   - `sting3.mp3` — impact hit at trigger 3 timestamp
   - `hook_sting.mp3` — dramatic orchestral boom at video start (first 3s)

Prompts:
- Track 1: "cinematic dark orchestral impact, deep sub bass, tense thriller underscore, heart-pounding dramatic atmosphere, builds suspense, no melody, 35 seconds"
- Track 2: "warm hopeful soft piano melody, uplifting gentle beat, positive transformation, 25 seconds"
- Stings: "dramatic cinematic impact sting, single deep sub bass hit, tension spike moment, heart-pounding, no melody, 2 seconds"
- Hook sting: "dramatic cinematic orchestral boom, powerful low frequency hit, epic movie trailer opening, thunder crack, reverberant impact, no melody, 3 seconds"

BGM dip behavior (from Whisper-aligned `bgm_dip_timestamps`):
- At each trigger timestamp: BGM volume drops to 0.03 for ~25 frames, sting plays at 0.70
- At `bgm_transition_sec`: Track 1 ends, Track 2 begins (hard cut)
- ElevenLabs files are ~1.5s — Remotion `loop={true}` fills full duration
- Implemented in Remotion `<Audio>` volume callback (Stage 5)

---

## ═══════════════════════════════════════════
## STAGE 5 — REMOTION COMPOSITION
## ═══════════════════════════════════════════

**File:** `stages/stage5_compose.py`
**Remotion project:** `remotion/`
**Skill:** `npx claude-code-templates@latest --skill video/remotion`

Stage 5 runs Whisper, then syncs timestamps, then triggers Remotion render:

```bash
# Step 1: Generate word-level captions from avatar audio
# large-v3 model gives best accuracy on proper nouns (Claude, n8n, HeyGen, etc.)
# First run downloads ~1.5GB model — subsequent runs use cache
whisper assets/avatar/avatar_video.mp4 \
  --model large-v3 \
  --output_format json \
  --output_dir assets/captions/ \
  --word_timestamps True

# Step 2: Align broll section timestamps to actual speech
python3 scripts/sync_broll_to_speech.py

# Step 3: Remotion render (scriptData + captionsData both inlined into props)
npx remotion render remotion/src/index.ts ReelComposition \
  --props='{"scriptData":{...},"assetsDir":"assets","captionsData":{...}}' \
  --output assets/final/final_reel.mp4 \
  --width 1080 --height 1920 --fps 30
```

Stage 5 Python loads `assets/script_data.json` and `assets/captions/avatar_video.json` and merges both into the `--props` JSON at render time. No fetching inside Remotion at render time.

### Final Video Spec
- Resolution: 1080 × 1920 (9:16 vertical)
- FPS: 30
- Duration: dynamic — `Math.ceil(total_duration_sec * 30)` frames (set by sync script from Whisper; typically ~76–80s)

### Layout

```
┌──────────────────────────┐  ← y: 0px
│   TITLE HEADER           │  1080 × 160px  white bg, 2-line title (red + black)
├──────────────────────────┤  ← y: 160px
│                          │
│   AVATAR (full frame)    │  1080 × 1400px  gradient bg, beauty filter
│                          │
│   ┌────────────────────┐ │  B-ROLL BOX (during b-roll window):
│   │  B-ROLL CLIP       │ │  880×1100px, centered, BOX_TOP=310, BOX_LEFT=100
│   │  Ken Burns zoom    │ │  portrait orientation (minimises 9:16 crop)
│   └────────────────────┘ │
│                          │
│   [falling leaf particles during A-roll window]
│                          │
├──────────────────────────┤  ← y: 1560px
│   SAFE ZONE (white)      │  1080 × 360px  captions + Instagram UI padding
└──────────────────────────┘  ← y: 1920px
```

**A/B rhythm:** 8s avatar (A-roll) → 4s b-roll box (B-roll) = 12s cycle. Flash + click at each cut.
During b-roll window: gradient overlay covers avatar, b-roll box sits on top. No avatar visible.

### Remotion Components

**`Root.tsx`**
- `calculateMetadata` reads `total_duration_sec` from props: `durationInFrames = Math.ceil(total_duration_sec * 30)`
- Default ceiling: `durationInFrames={2700}` (90s) as fallback
- `defaultProps` includes `captionsData: { segments: [], text: "" }` for Studio preview

**`ReelComposition.tsx`**
- Receives `scriptData`, `assetsDir`, `captionsData` as props
- Owns all `<Audio>` elements — avatar voice + trigger stings (BGM tracks removed)
- StatCard is NOT present — text stat overlays were removed. All sections use b-roll clips.

**`TitleHeader.tsx`**
- Static white bar at y=0→160, zIndex=40
- `splitTitle()` splits on ` — ` or `:` — max 4 words per line to prevent overflow
- line1: red `#E31A1A`, fontSize=44, weight=900; line2: black `#111`, fontSize=40, weight=800

**`AvatarPanel.tsx`**
- Full avatar zone (1080×1400, `top: 160`)
- `objectFit: "cover"`, `objectPosition: "50% 65%"`, `transformOrigin: "50% 35%"`, `BASE_ZOOM: 1.4`
- Gradient background: `linear-gradient(180deg, #0a0a12, #111827, #080810)`
- CSS beauty filter: `brightness(1.15) contrast(1.10) saturate(1.20)`

**`BrollClipCard.tsx`**
- B-roll box overlay during b-roll window only (4s of every 12s cycle)
- `BOX_WIDTH=880, BOX_HEIGHT=1100, BOX_LEFT=100, BOX_TOP=310, BOX_RADIUS=28`
- During b-roll window: full gradient overlay (zIndex=19) covers avatar, box (zIndex=20) on top
- Ken Burns zoom: 1.0 → 1.08 (regular sections), 1.0 → 1.14 (trigger sections)
- `loop` on `<Video>` fills 4s window from a 5s clip

**`ArollParticles.tsx`**
- 8 falling white oval leaf shapes during A-roll window, hidden during b-roll window
- Opacity 14–25%, independent loop timing per particle, zIndex=18

**`RhythmCuts.tsx`**
- White flash (6 frames) + sting click at every A→B cut
- `AROLL_SECS=8, CYCLE_SECS=12, CYCLE_FRAMES=288, AROLL_FRAMES=192`
- Sting volume: 0.20

**`SectionFlash.tsx`**
- 2-frame black flash before any section with `flash_before: true` (trigger sections)
- zIndex=100

**`HormoziCaptions.tsx`**
- Data via `captionsData` prop (no fetch at render time)
- `extractWords()`: merges hyphen tokens, strips trailing punctuation, corrects Whisper mishears (clot/clode/claud → "Claude")
- 3-word sliding window, active word in `#FF3D00`
- `CAPTION_BOTTOM_PX=440`, gap=20px between words, fontSize=72, weight=900
- `WebkitTextStroke: "4px black"`

**`LowerThird.tsx`** — `@automatewithanand` handle slides in for first 8s, `AVATAR_PANEL_TOP=160`

**`EndCard.tsx`** — FOLLOW overlay for last 2s of video

### Audio in Remotion

BGM bed tracks (track1_tension, track2_warm, hook_sting) have been **removed** — user found them annoying. Do not add them back.

Active audio mix:
| Track | Volume | Notes |
|-------|--------|-------|
| Avatar voice | 4.0 | `playbackRate=1.25` to match sped-up video |
| Trigger stings (sting1/2/3) | 0.20 | At each bgm_dip_timestamp via RhythmCuts |

```typescript
// Avatar voice at 1.25x playback
<Audio src={avatarPath} volume={4.0} playbackRate={PLAYBACK_RATE} />

// Trigger stings at Whisper-aligned timestamps (via Sequence)
<Sequence from={bgmDipFrames[0]} durationInFrames={Math.round(2 * fps)}>
  <Audio src={sting1Path} volume={0.20} />
</Sequence>
// ... sting2, sting3 same pattern
```

---

## ═══════════════════════════════════════════
## STAGE 6 — VIDEO DSSCL ANALYSER
## ═══════════════════════════════════════════

**File:** `stages/stage6_analyse.py`

Analyses the rendered `assets/final/final_reel.mp4` using Claude vision (Opus model).
Returns DSSCL scores and feedback. If score < 9.0, `pipeline.py` loops back to Stage 1.

**What it does:**
1. Extracts 12 frames evenly spaced across the video using `ffprobe` + `ffmpeg` (scaled to 540px wide, JPEG)
2. Sends all frames as a multi-image message to Claude Opus vision API
3. Scores on DSSCL formula: `Final = D×0.30 + Share×0.25 + Save×0.25 + C×0.10 + L×0.10`
4. Recalculates `final` score from raw components (doesn't trust Claude's arithmetic)
5. Writes analysis to `assets/analysis/video_analysis.json`
6. Returns `passed: true` if `final ≥ 9.0`

**Frame evaluation covers:**
- Hook (first 2 frames): scroll-stop, pattern interrupt, open loop
- B-roll (top 50%): quality, relevance, no text/watermarks
- On-screen text: legibility, punch, max 3–5 words
- Avatar (bottom 50%): energy, lighting, eye contact
- Captions: Hormozi style, sync, visibility
- Grand Takeaway frame: quotable line clearly visible
- CTA / emotion_save: warm close, specific tool named

**Output:** `assets/analysis/video_analysis.json`
```json
{
  "dsscl_scores": { "D": 8.5, "Share": 9.0, "Save": 9.0, "C": 7.5, "L": 8.0, "final": 8.63 },
  "passed": false,
  "strengths": ["strong hook", "clear CTA"],
  "weaknesses": ["B-roll not matching speech", "grand takeaway not quotable enough"],
  "script_feedback": "Specific script improvements for next iteration...",
  "visual_feedback": "B-roll, caption, avatar quality notes..."
}
```

**Pipeline loop behavior (in `pipeline.py`):**
- Max 3 outer pipeline iterations
- If `passed: false` → resets stages 1, 2, 3, 5 (keeps stage 4 music) → re-runs with video feedback
- Stage 1 receives `video_feedback` dict → prepends `build_video_feedback_prompt()` to script prompt
- If still < 9.0 after 3 iterations → accepts best result, logs warning

---

## ═══════════════════════════════════════════
## PIPELINE ORCHESTRATOR
## ═══════════════════════════════════════════

**File:** `pipeline.py`
**Skill:** `npx claude-code-templates@latest --skill development/senior-backend`

### Usage

```bash
python pipeline.py --topic "AI agents explained in 3 steps"
python pipeline.py --transcript path/to/transcript.txt
python pipeline.py --script assets/script_data.json          # skip stage 1
python pipeline.py --research-json path/to/research.json     # topic + hook_angle + why + outlier_ref fed to Stage 1
python pipeline.py --topic "..." --dry-run                   # stage 1 only, print script
python pipeline.py --topic "..." --skip-broll                # reuse existing broll
python pipeline.py --topic "..." --skip-avatar               # reuse existing avatar
python pipeline.py --topic "..." --skip-music                # reuse existing music
```

**Research JSON schema** (output of topic-research pipeline, schema_version 1.0):
```json
{
  "topic": "AI Automation Will Replace Your Job in 2026 — Unless You Do This",
  "hook_angle": "fear",
  "signal_strength": 9,
  "why": "Dan Martell crossed 106K views in 24 hours on this topic...",
  "outlier_ref": {
    "title": "...", "views": 238784,
    "thumbnail_formula": "...",
    "adaptation_for_anand": "..."
  },
  "backup_topics": [{"topic": "...", "hook_angle": "fomo", "signal_strength": 8}]
}
```

### Execution Model

```
Stage 1 (script) ←──────────────────────────────────────────┐
    ↓                                                        │ video_feedback
    ├── Stage 2 (broll)  ─┐                                  │ (script regenerated)
    ├── Stage 3 (avatar) ─┼── PARALLEL (ThreadPoolExecutor)  │
    └── Stage 4 (music)  ─┘                                  │
                          ↓ (wait for all 3)                 │
                     Stage 5 (compose)                       │
                          ↓                                  │
                     Stage 6 (analyse) ── score < 9.0 ───────┘
                          │
                     score ≥ 9.0 (or max 3 iterations)
                          ↓
                  assets/final/final_reel.mp4
```

**Note:** Stage 4 (music) is generated only once — it does not depend on script content so it is not re-run in the video analysis loop. Only stages 1, 2, 3, 5 reset per iteration.

### Crash Recovery State

Writes `pipeline_state.json` after each stage. Re-running auto-resumes:

```json
{
  "run_id": "20250321_143022",
  "topic": "AI agents explained in 3 steps",
  "stage1_complete": true,
  "stage2_complete": true,
  "stage3_complete": false,
  "stage4_complete": true,
  "script_path": "assets/script_data.json",
  "broll_paths": {
    "hook": "assets/broll/hook.mp4",
    "context": "assets/broll/context.mp4",
    "trigger_1": "assets/broll/trigger_1.mp4"
  },
  "avatar_path": null,
  "music_paths": {
    "track1": "assets/music/track1_tension.mp3",
    "track2": "assets/music/track2_warm.mp3"
  }
}
```

### Backend Standards (from senior-backend skill)

- All API calls: 3 retries, exponential backoff (1s → 2s → 4s)
- All downloads: verify non-zero filesize, retry on failure
- All stages: structured logging to `logs/pipeline.log` with timestamps + stage name
- Stage return type: `{"success": bool, "output_path": str, "duration_sec": float, "error": str|None}`
- All secrets via `.env` + `python-dotenv` — never hardcoded
- Parallel stages via `concurrent.futures.ThreadPoolExecutor`
- Graceful SIGINT handling: save state before exit

---

## ═══════════════════════════════════════════
## DEPENDENCIES
## ═══════════════════════════════════════════

### requirements.txt

```
anthropic>=0.25.0
requests>=2.31.0
python-dotenv>=1.0.0
openai-whisper>=20231117
torch>=2.0.0
tqdm>=4.65.0
```

### package.json (Remotion)

```json
{
  "dependencies": {
    "remotion": "4.0.438",
    "@remotion/cli": "4.0.438",
    "@remotion/captions": "4.0.438",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  }
}
```

### System dependencies

```bash
brew install ffmpeg        # macOS
sudo apt install ffmpeg    # Ubuntu/Debian
ffmpeg -version            # verify
```

---

## ═══════════════════════════════════════════
## COMMON ERRORS & FIXES
## ═══════════════════════════════════════════

| Error | Cause | Fix |
|-------|-------|-----|
| Kie.ai 422 | Missing `aspect_ratio` for text-to-video | Add `"aspect_ratio": "9:16"` to request body |
| Kie.ai 451 | `imageUrl` not publicly accessible | Omit `imageUrl` for pure text-to-video |
| Kie.ai 401 | Wrong auth header format | Use `Authorization: Bearer $KIE_API_KEY` |
| Kie.ai 402 | Insufficient credits | Top up at kie.ai dashboard before running |
| HeyGen `failed` status | Script too long or wrong avatar_id | Trim to <5000 chars, verify `HEYGEN_AVATAR_ID` in .env |
| HeyGen 401 | Wrong header name | Use `X-Api-Key` not `Authorization` |
| Remotion `MEDIA_ELEMENT_ERROR Code 4` on broll | Kling generates H264 High/Main profile — Chromium rejects it | Re-encode every clip after download: `ffmpeg -i in.mp4 -c:v libx264 -profile:v baseline -level 3.1 -pix_fmt yuv420p -movflags +faststart -y out.mp4` |
| Remotion OOM on render | Too many concurrent video inputs | Remotion handles sequentially — don't load all clips at once |
| Remotion render 404 on avatar | Run from wrong directory | Always `cd remotion && npx remotion render ...` — never from project root with `--prefix` |
| Video abruptly cuts at 60s | `durationInFrames={1800}` hardcoded OR `sync_broll_to_speech.py` not run | Use `calculateMetadata` in Root.tsx; always run sync before Remotion render |
| Old avatar used in new video | Pipeline resumed from state; Stage 3 skip guard short-circuits on existing file | Stale-asset guard now deletes the file automatically on mtime mismatch. Manual fix: `rm assets/avatar/avatar_video.mp4` |
| Old broll used in new video | Same stale-asset issue | Stale-asset guard deletes stale clips automatically. Manual fix: `rm assets/broll/*.mp4` |
| Captions misidentify words ("clot" instead of "Claude") | Whisper `small.en` inaccurate on proper nouns | Set `WHISPER_MODEL=large-v3` in `.env` |
| Caption shows "FOLLOW -UPS" split | Whisper splits hyphenated words | `extractWords()` merges tokens starting with "-" into previous word |
| sync_broll_to_speech shows FALLBACK sections | Whisper couldn't match section's first words | Upgrade to `large-v3`; fallback sections use interpolated timestamps |
| Broll clips show text/watermarks | Prompt doesn't explicitly forbid them | Add "absolutely no text overlays, no watermarks, no subtitles, no captions, pure cinematic footage only" to every broll_prompt |
| Broll/speech not in sync | HeyGen speaks at natural pace (differs from planned timing) | Run `sync_broll_to_speech.py` after Whisper — pipeline does this automatically in Stage 5 |
| Title header too long | Full title exceeds 4 words per line | `splitTitle()` in TitleHeader.tsx truncates to max 4 words per line |
| stage1_script.py NameError: name 'text' | `{text, size}` unescaped in f-string | Escape as `{{text, size}}` in any f-string containing literal braces |
| DSSCL loop > 5 | Claude can't hit 9.5 | Log warning, use best score, continue pipeline |

---

## ═══════════════════════════════════════════
## TARGET CONTENT PROFILE
## ═══════════════════════════════════════════

| Property | Value |
|----------|-------|
| Channel | @automatewithanand |
| Platforms | Instagram Reels, YouTube Shorts |
| Audience | Age 22–45, working professionals, India |
| Tone | Confident, direct, friend-to-friend. Never corporate. |
| Language | Conversational English, 8th-grade readability |
| Niche | AI automation for SMBs and solopreneurs |
| Visual style | Black + White + one accent (Red = danger / Blue = solution) |
| Caption style | Hormozi: bold white, 4px black stroke, max 3 words per frame |
| On-screen text | Montserrat ExtraBold, max 3–5 words per line, uppercase |
| Hook bank | 200 templates → `scripts/reference_scripts/english-hooks.md` |
| Format bank | 47 formats → `scripts/reference_scripts/content-formats.md` |
