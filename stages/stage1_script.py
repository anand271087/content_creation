"""
Stage 1 — Viral Script Generator (GOAT Framework)
Generates a 60-second viral reel script using the Claude API.
Output: assets/script_data.json
"""

import argparse
import json
import logging
import os
import re
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

# ── Setup ──────────────────────────────────────────────────────────────────────

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
ASSETS_DIR = PROJECT_ROOT / "assets"
SCRIPTS_DIR = PROJECT_ROOT / "reference"
RULES_PATH = PROJECT_ROOT / "scripts" / "learnings" / "accumulated_rules.md"
OUTPUT_PATH = ASSETS_DIR / "script_data.json"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [stage1_script] %(levelname)s — %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "pipeline.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("stage1_script")

# ── Constants ──────────────────────────────────────────────────────────────────

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8000
MAX_ITERATIONS = 5
DSSCL_PASS_THRESHOLD = 9.5
DSSCL_PASS_INDIVIDUAL = {"D": 9.0, "Share": 9.0, "Save": 9.0, "C": 7.0, "V": 8.5}

REQUIRED_SECTION_IDS = [
    "hook",
    "context",
    "trigger_1",
    "body_1",
    "trigger_2",
    "body_2",
    "trigger_3",
    "bridge",
    "grand_takeaway",
    "emotion_save",
]

OUTPUT_SCHEMA = """
{
  "title": "string",
  "hook_used": "#21",
  "format_used": "Format 4 — Common vs Elite",
  "total_duration_sec": 90,
  "dsscl_scores": {
    "D": 9.5,
    "Share": 9.5,
    "Save": 9.5,
    "C": 8.0,
    "L": 8.5,
    "V": 9.0,
    "final": 9.43
  },
  "dsscl_iteration": 1,
  "bgm_transition_sec": 35,
  "bgm_dip_timestamps": [10, 20, 30],
  "full_spoken_script": "full concatenated spoken text from all sections",
  "grand_takeaway_line": "the 1-2 quotable screenshot-worthy sentences from grand_takeaway section",
  "tool_mentioned": "[pick the tool actually relevant to this topic — Claude Code / Make.com / Zapier / ChatGPT / Notion / Airtable / HeyGen / n8n / etc. — see TOOL SELECTION RULE above]",
  "tone": "neutral",
  "sections": [
    {
      "id": "hook",
      "label": "HOOK",
      "start_sec": 0,
      "end_sec": 5,
      "spoken": "spoken text for this section",
      "on_screen_text": ["WORD.", "WORD.", "WORD."],
      "broll_prompt": "cinematic scene description, no text, no faces, 9:16 vertical, mood",
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
      "broll_type": "clip"
    },
    {
      "id": "body_1",
      "label": "BODY 1",
      "start_sec": 12,
      "end_sec": 20,
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
      "id": "trigger_2",
      "label": "TRIGGER 2",
      "start_sec": 20,
      "end_sec": 25,
      "spoken": "...",
      "on_screen_text": ["..."],
      "broll_prompt": "...",
      "expression_cue": "...",
      "vocal_direction": "...",
      "bgm_dip": true,
      "bgm_track": 1,
      "bgm_transition_here": false,
      "broll_type": "clip"
    },
    {
      "id": "body_2",
      "label": "BODY 2",
      "start_sec": 25,
      "end_sec": 30,
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
      "id": "trigger_3",
      "label": "TRIGGER 3",
      "start_sec": 30,
      "end_sec": 32,
      "spoken": "...",
      "on_screen_text": ["..."],
      "broll_prompt": "...",
      "expression_cue": "...",
      "vocal_direction": "...",
      "bgm_dip": true,
      "bgm_track": 1,
      "bgm_transition_here": false,
      "broll_type": "clip"
    },
    {
      "id": "bridge",
      "label": "BRIDGE",
      "start_sec": 32,
      "end_sec": 35,
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
      "id": "grand_takeaway",
      "label": "GRAND TAKEAWAY",
      "start_sec": 35,
      "end_sec": 40,
      "spoken": "...",
      "on_screen_text": ["ASKING FOR HELP", "vs", "BUILDING WHAT WORKS"],
      "broll_prompt": "clean minimal warm desk setup, soft golden light, hopeful, 9:16 vertical",
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
      "end_sec": 120,
      "spoken": "...",
      "on_screen_text": ["START WITH: [TOOL NAME]", "STEP 1: [ACTION]", "SAVE THIS"],
      "broll_prompt": "...",
      "expression_cue": "warm smile, leaning toward camera, friend-to-friend energy",
      "vocal_direction": "conversational, warm, relaxed pace",
      "bgm_dip": false,
      "bgm_track": 2,
      "bgm_transition_here": false,
      "broll_type": "clip",
      "tool_mentioned": "[same tool as top-level tool_mentioned field]"
    }
  ]
}
"""

# ── Reference files ────────────────────────────────────────────────────────────

def load_reference_files() -> tuple[str, str, str]:
    """Load GOAT framework reference files + Harsha skill overlay (5 hook formulas,
    7 templates, Value Loops, micro-hook cadence, CTA scaling by content type).

    Returns (hooks_content, formats_content, harsha_overlay).
    """
    hooks_path = SCRIPTS_DIR / "english-hooks.md"
    formats_path = SCRIPTS_DIR / "content-formats.md"
    if not hooks_path.exists():
        raise FileNotFoundError(f"Hook bank not found: {hooks_path}")
    if not formats_path.exists():
        raise FileNotFoundError(f"Format bank not found: {formats_path}")

    hooks_content = hooks_path.read_text(encoding="utf-8")
    formats_content = formats_path.read_text(encoding="utf-8")

    # Harsha skill overlay — SKILL card + hook formulas + templates + viral-density
    # rule (the last is the Virality-only "gold standard": 4 beats, ≤15s / 35-45 words,
    # no teaching, CTA carries a promise). If the dir is absent (fresh clone) we log a
    # warning and continue — overlay is optional.
    harsha_dir = SCRIPTS_DIR / "harsha_skill"
    harsha_overlay = ""
    if harsha_dir.exists():
        parts = []
        for name in ("SKILL.md", "hook-formulas.md", "templates.md", "viral-density.md"):
            fpath = harsha_dir / name
            if fpath.exists():
                parts.append(f"── {name} ────────────────\n{fpath.read_text(encoding='utf-8')}")
        harsha_overlay = "\n\n".join(parts)
        log.info("Loaded Harsha skill overlay (%d chars) from %d files.",
                 len(harsha_overlay), len(parts))
    else:
        log.warning("Harsha skill dir missing at %s — running without overlay.", harsha_dir)

    log.info("Loaded hook bank (%d chars) and format bank (%d chars).",
             len(hooks_content), len(formats_content))
    return hooks_content, formats_content, harsha_overlay


def load_accumulated_rules() -> str:
    """Load distilled rules from past pipeline runs (Stage 7 output). Returns empty string if none yet."""
    if RULES_PATH.exists():
        rules = RULES_PATH.read_text(encoding="utf-8").strip()
        if rules:
            log.info("Loaded accumulated rules (%d chars) from past runs.", len(rules))
            return rules
    return ""


