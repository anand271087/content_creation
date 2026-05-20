/**
 * screen_broll.mjs — Capture real tool UI as broll with cursor animation + highlights.
 *
 * For each section with broll_type="screen":
 *   1. Playwright navigates to screen_capture.url
 *   2. Injects cursor element (for hover effects on UI) + advances through cursor_steps
 *   3. IMPORTANT: Cursor and highlight overlays are HIDDEN before each screenshot.
 *      This produces CLEAN screenshots — Remotion's ScreenDemoLayer renders the
 *      synthetic cursor and highlight animations on top as Remotion overlays.
 *   4. Screenshots saved to assets/screen_screenshots/{section_id}_fN.png
 *   5. ffmpeg also builds a fallback Ken Burns video → assets/broll/{section_id}.mp4
 *      (used if Remotion ScreenDemoLayer is not available)
 *
 * screen_capture.cursor_steps schema (auto-populated by screen_choreography.mjs):
 *   {
 *     label: string,           // logged description
 *     spoken_cue: string,      // keyword for timeline sync
 *     xy: [x_frac, y_frac],   // cursor position as fraction of viewport (0–1)
 *     highlight_box: [x_frac, y_frac, w_frac, h_frac],  // highlight rect (optional)
 *     selector: string,        // CSS selector to move cursor to (overrides xy)
 *     click: boolean,          // simulate click ring animation (optional)
 *     type: string,            // text to type into field (optional)
 *     zoom_to: [x_frac, y_frac, w_frac, h_frac],  // region for Remotion ZoomPan
 *     wait_ms: number,         // how long this frame shows (default 1500ms)
 *   }
 */

import { chromium } from 'playwright';
import { execFileSync, execSync } from 'child_process';
import { readFileSync, writeFileSync, existsSync, mkdirSync, unlinkSync } from 'fs';
import { resolve, dirname, basename, join } from 'path';
import { fileURLToPath } from 'url';
import { config } from 'dotenv';
import { tmpdir } from 'os';

const __dir = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dir, '..');

config({ path: resolve(ROOT, '.env') });

const SCRIPT_DATA     = resolve(ROOT, 'assets/script_data.json');
const BROLL_DIR       = resolve(ROOT, 'assets/broll');
const AUTH_DIR        = resolve(ROOT, 'assets/.browser_auth');
// Clean screenshots (no overlays) for Remotion ScreenDemoLayer
const SCREENSHOTS_DIR = resolve(ROOT, 'assets/screen_screenshots');
// Temp dir for internal ffmpeg work (still uses old name for compat)
const TEMP_SHOTS_DIR  = resolve(ROOT, 'assets/.screen_screenshots_tmp');

const CHROME_USER_DATA = `/Users/${process.env.USER}/Library/Application Support/Google/Chrome`;

// Clip spec — must match Remotion b-roll box
const CLIP_DURATION  = 8;     // seconds (longer for screen demos)
const CLIP_WIDTH     = 880;
const CLIP_HEIGHT    = 1100;
const VIEWPORT_W     = 1440;  // browser viewport
const VIEWPORT_H     = 900;

// xfade dissolve duration between frames
const DISSOLVE_SEC   = 0.4;

const args = process.argv.slice(2);

// ── CSS injected into the page ───────────────────────────────────────────────

