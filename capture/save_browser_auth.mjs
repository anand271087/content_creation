/**
 * save_browser_auth.mjs — One-time interactive login to save Playwright storageState.
 *
 * Run once per tool that requires login. Opens a visible Chromium browser window,
 * navigates to the tool URL, you log in manually, then press Enter in the terminal.
 * Session is saved to assets/.browser_auth/{domain}.json and reused by screen_broll.mjs.
 *
 * Usage:
 *   node scripts/save_browser_auth.mjs claude.ai
 *   node scripts/save_browser_auth.mjs app.n8n.cloud
 *   node scripts/save_browser_auth.mjs make.com
 *   node scripts/save_browser_auth.mjs github.com
 *
 * The domain argument can be just the hostname or a full URL — both work.
 * Saved session files are gitignored (assets/.browser_auth/).
 */

import { chromium } from 'playwright';
import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { createInterface } from 'readline';

const __dir = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dir, '..');
const AUTH_DIR = resolve(ROOT, 'assets/.browser_auth');

// Parse argument — accept hostname or full URL
const arg = process.argv[2];
if (!arg) {
  console.error('Usage: node scripts/save_browser_auth.mjs <domain-or-url>');
  console.error('Examples:');
  console.error('  node scripts/save_browser_auth.mjs claude.ai');
  console.error('  node scripts/save_browser_auth.mjs app.n8n.cloud');
  console.error('  node scripts/save_browser_auth.mjs https://make.com/dashboard');
  process.exit(1);
}

// Normalise to a URL we can navigate to
let targetUrl;
let domain;
try {
  // If it already has a scheme, parse directly
  const parsed = new URL(arg.includes('://') ? arg : `https://${arg}`);
  domain = parsed.hostname;
  targetUrl = parsed.href;
} catch {
  console.error(`Invalid domain or URL: ${arg}`);
  process.exit(1);
}

const authStorePath = resolve(AUTH_DIR, `${domain}.json`);

// Check if auth already exists
if (existsSync(authStorePath)) {
  console.log(`\nAuth already saved for ${domain} at:`);
  console.log(`  ${authStorePath}`);
  console.log('\nTo refresh it, delete the file and run this script again.');
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  await new Promise(resolve => {
    rl.question('Overwrite existing auth? [y/N] ', (ans) => {
      rl.close();
      if (ans.toLowerCase() !== 'y') {
        console.log('Aborted.');
        process.exit(0);
      }
      resolve();
    });
  });
}

console.log(`\nOpening browser for: ${targetUrl}`);
console.log('Log in manually, then come back here and press Enter.\n');

// Launch visible (non-headless) Chromium
const browser = await chromium.launch({
  headless: false,
  args: [
    '--window-size=1400,900',
    '--disable-blink-features=AutomationControlled',
  ],
});

const context = await browser.newContext({
  viewport: { width: 1400, height: 900 },
  userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
});

const page = await context.newPage();

// Navigate to target
try {
  await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
} catch (e) {
  console.warn(`Navigation warning (may be fine): ${e.message}`);
}

// Wait for user to log in
const rl = createInterface({ input: process.stdin, output: process.stdout });
await new Promise(resolve => {
  rl.question(`\nLog in to ${domain} in the browser, then press Enter here to save session... `, () => {
    rl.close();
    resolve();
  });
});

// Save storage state
mkdirSync(AUTH_DIR, { recursive: true });
await context.storageState({ path: authStorePath });

// Verify it was saved
const { readFileSync } = await import('fs');
const saved = JSON.parse(readFileSync(authStorePath, 'utf8'));
const cookieCount = saved.cookies?.length ?? 0;
const originCount = saved.origins?.length ?? 0;

console.log(`\n✓ Auth saved to: ${authStorePath}`);
console.log(`  ${cookieCount} cookies, ${originCount} localStorage origins`);

if (cookieCount === 0 && originCount === 0) {
  console.warn('\n⚠  Warning: No cookies or localStorage found. Are you logged in?');
  console.warn('   Try navigating to a page that requires login, then run this script again.');
} else {
  console.log(`\nscreen_broll.mjs will use this session automatically for ${domain} URLs.`);
}

await browser.close();