# ── Prompt construction ────────────────────────────────────────────────────────

def build_initial_prompt(
    topic: str | None,
    transcript: str | None,
    hooks_content: str,
    formats_content: str,
    accumulated_rules: str = "",
    research_context: dict | None = None,
    harsha_overlay: str = "",
) -> str:
    if topic:
        content_block = f"TOPIC: {topic}"
    else:
        content_block = f"TRANSCRIPT:\n{transcript}"

    rules_block = ""
    if accumulated_rules:
        rules_block = f"""
=== RULES FROM PAST RUNS (non-negotiable — these fix recurring failures) ===
{accumulated_rules}

"""

    research_block = ""
    if research_context:
        hook_angle = research_context.get("hook_angle") or ""
        why = research_context.get("why") or ""
        outlier_ref = research_context.get("outlier_ref") or {}
        backup_topics = research_context.get("backup_topics") or []
        signal_strength = research_context.get("signal_strength")

        lines = ["=== RESEARCH CONTEXT (use this to sharpen the script) ==="]
        if signal_strength is not None:
            lines.append(f"Signal strength: {signal_strength}/10 — this topic is actively trending right now.")
        if hook_angle:
            lines.append(f"Primary hook angle: {hook_angle.upper()} — lead with this emotion. Make the viewer feel it in the first 3 seconds.")
        if why:
            lines.append(f"Why this topic is trending NOW: {why}")
            lines.append("→ You can reference this real-world evidence in the script as proof the topic matters.")
        if outlier_ref:
            title = outlier_ref.get("title", "")
            views = outlier_ref.get("views", "")
            formula = outlier_ref.get("thumbnail_formula", "")
            adaptation = outlier_ref.get("adaptation_for_anand", "")
            if title and views:
                lines.append(f"Outlier reference video: \"{title}\" — {views:,} views." if isinstance(views, int) else f"Outlier reference video: \"{title}\" — {views} views.")
            if formula:
                lines.append(f"What made that video work: {formula}")
            if adaptation:
                lines.append(f"How to adapt for @automatewithanand: {adaptation}")
        if backup_topics:
            topics_list = "; ".join(t.get("topic", "") for t in backup_topics if t.get("topic"))
            if topics_list:
                lines.append(f"Backup topics (use only if main topic can't reach DSSCL 9.5): {topics_list}")
        lines.append("")
        research_block = "\n".join(lines) + "\n"

    harsha_block = ""
    if harsha_overlay:
        harsha_block = f"""
=== HARSHA'S SCRIPTWRITING METHOD — apply on top of the GOAT framework ===
The GOAT 10-section structure below is unchanged. But when writing each section,
also obey Harsha's method (short-form virality craft). This overlay is *additive*,
not a replacement. The two work together: GOAT gives you the skeleton; Harsha gives
you the muscle.

Key overlays to apply while writing:
1. HOOK (section 'hook') — pick from Harsha's 5 formulas AND from the 200-hook bank.
   Prefer NEGATIVE / CONTRARIAN / CURIOSITY-GAP hooks; they outperform positive hooks
   by 40–60%. Test the finalised hook against Scroll-Stop, Clarity, Curiosity,
   Relevance, and Uniqueness before committing.
2. TEMPLATE — pick one of Harsha's 7 templates (Problem-Solution, Myth-Busting,
   Behind-the-Scenes, List/Tips, Transformation, Q&A, Mistake-Lesson) as the
   underlying narrative shape for body_1 + body_2 + bridge. Record which template
   in the top-level "template_used" field.
3. VALUE LOOPS in every body section — every point must be a full loop:
   WHAT it is → HOW to do it → WHY it matters. Never leave 'why' implied.
4. MICRO-HOOKS every 8–10 seconds — Harsha's trigger_1/2/3 slots are already
   micro-hooks. Reinforce them: use lines like "But here's what most people miss…",
   "Wait, it gets better…", "The last one changes everything…" as connectors.
5. CTA scales with content_type. Detect the content_type and set the field in the
   top-level JSON:
     - "Virality"    → soft CTA in emotion_save ("Follow if…", "Save this")
     - "Authority"   → save CTA ("Save this — you'll want it when you build yours")
     - "Conversion"  → keyword CTA feeding the ManyChat funnel ("Comment [KEYWORD]
                       and I'll send you [resource]"). Use for anything selling calls.
   ⚠️ If content_type == "Virality": ALSO obey viral-density.md (below). Every line
   must land — max 4 beats total across hook+context+bodies+takeaway, no teaching
   breakdown (teaching lives in Authority content), CTA carries a promise
   ("Follow and I'll show you exactly how"). The 10-section GOAT structure still
   applies as scaffolding, but each section must be compressed so the *spoken*
   line does one specific job and nothing repeats. Fuse proof + dream into a
   SINGLE line where possible. Cut anything the script survives without.
6. INVERTED PYRAMID — order points by 2nd-best first, best second, then descending.
   Never open the body with your strongest point; save it for body_2 or trigger_3.
7. CONDENSATION — obey Harsha's One-Sentence Rule (each section describes ONE clear
   idea in a sentence), 10-Second Rule (compress until removing another word breaks
   meaning), Clarity Test (a first-time viewer must "get it" without pausing).

New top-level fields to include in the output JSON:
- "content_type":   one of "Virality" | "Authority" | "Conversion"
- "hook_formula":   one of "Negative" | "Curiosity Gap" | "Direct Challenge" |
                    "Contrarian" | "But Wait Flip" | "Other (from 200-bank)"
- "template_used":  one of "Problem-Solution" | "Myth-Busting" | "Behind-the-Scenes"
                    | "List/Tips" | "Transformation" | "Question-Answer" |
                    "Mistake-Lesson"

The three reference files below encode the full method. Read them and apply their
rules while writing every section.

{harsha_overlay}

=== END HARSHA'S METHOD ===
"""

    return f"""You are an Instagram scriptwriting expert who creates viral short-form video scripts (30–90 seconds) for @automatewithanand, targeting AI automation content.

AUDIENCE PERSONA:
- Age 25–42, ambitious professionals — employed or running a small business
- Geography: India-first, but resonates with South Asian diaspora (US/UK/UAE/SG/AU)
- Pain: Drowning in manual work, watching peers get ahead, afraid AI will make their skills irrelevant
- Language: Conversational English, 8th-grade readability, occasional desi cultural references okay
- Fears: Being replaced by AI, falling behind colleagues, wasting their prime earning years on grunt work
- Wants: Income leverage, time freedom, becoming the "AI guy/girl" in their circle, status as early adopter
- Identity: They see themselves as smart and hardworking — they just need the right tools and someone to show them how
- Trigger phrase mindset: "If I had known this earlier..." / "Why is nobody talking about this?

CHANNEL VOICE & STYLE:
- Host: Anand — relatable South Indian tech professional, not a guru, more like a smart friend who figured it out first
- Tone: Confident but not arrogant, practical over theoretical, slightly conspiratorial ("most people don't know this")
- No fluff. Every sentence earns its place.
- Speak like you're talking to one person, not an audience
- Use pattern interrupts — unexpected stats, counterintuitive statements, or bold claims in the first 3 seconds

NON-NEGOTIABLE WRITING RULES:
- Hook in the first 3 seconds — bold statement, open loop, surprising fact, emotional trigger. Stop the scroll immediately.
- No filler — no welcome intros, no wasted sentences. Every word earns its place.
- Conversational language — spoken on camera, 8th-grade readability.
- Active voice only — never passive.
- Write for TTS pacing — use commas at natural breath points. Any sentence over 12 words must have at least one comma. Think of it as writing for an actor, not a reader.
- Spell out all numbers and currency for TTS: write "forty thousand rupees" not "₹40,000", "ninety thousand rupees" not "₹90K", "three hours" not "3 hrs". Currency symbols and raw numbers will be mispronounced.
- No em-dashes in spoken text — replace with a comma or period instead.
- Single core idea — one script, one message, maximum clarity.
- Deep research — real examples, real numbers. No generic claims.
- Originality — fresh angle. Never reuse prior examples.
- Emotional drivers — desire, fear, urgency, identity, transformation.
- Shareability test — "Will viewer send this to 3 friends right now?" If not → rewrite.
- Build to a climax — end with a "I need to act NOW" moment.
- Plain language only — if a 16-year-old wouldn't understand it instantly, rewrite it. No jargon without an instant plain-English follow-up.
- Max 12 words per sentence. Count them. Split anything longer into two sentences.
- Read it out loud test — every line must sound like something you'd actually say to a friend. If it sounds like a LinkedIn post, rewrite it.

{research_block}{rules_block}{harsha_block}VOICE & ORIGINALITY RULES — scored as V (minimum 8.5 to pass):

HOOK — use the 200-hook bank below as your primary source (Step 1 instructions unchanged).
After selecting the best hook from the bank, apply this filter before finalising:

BANNED HOOK EXECUTIONS — if your chosen hook template produces any of these after filling the blanks, pick the next best hook from the bank instead:
- Uses "amateurs" / "pros" as a contrast device in the filled output
- Uses "elite operators" / "top 1%" / "game changer" / "next level" in the filled output
- Fills to a structure like "While [group A] does X, [group B] does Y"
- Fills to an opening like "I built / created / set up X [time period] ago"

The hook bank has 200 options — there is always a better hook available. Never force a banned execution. Move to the next candidate hook and fill that instead.

CULTURAL GROUNDING — required in every script (missing = V score 6 or below):
Every script must feel like it comes from a real person, not a generic AI content template.
Achieve this through specificity — not necessarily Indian specificity.

Use this rotation across scripts to reach both Indian and global audiences:
- 40% Indian-anchored: city from (Bengaluru, Pune, Mumbai, Hyderabad, Chennai, Delhi) + rupee amount
- 30% South Asian diaspora: city from (Dubai, Singapore, London, Toronto, Sydney) + dollar amount
- 30% Globally neutral: role-anchored story ("a SaaS founder", "a freelance designer", "a two-person agency") with no city, universally relatable amount in dollars

Cultural texture (chai, Sunday afternoon, Monday morning) is OPTIONAL — use only when it fits naturally.
Never force it. A script without cultural texture that lands globally beats a script with forced references that feels locally limited.

PROOF STORY — must contain all four regardless of geography:
- Person type + location OR role (city name OR job title — one of the two is enough)
- Tool name (specific — not just "AI", name the actual tool)
- Time saved (specific number — "forty minutes", "three hours", "one afternoon")
- Money saved or earned (specific amount in the relevant currency, spelled out for TTS)
- ONE workflow detail: what specifically changed? what did they stop doing manually?
- Seeded in trigger_3 (one line), paid off fully in emotion_save (full story)

AMOUNT FORMAT FOR TTS — always spell out, never symbols:
- Indian: "forty thousand rupees" not "₹40,000"
- Dollar: "two thousand dollars" not "$2,000"
- Dirham: "seven thousand dirhams" not "AED 7,000"
- Pound: "fifteen hundred pounds" not "£1,500"

SCRIPT LENGTH:
- If full_spoken_script exceeds 65 seconds spoken aloud — the emotion_save section must NOT contain step-by-step tutorial instructions
- Tutorial content belongs in a follow-up video, not this reel
- emotion_save = warm payoff + CTA, not a walkthrough

CTA — one keyword, one offer, one closer:
- Format: "Comment [KEYWORD] below and I'll DM you [specific thing]"
- Never send viewer off-platform (no GitHub links, no "search for X")
- Save prompt comes AFTER the CTA keyword line
- Final line of emotion_save must be aspirational and visual, not instructional
  Strong closers: "untouchable in six months" / "invisible team working for them" / "deliver it before the call even ends"

V SCORE GUIDE:
- 10: Zero banned executions, strong hook from bank, full proof story with specific detail, single CTA, aspirational closer
-  8: One minor cliché slipped through, proof story slightly generic, closer is good not great
-  6: Hook from bank but filled with familiar/generic language, proof story has numbers but no specific workflow detail
-  4: One or more banned executions used, no cultural grounding, tutorial content in emotion_save
-  2: Ignored hook bank entirely, generic opener, two CTAs, no specificity anywhere

=== HOOK BANK (200 templates) ===
{hooks_content}

=== FORMAT BANK (47 structures) ===
{formats_content}

CONTENT TO SCRIPT:
{content_block}

STEP-BY-STEP INSTRUCTIONS:

0. TOOL SELECTION RULE — do this FIRST before writing anything:
   The "tool_mentioned" field must be the tool ACTUALLY relevant to this video's topic.
   Do NOT default to n8n. Pick from this list based on what the video is about:

   - Claude Code / Claude API  → if topic is about AI coding, terminal AI, Anthropic tools, coding assistants
   - Make.com                  → if topic is about visual no-code automation, drag-and-drop workflows
   - Zapier                    → if topic is about no-code automation for non-technical users
   - n8n                       → ONLY if topic is specifically about self-hosted or open-source automation
   - ChatGPT / GPT-4o          → if topic is about prompt engineering, AI chat, OpenAI tools
   - Notion AI                 → if topic is about knowledge management, docs, wikis, second brain
   - Airtable                  → if topic is about databases, CRM, spreadsheet automation
   - Google Sheets + Apps Script → if topic is about spreadsheet automation, reporting
   - HeyGen / ElevenLabs       → if topic is about AI video generation, voice cloning
   - Perplexity / Gemini       → if topic is about AI research tools, Google ecosystem
   - Cursor / Windsurf         → if topic is about AI-powered code editors

   The tool named in emotion_save MUST match what the video is actually teaching.
   Do not mention n8n in a Claude Code video. Do not mention Zapier in an Airtable video.

1. HOOK SELECTION:
   - Scan all 200 hooks in the hook bank above
   - Pick 2–3 best-fit hooks for this topic
   - Fill blanks with AI/automation-specific language
   - Pick the strongest → use as HOOK (0–5 sec)
   - Record chosen hook number in "hook_used" field

2. FORMAT SELECTION:
   - Use the goal→format lookup table in the format bank
   - Pick format that best matches this content goal
   - Use that format's structure as backbone for CONTEXT → TRIGGER → TAKEAWAY
   - Record chosen format number in "format_used" field

3. WRITE ALL 10 MANDATORY SECTIONS in this exact order with these exact timestamps:
   - HOOK:          0–5 sec   (pattern interrupt, open loop, big TAM)
   - CONTEXT:       5–10 sec  (bridge hook to content)
   - TRIGGER 1:    10–12 sec  (spike, tease only — bgm_dip: true)
   - BODY 1:       12–20 sec  (develop the loop)
   - TRIGGER 2:    20–25 sec  (stat/contrast spike — bgm_dip: true)
   - BODY 2:       25–30 sec  (make it personal)
   - TRIGGER 3:    30–32 sec  (real story with city, tool name, rupee/dollar amount, time saved — bgm_dip: true)
   - BRIDGE:       32–35 sec  (emotional pivot, shifting from dark to warm)
   - GRAND TAKEAWAY: 35–40 sec (EXACTLY ONE quotable sentence — screenshot-worthy, slow delivery — bgm_transition_here: true, bgm_track: 2)
   - EMOTION+SAVE: 40–120 sec (warm friend-to-friend, name ONE specific tool OR time estimate, CTA must include a keyword action: "Comment [WORD] below and I'll DM you [specific thing]" — use this section to deliver deep value: expand the story, add a second real-world example, give step-by-step setup instructions for the named tool, and build emotional momentum before the CTA. Target 60–80 seconds of spoken content for this section alone.)

4. FOR EVERY SECTION include all these fields:
   - spoken: actual words spoken on camera
   - on_screen_text: array of strings, each MAX 3–5 words, uppercase
   - DEFAULT RULE: Use "diagram" or "screen" for context, body_1, body_2, bridge whenever possible. Use "clip" ONLY when neither diagram nor screen fits. Triggers, hook, grand_takeaway, emotion_save must ALWAYS be "clip".

   PRIORITY ORDER (apply in this order):
   1. "terminal" — if the section is about a CLI tool (Claude Code, n8n CLI, Cursor, Python script, shell command) and a terminal demo would be the most engaging visual. The terminal shows a dark macOS-style window with the actual command being typed and realistic output streaming below. Perfect for "run this command → see the output" moments.
      Add these fields:
        "terminal_tool":    display name for the titlebar (e.g. "Claude Code", "n8n CLI", "Python")
        "terminal_command": the exact command string shown in the prompt (e.g. 'claude "design a landing page"')
        "terminal_output":  array of output lines — each is {{ "line": "...", "delay_ms": 150, "color": "success" }}
                            color must be one of: default | dim | success | warning | error | info | accent | cyan | orange
                            delay_ms = ms to wait before this line appears (realistic streaming effect)
      terminal_output rules:
        - 6–12 lines total — enough to fill the screen without overflow
        - Start with 1–2 "dim" status lines ("Reading codebase...", "Analyzing dependencies...")
        - Middle lines show the actual work ("✓ Created: src/components/Hero.tsx" in "success")
        - End with a summary line in "success" ("✓ Done in 12s — 847 lines written")
        - Use "error" color for any warnings/errors to add visual interest
        - delay_ms: 150–400ms per line (faster for "reading" lines, slower for "creating" lines)
      Use "terminal" for: body_1, body_2, bridge, context — NEVER for hook, triggers, grand_takeaway, emotion_save.

   2. "screen" — if the section mentions a SPECIFIC NAMED TOOL, product, model, or website that has a publicly accessible URL (Claude Code, n8n, Make.com, GitHub, OpenAI Codex, Gemini, Seed Dance, HuggingFace benchmarks, etc.). This includes news/analysis content — if the section talks ABOUT a tool or model demo, show its actual website/app/leaderboard.
   3. "text_card" — if the section enumerates 3–5 numbered or bulleted items in the spoken text
      (e.g. "first X, second Y, third Z" or "there are five types: one..., two..., three...").
      Add a "card_lines" field with the exact short labels (2–4 words each) to show on the card.
      card_lines example: ["Pure Prompt Skills", "Utility Scripts", "API Integrations", "Backend Services", "Proprietary Data"]
      These labels appear as a bold numbered list on an infographic card. They must match what's spoken exactly.
      Do NOT use for hook, triggers, grand_takeaway, emotion_save.

   4. "diagram" — if the section explains a process, workflow, comparison, statistics, or step-by-step concept with NO clear single tool URL to show.
   5. "clip" — fallback only: hook, triggers, grand_takeaway, emotion_save, or purely emotional/narrative sections with no tool or concept to show.

   DIAGRAM SECTIONS (broll_type: "diagram"):
   - Add a "diagram_prompt" field describing what to draw in plain English.
   - Keep it simple: 3–5 elements max (boxes, arrows, labels).
   - diagram_prompt example: "3 boxes left to right: Nano Banana → Kling → Claude Code, label each with what it does"
   - diagram_prompt example: "2 columns: LEFT=Old Way (agency ₹10L, 3 months), RIGHT=New Way (Claude Code ₹3200, 30 min), red X left, green check right"

   SCREEN SECTIONS (broll_type: "screen"):
   - Use for context, body_1, body_2, bridge sections that mention ANY specific named tool, model, or website.
   - EXPANDED USE CASES — screen is appropriate for:
       • Tutorial/demo: walking through a tool's UI (Claude Code, n8n, Make.com)
       • News/analysis: section talks about a specific model or product (Gemini → gemini.google.com, Codex → platform.openai.com/codex, Seed Dance → seedance.ai)
       • Benchmarks: section references a leaderboard or benchmark result (HuggingFace → huggingface.co/spaces/lmarena-ai/chatbot-arena-leaderboard)
       • GitHub projects: section mentions an open-source repo (GLM5 → github.com/THUDM/GLM-4, OpenClaw → github.com/nicklockwood/OpenClaw)
       • Product announcements: section discusses a new product page (openai.com/codex, anthropic.com/claude)
   - Do NOT use for triggers, hook, grand_takeaway, emotion_save — those must be "clip".
   - Add a "screen_capture" field with url and description:
       "screen_capture": {{
         "url": "https://claude.ai/code",
         "description": "Claude Code desktop app showing the Schedule tab with a daily 6am task configured"
       }}
   - Use the tool's exact public URL. Prefer the most visually interesting page (demo page > landing page > docs).
   - Public URLs (docs.anthropic.com, n8n.io, make.com, github.com, huggingface.co, platform.openai.com, gemini.google.com) work without login.
   - Still include broll_prompt as fallback (used if screenshot fails).
   - screen_capture examples:
       Claude Code: {{"url": "https://claude.ai/code", "description": "Claude Code desktop app showing an agent task running in terminal"}}
       n8n workflow: {{"url": "https://n8n.io", "description": "n8n automation workflow canvas with nodes connected"}}
       OpenAI Codex: {{"url": "https://platform.openai.com/codex", "description": "OpenAI Codex app showing a vibe coding project being built in seconds"}}
       Gemini: {{"url": "https://gemini.google.com", "description": "Google Gemini chat interface showing the Deepthink model selector"}}
       HuggingFace leaderboard: {{"url": "https://huggingface.co/spaces/lmarena-ai/chatbot-arena-leaderboard", "description": "ChatBot Arena leaderboard showing model rankings"}}
       GitHub repo: {{"url": "https://github.com/THUDM/GLM-4", "description": "GLM-4 GitHub repo showing star count and model description"}}
       Seed Dance: {{"url": "https://www.seedance.ai", "description": "Seed Dance 2.0 product page showing video generation capabilities"}}

   - broll_prompt: Kling-optimized cinematic scene (required even for diagram sections — used as fallback). CRITICAL RULE: the broll MUST VISUALLY SHOW what is being spoken about in that section. If section talks about Claude Code → show Claude Code CLI in terminal. If it talks about Make.com → show Make.com workflow canvas. If it talks about n8n → show n8n node connections. If it talks about money/revenue → show money/numbers. If it talks about AI agents → show robots/AI interfaces. Generic dark cinematics are REJECTED.

     Use this exact formula:
     "[SHOT TYPE], [WHAT IS BEING SPOKEN ABOUT — the actual tool/concept/object], [ENVIRONMENT], [LIGHTING], [CAMERA STYLE], [MOOD], absolutely no text overlays, no watermarks, no subtitles, no captions, no Chinese text, no Chinese characters, no Japanese text, no Japanese kanji, no Korean text, no Korean hangul, no Arabic script, no Hindi script, no non-Latin script, no foreign language text of any kind, English only if any text must appear, no writing on walls or objects or screens, pure cinematic footage only, 9:16 vertical"

     SHOT TYPES by section:
       hook:          "Extreme close-up"
       context:       "Medium establishing shot"
       trigger_1:     "Extreme close-up"
       body_1:        "Medium shot"
       trigger_2:     "Tight close-up"
       body_2:        "Medium close-up"
       trigger_3:     "Over-shoulder POV"
       bridge:        "Wide pulling to medium"
       grand_takeaway:"Clean minimal wide shot"
       emotion_save:  "Warm medium shot"

     LIGHTING + CAMERA STYLE to always append:
       hook/triggers: "dramatic side lighting, red accent, shallow depth of field, Sony A7IV, motion blur"
       body sections: "soft blue-white office light, shallow depth of field, Sony A7IV, smooth camera motion"
       bridge:        "transitional warm-to-dark split lighting, slow dolly"
       grand_takeaway:"soft diffused warm window light, minimal composition, Sony A7IV"
       emotion_save:  "golden hour warmth, soft bokeh background, Sony A7IV"

     EXAMPLES of topic-matched prompts:
       If spoken = "AI agents replace entire teams": "Tight close-up, humanoid robot arms doing office work at a desk with multiple monitors, dark modern office, dramatic red accent lighting, shallow depth of field Sony A7IV, tense cinematic, absolutely no text overlays, no watermarks, pure cinematic footage only, 9:16 vertical"
       If spoken = "Set it up in Claude Code in 20 minutes": "Over-shoulder POV, developer typing in VS Code terminal with Claude Code CLI responses appearing in real time, dark modern office setup, soft blue monitor glow, Sony A7IV, cinematic focus pull, absolutely no text overlays, no watermarks, pure cinematic footage only, 9:16 vertical"
       If spoken = "Set it up in Make.com in 20 minutes": "Over-shoulder POV, person dragging modules on Make.com workflow canvas on a widescreen monitor, clean minimal desk, soft blue-white office light, Sony A7IV, cinematic focus pull, absolutely no text overlays, no watermarks, pure cinematic footage only, 9:16 vertical"
       If spoken = "₹40 lakh revenue last month": "Medium close-up, laptop screen showing revenue dashboard with large numbers, Bangalore city skyline visible through window at night, warm ambient light, Sony A7IV shallow depth of field, absolutely no text overlays, no watermarks, pure cinematic footage only, 9:16 vertical"
       If spoken = "Most people use AI like a search engine": "Medium establishing shot, person typing into ChatGPT on laptop in coffee shop, blue screen glow on face, soft ambient light, Sony A7IV smooth motion, absolutely no text overlays, no watermarks, pure cinematic footage only, 9:16 vertical"
   - expression_cue: how avatar should look (e.g. "dead serious, eyes locked into camera")
   - vocal_direction: how avatar should sound (e.g. "slow and deliberate, one word at a time")
   - bgm_dip: true only for trigger_1, trigger_2, trigger_3
   - bgm_track: 1 for sections 0–35s, 2 for sections 35–120s
   - bgm_transition_here: true ONLY for grand_takeaway section
   - ⚠️ broll_type ALLOWLIST (HARD RULE — v2 polish port from the VSL pipeline):
     ONLY THREE VALUES ARE PERMITTED:  "clip" | "diagram" | "text_card"
     • "clip"      — for hook, all 3 triggers, grand_takeaway, emotion_save, AND any other section where a cinematic broll fits (default for most sections)
     • "diagram"   — for sections that explain a process/comparison/architecture/stats (uses the diagram_prompt field)
     • "text_card" — for sections that enumerate 3–5 short numbered/bulleted items (uses card_lines field)
     The legacy values "screen" and "terminal" are BANNED.  They produced low-quality
     screen-recording fallbacks and a watermark-style terminal mock that broke retention.
     Do NOT emit broll_type: "screen" under any circumstance.  Do NOT emit broll_type: "terminal".
     Do NOT emit screen_capture or terminal_command/terminal_tool/terminal_output fields.
     If a section talks about a tool/model/website, choose "clip" with a clear cinematic
     broll_prompt OR "diagram" with a diagram_prompt — never "screen" or "terminal".
   - flash_before: true for trigger_1, trigger_2, trigger_3 — creates a 2-frame black flash before the section (visual chapter break/reset)
   - broll_prompt: MUST include "absolutely no text overlays, no watermarks, no subtitles, no captions, no Chinese text, no Japanese text, no Korean text, no foreign language text, English only if any text appears, pure cinematic footage only" in EVERY section's broll_prompt

5. SET THE TONE FIELD in the top-level JSON:
   - "tone": one of "urgent" | "inspiring" | "neutral"
   - urgent:    script is about threats, fear, time pressure (e.g. "your job is at risk")
   - inspiring: script is about possibility, transformation, growth (e.g. "here's what's possible")
   - neutral:   factual, educational, informational

6. DSSCL SELF-SCORING — score yourself honestly on:
   - D (Double Watch): info density, curiosity loops, rewatch value
   - Share: quotable lines, identity signal, "be first to share this"
   - Save: concrete takeaway, tool name, FOMO, bookmark-worthy
   - C (Comment): debate trigger, relatable frustration, opinion bait
   - L (Like): general quality
   All scores 1–10. Be rigorous — pipeline will reject scores below 9.5 final.

VIRALITY CHECKLIST (verify before outputting):
[ ] Hook is from the hook bank — blanks filled, not generic
[ ] Format from format bank is clearly reflected in structure
[ ] Hook is a pattern interrupt — viewer did NOT expect this
[ ] Hook targets big TAM — broad enough to stop anyone in audience
[ ] Hook promise is PAID OFF visually in emotion_save broll (if hook shows a result, the broll must show that result)
[ ] Exactly 3 triggers at correct timestamps with bgm_dip: true
[ ] Grand Takeaway is EXACTLY ONE quotable sentence — not two, not a list
[ ] emotion_save names ONE specific tool OR gives ONE time estimate
[ ] emotion_save CTA includes a specific keyword action ("Comment X below and I'll DM you Y")
[ ] bgm_transition_here: true on grand_takeaway section ONLY
[ ] Trigger sections (1/2/3) have broll_type: "clip" (never "screen", "text_card", "diagram", or "terminal")
[ ] text_card sections have "card_lines" field with 3–5 short labels (2–4 words each)
[ ] Screen sections (broll_type: "screen") have screen_capture.url populated and are only on context/body_1/body_2
[ ] Terminal sections (broll_type: "terminal") have terminal_command, terminal_tool, and terminal_output (6–12 lines) populated
[ ] terminal_output lines use only allowed color values: default | dim | success | warning | error | info | accent | cyan | orange
[ ] card_source_name and card_source_subtitle set on all card sections
[ ] All on_screen_text entries: max 3–5 words each, NO overlapping text between sections
[ ] broll_prompt in every section uses Kling formula: [SHOT TYPE] + [SUBJECT+ACTION] + [ENVIRONMENT] + [LIGHTING] + [CAMERA STYLE] + [MOOD]
[ ] broll_prompt uses correct SHOT TYPE for the section type (extreme close-up for hooks/triggers, medium for body, wide for grand_takeaway)
[ ] broll_prompt lighting matches section mood (red dramatic for hooks/triggers, warm golden for emotion_save)
[ ] broll_prompt in EVERY section ends with "absolutely no text overlays, no watermarks, no subtitles, no captions, no Chinese text, no Japanese text, no Korean text, no foreign language text, English only if any text appears, pure cinematic footage only, 9:16 vertical"
[ ] layout field present in every section: "broll_full" for triggers/bridge/grand_takeaway, "split" for hook/context/body/emotion_save
[ ] expression_cue and vocal_direction present in every section

Return ONLY a valid JSON object matching this exact schema, no markdown, no explanation:
{OUTPUT_SCHEMA}"""


