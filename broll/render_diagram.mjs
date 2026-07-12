/**
 * render_diagram.mjs — Convert .excalidraw JSON files to PNG using Playwright.
 * Usage: node scripts/render_diagram.mjs [section_id ...]
 *   No args: renders all .excalidraw files in assets/diagrams/
 */

import { chromium } from 'playwright';
import { readFileSync, writeFileSync, readdirSync, existsSync } from 'fs';
import { resolve, dirname, basename } from 'path';
import { fileURLToPath } from 'url';

const __dir = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dir, '..');
const DIAGRAMS_DIR = resolve(ROOT, 'assets/diagrams');
const RENDERER_HTML = resolve(__dir, 'excalidraw_renderer.html');

const args = process.argv.slice(2);

// Collect files to render
let files = [];
if (args.length > 0) {
  files = args.map(id => resolve(DIAGRAMS_DIR, `${id}.excalidraw`));
} else {
  if (!existsSync(DIAGRAMS_DIR)) { console.log('No diagrams directory'); process.exit(0); }
  files = readdirSync(DIAGRAMS_DIR)
    .filter(f => f.endsWith('.excalidraw'))
    .map(f => resolve(DIAGRAMS_DIR, f));
}

if (files.length === 0) { console.log('No .excalidraw files to render'); process.exit(0); }

console.log(`Rendering ${files.length} diagram(s)...`);

const browser = await chromium.launch({ headless: true });
// 1080×880 = top half of 9:16 frame (1080×1920), diagram zone
const context = await browser.newContext({ viewport: { width: 1080, height: 880 } });
const page = await context.newPage();

// Load renderer HTML (offline capable — CDN scripts load from network)
await page.goto(`file://${RENDERER_HTML}`, { waitUntil: 'networkidle', timeout: 30000 });

// Wait for ExcalidrawLib to be available
await page.waitForFunction(() => typeof window.ExcalidrawLib !== 'undefined', { timeout: 30000 });

for (const filePath of files) {
  if (!existsSync(filePath)) { console.warn(`Missing: ${filePath}`); continue; }

  const sectionId = basename(filePath, '.excalidraw');
  const outPath = resolve(DIAGRAMS_DIR, `${sectionId}.png`);

  console.log(`  [${sectionId}] rendering...`);

  const json = JSON.parse(readFileSync(filePath, 'utf8'));

  // Reset state
  await page.evaluate(() => { window.renderDone = false; window._pngBytes = null; window.renderError = null; });

  // Call renderDiagram
  await page.evaluate((data) => window.renderDiagram(data), json);

  // Wait for completion
  await page.waitForFunction(() => window.renderDone === true, { timeout: 15000 });

  const result = await page.evaluate(() => ({
    bytes: window._pngBytes,
    error: window.renderError,
  }));

  if (result.error) {
    console.error(`  [${sectionId}] ERROR: ${result.error}`);
    continue;
  }

  writeFileSync(outPath, Buffer.from(result.bytes));
  console.log(`  [${sectionId}] saved → ${outPath} (${result.bytes.length} bytes)`);
}

await browser.close();
console.log('Done.');
