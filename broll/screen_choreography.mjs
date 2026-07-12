/**
 * screen_choreography.mjs — Auto-generate cursor_steps for screen sections via Claude API.
 *
 * Reads assets/script_data.json, finds sections with broll_type="screen",
 * calls Claude API to generate cursor_steps[] for each based on:
 *   - section.spoken (what's being said)
 *   - section.screen_capture.url (which tool)
 *   - section.screen_capture.description (what the scene should show)
 *
 * Writes cursor_steps back into assets/script_data.json before screen_broll.mjs runs.
 *
 * Each cursor_step schema:
 *   {
 *     label: string,           // logged description
 *     spoken_cue: string,      // keyword from spoken text → used by timeline builder for sync
 *     xy: [x_frac, y_frac],    // cursor position as fraction of viewport (0–1)
 *     selector: string,        // CSS selector (overrides xy if provided)
 *     highlight_box: [x_frac, y_frac, w_frac, h_frac],  // highlight rect (optional)
 *     highlight: boolean,      // use selector for highlight (optional)
 *     click: boolean,          // animate click (optional)
 *     type: string,            // text to type into field (optional) — shown in screenshot + TypingSimulator
 *     zoom_to: [x_frac, y_frac, w_frac, h_frac],  // region for Remotion ZoomPan (optional)
 *     wait_ms: number,         // how long this frame shows (default 1500ms)
 *   }
 */

import Anthropic from '@anthropic-ai/sdk';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { config } from 'dotenv';

const __dir = dirname(fileURLToPath(import.meta.url));
const ROOT   = resolve(__dir, '..');

config({ path: resolve(ROOT, '.env') });

const SCRIPT_DATA = resolve(ROOT, 'assets/script_data.json');

// ── Claude prompt ─────────────────────────────────────────────────────────────

function buildPrompt(section) {
  const sectionDuration = section.end_sec - section.start_sec;
  return `You are generating a cursor choreography for a screen recording tutorial segment.

SECTION: "${section.label}" (${sectionDuration}s long)
TOOL URL: ${section.screen_capture.url}
WHAT TO SHOW: ${section.screen_capture.description}
SPOKEN TEXT: "${section.spoken}"

Generate 3–6 cursor_steps that show a realistic interaction with this tool UI, matching what's being spoken.

CRITICAL RULES:
- Every step must click or highlight the EXACT ELEMENT the spoken text is referring to.
  If spoken = "the benchmark score is 50.4" → cursor moves to that score bar/number and highlights it.
  If spoken = "Gemini Deepthink crushed Arc AGI 2" → cursor hovers over Gemini's row in the leaderboard and clicks it.
  If spoken = "this is the new feature" → cursor highlights that feature's UI element.
  NEVER have the cursor floating around randomly — every move must be driven by the spoken text.
- highlight_box is MANDATORY on every step — always highlight the element being spoken about.
- click: true is REQUIRED on the primary element of focus in each step.
- zoom_to is REQUIRED on any step where a stat, number, score, or small UI detail is being mentioned — zoom in so the viewer can read it clearly.
- spoken_cue: exact 1–3 keywords from the spoken text that this cursor action illustrates.
- Use xy coordinates as fractions of a 1440×900 viewport (0.0–1.0).
- wait_ms: 1200–2000ms per step (longer for complex UI, shorter for simple cursor moves).
- Total wait_ms across all steps should roughly match the section duration in ms (${sectionDuration * 1000}ms).
- Keep it simple — 3–4 steps is better than 8 steps.

Common layout assumptions for popular tools:
- Make.com: left sidebar ~0.05–0.15x, canvas center ~0.4–0.7x, node buttons ~0.3–0.6x
- n8n: left panel ~0.05–0.18x, workflow canvas ~0.2–0.8x, add button top-right ~0.85–0.95x
- Claude.ai: left sidebar ~0.05–0.2x, main chat ~0.25–0.75x, input box ~0.5, 0.85–0.95y
- GitHub: file tree ~0.05–0.2x, code area ~0.2–0.85x, header ~0.0–0.08y
- HuggingFace leaderboard: table rows ~0.15–0.85x, score columns ~0.5–0.85x, search ~0.3, 0.15y
- OpenAI/Anthropic product pages: hero section ~0.3–0.7x/0.1–0.4y, feature cards ~0.15–0.85x/0.4–0.75y

Return ONLY a valid JSON array of cursor_steps objects. No explanation, no markdown fences.

Example output:
[
  {
    "label": "Hover workflow canvas",
    "spoken_cue": "open make.com",
    "xy": [0.45, 0.45],
    "wait_ms": 1500
  },
  {
    "label": "Click Add Module button",
    "spoken_cue": "click trigger",
    "xy": [0.38, 0.42],
    "click": true,
    "highlight_box": [0.32, 0.38, 0.14, 0.08],
    "wait_ms": 1800
  },
  {
    "label": "Select Claude AI node",
    "spoken_cue": "Claude AI",
    "xy": [0.52, 0.55],
    "click": true,
    "zoom_to": [0.38, 0.45, 0.28, 0.18],
    "wait_ms": 1600
  },
  {
    "label": "Type prompt in field",
    "spoken_cue": "write a prompt",
    "xy": [0.50, 0.72],
    "type": "Classify this support ticket as urgent, normal, or low priority",
    "highlight_box": [0.2, 0.68, 0.6, 0.08],
    "wait_ms": 2000
  }
]`;
}

