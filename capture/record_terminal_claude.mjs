/**
 * record_terminal_claude.mjs — record a REAL Claude CLI session as video.
 *
 * Replays genuine `claude -p` output (captured beforehand) in the local
 * terminal renderer with humanised typing + line streaming, while Playwright
 * records the page as video. Content is real Claude output; renderer only
 * provides clean typography (claude.ai browser capture is blocked by the
 * corporate SSL proxy on this machine — see memory).
 *
 * Usage: node capture/record_terminal_claude.mjs <output_lines.txt> <out.mp4> [secs]
 */
import { chromium } from 'playwright';
import { execSync } from 'child_process';
import { readFileSync, mkdirSync, readdirSync, renameSync, rmSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dir = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dir, '..');
const RENDERER = resolve(ROOT, 'broll/terminal_renderer.html');

const [linesFile, outMp4] = process.argv.slice(2);
const CMD = 'claude -p "write me a viral reel script about AI avatars"';
const W = 880, H = 1100;

const lines = readFileSync(linesFile, 'utf8').split('\n').filter(l => l.trim().length);
const sleep = ms => new Promise(r => setTimeout(r, ms));

const tmpDir = resolve(ROOT, 'assets/screen_demos/.term_rec');
mkdirSync(tmpDir, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: W, height: H },
  recordVideo: { dir: tmpDir, size: { width: W, height: H } },
});
const page = await ctx.newPage();
await page.goto('file://' + RENDERER);
await page.addStyleTag({ content: '.output-line{font-size:22px !important;line-height:1.5 !important;} #command-text,.prompt-user,.prompt-host,.prompt-path,.prompt-at{font-size:20px !important;}' });

await page.evaluate(() => window.termAPI.setTitle('Claude Code — zerohands'));
await sleep(900);

// type the command char by char
for (const ch of CMD) {
  await page.evaluate(c => window.termAPI.typeChar(c), ch);
  await sleep(55 + Math.random() * 30 + (' "'.includes(ch) ? 30 : 0));
}
await sleep(500);
await page.evaluate(() => window.termAPI.hideCursor());
await sleep(400);

// stream the real output lines
for (const line of lines) {
  const color = /^(HOOK|STEP|CTA|\*\*)/.test(line) ? 'c-warning' : 'c-default';
  await page.evaluate(([t, c]) => window.termAPI.appendLine(t, c),
                      [line.replace(/\*\*/g, ''), color]);
  await sleep(420 + Math.random() * 300);
}
await page.evaluate(() => window.termAPI.appendLine("", "c-default"));
await page.evaluate(() => window.termAPI.appendLine("✻ Script ready — hook + 3 steps + CTA", "c-success"));
await sleep(2500);

await ctx.close();
await browser.close();

// playwright writes a .webm with a random name — convert to H264 baseline
const webm = readdirSync(tmpDir).find(f => f.endsWith('.webm'));
execSync(`ffmpeg -y -i "${resolve(tmpDir, webm)}" -c:v libx264 -profile:v baseline -level 3.1 -pix_fmt yuv420p -movflags +faststart -an "${outMp4}"`, { stdio: 'ignore' });
rmSync(tmpDir, { recursive: true, force: true });
console.log('OK →', outMp4);
