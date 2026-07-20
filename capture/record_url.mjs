/**
 * record_url.mjs — generic "any URL, any actions" screen recorder.
 *
 * The one-command generalization of record_tool_demos.mjs (public pages) and
 * record_logged_in.mjs (session reuse). Actions come from the CLI instead of
 * a hardcoded per-site dict.
 *
 * Usage:
 *   node capture/record_url.mjs <url> --name mydemo [--secs 10] [--login]
 *        [--actions "wait:2000; scroll:800:3000; type:textarea:hello world; click:.btn; press:Enter"]
 *
 * Action DSL (semicolon-separated, executed in order after page load):
 *   wait:<ms>                    pause
 *   scroll:<toY>[:<ms>]          eased smooth scroll (default 3000ms)
 *   type:<selector>:<text>       click selector, type text (human cadence)
 *   click:<selector>             click an element
 *   press:<key>                  keyboard key (Enter, Tab, ...)
 *   hide                         hide cookie/consent overlays (also runs once
 *                                automatically after load)
 *
 * --login: copies the session-bearing parts of the user's Chrome profile
 *   (Chrome must be QUIT). NEVER types passwords — reuses existing sessions
 *   only. DBSC-bound sites (claude.ai) won't carry: use capture_window.py.
 *
 * Output: assets/screen_demos/<name>.mp4 (1200x1160, card aspect)
 */
import { chromium } from "playwright";
import { mkdirSync, cpSync, rmSync, readdirSync, existsSync } from "fs";
import { resolve, join } from "path";
import { execSync } from "child_process";
import os from "os";

const ROOT = resolve(new URL(".", import.meta.url).pathname, "..");
const OUT_DIR = join(ROOT, "assets", "screen_demos");
mkdirSync(OUT_DIR, { recursive: true });
const VIEW = { width: 1200, height: 740 };  // must fit screen: headed Chrome clamps viewport, Playwright grey-pads recordVideo

// ── args ──
const argv = process.argv.slice(2);
const url = argv.find(a => !a.startsWith("--"));
const flag = (name, dflt = null) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 ? argv[i + 1] : dflt;
};
const name = flag("name", "demo");
const secs = parseFloat(flag("secs", "10"));
const login = argv.includes("--login");
const actionsStr = flag("actions", "");
if (!url) { console.log("usage: node capture/record_url.mjs <url> --name x [--secs 10] [--login] [--actions '...']"); process.exit(2); }

const hideOverlays = async (page) => {
  for (const label of ["Accept All Cookies", "Accept all", "Accept All", "Accept", "I agree", "Got it"]) {
    try {
      const btn = page.getByRole("button", { name: label, exact: false }).first();
      if (await btn.isVisible({ timeout: 500 })) { await btn.click({ timeout: 1200 }); break; }
    } catch { /* try next */ }
  }
  await page.addStyleTag({ content: `
    [id*="cookie" i], [class*="cookie" i], [id*="consent" i], [class*="consent" i],
    [id*="onetrust" i], [class*="cky-" i], #CybotCookiebotDialog
    { display:none !important; }` }).catch(() => {});
};

const smoothScroll = (page, toY, ms) => page.evaluate(({ toY, ms }) => new Promise(done => {
  const y0 = window.scrollY, dy = toY - y0, t0 = performance.now();
  const step = t => {
    const p = Math.min(1, (t - t0) / ms);
    const e = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
    window.scrollTo(0, y0 + dy * e);
    p < 1 ? requestAnimationFrame(step) : done();
  };
  requestAnimationFrame(step);
}), { toY, ms });

async function runActions(page, spec) {
  for (const raw of spec.split(";").map(s => s.trim()).filter(Boolean)) {
    const [cmd, ...rest] = raw.split(":");
    try {
      if (cmd === "wait") await page.waitForTimeout(parseInt(rest[0] || "1000"));
      else if (cmd === "scroll") await smoothScroll(page, parseInt(rest[0] || "800"), parseInt(rest[1] || "3000"));
      else if (cmd === "type") {
        const sel = rest[0];
        const text = rest.slice(1).join(":");
        const box = page.locator(sel).first();
        await box.click({ timeout: 5000 });
        await box.pressSequentially(text, { delay: 65 });
      }
      else if (cmd === "click") await page.locator(rest.join(":")).first().click({ timeout: 5000 });
      else if (cmd === "press") await page.keyboard.press(rest[0] || "Enter");
      else if (cmd === "hide") await hideOverlays(page);
      else console.log(`  unknown action: ${raw}`);
    } catch (e) {
      console.log(`  action failed (${raw}): ${String(e).slice(0, 90)}`);
    }
  }
}

function chromeRunning() {
  try { execSync("pgrep -x 'Google Chrome'", { stdio: "pipe" }); return true; } catch { return false; }
}

async function makeContext() {
  if (!login) {
    const browser = await chromium.launch({ headless: true, args: ["--disable-blink-features=AutomationControlled"] });
    const ctx = await browser.newContext({
      viewport: VIEW, recordVideo: { dir: "/tmp/cc_rec_url", size: VIEW },
      userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    });
    return { ctx, browser };
  }
  if (chromeRunning()) {
    console.log("ERROR: --login needs Google Chrome QUIT (profile lock). Cmd+Q and retry.");
    process.exit(2);
  }
  const CHROME = join(os.homedir(), "Library/Application Support/Google/Chrome");
  const SCRATCH = "/tmp/cc_chrome_profile_url";
  rmSync(SCRATCH, { recursive: true, force: true });
  mkdirSync(join(SCRATCH, "Default"), { recursive: true });
  cpSync(join(CHROME, "Local State"), join(SCRATCH, "Local State"));
  for (const item of ["Cookies", "Cookies-journal", "Login Data", "Preferences",
                      "Local Storage", "IndexedDB", "Session Storage"]) {
    const src = join(CHROME, "Default", item);
    if (existsSync(src)) cpSync(src, join(SCRATCH, "Default", item), { recursive: true });
  }
  const ctx = await chromium.launchPersistentContext(SCRATCH, {
    channel: "chrome", headless: false, viewport: VIEW,
    recordVideo: { dir: "/tmp/cc_rec_url", size: VIEW },
    args: ["--disable-blink-features=AutomationControlled"],
  });
  return { ctx, browser: null };
}

const { ctx, browser } = await makeContext();
const page = await ctx.newPage();
let ok = true;
try {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 40000 });
  await page.waitForTimeout(3000);
  const body = (await page.textContent("body").catch(() => "")) || "";
  if (/verify you are human|just a moment|checking your browser/i.test(body.slice(0, 2500))) {
    console.log("BLOCKED: challenge page — try --login, or capture_window.py, or the Wayback route");
    ok = false;
  } else {
    await hideOverlays(page);
    if (actionsStr) await runActions(page, actionsStr);
    const spent = 3000;   // rough; pad to requested duration
    await page.waitForTimeout(Math.max(500, secs * 1000 - spent));
  }
} catch (e) { console.log("nav error:", String(e).slice(0, 120)); ok = false; }

const video = page.video();
await page.close();
await ctx.close();
if (browser) await browser.close();
if (ok && video) {
  const path = await video.path();
  const dst = join(OUT_DIR, `${name}.mp4`);
  execSync(`ffmpeg -y -v error -i "${path}" -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -an "${dst}"`);
  console.log(`OK → ${dst}`);
}
rmSync("/tmp/cc_rec_url", { recursive: true, force: true });
process.exit(ok ? 0 : 1);