def build_feedback_prompt(
    score: float,
    iteration: int,
    lowest_two: list[str],
) -> str:
    dimensions_str = ", ".join(lowest_two)
    return f"""Script scored {score:.2f}/10. Pipeline requires >= 9.5. Iteration {iteration}/5.
Weakest signals: {dimensions_str}

Required fixes:
- Hook: pick a different hook from the 200-hook bank — avoid banned executions (amateurs/pros/elite operators/top 1%/while X does Y/diary entry opener)
- Grand Takeaway: must be exactly ONE quotable sentence — the kind people screenshot
- Save trigger: must name a specific tool OR give a concrete time estimate
- V (Voice): check for banned hook executions, verify proof story has city/role + tool + time + money + one workflow detail, confirm single CTA only, confirm emotion_save ends on aspirational visual line not a tutorial step
- Language: no jargon, max 12 words per sentence, every line sounds like natural speech not a blog post

Rewrite keeping same 10-section structure and JSON schema. Return only the JSON object."""


def build_video_feedback_prompt(
    video_dsscl_score: float,
    pipeline_iteration: int,
    script_feedback: str,
    weaknesses: list[str],
) -> str:
    """Prompt used when the rendered VIDEO scores below threshold — feeds back into Stage 1."""
    weaknesses_str = "\n".join(f"- {w}" for w in weaknesses)
    return f"""The rendered video scored {video_dsscl_score:.2f}/10 on DSSCL analysis (target ≥ 9.0). Pipeline iteration {pipeline_iteration}.

VIDEO ANALYSIS FEEDBACK:
{script_feedback}

WEAKNESSES OBSERVED IN THE VIDEO:
{weaknesses_str}

Rewrite the script from scratch on the same topic, addressing every weakness above.
Key requirements:
- Hook must be a stronger pattern interrupt with broader TAM
- Grand Takeaway must be a single quotable line people will screenshot
- Trigger 3 must include a real example with city, tool name, rupee/dollar amount, and time saved
- emotion_save section must clearly name ONE specific tool
- Keep the same 10-section structure and JSON schema

Return ONLY the JSON object, no markdown, no explanation."""


