/**
 * screen_timeline.mjs — Sync cursor_steps to Whisper word timestamps.
 *
 * Reads:
 *   - assets/script_data.json        → cursor_steps[] with spoken_cue per step
 *   - assets/captions/avatar_video.json → Whisper word timestamps
 *
 * For each screen section, matches each step's spoken_cue to the closest
 * Whisper word timestamp, computes frame offset, writes:
 *   assets/screen_timelines/{section_id}.json
 *
 * Output schema:
 * {
 *   "section_id": "body_1",
 *   "section_start_sec": 12,
 *   "actions": [
 *     { "frame": 360, "type": "CURSOR_MOVE", "to": [0.15, 0.22] },
 *     { "frame": 420, "type": "HIGHLIGHT", "box": [0.1, 0.18, 0.3, 0.08] },
 *     { "frame": 445, "type": "CLICK", "at": [0.48, 0.55] },
 *     { "frame": 502, "type": "TYPE", "text": "Classify this support ticket", "at": [0.48, 0.72] },
 *     { "frame": 560, "type": "ZOOM", "region": [0.35, 0.45, 0.3, 0.2] }
 *   ]
 * }
 *
 * Frames are global (from video start, 30fps). Remotion reads these to drive
 * ScreenDemoLayer animations in sync with spoken words.
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dir  = dirname(fileURLToPath(import.meta.url));
const ROOT   = resolve(__dir, '..');
const FPS    = 30;
const SPEED  = 1.25; // Remotion playbackRate — Whisper timestamps are in real-time,
                      // so frame = timestamp_sec / SPEED * FPS

const SCRIPT_DATA    = resolve(ROOT, 'assets/script_data.json');
const CAPTIONS_JSON  = resolve(ROOT, 'assets/captions/avatar_video.json');
const TIMELINES_DIR  = resolve(ROOT, 'assets/screen_timelines');

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Flatten Whisper segments → [{word, start, end}] */
function extractWords(whisperData) {
  const words = [];
  for (const seg of whisperData.segments || []) {
    for (const w of seg.words || []) {
      if (w.word && w.start !== undefined) {
        words.push({ word: w.word.toLowerCase().trim(), start: w.start, end: w.end });
      }
    }
  }
  return words;
}

/**
 * Find the best matching timestamp for a spoken_cue string.
 * Tries exact substring match across consecutive words, then falls back to
 * individual word match, then falls back to the section start time.
 */
function findTimestamp(cue, words, fallbackSec) {
  if (!cue || words.length === 0) return fallbackSec;

  const cueTokens = cue.toLowerCase().split(/\s+/).filter(Boolean);
  if (cueTokens.length === 0) return fallbackSec;

  // Try to find the sequence of words matching the cue
  for (let i = 0; i <= words.length - cueTokens.length; i++) {
    const match = cueTokens.every((token, j) => {
      const w = words[i + j].word.replace(/[^a-z0-9]/g, '');
      const t = token.replace(/[^a-z0-9]/g, '');
      return w.includes(t) || t.includes(w);
    });
    if (match) return words[i].start;
  }

  // Try single-word match for first token
  const firstToken = cueTokens[0].replace(/[^a-z0-9]/g, '');
  const found = words.find(w => {
    const wc = w.word.replace(/[^a-z0-9]/g, '');
    return wc.includes(firstToken) || firstToken.includes(wc);
  });
  if (found) return found.start;

  return fallbackSec;
}

/** Convert real-time seconds to Remotion global frame (accounting for playbackRate) */
function secToFrame(sec) {
  return Math.round((sec / SPEED) * FPS);
}

// ── Main ──────────────────────────────────────────────────────────────────────

if (!existsSync(SCRIPT_DATA)) {
  console.error(`script_data.json not found`);
  process.exit(1);
}

if (!existsSync(CAPTIONS_JSON)) {
  console.log('Whisper captions not found — screen_timeline skipped (run after Whisper).');
  process.exit(0);
}

mkdirSync(TIMELINES_DIR, { recursive: true });

const scriptData  = JSON.parse(readFileSync(SCRIPT_DATA, 'utf8'));
const whisperData = JSON.parse(readFileSync(CAPTIONS_JSON, 'utf8'));
const allWords    = extractWords(whisperData);

const screenSections = scriptData.sections.filter(
  s => s.broll_type === 'screen' && s.screen_capture?.cursor_steps?.length > 0
);

if (screenSections.length === 0) {
  console.log('No screen sections with cursor_steps — skipping timeline build.');
  process.exit(0);
}

console.log(`\nBuilding screen timelines for ${screenSections.length} section(s)...\n`);

let built = 0;
for (const section of screenSections) {
  const outPath = resolve(TIMELINES_DIR, `${section.id}.json`);
  const steps   = section.screen_capture.cursor_steps;

  // Filter words in this section's time window (with ±3s buffer for alignment drift)
  const bufStart = Math.max(0, section.start_sec - 3);
  const bufEnd   = section.end_sec + 3;
  const sectionWords = allWords.filter(w => w.start >= bufStart && w.start <= bufEnd);

  const actions = [];
  let prevFrame = secToFrame(section.start_sec);

  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    const cue  = step.spoken_cue || step.label || '';

    // Find timestamp for this step — search section words first, then global
    let timestamp = findTimestamp(cue, sectionWords, null);
    if (timestamp === null) {
      timestamp = findTimestamp(cue, allWords, null);
    }
    if (timestamp === null) {
      // Distribute evenly across section if no match
      const fraction = (i + 1) / (steps.length + 1);
      timestamp = section.start_sec + fraction * (section.end_sec - section.start_sec);
    }

    const frame = Math.max(prevFrame + 15, secToFrame(timestamp)); // min 15 frames apart
    prevFrame = frame;

    // CURSOR_MOVE is always first action for each step
    if (step.xy || step.selector) {
      actions.push({
        frame,
        type: 'CURSOR_MOVE',
        to: step.xy || null,
        selector: step.selector || null,
        screenshot_index: i + 1,  // which clean screenshot to show
      });
    }

    // HIGHLIGHT action
    if (step.highlight_box) {
      actions.push({
        frame: frame + 8,
        type: 'HIGHLIGHT',
        mode: 'border',
        box: step.highlight_box,
      });
    }

    // CLICK action
    if (step.click) {
      actions.push({
        frame: frame + 12,
        type: 'CLICK',
        at: step.xy || null,
      });
    }

    // TYPE action
    if (step.type) {
      actions.push({
        frame: frame + 18,
        type: 'TYPE',
        text: step.type,
        at: step.xy || null,
      });
    }

    // ZOOM action
    if (step.zoom_to) {
      actions.push({
        frame: frame + 5,
        type: 'ZOOM',
        region: step.zoom_to,
      });
    }
  }

  const timeline = {
    section_id: section.id,
    section_start_sec: section.start_sec,
    section_end_sec:   section.end_sec,
    screenshot_count: steps.length + 1,  // +1 for initial state
    actions,
  };

  writeFileSync(outPath, JSON.stringify(timeline, null, 2), 'utf8');
  console.log(`  [${section.id}] ✓ ${actions.length} actions → ${outPath.replace(ROOT + '/', '')}`);
  built++;
}

console.log(`\nDone: ${built}/${screenSections.length} timelines built.`);
