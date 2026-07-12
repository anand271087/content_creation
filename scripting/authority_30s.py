"""
authority_30s.py — 30-45s Authority reel builder.

Generates a teaching-style script following Harsha's Authority rules
(inverted pyramid, Value Loops, micro-hooks every 8-10s, Save CTA) and writes
assets/script_data.json in the pipeline's 10-section schema so pipeline.py can
render it with full b-roll, on-screen text, music stings, and captions.

Section mapping (Authority content into the 10-section schema):
    hook           → bold problem statement (0-4s)
    context        → what most people wrongly think (4-7s)
    trigger_1      → micro-hook "But here's what most miss" (7-8s)
    body_1         → point #1 = 2nd BEST — Value Loop What/How/Why (8-14s)
    trigger_2      → micro-hook "The bigger issue" (14-16s)
    body_2         → point #2 = BEST — Value Loop What/How/Why (16-24s)
    trigger_3      → micro-hook "One more thing" (24-25s)
    bridge         → point #3 = 3rd priority — compressed Value Loop (25-30s)
    grand_takeaway → "It's these three things" summary line (30-34s)
    emotion_save   → Save CTA + framework name (34-40s)

Usage:
    python3 scripts/authority_30s.py --topic "Why AI Avatars Look Fake"
    python3 scripts/authority_30s.py --topic "..." --dry-run       # script only
    python3 scripts/authority_30s.py --script existing.json        # skip Claude
    python3 scripts/authority_30s.py --topic "..." --no-render     # gen + save, no pipeline

Env: ANTHROPIC_API_KEY (Claude for script), plus everything pipeline.py needs.
"""
from __future__ import annotations
import argparse, json, logging, os, re, subprocess, sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
REF_DIR = ROOT / "reference" / "harsha_skill"
SCRIPT_OUT = ROOT / "assets" / "script_data.json"

for d in (SCRIPT_OUT.parent,):
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [authority_30s] %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("authority_30s")


def env(name: str, required: bool = True) -> str:
    load_dotenv(ROOT / ".env")
    v = (os.getenv(name) or "").strip()
    if required and not v:
        log.error("Missing env: %s", name); sys.exit(2)
    return v


# ── Claude prompt template ──────────────────────────────────────────────────