# ── DSSCL scoring ──────────────────────────────────────────────────────────────

def calculate_dsscl_score(script_json: dict) -> float:
    scores = script_json.get("dsscl_scores", {})
    D     = scores.get("D", 0)
    share = scores.get("Share", 0)
    save  = scores.get("Save", 0)
    C     = scores.get("C", 0)
    L     = scores.get("L", 0)
    V     = scores.get("V", 0)
    return (D * 0.28) + (share * 0.23) + (save * 0.23) + (C * 0.10) + (L * 0.08) + (V * 0.08)


def passes_individual_thresholds(script_json: dict) -> tuple[bool, list[str]]:
    """Returns (passes, list_of_failing_dimensions)."""
    scores = script_json.get("dsscl_scores", {})
    failures = []
    for dim, threshold in DSSCL_PASS_INDIVIDUAL.items():
        val = scores.get(dim, 0)
        if val < threshold:
            failures.append(f"{dim}={val:.1f} (needs {threshold})")
    return len(failures) == 0, failures


def get_lowest_two_dimensions(script_json: dict) -> list[str]:
    scores = script_json.get("dsscl_scores", {})
    dim_scores = {
        "D": scores.get("D", 0),
        "Share": scores.get("Share", 0),
        "Save": scores.get("Save", 0),
        "C": scores.get("C", 0),
        "L": scores.get("L", 0),
    }
    sorted_dims = sorted(dim_scores.items(), key=lambda x: x[1])
    return [f"{d}={v:.1f}" for d, v in sorted_dims[:2]]