const CURSOR_CSS = `
  #pw-cursor {
    position: fixed;
    z-index: 2147483647;
    pointer-events: none;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.95);
    border: 2px solid rgba(30, 30, 30, 0.6);
    box-shadow: 0 3px 12px rgba(0,0,0,0.35), 0 1px 3px rgba(0,0,0,0.2);
    transform: translate(-50%, -50%);
    transition: left 0.55s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                top  0.55s cubic-bezier(0.25, 0.46, 0.45, 0.94);
    opacity: 0;
  }
  #pw-cursor.visible { opacity: 1; }
  #pw-cursor.clicking {
    animation: pw-click 0.35s ease-out;
  }
  @keyframes pw-click {
    0%   { transform: translate(-50%,-50%) scale(1); box-shadow: 0 3px 12px rgba(0,0,0,0.35); }
    30%  { transform: translate(-50%,-50%) scale(0.7); }
    60%  { transform: translate(-50%,-50%) scale(1.15); box-shadow: 0 0 0 12px rgba(255,255,255,0.15); }
    100% { transform: translate(-50%,-50%) scale(1); }
  }
  .pw-highlight {
    position: fixed;
    pointer-events: none;
    z-index: 2147483646;
    border: 3px solid rgba(59, 130, 246, 0.9);
    border-radius: 8px;
    box-shadow:
      0 0 0 2px rgba(59, 130, 246, 0.25),
      0 0 20px rgba(59, 130, 246, 0.35),
      inset 0 0 20px rgba(59, 130, 246, 0.05);
    animation: pw-pulse 1.2s ease-in-out infinite;
  }
  @keyframes pw-pulse {
    0%, 100% {
      box-shadow: 0 0 0 2px rgba(59,130,246,0.2), 0 0 20px rgba(59,130,246,0.3);
    }
    50% {
      box-shadow: 0 0 0 6px rgba(59,130,246,0.1), 0 0 40px rgba(59,130,246,0.5);
    }
  }
`;

// ── Helpers ───────────────────────────────────────────────────────────────────

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function getDomain(url) {
  try { return new URL(url).hostname; } catch { return url; }
}

async function injectCursor(page) {
  await page.addStyleTag({ content: CURSOR_CSS });
  await page.evaluate(() => {
    if (document.getElementById('pw-cursor')) return;
    const el = document.createElement('div');
    el.id = 'pw-cursor';
    document.body.appendChild(el);
  });
}

async function moveCursor(page, xFrac, yFrac) {
  const x = Math.round(xFrac * VIEWPORT_W);
  const y = Math.round(yFrac * VIEWPORT_H);
  await page.evaluate(({ x, y }) => {
    const el = document.getElementById('pw-cursor');
    if (!el) return;
    el.classList.add('visible');
    el.style.left = x + 'px';
    el.style.top  = y + 'px';
  }, { x, y });
  // Also move actual mouse for hover effects
  await page.mouse.move(x, y, { steps: 10 });
}

async function clearHighlights(page) {
  await page.evaluate(() => {
    document.querySelectorAll('.pw-highlight').forEach(el => el.remove());
  });
}

async function addHighlightBox(page, box) {
  // box: [x_frac, y_frac, w_frac, h_frac]
  const [xf, yf, wf, hf] = box;
  const x = Math.round(xf * VIEWPORT_W);
  const y = Math.round(yf * VIEWPORT_H);
  const w = Math.round(wf * VIEWPORT_W);
  const h = Math.round(hf * VIEWPORT_H);
  await page.evaluate(({ x, y, w, h }) => {
    const el = document.createElement('div');
    el.className = 'pw-highlight';
    el.style.left   = x + 'px';
    el.style.top    = y + 'px';
    el.style.width  = w + 'px';
    el.style.height = h + 'px';
    document.body.appendChild(el);
  }, { x, y, w, h });
}

async function addHighlightSelector(page, selector) {
  try {
    const box = await page.locator(selector).first().boundingBox();
    if (!box) return;
    await page.evaluate(({ x, y, w, h }) => {
      const el = document.createElement('div');
      el.className = 'pw-highlight';
      el.style.left   = (x - 4) + 'px';
      el.style.top    = (y - 4) + 'px';
      el.style.width  = (w + 8) + 'px';
      el.style.height = (h + 8) + 'px';
      document.body.appendChild(el);
    }, { x: box.x, y: box.y, w: box.width, h: box.height });
  } catch {}
}

