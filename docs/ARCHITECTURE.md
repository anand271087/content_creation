# AI Reel Pipeline — Architecture

A productized system that converts a single content brief into a finished,
publish-ready 60–90 second vertical video reel. Built as a deterministic,
resumable, multi-stage orchestration with clean separation between the
narrative layer (script), the visual layer (avatar + b-roll), the audio
layer (music + voice), and the composition layer (final video).

---

## 1. Functional Architecture

What the system does, viewed as a flow of content artifacts. Every box is an
isolated unit; every arrow is a data hand-off via a versioned JSON contract.

```
                       ┌─────────────────────────────┐
                       │   CONTENT BRIEF / TOPIC     │
                       │   (prompt template input)   │
                       └──────────────┬──────────────┘
                                      │
                                      ▼
                       ┌─────────────────────────────┐
                       │   STAGE 1                   │
                       │   Script Generation         │
                       │                             │
                       │   • Reads client prompt     │
                       │   • Produces 10-section     │
                       │     structured narrative    │
                       │   • Self-scoring loop until │
                       │     quality threshold met   │
                       └──────────────┬──────────────┘
                                      │
                              script_data.json
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
     ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
     │   STAGE 2       │    │   STAGE 3       │    │   STAGE 4       │
     │   B-Roll        │    │   Avatar        │    │   Audio         │
     │                 │    │                 │    │                 │
     │  Motion graphic │    │  Synthetic      │    │  Ambient bed +  │
     │  clips per      │    │  talking-head   │    │  impact stings  │
     │  section type   │    │  video          │    │                 │
     │                 │    │                 │    │                 │
     │  • clip         │    │                 │    │                 │
     │  • diagram      │    │                 │    │                 │
     │  • screen       │    │                 │    │                 │
     │  • terminal     │    │                 │    │                 │
     └────────┬────────┘    └────────┬────────┘    └────────┬────────┘
              │                      │                      │
              └──────────────────────┼──────────────────────┘
                                     │
                                     ▼
                       ┌─────────────────────────────┐
                       │   STAGE 5                   │
                       │   Compose & Render          │
                       │                             │
                       │   • Word-level transcript   │
                       │     alignment               │
                       │   • Section timestamp sync  │
                       │   • Composition assembly    │
                       │   • 1080×1920 render        │
                       │   • 1.25× post-ready cut    │
                       │   • Thumbnail trailing card │
                       └──────────────┬──────────────┘
                                      │
                                      ▼
                       ┌─────────────────────────────┐
                       │   STAGE 6                   │
                       │   Quality Review            │
                       │                             │
                       │   Multi-image evaluation    │
                       │   against design rubric.    │
                       │   Loops back if below bar.  │
                       └──────────────┬──────────────┘
                                      │
                                      ▼
                       ┌─────────────────────────────┐
                       │   STAGE 8                   │
                       │   Social Copy               │
                       │                             │
                       │   YouTube / Instagram /     │
                       │   LinkedIn captions and     │
                       │   hashtags                  │
                       └──────────────┬──────────────┘
                                      │
                                      ▼
                       ┌─────────────────────────────┐
                       │   FINAL REEL + ASSETS       │
                       │                             │
                       │   • final_reel.mp4          │
                       │   • final_reel_fast.mp4     │
                       │   • Captions, thumbnail     │
                       │   • Social copy files       │
                       └─────────────────────────────┘
```

### Key Design Properties

- **Deterministic** — same input + same prompt = same artifact set.
- **Resumable** — every stage writes state; pipeline auto-resumes on retry.
- **Stage-isolated** — no stage reads from another stage's working directory.
- **Parallel where possible** — Stages 2, 3, 4 run concurrently after Stage 1.
- **Re-renderable in minutes** — Stage 5 alone can be re-run when only visuals
  or templates change, without re-generating script or avatar.

---

## 2. Technical Architecture

How the system is built, viewed as runtime components and external services.
Components own their boundaries; everything else is interchangeable.

```
┌──────────────────────────────────────────────────────────────────────┐
│                          ORCHESTRATION LAYER                          │
│                                                                       │
│   pipeline.py                                                         │
│   • Stage runner with retry, parallel execution, crash recovery       │
│   • State persistence (pipeline_state.json)                           │
│   • Structured logging                                                │
└──────────────────────────────────────────────────────────────────────┘
            │
            ├─────────────────────────────────────────────────────────────┐
            ▼                                                              ▼
┌────────────────────────────┐                          ┌──────────────────────────────┐
│   AI / LANGUAGE LAYER      │                          │   MEDIA GENERATION LAYER     │
│                            │                          │                              │
│   • Script generator       │                          │   • Synthetic avatar API     │
│     (Anthropic API)        │                          │     (HeyGen)                 │
│                            │                          │                              │
│   • Script quality scorer  │                          │   • Audio generation API     │
│     (Anthropic API)        │                          │     (ElevenLabs via Kie.ai)  │
│                            │                          │                              │
│   • Visual quality scorer  │                          │   • Image generation         │
│     (Anthropic vision)     │                          │     (Imagen / nano-banana)   │
│                            │                          │                              │
│   • Social copy writer     │                          │   • Word-level transcription │
│     (Anthropic API)        │                          │     (Whisper, local)         │
└────────────────────────────┘                          └──────────────────────────────┘
            │                                                              │
            └───────────────────────────┬──────────────────────────────────┘
                                        ▼
                       ┌──────────────────────────────────┐
                       │   ANIMATION & RENDER LAYER       │
                       │                                  │
                       │   • Motion-graphic engine        │
                       │     (HyperFrames — HTML+GSAP →   │
                       │      headless browser → MP4)     │
                       │                                  │
                       │   • Video composition engine     │
                       │     (Remotion — React → MP4)     │
                       │                                  │
                       │   • Media transcode engine       │
                       │     (FFmpeg — H264 baseline,     │
                       │      1.25× speed-up, concat)     │
                       └─────────────────┬────────────────┘
                                         │
                                         ▼
                       ┌──────────────────────────────────┐
                       │   ASSET STORE                    │
                       │                                  │
                       │   • script_data.json (contract)  │
                       │   • broll/*.mp4                  │
                       │   • avatar/avatar_video.mp4      │
                       │   • music/*.mp3                  │
                       │   • captions/avatar_video.json   │
                       │   • final/final_reel*.mp4        │
                       │   • social/*.txt                 │
                       │   • analysis/video_analysis.json │
                       └──────────────────────────────────┘
```