AUTHORITY_PROMPT = """You are writing an AUTHORITY reel (30-40 seconds) for @automatewithanand
(AI automation content for founders / SMB owners who want to be online but
can't/won't film daily).

Obey the SKILL.md rules literally. Authority = teaching, trust-building,
Save-worthy. NOT viral density. NOT a viral hook chase.

REFERENCE 1: Harsha's SKILL.md (viral-script-writer skill card).
{skill_md}

REFERENCE 2: hook-formulas.md — pick a NEGATIVE / CONTRARIAN hook.
{hook_formulas}

REFERENCE 3: templates.md — Authority pieces usually use Myth-Busting,
Problem-Solution, or Mistake-Lesson templates.
{templates}

TOPIC: {topic}

═══════════════════════════════════════════════════════════════════════════
GATED PASSES — you must apply EVERY pass below and confirm each in the
`self_check` field of the JSON. If ANY pass fails, rewrite before returning.
═══════════════════════════════════════════════════════════════════════════

PASS 1 — Hook Pass (5 hook tests)
  The hook (section id="hook") must pass ALL FIVE tests from SKILL.md:
    (a) Scroll-Stop: bold enough to freeze a scrolling thumb
    (b) Clarity:     one clear claim, no compound sentences
    (c) Curiosity:   opens a loop the viewer wants closed
    (d) Relevance:   speaks to the target ICP (founders / SMB owners)
    (e) Uniqueness:  contrarian or negative angle — NOT positive framing
  Use a NEGATIVE / CONTRARIAN / CURIOSITY-GAP formula from hook-formulas.md.
  Example (good): "Most AI avatars look fake — and it's not the tool's fault."
  Example (bad):  "AI avatars are amazing." (positive, no curiosity, no scroll-stop)

PASS 2 — Inverted Pyramid Pass
  Order the 3 points so that:
    body_1 = 2nd BEST point (strong open, but NOT the killer)
    body_2 = BEST point (the killer, lands the video)
    bridge = 3rd point (rounds out the framework)
  NEVER open with the strongest point — save it for the middle.
  Example ordering for "Why AI Avatars Look Fake":
    2nd best → eye contact / gaze drift
    BEST    → mismatched vocal energy vs facial expression
    3rd     → over-smooth skin / uncanny lighting

PASS 3 — Value Loop Pass (per point)
  Each of body_1, body_2, bridge must contain three moves in ONE sentence flow:
    WHAT it is  → name the mistake / mechanism
    HOW to fix  → concrete micro-step (a setting, a prompt trick, a comparison)
    WHY         → the payoff / cost of getting it wrong
  Example (compressed into one spoken flow):
    "The avatar's gaze drifts off-camera every second sentence — fix it by
     shortening each spoken line to under twelve words — because your brain
     reads long-form gaze wander as a lie."

PASS 4 — Micro-Hook Cadence Pass
  A re-engagement line MUST appear every 8-10 seconds inside the body.
  In this 10-section schema they sit at trigger_1 (7-8s), trigger_2 (14-16s),
  trigger_3 (24-25s). Each MUST break state and tease the next point:
    trigger_1: "But here's what most people miss."
    trigger_2: "The bigger issue is this."
    trigger_3: "One more thing — this one matters most."
  Never re-use the same micro-hook phrasing twice.

PASS 5 — Density Pass (from SKILL.md Step 6)
  After drafting, rewrite EVERY line tighter:
    - Delete any sentence the video survives without (setup, throat-clearing,
      "so here's the thing", "let me explain", filler adjectives).
    - Compress each sentence:
      "The reason it works isn't the tool, it's three things"
       → "It's not the tool. It's three things."
    - Fire lists instead of unfolding them:
      "bad footage, cheap voice, lazy script — that's why."
    - Make EVERY line do a DIFFERENT job (hook / setup / point / takeaway / CTA).
      No two lines do the same job.
    - Dense ≠ rushed. Every surviving line should still breathe.
    - Aim: "every line is a headline."

PASS 6 — Condensation Rules (from SKILL.md non-negotiables)
    (a) One-Sentence Rule: every point must be expressible in one spoken sentence.
    (b) 10-Second Rule: each point (body_N) must fit in ≤10 seconds of spoken time.
    (c) Clarity Test: a 22-45 year old scrolling on mute must "get" the point
        from the on_screen_text alone (that's why on_screen_text is a full
        headline, never a fragment).

PASS 7 — CTA Pass (Save, not Follow)
  Authority CTA = SAVE, not FOLLOW-first. The emotion_save section MUST:
    - Direct the viewer to SAVE the video ("Save this — it's your checklist")
    - Name the framework as a named thing worth saving
    - Follow-ask is secondary and comes AFTER the save-ask
  Example: "Save this — next time you build an AI avatar, run through these
   three checks. Follow for the full breakdown."

PASS 8 — Voice & Brand Pass
    - No "Hey guys", "In this video", "What's up" openings (banned).
    - No hype. No jargon. Founder-to-founder tone.
    - 8th-grade readability. Short punchy sentences.
    - Tools can be named naturally: HeyGen, ElevenLabs, Claude, ManyChat, n8n.
    - Spell out numbers for TTS ("three things" not "3 things").
    - Script must work on mute (captions carry it — see PASS 6c).

PASS 9 — Broll Type Pass (Authority visual style)
  Every broll_prompt MUST specify visual TYPE + CONTENT and be one of:
    - Screen recording of a real tool (HeyGen editor, comparison side-by-side)
    - Static graphic / diagram (labeled illustration of the concept)
    - Real tool footage (waveforms, avatar rendering, character panel)
  Broll_prompts MUST NOT be dark cinematic tension shots — that's Virality only.
  Every broll_prompt MUST end with:
    "absolutely no text overlays, no watermarks, no captions, 9:16 vertical"

PASS 10 — Runtime Pass
  Total spoken script: 85-110 words. Runtime: 32-40 seconds.
  Nothing longer, nothing shorter. Trim in the Density Pass if over.

═══════════════════════════════════════════════════════════════════════════
Now write the JSON. Include a `self_check` object with each pass marked
"pass" or a short reason it failed. If ANY pass is not "pass", rewrite the
script and re-check before returning.
═══════════════════════════════════════════════════════════════════════════

BROLL DIRECTION for AUTHORITY content — every broll_prompt must be one of:
- Screen recording style (HeyGen UI, comparison charts, before/after)
- Static graphic (a labeled illustration of the concept)
- Real footage of the tool being talked about (avatar rendering, waveforms)
- NOT dramatic cinematic tension shots (those are Virality only)
For each section, write a broll_prompt that specifies TYPE (screen / graphic /
tool footage) and CONTENT (what's on screen). Always end with:
"absolutely no text overlays, no watermarks, 9:16 vertical".

Return ONLY a JSON object matching this exact schema (no markdown, no prose):
{{
  "title": "<punchy title, 6-10 words>",
  "content_type": "Authority",
  "hook_used": "<# from english-hooks.md OR name from hook-formulas.md>",
  "format_used": "Myth-Busting | Problem-Solution | Mistake-Lesson",
  "template_used": "Harsha Authority Value-Loop 3-point",
  "total_duration_sec": <int, 32-40>,
  "runtime_estimate_sec": <same as total_duration_sec>,
  "word_count": <spoken word count>,
  "tone": "authoritative, founder-to-founder, teaching without preaching",
  "dsscl_scores": {{ "D": 9.5, "Share": 9.0, "Save": 9.7, "C": 8.5, "L": 8.5, "final": 9.31 }},
  "dsscl_iteration": 1,
  "bgm_transition_sec": 30,
  "bgm_dip_timestamps": [7, 14, 24],
  "full_spoken_script": "<all sections concatenated with periods between>",
  "grand_takeaway_line": "<one sentence, 10 words or fewer>",
  "tool_mentioned": "<one tool name — HeyGen, ElevenLabs, Claude, n8n, etc.>",
  "self_check": {{
    "pass_1_hook_5_tests":       "pass | <reason>",
    "pass_2_inverted_pyramid":   "pass | <reason>",
    "pass_3_value_loop_per_point": "pass | <reason>",
    "pass_4_micro_hook_cadence": "pass | <reason>",
    "pass_5_density":            "pass | <reason>",
    "pass_6_condensation":       "pass | <reason>",
    "pass_7_save_cta":           "pass | <reason>",
    "pass_8_voice_brand":        "pass | <reason>",
    "pass_9_broll_type":         "pass | <reason>",
    "pass_10_runtime":           "pass | <reason>"
  }},
  "sections": [
    {{
      "id": "hook", "label": "HOOK",
      "start_sec": 0, "end_sec": 4,
      "spoken": "<bold problem claim, ~10 words>",
      "on_screen_text": ["<3-5 word punch>", "<3-5 word punch>"],
      "broll_prompt": "<screen recording / graphic — 9:16 vertical>",
      "expression_cue": "direct eye contact, serious, slight lean forward",
      "vocal_direction": "confident, measured, no rush",
      "bgm_dip": false, "bgm_track": 1, "bgm_transition_here": false,
      "broll_type": "clip"
    }},
    {{
      "id": "context", "label": "CONTEXT — the wrong assumption",
      "start_sec": 4, "end_sec": 7,
      "spoken": "<what most people wrongly blame, ~8 words>",
      "on_screen_text": ["MOST PEOPLE BLAME:", "<the wrong culprit>"],
      "broll_prompt": "<visual of the wrong assumption>",
      "expression_cue": "raised eyebrow, mild skepticism",
      "vocal_direction": "conversational, setup pace",
      "bgm_dip": false, "bgm_track": 1, "bgm_transition_here": false,
      "broll_type": "clip"
    }},
    {{
      "id": "trigger_1", "label": "MICRO-HOOK #1",
      "start_sec": 7, "end_sec": 8,
      "spoken": "But here's what most people miss.",
      "on_screen_text": ["BUT HERE'S", "WHAT THEY MISS"],
      "broll_prompt": "<visual pattern interrupt — arrow or highlight>",
      "expression_cue": "beat, then look direct",
      "vocal_direction": "drop voice, deliberate pause between words",
      "bgm_dip": true, "bgm_track": 1, "bgm_transition_here": false,
      "broll_type": "clip", "flash_before": true
    }},
    {{
      "id": "body_1", "label": "POINT 1 — 2nd BEST (Value Loop)",
      "start_sec": 8, "end_sec": 14,
      "spoken": "<the 2nd-best point delivered as What / How / Why in ONE flow, ~18 words>",
      "on_screen_text": ["<point-1 name>", "<the concrete micro-step>"],
      "broll_prompt": "<illustration or screen recording of point 1's mechanism>",
      "expression_cue": "leaning in, teaching mode",
      "vocal_direction": "explanatory, land the mechanism clearly",
      "bgm_dip": false, "bgm_track": 1, "bgm_transition_here": false,
      "broll_type": "clip"
    }},
    {{
      "id": "trigger_2", "label": "MICRO-HOOK #2",
      "start_sec": 14, "end_sec": 16,
      "spoken": "But the bigger issue is this.",
      "on_screen_text": ["THE BIGGER", "ISSUE"],
      "broll_prompt": "<zoom-in graphic or highlighted arrow>",
      "expression_cue": "pause, then intensify",
      "vocal_direction": "slow, weighty",
      "bgm_dip": true, "bgm_track": 1, "bgm_transition_here": false,
      "broll_type": "clip", "flash_before": true
    }},
    {{
      "id": "body_2", "label": "POINT 2 — BEST (Value Loop)",
      "start_sec": 16, "end_sec": 24,
      "spoken": "<the killer point as What / How / Why, ~22 words>",
      "on_screen_text": ["<point-2 name>", "<the concrete micro-step>"],
      "broll_prompt": "<the strongest illustration — screen recording or side-by-side>",
      "expression_cue": "full engagement, direct eye contact",
      "vocal_direction": "clear, confident, this is THE point",
      "bgm_dip": false, "bgm_track": 1, "bgm_transition_here": false,
      "broll_type": "clip"
    }},
    {{
      "id": "trigger_3", "label": "MICRO-HOOK #3",
      "start_sec": 24, "end_sec": 25,
      "spoken": "One more thing.",
      "on_screen_text": ["ONE", "MORE THING"],
      "broll_prompt": "<visual accent — pointing arrow or count-up>",
      "expression_cue": "small smile, teasing",
      "vocal_direction": "quick, tease",
      "bgm_dip": true, "bgm_track": 1, "bgm_transition_here": false,
      "broll_type": "clip", "flash_before": true
    }},
    {{
      "id": "bridge", "label": "POINT 3 — SUPPORTING (compressed)",
      "start_sec": 25, "end_sec": 30,
      "spoken": "<3rd point, compressed Value Loop, ~14 words>",
      "on_screen_text": ["<point-3 name>", "<micro-step>"],
      "broll_prompt": "<supporting visual — chart or screen>",
      "expression_cue": "wrap-up teaching pose",
      "vocal_direction": "clean and definitive",
      "bgm_dip": false, "bgm_track": 1, "bgm_transition_here": false,
      "broll_type": "clip"
    }},
    {{
      "id": "grand_takeaway", "label": "GRAND TAKEAWAY",
      "start_sec": 30, "end_sec": 34,
      "spoken": "<the one-liner Authority summary — quotable, 10 words or fewer>",
      "on_screen_text": ["<the takeaway line, split into 2>", "<...>"],
      "broll_prompt": "<clean minimal graphic showing the 3-point framework as a labeled diagram, warm palette>",
      "expression_cue": "calm, confident, direct",
      "vocal_direction": "slow, land each word",
      "bgm_dip": false, "bgm_track": 2, "bgm_transition_here": true,
      "broll_type": "clip"
    }},
    {{
      "id": "emotion_save", "label": "SAVE CTA",
      "start_sec": 34, "end_sec": 40,
      "spoken": "Save this — next time you build an AI avatar, this is your checklist. Follow for the full breakdown.",
      "on_screen_text": ["SAVE THIS", "YOUR CHECKLIST"],
      "broll_prompt": "<save-icon UI + the 3-point framework recap on screen, warm blue palette, 9:16>",
      "expression_cue": "warm, friend-to-friend",
      "vocal_direction": "conversational, relaxed close",
      "bgm_dip": false, "bgm_track": 2, "bgm_transition_here": false,
      "broll_type": "clip", "tool_mentioned": "HeyGen"
    }}
  ]
}}

Do NOT deviate from this section structure. Fill EVERY field. Every section
must have a broll_prompt suitable for the AUTHORITY visual style (screen
recording / graphic / tool footage) — no cinematic dark tension shots.
"""