# ── JSON extraction ────────────────────────────────────────────────────────────

def extract_json_from_response(text: str) -> dict:
    """Parse JSON from Claude response, handling markdown code blocks."""
    text = text.strip()

    # Strip ```json ... ``` or ``` ... ``` wrappers
    fenced = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if fenced:
        text = fenced.group(1).strip()

    # Find the outermost JSON object
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in response.")

    # Walk to find matching closing brace
    depth = 0
    end = -1
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break

    if end == -1:
        raise ValueError("Unbalanced JSON object in response.")

    json_str = text[start : end + 1]
    return json.loads(json_str)


# ── Validation ─────────────────────────────────────────────────────────────────

def _sanitize_banned_broll_types(script_json: dict) -> int:
    """v2 polish port — Stage 1's prompt now bans `screen` and `terminal`, but if a model
    still emits them, defensively rewrite to `diagram` so downstream stages don't render
    the low-quality fallbacks. Returns the count of sanitized sections (for logging)."""
    sanitized = 0
    for section in script_json.get("sections", []):
        bt = section.get("broll_type")
        if bt in ("screen", "terminal"):
            logger.warning("[%s] sanitizing banned broll_type=%r → 'diagram'", section.get("id"), bt)
            section["broll_type"] = "diagram"
            # Strip type-specific fields that no longer apply.
            section.pop("screen_capture", None)
            for k in ("terminal_tool", "terminal_command", "terminal_output"):
                section.pop(k, None)
            # If no diagram_prompt exists, derive one from on_screen_text / spoken.
            if not section.get("diagram_prompt"):
                lines = section.get("on_screen_text", []) or []
                if lines:
                    section["diagram_prompt"] = (
                        "Clean dark diagram with " + str(len(lines)) +
                        " labeled boxes: " + ", ".join(lines[:5])
                    )
                else:
                    section["diagram_prompt"] = (
                        "Clean dark concept diagram illustrating: " +
                        (section.get("spoken", "")[:120] or section.get("label", ""))
                    )
            sanitized += 1
    return sanitized