### External Services

| Service                  | Purpose                            | Replaceable? |
|--------------------------|------------------------------------|--------------|
| Anthropic API            | Script, scoring, social copy       | No (model-specific) |
| HeyGen                   | Synthetic talking-head avatar      | Yes (any avatar API) |
| Kie.ai (ElevenLabs)      | Ambient music + impact stings      | Yes (any TTS/SFX) |
| Kie.ai (Imagen / Kling)  | Reference imagery (optional)       | Yes |
| OpenAI Whisper           | Word-level transcript alignment    | Yes (local) |

### Internal Components

| Component         | Technology              | Role                              |
|-------------------|-------------------------|-----------------------------------|
| Orchestrator      | Python 3.11             | Stage runner, state machine       |
| Animation engine  | HyperFrames + GSAP      | Motion graphics → MP4             |
| Composition       | Remotion + React        | Layered timeline → MP4            |
| Transcode         | FFmpeg                  | Codec normalization, speed-up     |
| Asset store       | Filesystem (versioned)  | Stage-to-stage hand-off           |
| Captions          | Whisper word-level JSON | Sync source for visuals + audio   |

---

## 3. Operational Model

A single command produces a finished reel. The system is built to run unattended
on a workstation or a single-tenant cloud worker.

| Stage          | Typical Duration | Parallel | Cost Footprint |
|----------------|------------------|----------|----------------|
| Script         | ~90 seconds       | No       | LLM tokens                            |
| B-Roll         | ~3 minutes        | Yes      | Browser render, optional media APIs   |
| Avatar         | ~5–10 minutes     | Yes      | Avatar generation credits             |
| Audio          | ~2 minutes        | Yes      | TTS / SFX credits                     |
| Compose        | ~5–10 minutes     | No       | Local CPU                             |
| Quality Review | ~1 minute         | No       | LLM tokens (vision)                   |
| Social Copy    | ~20 seconds       | No       | LLM tokens                            |

End-to-end wall-clock: **15–25 minutes per reel** on standard developer hardware.

---

## 4. Quality Controls

- **Script gate** — generated scripts are scored against a structured rubric and
  re-generated until they clear a quality threshold.
- **Pre-render check** — script is sanity-checked before paying for avatar /
  media generation.
- **Visual review** — finished reels are evaluated against a multi-dimensional
  rubric (hook strength, on-screen text legibility, audio sync, CTA clarity).
- **Stale-asset guard** — downstream assets are auto-invalidated when their
  upstream contract changes.

---

## 5. Extensibility Surfaces

The pipeline is intentionally modular. The four high-leverage extension points:

1. **Prompt template** — swap the scripting style without touching code.
2. **Visual templates** — add new motion-graphic patterns by dropping HTML files.
3. **Avatar provider** — replace the avatar service via configuration only.
4. **Composition layer** — change reel layout, captions, or rhythm via React
   components without affecting upstream stages.

Each surface is independently testable and version-controlled.

---

## 6. Where The Client Prompt Goes

The pipeline accepts a client-supplied prompt template that fully replaces
the default Stage 1 generator. The template is the only piece of business
logic the client needs to own — every downstream stage is template-agnostic.

See [PROMPT_TEMPLATE.md](PROMPT_TEMPLATE.md) for the placeholder and
integration instructions.

---

## 7. What This System Does Not Do

To set expectations crisply, the pipeline does not:

- Generate scripts longer than ~90 seconds of spoken content (by design).
- Mix multiple speakers or styles in a single reel.
- Render landscape (16:9) outputs — vertical 9:16 only.
- Auto-publish to social platforms — outputs are files; distribution is
  external.
- Process live or streaming inputs — batch-only.

These are constraints we hold deliberately to keep the system fast, cheap,
and predictable.

---

## Document Conversion

This document is written in Markdown for easy review and version control.
To convert to Word or PDF for distribution:

```bash
# To Word
pandoc docs/ARCHITECTURE.md -o ARCHITECTURE.docx

# To PDF
pandoc docs/ARCHITECTURE.md -o ARCHITECTURE.pdf --pdf-engine=xelatex
```

Or open this file in any Markdown editor (Typora, Obsidian, VS Code preview)
and export from there.
