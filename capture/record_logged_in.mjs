/**
 * record_logged_in.mjs — record the REAL logged-in tool UIs using the user's
 * own Chrome profile (their sessions/cookies), per the user's hint: "I have
 * logged into everything — use the same Chrome and open as a tab."
 *
 * How it works:
 *   1. Requires Google Chrome to be QUIT (profile lock). The script checks.
 *   2. Copies the session-bearing parts of the default Chrome profile to a
 *      scratch dir (Cookies, Local Storage, IndexedDB, Login Data, Local State).
 *   3. Launches REAL Chrome (channel:'chrome') via Playwright persistent
 *      context on the copied profile — cookie decryption works because the
 *      same Chrome binary reads the same macOS keychain key.
 *      → macOS may show ONE keychain prompt: click "Always Allow".
 *   4. Opens each tool's logged-in app URL, scrolls/records ~10s, verifies
 *      no login wall / Cloudflare, saves assets/screen_demos/{key}.mp4
 *      (same filenames the countdown compositor uses — drop-in replacement).
 *
 * Usage:  node scripts/record_logged_in.mjs [key ...]     (default: all)
 */
import { chromium } from "playwright";
import { mkdirSync, cpSync, rmSync, readdirSync, existsSync } from "fs";
import { resolve, join } from "path";
import { execSync } from "child_process";
import os from "os";

const ROOT = resolve(new URL(".", import.meta.url).pathname, "..");
const OUT_DIR = join(ROOT, "assets", "screen_demos");
mkdirSync(OUT_DIR, { recursive: true });

const CHROME_DIR = join(os.homedir(), "Library/Application Support/Google/Chrome");
const SCRATCH = "/tmp/cc_chrome_profile";
const VIEW = { width: 1200, height: 1160 };

// Logged-in app URLs. If a page still shows a login wall it is rejected,
// never silently used.
const DEMOS = {
  perplexity: { url: "https://www.perplexity.ai/",        type: "type",
                query: "best AI tools for founders in 2026" },
  n8n:        { url: "https://app.n8n.cloud/",            type: "scroll" },
  elevenlabs: { url: "https://elevenlabs.io/app/speech-synthesis", type: "scroll" },
  claude:     { url: "https://claude.ai/new",             type: "type",
                query: "Write a 15 second viral reel script about AI avatars" },
  heygen:     { url: "https://app.heygen.com/home",       type: "scroll" },
};

function chromeRunning() {
  try { execSync("pgrep -x 'Google Chrome'", { stdio: "pipe" }); return true; }
  catch { return false; }
}

function copyProfile() {
  rmSync(SCRATCH, { recursive: true, force: true });
  mkdirSync(join(SCRATCH, "Default"), { recursive: true });
  cpSync(join(CHROME_DIR, "Local State"), join(SCRATCH, "Local State"));
  for (const item of ["Cookies", "Cookies-journal", "Login Data", "Preferences",
                      "Local Storage", "IndexedDB", "Session Storage"]) {
    const src = join(CHROME_DIR, "Default", item);
    if (existsSync(src)) cpSync(src, join(SCRATCH, "Default", item), { recursive: true });
  }
  console.log("profile copied →", SCRATCH);
}

const smoothScroll = async (page, toY, ms) => {
  await page.evaluate(({ toY, ms }) => new Promise(done => {
    const startY = window.scrollY, dy = toY - startY, t0 = performance.now();
    const step = (t) => {
      const p = Math.min(1, (t - t0) / ms);
      const e = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
      window.scrollTo(0, startY + dy * e);
      p < 1 ? requestAnimationFrame(step) : done();
    };
    requestAnimationFrame(step);
  }), { toY, ms });
};

async function looksBlocked(page) {
  const body = (await page.textContent("body").catch(() => "")) || "";
  const head = body.slice(0, 3000);
  return /verify you are human|just a moment|checking your browser/i.test(head)
      || /log in|sign in to continue|welcome back.*password/i.test(head.slice(0, 600));
}

async function record(ctx, key, spec) {
  const page = await ctx.newPage();
  try {
    await page.goto(spec.url, { waitUntil: "domcontentloaded", timeout: 40000 });
    await page.waitForTimeout(4500);   // let the SPA hydrate
    if (await looksBlocked(page)) {
      console.log(`  [${key}] BLOCKED or login wall — not using`);
      await page.close();
      return false;
    }
    if (spec.type === "type") {
      const box = page.locator('textarea, [contenteditable="true"]').first();
      try {
        await box.click({ timeout: 5000 });
        await box.pressSequentially(spec.query, { delay: 65 });
        await page.waitForTimeout(2000);
      } catch { await smoothScroll(page, 600, 3000); }
    } else {
      await page.waitForTimeout(800);
      await smoothScroll(page, 700, 3200);
      await page.waitForTimeout(1200);
      await smoothScroll(page, 1300, 2600);
    }
    await page.waitForTimeout(1500);
  } catch (e) {
    console.log(`  [${key}] error: ${String(e).slice(0, 120)}`);
    await page.close().catch(() => {});
    return false;
  }
  const video = page.video();
  await page.close();
  const path = await video.path();
  const dst = join(OUT_DIR, `${key}.mp4`);
  execSync(`ffmpeg -y -v error -i "${path}" -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -an "${dst}"`);
  console.log(`  [${key}] OK → ${dst}`);
  return true;
}

// ── main ──
if (chromeRunning()) {
  console.log("ERROR: Google Chrome is running. Quit Chrome (Cmd+Q) and re-run — "
    + "the profile is locked while Chrome is open.");
  process.exit(2);
}
copyProfile();

const ctx = await chromium.launchPersistentContext(SCRATCH, {
  channel: "chrome",
  headless: false,                       // headed = logged-in sites trust it
  viewport: VIEW,
  recordVideo: { dir: "/tmp/cc_rec", size: VIEW },
  args: ["--disable-blink-features=AutomationControlled"],
});

const wanted = process.argv.slice(2);
const keys = wanted.length ? wanted : Object.keys(DEMOS);
for (const key of keys) {
  if (!DEMOS[key]) { console.log("unknown:", key); continue; }
  console.log(`Recording ${key} (logged in)…`);
  await record(ctx, key, DEMOS[key]);
}
await ctx.close();
rmSync("/tmp/cc_rec", { recursive: true, force: true });
console.log("done");