def load_refs() -> tuple[str, str, str]:
    skill = (REF_DIR / "SKILL.md").read_text(encoding="utf-8")
    hooks = (REF_DIR / "hook-formulas.md").read_text(encoding="utf-8")
    templates = (REF_DIR / "templates.md").read_text(encoding="utf-8")
    return skill, hooks, templates


MAX_PASS_RETRIES = 2  # extra attempts if self_check reports a failed pass


def _one_shot(client: anthropic.Anthropic, prompt: str) -> dict:
    resp = client.messages.create(
        model="claude-sonnet-4-5", max_tokens=6000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", text, flags=re.DOTALL).strip()
    return json.loads(text)


def _failed_passes(data: dict) -> list[tuple[str, str]]:
    """Return list of (pass_name, failure_reason) for anything not 'pass'."""
    sc = data.get("self_check") or {}
    failed = []
    for k, v in sc.items():
        s = str(v).strip().lower()
        if not s.startswith("pass"):
            failed.append((k, str(v)))
    return failed


def call_claude(topic: str) -> dict:
    key = env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)
    skill, hooks, templates = load_refs()
    prompt = AUTHORITY_PROMPT.format(
        skill_md=skill, hook_formulas=hooks, templates=templates, topic=topic,
    )
    log.info("Calling Claude (prompt=%d chars)…", len(prompt))
    data = _one_shot(client, prompt)

    # Retry loop — if self_check flags any failed pass, ask Claude to fix that pass
    attempts = 1
    while attempts <= MAX_PASS_RETRIES:
        failed = _failed_passes(data)
        if not failed:
            log.info("All 10 passes reported 'pass' on attempt %d.", attempts)
            break
        log.warning("Attempt %d failed passes: %s", attempts,
                    ", ".join(f for f, _ in failed))
        fix_note = "\n".join(f"- {f}: {r}" for f, r in failed)
        fix_prompt = (
            prompt + "\n\n=== PREVIOUS ATTEMPT FAILED PASSES ===\n"
            f"{fix_note}\n\nRewrite the ENTIRE script fixing those passes. "
            "Return the same JSON schema with all self_check values now 'pass'."
        )
        data = _one_shot(client, fix_prompt)
        attempts += 1

    # Sanity checks
    wc = data.get("word_count") or len(data.get("full_spoken_script", "").split())
    dur = data.get("total_duration_sec") or 0
    log.info("Script: %d words / %ds runtime / content_type=%s",
             wc, dur, data.get("content_type"))
    if data.get("content_type") != "Authority":
        log.warning("content_type=%s → forcing Authority.", data.get("content_type"))
        data["content_type"] = "Authority"
    if len(data.get("sections", [])) != 10:
        log.warning("Expected 10 sections, got %d", len(data.get("sections", [])))
    return data