def validate_script_json(script_json: dict) -> list[str]:
    """Return list of validation errors (empty = valid)."""
    # Sanitize before validation so banned types don't trip downstream checks.
    n = _sanitize_banned_broll_types(script_json)
    if n:
        logger.info("Sanitizer: rewrote %d banned broll_type section(s) to 'diagram'.", n)
    errors = []

    # Required top-level keys
    required_keys = [
        "title", "hook_used", "format_used", "total_duration_sec",
        "dsscl_scores", "bgm_transition_sec", "bgm_dip_timestamps",
        "full_spoken_script", "grand_takeaway_line", "tone", "sections",
    ]
    for key in required_keys:
        if key not in script_json:
            errors.append(f"Missing top-level key: {key}")

    # Sections
    sections = script_json.get("sections", [])
    section_ids = [s.get("id") for s in sections]
    for required_id in REQUIRED_SECTION_IDS:
        if required_id not in section_ids:
            errors.append(f"Missing section: {required_id}")

    # Per-section field checks
    required_section_keys = [
        "id", "label", "start_sec", "end_sec", "spoken",
        "on_screen_text", "broll_prompt", "expression_cue",
        "vocal_direction", "bgm_dip", "bgm_track", "bgm_transition_here",
    ]
    for section in sections:
        sid = section.get("id", "unknown")
        for key in required_section_keys:
            if key not in section:
                errors.append(f"Section '{sid}' missing field: {key}")

    # terminal section field checks
    valid_colors = {"default", "dim", "success", "warning", "error", "info", "accent", "cyan", "orange"}
    for section in sections:
        sid = section.get("id", "unknown")
        if section.get("broll_type") == "terminal":
            for f in ("terminal_tool", "terminal_command", "terminal_output"):
                if not section.get(f):
                    errors.append(f"Section '{sid}' is broll_type=terminal but missing field: {f}")
            for line in section.get("terminal_output", []):
                if isinstance(line, dict):
                    c = line.get("color", "default")
                    if c not in valid_colors:
                        errors.append(f"Section '{sid}' terminal_output has invalid color '{c}'")

    # bgm_dip checks
    trigger_ids = {"trigger_1", "trigger_2", "trigger_3"}
    for section in sections:
        sid = section.get("id")
        if sid in trigger_ids and not section.get("bgm_dip"):
            errors.append(f"Section '{sid}' must have bgm_dip: true")

    # bgm_transition_here check
    gt_sections = [s for s in sections if s.get("id") == "grand_takeaway"]
    if gt_sections and not gt_sections[0].get("bgm_transition_here"):
        errors.append("grand_takeaway must have bgm_transition_here: true")

    return errors