// ── Main ──────────────────────────────────────────────────────────────────────

if (!existsSync(SCRIPT_DATA)) {
  console.error(`script_data.json not found at ${SCRIPT_DATA}`);
  process.exit(1);
}

const apiKey = process.env.ANTHROPIC_API_KEY;
if (!apiKey) {
  console.error('ANTHROPIC_API_KEY not set');
  process.exit(1);
}

const client = new Anthropic({ apiKey });

const scriptData = JSON.parse(readFileSync(SCRIPT_DATA, 'utf8'));
const screenSections = scriptData.sections.filter(
  s => s.broll_type === 'screen' && s.screen_capture?.url
);

if (screenSections.length === 0) {
  console.log('No screen sections found — skipping choreography generation.');
  process.exit(0);
}

// Filter to sections that don't already have cursor_steps
const toGenerate = screenSections.filter(
  s => !s.screen_capture.cursor_steps || s.screen_capture.cursor_steps.length === 0
);

if (toGenerate.length === 0) {
  console.log('All screen sections already have cursor_steps — skipping.');
  process.exit(0);
}

console.log(`\nGenerating choreography for ${toGenerate.length} screen section(s)...\n`);

let updated = 0;
for (const section of toGenerate) {
  console.log(`  [${section.id}] Generating cursor_steps for: ${section.screen_capture.description?.slice(0, 60)}...`);

  try {
    const response = await client.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 1200,
      messages: [{ role: 'user', content: buildPrompt(section) }],
    });

    const raw = response.content[0].text.trim();

    // Strip markdown fences if present
    const clean = raw.replace(/^```(?:json)?\s*/m, '').replace(/\s*```$/m, '').trim();

    // Parse JSON array
    const steps = JSON.parse(clean);

    if (!Array.isArray(steps)) throw new Error('Response is not an array');

    // Write steps back into script_data sections
    const idx = scriptData.sections.findIndex(s => s.id === section.id);
    if (idx !== -1) {
      scriptData.sections[idx].screen_capture.cursor_steps = steps;
    }

    console.log(`  [${section.id}] ✓ ${steps.length} steps generated`);
    updated++;
  } catch (err) {
    console.error(`  [${section.id}] ✗ Failed: ${err.message}`);
    // Leave cursor_steps empty — screen_broll.mjs falls back to static screenshot
  }
}

// Write updated script_data.json
writeFileSync(SCRIPT_DATA, JSON.stringify(scriptData, null, 2), 'utf8');
console.log(`\nDone: ${updated}/${toGenerate.length} sections choreographed. script_data.json updated.`);
