---
name: viral-script-writer
description: >-
  Use when writing or generating a short-form video script (Instagram Reels,
  YouTube Shorts, TikTok) for the ZeroHands / @automatewithanand brand, or when
  turning a topic brief into a script. Encodes Harsha Tambraeni's Ultimate Script
  Writing method: the 3-act structure, the 5 hook formulas, inverted-pyramid value
  delivery, micro-hooks every 8-10 seconds, extreme density on viral scripts, and
  CTAs scaled by content type (Virality / Authority / Conversion). Trigger on any
  request to write, draft, rewrite, or score a reel/short script.
---

# Viral Script Writer

Generates short-form scripts the way Harsha Tambraeni's method prescribes, tuned
for the ZeroHands brand (AI Avatar systems for founders). The goal of every line
is to keep **Reality ahead of Expectations** so watch time and completion stay high
— that is the single rule the algorithm rewards.

## Inputs & outputs

**Input:** a topic brief (e.g. `topic_brief.json`) containing at minimum a topic,
and ideally the intended content type and pillar. If content type or pillar are
missing, infer them (see Step 1) and state the assumption in the output.

**Output:** a script object with these fields:
- `content_type`: Virality | Authority | Conversion
- `pillar`: Awareness | Proof & Results | Systems & Action
- `template`: which of the 7 templates was used
- `hook`: the scripted hook (also note the visual + auditory hook cue)
- `body`: the value section, written for spoken delivery
- `cta`: the call to action
- `runtime_estimate_sec`: Virality ≤15s (hard cap); Authority/Conversion 20-45s
- `micro_hooks_used`: list of the re-engagement lines placed in the body

Write `body` and `hook` as **spoken** lines (how Anand actually talks), not prose.

## Non-negotiable rules (check every script against these)

1. Hook lands in the first 3 seconds and passes the 5 hook tests (see below).
2. Body uses the **inverted pyramid** order: second-best point first, best point
   second, rest descending. Never open with your strongest point.
3. Every point is a full **Value Loop**: What it is → How to do it → Why it matters.
4. A **micro-hook** appears every 8-10 seconds in the body.
5. Max **1-3 points** per script. No information overload.
6. CTA strength **scales with content type** (see CTA section). Never hard-sell on
   Virality content.
7. Obey the condensation rules: One-Sentence Rule, 10-Second Rule, Clarity Test.
8. Never open with "Hey guys", "In this video", "What's up" — banned.
9. No music-dependent jokes; the script must work on mute (captions carry it).
10. **Density.** Every line must earn its place — maximum value or intrigue per
    second, zero dead air. On **Virality** scripts this is the top priority and has a
    hard spec (see "Viral density spec"). Loose, wordy scripts fail.

## Process

### Step 1 — Classify
Determine `content_type` and `pillar`.
- **Virality** = broad, relatable, get discovered. Soft CTA. Pillar usually Awareness.
- **Authority** = specific, educational, build trust. Save CTA. Pillar usually Systems & Action or Proof.
- **Conversion** = direct, turn warm viewers into calls. Keyword CTA. Pillar usually Proof & Results.

### Step 2 — Pick a template
Choose the best fit from `references/templates.md` (Problem-Solution, Myth-Busting,
Behind-the-Scenes, List/Tips, Transformation, Question-Answer, Mistake-Lesson).

### Step 3 — Write the hook
Pick a formula from `references/hook-formulas.md`. Prefer **negative / contrarian /
curiosity-gap** hooks — they outperform positive hooks by 40-60%. Then add a visual
hook cue (text overlay in first 0.5s) and an auditory cue.
Test the hook against: Scroll-Stop, Clarity, Curiosity, Relevance, Uniqueness.

### Step 4 — Write the body
- Order points by inverted pyramid (2nd-best, best, then descending).
- Write each point as a Value Loop (What / How / Why).
- Insert a micro-hook before each new point ("But here's what most people miss…",
  "Stay with me, the last one matters most…", "Wait, it gets better…").
- Optionally layer one advanced retention device: In Medias Res, Breadcrumb,
  Retention Hook Ladder, or Callback (see `references/templates.md`).
- Cut any sentence the video survives without.

### Step 5 — Write the CTA (scale by content type)
- **Virality → soft:** "Follow if…" / "Save this".
- **Authority → save/trust:** "Save this, you'll want it when you build yours".
- **Conversion → keyword (highest converting):** "Comment [KEYWORD] and I'll send you
  [resource]" — this feeds the ManyChat → booking funnel, so always use a keyword on
  Conversion scripts. Integrate it natively (solve a pain, offer the resource as help).

### Step 6 — Density pass (REQUIRED, do not skip)
After drafting, rewrite the whole script tighter. For **every** script:
- Delete any word or sentence the script survives without (setup lines,
  throat-clearing like "so here's the thing" / "let me explain", filler adjectives).
- Compress each sentence: "The reason it works isn't the tool, it's three things"
  → "It's not the tool. It's three things."
- Fire lists instead of unfolding them: "bad footage, cheap voice, lazy script — that's why."
- Make every line do a *different* job (hook / reveal / proof / dream / CTA). No two
  lines should do the same job.
- Dense ≠ rushed. Remove waste, don't cram syllables. Every surviving line should
  still breathe. Aim: "every line is a headline."

**If content_type = Virality, additionally apply the Viral density spec below.**

#### Viral density spec (Virality only)
Model every viral script on the gold-standard example in
`references/viral-density.md`. Rules:
- **Max 15 seconds** (~35-45 words total). Hard cap.
- **One sentence per beat.** Structure = Hook → Reveal/Payoff → Proof+Dream → CTA.
  Four beats, roughly four sentences.
- **Front-load the two most gripping beats** (bold claim + the reveal/intrigue) in
  the first two lines. Do not ramp up to the reveal — open near it.
- **Fuse proof and dream into one line** (the mechanism AND why anyone wants it):
  e.g. "I recorded once, and now this runs every day while I'm with my family."
- **CTA carries a promise**, not just an ask: "Follow and I'll show you exactly how."
- **Strip anything that teaches.** A how-to breakdown (e.g. "3 reasons it looks fake")
  is Authority content, not Virality. A viral script's only jobs are stop-the-scroll
  and earn the follow — pure intrigue, no lesson.

### Step 7 — Self-check
Run the script against the Non-negotiable rules and the mistake list in
`references/templates.md` (Common Mistakes section). For Virality, also confirm the
Viral density spec (≤15s, one sentence per beat, no teaching). Fix before returning.

## Brand context (bake into voice)

- **Who:** Anand Kaliappan — ZeroHands, @automatewithanand. 17+ years engineering → AI founder.
- **Offer:** done-for-you AI Avatar systems for founders (advertise yourself, grow
  revenue, zero camera time).
- **ICP:** SMB founders who know they should be visible online but can't / won't be on
  camera daily.
- **Pillars:** Awareness · Proof & Results · Systems & Action.
- **Voice:** direct, confident, simple English, founder-to-founder. No hype, no jargon,
  no filler intros. Short punchy sentences.
- **Tools he can reference naturally:** HeyGen, ElevenLabs, Claude, ManyChat, n8n.

## Integration note

This skill produces the script; it does not score it. Hand the output to the
pipeline's scoring stage. Because the method front-loads a strong hook and keeps a
micro-hook cadence, it is built to score well on hook strength, retention, and voice.
If the score stage rejects a script, regenerate Step 3-4 with a different hook formula
and a tighter point set rather than rewriting the whole thing.