# ── API call with retry ────────────────────────────────────────────────────────

def call_claude_with_retry(
    client: anthropic.Anthropic,
    messages: list[dict],
    max_retries: int = 3,
) -> str:
    """Call Claude API with exponential backoff. Returns response text."""
    delay = 1
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            log.info("Claude API call — attempt %d/%d.", attempt, max_retries)
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=messages,
            )
            return response.content[0].text
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                log.warning("Claude API 5xx error (attempt %d): %s", attempt, exc)
                last_error = exc
                if attempt < max_retries:
                    log.info("Retrying in %ds...", delay)
                    time.sleep(delay)
                    delay *= 2
            else:
                raise  # 4xx errors are not retried
        except anthropic.APIConnectionError as exc:
            log.warning("Claude API connection error (attempt %d): %s", attempt, exc)
            last_error = exc
            if attempt < max_retries:
                log.info("Retrying in %ds...", delay)
                time.sleep(delay)
                delay *= 2

    raise RuntimeError(f"Claude API failed after {max_retries} attempts: {last_error}")


# ── DSSCL loop ─────────────────────────────────────────────────────────────────

def run_dsscl_loop(
    client: anthropic.Anthropic,
    initial_prompt: str,
) -> dict:
    """Run generation + DSSCL loop up to MAX_ITERATIONS. Returns best script JSON."""
    messages = [{"role": "user", "content": initial_prompt}]

    best_script = None
    best_score = 0.0

    for iteration in range(1, MAX_ITERATIONS + 1):
        log.info("DSSCL iteration %d/%d — calling Claude...", iteration, MAX_ITERATIONS)

        raw_text = call_claude_with_retry(client, messages)

        try:
            script_json = extract_json_from_response(raw_text)
        except (ValueError, json.JSONDecodeError) as exc:
            log.error("Failed to parse JSON from Claude response (iteration %d): %s", iteration, exc)
            log.debug("Raw response: %s", raw_text[:500])
            # Inject error into conversation and retry
            messages.append({"role": "assistant", "content": raw_text})
            messages.append({
                "role": "user",
                "content": "Your response was not valid JSON. Return ONLY the raw JSON object, no markdown, no explanation.",
            })
            continue

        # Validate structure
        validation_errors = validate_script_json(script_json)
        if validation_errors:
            log.warning("Script validation errors (iteration %d): %s", iteration, validation_errors)

        # Score
        final_score = calculate_dsscl_score(script_json)
        script_json["dsscl_scores"]["final"] = round(final_score, 2)
        script_json["dsscl_iteration"] = iteration

        passes_thresh, individual_failures = passes_individual_thresholds(script_json)

        log.info(
            "Iteration %d — DSSCL final=%.2f | D=%.1f Share=%.1f Save=%.1f C=%.1f L=%.1f",
            iteration,
            final_score,
            script_json["dsscl_scores"].get("D", 0),
            script_json["dsscl_scores"].get("Share", 0),
            script_json["dsscl_scores"].get("Save", 0),
            script_json["dsscl_scores"].get("C", 0),
            script_json["dsscl_scores"].get("L", 0),
        )

        if final_score > best_score:
            best_score = final_score
            best_script = script_json

        if final_score >= DSSCL_PASS_THRESHOLD and passes_thresh:
            log.info("DSSCL threshold met (%.2f >= %.1f). Accepting script.", final_score, DSSCL_PASS_THRESHOLD)
            return best_script

        if individual_failures:
            log.info("Individual threshold failures: %s", individual_failures)

        if iteration < MAX_ITERATIONS:
            lowest_two = get_lowest_two_dimensions(script_json)
            feedback = build_feedback_prompt(final_score, iteration + 1, lowest_two)
            log.info("Score %.2f < %.1f — requesting improvement (lowest: %s).",
                     final_score, DSSCL_PASS_THRESHOLD, lowest_two)
            # Continue conversation with assistant response + new feedback
            messages.append({"role": "assistant", "content": raw_text})
            messages.append({"role": "user", "content": feedback})
        else:
            log.warning(
                "DSSCL score %.2f after %d iterations — using best result (%.2f).",
                final_score,
                MAX_ITERATIONS,
                best_score,
            )

    return best_script