def print_script_summary(d: dict) -> None:
    print("\n─── AUTHORITY SCRIPT ───────────────────────────────")
    print(f"  Title:          {d.get('title')}")
    print(f"  Content type:   {d.get('content_type')}")
    print(f"  Template:       {d.get('template_used')}")
    print(f"  Word count:     {d.get('word_count')}  (target 85-110)")
    print(f"  Runtime:        {d.get('total_duration_sec')}s  (target 32-40)")
    print(f"  Tool mentioned: {d.get('tool_mentioned')}")
    print(f"  Takeaway:       {d.get('grand_takeaway_line')}")
    sc = d.get("self_check") or {}
    if sc:
        print("\n  Self-check passes:")
        for k, v in sc.items():
            mark = "✓" if str(v).strip().lower().startswith("pass") else "✗"
            print(f"    {mark} {k:32s} {v}")
    print("\n  Sections:")
    for s in d.get("sections", []):
        print(f"   [{s['start_sec']:>2}-{s['end_sec']:>2}s] {s['label']}: "
              f"{s.get('spoken','')[:80]}{'…' if len(s.get('spoken',''))>80 else ''}")
    print("────────────────────────────────────────────────────\n")


def run_pipeline(script_path: Path) -> int:
    """Delegate to pipeline.py to render b-roll + avatar + music + compose."""
    py = "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
    cmd = [py, str(ROOT / "pipeline.py"), "--script", str(script_path),
           "--skip-analysis"]
    log.info("Delegating to pipeline: %s", " ".join(cmd))
    return subprocess.call(cmd)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--topic", help="Topic for the Authority reel")
    p.add_argument("--script", help="Skip Claude — use existing script_data.json")
    p.add_argument("--dry-run", action="store_true",
                   help="Generate script only; print + save; do not call pipeline")
    p.add_argument("--no-render", action="store_true",
                   help="Save script but skip pipeline invocation")
    args = p.parse_args()

    if args.script:
        data = json.loads(Path(args.script).read_text())
        log.info("Using existing script from %s", args.script)
    else:
        if not args.topic:
            log.error("Need --topic (or --script)."); return 2
        data = call_claude(args.topic)

    SCRIPT_OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    log.info("Wrote script → %s", SCRIPT_OUT)
    print_script_summary(data)

    if args.dry_run or args.no_render:
        log.info("Skip rendering.")
        return 0

    return run_pipeline(SCRIPT_OUT)


if __name__ == "__main__":
    sys.exit(main())
