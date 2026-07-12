/**
 * run_terminal_demo.mjs — Render terminal broll sections as animated screenshots.
 *
 * For each section with broll_type="terminal":
 *   1. Playwright opens terminal_renderer.html (no network, pure local HTML)
 *   2. Types the command character-by-character (60-80ms per key, humanised)
 *   3. Streams output lines one by one (line delays from terminal_output[].delay_ms)
 *   4. Takes 5 clean screenshots at key moments:
 *        f0 = empty prompt (baseline)
 *        f1 = command fully typed, before Enter
 *        f2 = first output line(s) visible
 *        f3 = mid-output (50% of lines)
 *        f4 = all output complete
 *   5. Screenshots → assets/screen_screenshots/{section_id}_fN.png
 *   6. Builds a fallback Ken Burns .mp4 → assets/broll/{section_id}.mp4
 *      (used if ScreenDemoLayer is unavailable)
 *
 * terminal_command field from script_data.json:
 *   string — e.g. 'claude "design a landing page for my SaaS"'
 *
 * terminal_output field from script_data.json:
 *   array of { line: string, delay_ms: number, color: string }
 *   color = one of: default | dim | success | warning | error | info | accent | cyan | orange
 *
 * terminal_tool field: display name for titlebar, e.g. "Claude Code"
 */

import { chromium } from 'playwright';
import { execFileSync, execSync } from 'child_process';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { resolve, dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dir = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dir, '..');

const SCRIPT_DATA     = resolve(ROOT, 'assets/script_data.json');
const SCREENSHOTS_DIR = resolve(ROOT, 'assets/screen_screenshots');
const BROLL_DIR       = resolve(ROOT, 'assets/broll');

// Terminal page dimensions must match box in Remotion
const CLIP_WIDTH  = 880;
const CLIP_HEIGHT = 1100;

// Typing speed: uniform char delay, plus occasional pause at word boundaries
const CHAR_DELAY_MS    = 65;   // base per character
const WORD_PAUSE_EXTRA = 35;   // added after spaces and punctuation

// ─── Helpers ─────────────────────────────────────────────────────────────────

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function humanDelay(ch) {
  let d = CHAR_DELAY_MS + Math.floor(Math.random() * 25);
  if (' "\'()[]{}:'.includes(ch)) d += WORD_PAUSE_EXTRA;
  return d;
}

async function takeScreenshot(page, sectionId, frameIdx) {
  const out = resolve(SCREENSHOTS_DIR, `${sectionId}_f${frameIdx}.png`);
  await page.screenshot({ path: out, fullPage: false });
  console.log(`  📸 ${sectionId}_f${frameIdx}.png`);
  return out;
}

async function buildFallbackMp4(sectionId, screenshots) {
  // Ken Burns zoom: f0→f4, 2s each, dissolve 0.3s between
  // Output: assets/broll/{sectionId}.mp4 (H264 baseline for Remotion)
  const outMp4 = resolve(BROLL_DIR, `${sectionId}.mp4`);

  // Build concat with xfade filters
  const frames = screenshots.filter(existsSync);
  if (frames.length < 2) {
    console.log(`  ⚠ Not enough frames for ${sectionId} — skipping fallback mp4`);
    return;
  }

  // Use ffmpeg concat + xfade to build a smooth 8s clip
  const dur = 8 / frames.length;         // equal time per frame
  const dissolve = 0.3;
  const tmpFrames = frames.map((f, i) => `file '${f}'`).join('\n');
  const concatList = resolve(ROOT, `assets/broll/.concat_${sectionId}.txt`);
  writeFileSync(concatList, frames.map(f => `file '${f}'\nduration ${dur}`).join('\n'));

  try {
    execFileSync('ffmpeg', [
      '-y',
      '-f', 'concat', '-safe', '0', '-i', concatList,
      '-vf',
      [
        // Scale to clip size
        `scale=${CLIP_WIDTH}:${CLIP_HEIGHT}:force_original_aspect_ratio=decrease`,
        `pad=${CLIP_WIDTH}:${CLIP_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=0d1117`,
        // Gentle zoom across entire clip
        `zoompan=z='if(lte(zoom,1.0),1.04,zoom)':d=${Math.ceil(dur*30)}:s=${CLIP_WIDTH}x${CLIP_HEIGHT}`,
      ].join(','),
      '-c:v', 'libx264',
      '-profile:v', 'baseline',
      '-level', '3.1',
      '-pix_fmt', 'yuv420p',
      '-movflags', '+faststart',
      '-r', '30',
      '-t', '8',
      '-an',
      outMp4,
    ], { stdio: 'pipe' });
    console.log(`  🎬 Fallback mp4: ${sectionId}.mp4`);
  } catch (e) {
    // Simpler fallback — just use the last screenshot
    try {
      execFileSync('ffmpeg', [
        '-y',
        '-loop', '1', '-i', frames[frames.length - 1],
        '-vf', `scale=${CLIP_WIDTH}:${CLIP_HEIGHT}:force_original_aspect_ratio=decrease,pad=${CLIP_WIDTH}:${CLIP_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=0d1117`,
        '-c:v', 'libx264', '-profile:v', 'baseline', '-level', '3.1',
        '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
        '-r', '30', '-t', '8', '-an', outMp4,
      ], { stdio: 'pipe' });
      console.log(`  🎬 Simple fallback mp4: ${sectionId}.mp4`);
    } catch (e2) {
      console.error(`  ❌ Could not build fallback mp4 for ${sectionId}: ${e2.message}`);
    }
  }
}