# ── Main stage function ────────────────────────────────────────────────────────

def run_stage1(topic: str = None, transcript: str = None, video_feedback: dict = None, research_context: dict = None) -> dict:
    """
    Generate a viral 60-second reel script using the GOAT Framework.

    Args:
        topic: Topic string (used if transcript not provided)
        transcript: Raw transcript text
        video_feedback: Optional dict from Stage 6 video analysis with keys:
                        dsscl_scores, script_feedback, weaknesses, pipeline_iteration

    Returns:
        {"success": bool, "output_path": str, "duration_sec": float, "error": str|None}
    """
    start_time = time.time()

    if not topic and not transcript:
        return {
            "success": False,
            "output_path": str(OUTPUT_PATH),
            "duration_sec": 0.0,
            "error": "Either topic or transcript must be provided.",
        }

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "success": False,
            "output_path": str(OUTPUT_PATH),
            "duration_sec": 0.0,
            "error": "ANTHROPIC_API_KEY not set in environment.",
        }

    try:
        if video_feedback:
            log.info(
                "Stage 1 re-run with video feedback (pipeline iteration %d) — video DSSCL=%.2f",
                video_feedback.get("pipeline_iteration", "?"),
                video_feedback.get("dsscl_scores", {}).get("final", 0),
            )
        else:
            log.info("Stage 1 starting — topic=%r, transcript=%s",
                     topic, "provided" if transcript else "none")

        # Load reference files
        hooks_content, formats_content, harsha_overlay = load_reference_files()
        accumulated_rules = load_accumulated_rules()

        # Build initial prompt — if video_feedback provided, prepend it as context
        initial_prompt = build_initial_prompt(topic, transcript, hooks_content, formats_content, accumulated_rules, research_context, harsha_overlay=harsha_overlay)
        if video_feedback:
            vfb_prefix = build_video_feedback_prompt(
                video_dsscl_score=video_feedback["dsscl_scores"]["final"],
                pipeline_iteration=video_feedback["pipeline_iteration"],
                script_feedback=video_feedback["script_feedback"],
                weaknesses=video_feedback.get("weaknesses", []),
            )
            initial_prompt = vfb_prefix + "\n\n---\n\nFULL SCRIPT FRAMEWORK:\n" + initial_prompt

        log.info("Prompt built (%d chars). Starting DSSCL loop...", len(initial_prompt))

        # Create Anthropic client
        client = anthropic.Anthropic(api_key=api_key)

        # Run DSSCL loop
        script_json = run_dsscl_loop(client, initial_prompt)

        if script_json is None:
            return {
                "success": False,
                "output_path": str(OUTPUT_PATH),
                "duration_sec": time.time() - start_time,
                "error": "DSSCL loop produced no valid script.",
            }

        # Final validation
        validation_errors = validate_script_json(script_json)
        if validation_errors:
            log.warning("Final script has validation issues: %s", validation_errors)

        # Write output
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(script_json, indent=2, ensure_ascii=False), encoding="utf-8")

        duration = time.time() - start_time
        log.info(
            "Stage 1 complete — saved to %s (DSSCL final=%.2f, iteration=%d, %.1fs)",
            OUTPUT_PATH,
            script_json.get("dsscl_scores", {}).get("final", 0),
            script_json.get("dsscl_iteration", 0),
            duration,
        )

        return {
            "success": True,
            "output_path": str(OUTPUT_PATH),
            "duration_sec": round(duration, 2),
            "error": None,
        }

    except Exception as exc:
        duration = time.time() - start_time
        log.exception("Stage 1 failed: %s", exc)
        return {
            "success": False,
            "output_path": str(OUTPUT_PATH),
            "duration_sec": round(duration, 2),
            "error": str(exc),
        }


# ── CLI entrypoint ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Stage 1 — Generate a viral 60-second reel script using the GOAT Framework."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--topic", type=str, help="Topic for the reel (e.g. 'AI agents explained in 3 steps')")
    group.add_argument("--transcript", type=str, help="Path to a transcript .txt file")
    args = parser.parse_args()

    transcript_text = None
    if args.transcript:
        transcript_path = Path(args.transcript)
        if not transcript_path.exists():
            print(f"Error: transcript file not found: {transcript_path}")
            raise SystemExit(1)
        transcript_text = transcript_path.read_text(encoding="utf-8")
        print(f"Loaded transcript from {transcript_path} ({len(transcript_text)} chars).")

    result = run_stage1(topic=args.topic, transcript=transcript_text)

    print("\n" + "=" * 60)
    print("STAGE 1 RESULT")
    print("=" * 60)
    print(f"Success:     {result['success']}")
    print(f"Output:      {result['output_path']}")
    print(f"Duration:    {result['duration_sec']}s")
    if result["error"]:
        print(f"Error:       {result['error']}")

    if result["success"]:
        script = json.loads(Path(result["output_path"]).read_text(encoding="utf-8"))
        print(f"\nTitle:       {script.get('title')}")
        print(f"Hook used:   {script.get('hook_used')}")
        print(f"Format used: {script.get('format_used')}")
        scores = script.get("dsscl_scores", {})
        print(f"DSSCL:       D={scores.get('D')} Share={scores.get('Share')} "
              f"Save={scores.get('Save')} C={scores.get('C')} L={scores.get('L')} "
              f"→ Final={scores.get('final')}")
        print(f"Iterations:  {script.get('dsscl_iteration')}")
        print(f"Tool:        {script.get('tool_mentioned')}")
        print(f"\nGrand Takeaway:\n  {script.get('grand_takeaway_line')}")
        print(f"\nFull script preview:\n  {script.get('full_spoken_script', '')[:300]}...")
        print(f"\nFull JSON written to: {result['output_path']}")