async function animateClick(page) {
  await page.evaluate(() => {
    const el = document.getElementById('pw-cursor');
    if (!el) return;
    el.classList.remove('clicking');
    void el.offsetWidth; // reflow
    el.classList.add('clicking');
  });
  await sleep(380);
  await page.evaluate(() => {
    document.getElementById('pw-cursor')?.classList.remove('clicking');
  });
}

/** Hide cursor and all highlight overlays so screenshot is clean (no baked-in overlays). */
async function hideOverlays(page) {
  await page.evaluate(() => {
    const cursor = document.getElementById('pw-cursor');
    if (cursor) cursor.style.opacity = '0';
    document.querySelectorAll('.pw-highlight').forEach(el => { el.style.opacity = '0'; });
  });
}

/** Restore overlays after screenshot (for hover effects). */
async function showOverlays(page) {
  await page.evaluate(() => {
    const cursor = document.getElementById('pw-cursor');
    if (cursor) cursor.style.opacity = '1';
    document.querySelectorAll('.pw-highlight').forEach(el => { el.style.opacity = '1'; });
  });
}

/**
 * Take a CLEAN screenshot (no cursor/highlights baked in).
 * Saves to SCREENSHOTS_DIR for Remotion ScreenDemoLayer.
 * Also saves a copy to TEMP_SHOTS_DIR for ffmpeg fallback video.
 */
async function takeFrame(page, outPath, tempPath) {
  await hideOverlays(page);
  await sleep(60); // let CSS opacity transition settle
  await page.screenshot({ path: outPath, fullPage: false });
  if (tempPath) {
    // Hard-link or copy for ffmpeg fallback
    try {
      const { copyFileSync } = await import('fs');
      copyFileSync(outPath, tempPath);
    } catch {}
  }
  await showOverlays(page);
}

/**
 * Stitch screenshot frames into a video using ffmpeg xfade dissolves.
 * frames: [{ path, duration }]  (duration = seconds to show each frame)
 */
function framesToVideo(frames, outputPath) {
  if (frames.length === 0) throw new Error('No frames');

  if (frames.length === 1) {
    // Single frame → Ken Burns zoom
    const filter = [
      `scale=${CLIP_WIDTH}:${CLIP_HEIGHT}:force_original_aspect_ratio=increase`,
      `crop=${CLIP_WIDTH}:${CLIP_HEIGHT}:(iw-${CLIP_WIDTH})/2:0`,
      `zoompan=z='min(zoom+0.0012,1.20)':d=${CLIP_DURATION * 30}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=${CLIP_WIDTH}x${CLIP_HEIGHT}`,
      `setsar=1`,
    ].join(',');
    execFileSync('ffmpeg', [
      '-loop', '1', '-i', frames[0].path,
      '-t', String(CLIP_DURATION),
      '-vf', filter,
      '-c:v', 'libx264', '-profile:v', 'baseline', '-level', '3.1',
      '-pix_fmt', 'yuv420p', '-r', '30', '-an', '-y', outputPath,
    ], { stdio: 'pipe' });
    return;
  }

  // Multiple frames — xfade chain
  // First scale+crop each frame to portrait, then chain with xfade
  const scaleFilter = `scale=${CLIP_WIDTH}:${CLIP_HEIGHT}:force_original_aspect_ratio=increase,crop=${CLIP_WIDTH}:${CLIP_HEIGHT}:(iw-${CLIP_WIDTH})/2:0,setsar=1`;

  const inputs = frames.flatMap(f => ['-loop', '1', '-t', String(f.duration + DISSOLVE_SEC), '-i', f.path]);

  // Build filter_complex: scale each input, then chain xfades
  let filterLines = [];
  for (let i = 0; i < frames.length; i++) {
    filterLines.push(`[${i}:v]${scaleFilter}[v${i}]`);
  }

  // Chain xfades: offset = cumulative duration of previous frames
  let offset = 0;
  let prev = 'v0';
  for (let i = 1; i < frames.length; i++) {
    offset += frames[i - 1].duration;
    const out = i === frames.length - 1 ? 'vout' : `x${i}`;
    filterLines.push(`[${prev}][v${i}]xfade=transition=dissolve:duration=${DISSOLVE_SEC}:offset=${offset}[${out}]`);
    prev = out;
    offset -= DISSOLVE_SEC; // xfade overlaps by dissolve duration
  }

  execFileSync('ffmpeg', [
    ...inputs,
    '-filter_complex', filterLines.join(';'),
    '-map', '[vout]',
    '-c:v', 'libx264', '-profile:v', 'baseline', '-level', '3.1',
    '-pix_fmt', 'yuv420p', '-r', '30', '-an', '-y', outputPath,
  ], { stdio: 'pipe' });
}