// ─── Core: render one terminal section ───────────────────────────────────────

async function renderTerminalSection(page, section) {
  const sid  = section.id;
  const cmd  = section.terminal_command  || '$ echo "hello world"';
  const lines = section.terminal_output  || [];
  const tool = section.terminal_tool     || 'Terminal';

  console.log(`\n── [${sid}] ${tool} ─────────────────────────`);
  console.log(`  Command: ${cmd}`);
  console.log(`  Output:  ${lines.length} lines`);

  const htmlPath = `file://${resolve(__dir, 'terminal_renderer.html')}`;
  await page.goto(htmlPath, { waitUntil: 'domcontentloaded' });
  await page.setViewportSize({ width: CLIP_WIDTH, height: CLIP_HEIGHT });
  await sleep(200);

  // Set titlebar
  await page.evaluate((t) => window.termAPI.setTitle(t), tool);

  // f0 — empty prompt
  const screenshots = [];
  screenshots.push(await takeScreenshot(page, sid, 0));
  await sleep(120);

  // Type command
  for (const ch of cmd) {
    await page.evaluate((c) => window.termAPI.typeChar(c), ch);
    await sleep(humanDelay(ch));
  }

  // f1 — command typed, cursor visible
  screenshots.push(await takeScreenshot(page, sid, 1));
  await sleep(300);

  // Hide cursor (simulate pressing Enter → command running)
  await page.evaluate(() => window.termAPI.hideCursor());
  await sleep(150);

  // Stream output lines
  for (let i = 0; i < lines.length; i++) {
    const lineSpec = lines[i];
    const text     = typeof lineSpec === 'string' ? lineSpec : lineSpec.line;
    const delay    = typeof lineSpec === 'object'  ? (lineSpec.delay_ms ?? 120) : 120;
    const color    = typeof lineSpec === 'object'  ? (lineSpec.color ?? 'default') : 'default';

    await sleep(Math.min(delay, 800)); // cap individual delay so screenshots don't take forever
    await page.evaluate(
      ([t, c]) => window.termAPI.appendLine(t, 'c-' + c),
      [text, color]
    );

    // f2 — first line
    if (i === 0) {
      await sleep(80);
      screenshots.push(await takeScreenshot(page, sid, 2));
    }
    // f3 — midpoint
    if (i === Math.floor(lines.length / 2) && lines.length > 2) {
      await sleep(80);
      screenshots.push(await takeScreenshot(page, sid, 3));
    }
  }

  // f4 — all output done (always captured)
  await sleep(200);
  screenshots.push(await takeScreenshot(page, sid, 4));

  // Ensure we always have exactly 5 screenshots (pad with last if needed)
  while (screenshots.length < 5) {
    const last = screenshots[screenshots.length - 1];
    const idx  = screenshots.length;
    const dst  = resolve(SCREENSHOTS_DIR, `${sid}_f${idx}.png`);
    execFileSync('cp', [last, dst]);
    screenshots.push(dst);
  }

  await buildFallbackMp4(sid, screenshots);
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  mkdirSync(SCREENSHOTS_DIR, { recursive: true });
  mkdirSync(BROLL_DIR,       { recursive: true });

  const data = JSON.parse(readFileSync(SCRIPT_DATA, 'utf8'));
  const terminalSections = (data.sections || []).filter(
    s => s.broll_type === 'terminal'
  );

  if (terminalSections.length === 0) {
    console.log('No terminal sections found in script_data.json — nothing to do.');
    process.exit(0);
  }

  console.log(`\n🖥  Terminal demo renderer — ${terminalSections.length} section(s)\n`);

  // Check for existing screenshots (skip if already present unless forced)
  const force = process.argv.includes('--force');
  const toProcess = terminalSections.filter(s => {
    const f0 = resolve(SCREENSHOTS_DIR, `${s.id}_f0.png`);
    if (!force && existsSync(f0)) {
      console.log(`  ⏭  [${s.id}] Screenshots already exist — skipping (use --force to redo)`);
      return false;
    }
    return true;
  });

  if (toProcess.length === 0) {
    console.log('\n✅ All terminal sections already captured.\n');
    process.exit(0);
  }

  const browser = await chromium.launch({ headless: true });
  const page    = await browser.newPage();

  try {
    for (const section of toProcess) {
      await renderTerminalSection(page, section);
    }
  } finally {
    await browser.close();
  }

  console.log('\n✅ Terminal demo capture complete.\n');
}

main().catch(err => {
  console.error('Fatal:', err);
  process.exit(1);
});
