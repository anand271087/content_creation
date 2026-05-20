/**
 * render_doc_diagrams.mjs — Render docs/diagrams/*.excalidraw to PNG for the
 * architecture doc. Outputs at 1600×1200 landscape (high-res for Word embed).
 */
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, readdirSync, existsSync } from 'fs';
import { resolve, dirname, basename } from 'path';
import { fileURLToPath } from 'url';

const __dir = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dir, '..');
const DIAGRAMS_DIR = resolve(ROOT, 'docs/diagrams');
const RENDERER_HTML = resolve(__dir, 'excalidraw_renderer.html');

const files = readdirSync(DIAGRAMS_DIR)
  .filter(f => f.endsWith('.excalidraw'))
  .map(f => resolve(DIAGRAMS_DIR, f));

if (files.length === 0) {
  console.log('No .excalidraw files found');
  process.exit(0);
}

console.log(`Rendering ${files.length} diagram(s) at 1600x1200 landscape...`);

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1600, height: 1200 } });
const page = await context.newPage();

await page.goto(`file://${RENDERER_HTML}`, { waitUntil: 'networkidle', timeout: 30000 });
await page.waitForFunction(() => typeof window.ExcalidrawLib !== 'undefined', { timeout: 30000 });

// Override the renderer to use exportToBlob with higher dimensions
await page.evaluate(() => {
  window.renderHighRes = async function(excalidrawJson) {
    try {
      const { exportToBlob } = window.ExcalidrawLib;
      const elements = excalidrawJson.elements || [];
      const appState = {
        ...(excalidrawJson.appState || {}),
        viewBackgroundColor: '#ffffff',
        exportWithDarkMode: false,
      };
      const blob = await exportToBlob({
        elements,
        appState,
        files: excalidrawJson.files || {},
        mimeType: 'image/png',
        getDimensions: () => ({ width: 1600, height: 1200 }),
        exportPadding: 30,
      });
      const buf = await blob.arrayBuffer();
      const bytes = new Uint8Array(buf);
      let b64 = '';
      for (let i = 0; i < bytes.length; i++) b64 += String.fromCharCode(bytes[i]);
      window.__pngBase64 = btoa(b64);
      return true;
    } catch (e) {
      window.__renderError = String(e);
      return false;
    }
  };
});

for (const filePath of files) {
  const id = basename(filePath, '.excalidraw');
  const outPath = resolve(DIAGRAMS_DIR, `${id}.png`);
  const jsonData = JSON.parse(readFileSync(filePath, 'utf8'));

  await page.evaluate(() => {
    window.__pngBase64 = null;
    window.__renderError = null;
  });

  const ok = await page.evaluate(async (data) => {
    return await window.renderHighRes(data);
  }, jsonData);

  if (!ok) {
    const err = await page.evaluate(() => window.__renderError);
    console.error(`✗ ${id}: ${err}`);
    continue;
  }

  const b64 = await page.evaluate(() => window.__pngBase64);
  writeFileSync(outPath, Buffer.from(b64, 'base64'));
  console.log(`✓ ${id}.png`);
}

await browser.close();
console.log('Done.');