// ── Main capture ─────────────────────────────────────────────────────────────

async function captureSection(section) {
  const sectionId = section.id;
  const capture   = section.screen_capture;
  const url       = capture.url;
  const steps     = capture.cursor_steps || [];
  const domain    = getDomain(url);
  const outputPath = resolve(BROLL_DIR, `${sectionId}.mp4`);

  // Skip if already captured (both mp4 and at least 2 clean screenshots)
  const shot0 = resolve(SCREENSHOTS_DIR, `${sectionId}_f0.png`);
  if (existsSync(outputPath) && existsSync(shot0)) {
    const size = readFileSync(outputPath).length;
    if (size > 10000) {
      console.log(`  [${sectionId}] already captured (${Math.round(size / 1024)}KB) — skipping`);
      return { sectionId, success: true, skipped: true };
    }
  }

  console.log(`  [${sectionId}] capturing ${url} (${steps.length} steps)`);
  mkdirSync(SCREENSHOTS_DIR, { recursive: true });
  mkdirSync(TEMP_SHOTS_DIR, { recursive: true });

  const authStorePath = resolve(AUTH_DIR, `${domain}.json`);
  const hasStoredAuth = existsSync(authStorePath);
  const hasChromeProfile = existsSync(CHROME_USER_DATA);

  let browser = null;
  let context  = null;

  try {
    // Auth: stored state > Chrome profile > headless anonymous
    if (hasStoredAuth) {
      browser = await chromium.launch({ headless: true });
      context = await browser.newContext({
        storageState: authStorePath,
        viewport: { width: VIEWPORT_W, height: VIEWPORT_H },
      });
    } else if (hasChromeProfile) {
      const tempProfile = resolve(AUTH_DIR, '.chrome_tmp');
      browser = await chromium.launchPersistentContext(tempProfile, {
        channel: 'chrome',
        headless: true,
        viewport: { width: VIEWPORT_W, height: VIEWPORT_H },
        args: ['--profile-directory=Default'],
      });
      context = browser;
    } else {
      browser = await chromium.launch({ headless: true });
      context = await browser.newContext({
        viewport: { width: VIEWPORT_W, height: VIEWPORT_H },
      });
    }

    const page = context.newPage ? await context.newPage() : context;
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await sleep(2500); // let page settle

    // Inject cursor
    await injectCursor(page);

    const frames = [];

    // Frame 0 — initial page state, clean screenshot
    const f0      = resolve(SCREENSHOTS_DIR, `${sectionId}_f0.png`);
    const f0Temp  = resolve(TEMP_SHOTS_DIR,  `${sectionId}_f0.png`);
    await takeFrame(page, f0, f0Temp);
    frames.push({ path: f0Temp, duration: 1.2 });

    // Show cursor at center (for hover effects on real UI elements)
    if (steps.length > 0) {
      await moveCursor(page, 0.5, 0.45);
      await sleep(300);
    }

    // Walk through steps
    for (let i = 0; i < steps.length; i++) {
      const step = steps[i];
      console.log(`    step ${i + 1}/${steps.length}: ${step.label || ''}`);

      await clearHighlights(page);

      // Move cursor (triggers real hover effects like dropdowns)
      if (step.selector) {
        try {
          const box = await page.locator(step.selector).first().boundingBox();
          if (box) {
            await moveCursor(page, box.x / VIEWPORT_W + box.width / (2 * VIEWPORT_W),
                                   box.y / VIEWPORT_H + box.height / (2 * VIEWPORT_H));
          }
        } catch {}
      } else if (step.xy) {
        await moveCursor(page, step.xy[0], step.xy[1]);
      }

      await sleep(550); // let UI hover state update

      // Real click (opens dropdowns, selects items)
      if (step.click && step.selector) {
        try { await page.locator(step.selector).first().click({ force: true }); } catch {}
        await sleep(400);
      } else if (step.click && step.xy) {
        const cx = Math.round(step.xy[0] * VIEWPORT_W);
        const cy = Math.round(step.xy[1] * VIEWPORT_H);
        await page.mouse.click(cx, cy);
        await sleep(400);
      }

      // Type text into focused element
      if (step.type) {
        const tx = step.xy ? Math.round(step.xy[0] * VIEWPORT_W) : null;
        const ty = step.xy ? Math.round(step.xy[1] * VIEWPORT_H) : null;
        if (tx && ty) await page.mouse.click(tx, ty);
        await sleep(200);
        // Clear existing text and type new content
        await page.keyboard.press('Control+a');
        await page.keyboard.type(step.type, { delay: 0 }); // instant — Remotion will animate
        await sleep(300);
      }

      await sleep(200); // let page update

      // Take CLEAN screenshot (overlays hidden — Remotion adds them back as overlays)
      const fPath     = resolve(SCREENSHOTS_DIR, `${sectionId}_f${i + 1}.png`);
      const fPathTemp = resolve(TEMP_SHOTS_DIR,  `${sectionId}_f${i + 1}.png`);
      await takeFrame(page, fPath, fPathTemp);
      frames.push({ path: fPathTemp, duration: (step.wait_ms || 1500) / 1000 });
    }

    // Build fallback Ken Burns video from temp screenshots
    console.log(`    building fallback video from ${frames.length} frame(s)…`);
    framesToVideo(frames, outputPath);

    const size = readFileSync(outputPath).length;
    const shotCount = frames.length;
    console.log(`  [${sectionId}] ✓ ${shotCount} clean screenshots + ${Math.round(size / 1024)}KB fallback video`);
    return { sectionId, success: true };

  } catch (err) {
    console.error(`  [${sectionId}] ✗ FAILED: ${err.message}`);
    return { sectionId, success: false, error: err.message };
  } finally {
    try {
      if (context && context.close) await context.close();
      if (browser && browser !== context && browser.close) await browser.close();
    } catch {}
  }
}

// ── Entry ────────────────────────────────────────────────────────────────────

if (!existsSync(SCRIPT_DATA)) {
  console.error(`script_data.json not found at ${SCRIPT_DATA}`);
  process.exit(1);
}

const scriptData = JSON.parse(readFileSync(SCRIPT_DATA, 'utf8'));
let sections = scriptData.sections.filter(s => s.broll_type === 'screen' && s.screen_capture?.url);

if (args.length > 0) {
  sections = sections.filter(s => args.includes(s.id));
}

if (sections.length === 0) {
  console.log('No screen broll sections found.');
  process.exit(0);
}

mkdirSync(AUTH_DIR,   { recursive: true });
mkdirSync(BROLL_DIR,  { recursive: true });

console.log(`\nCapturing ${sections.length} screen section(s) with cursor animation…\n`);

let passed = 0;
const failed = [];

for (const section of sections) {
  const result = await captureSection(section);
  if (result.success) passed++;
  else failed.push(result.sectionId);
}

console.log(`\nDone: ${passed} captured, ${failed.length} failed.`);
if (failed.length > 0) {
  console.log(`Failed: ${failed.join(', ')}`);
  process.exit(1);
}
