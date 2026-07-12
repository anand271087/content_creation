/**
 * record_tool_demos.mjs — capture live screen recordings of public tool pages
 * for the countdown reel's demo cards.
 *
 * Rules (from project memory):
 *   - NEVER record claude.ai or any login-walled URL — triggers Cloudflare
 *     verify-human. Claude is recorded from docs.claude.com instead.
 *   - Public marketing/docs pages only; every capture is frame-verified after.
 *
 * Output: assets/screen_demos/{key}.mp4  (~9s each, 1200x1160 ≈ card aspect)
 *
 * Usage:  node scripts/record_tool_demos.mjs [key ...]   (default: all)
 */
import { chromium } from "playwright";
import { mkdirSync, renameSync, readdirSync, rmSync, existsSync } from "fs";
import { resolve, join } from "path";
import { execSync } from "child_process";

const ROOT = resolve(new URL(".", import.meta.url).pathname, "..");
const OUT_DIR = join(ROOT, "assets", "screen_demos");
mkdirSync(OUT_DIR, { recursive: true });

const VIEW = { width: 1200, height: 1160 };
const RECORD_SECS = 9;

const smoothScroll = async (page, toY, ms) => {
  await page.evaluate(({ toY, ms }) => new Promise(done => {
    const startY = window.scrollY, dy = toY - startY, t0 = performance.now();
    const step = (t) => {
      const p = Math.min(1, (t - t0) / ms);
      const e = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2; // easeInOut
      window.scrollTo(0, startY + dy * e);
      p < 1 ? requestAnimationFrame(step) : done();
    };
    requestAnimationFrame(step);
  }), { toY, ms });
};

const hideOverlays = async (page) => {
  // 1) click an accept button if one exists (handles custom banners)
  for (const label of ["Accept All Cookies", "Accept all", "Accept All", "Accept", "I agree", "Got it"]) {
    try {
      const btn = page.getByRole("button", { name: label, exact: false }).first();
      if (await btn.isVisible({ timeout: 600 })) { await btn.click({ timeout: 1500 }); break; }
    } catch { /* keep trying */ }
  }
  // 2) best-effort CSS hide for anything left
  await page.addStyleTag({ content: `
    [id*="cookie" i], [class*="cookie" i], [id*="consent" i], [class*="consent" i],
    [id*="onetrust" i], [class*="onetrust" i], [class*="cky-" i], #CybotCookiebotDialog
    { display: none !important; visibility: hidden !important; }
  ` }).catch(() => {});
};

const DEMOS = {
  perplexity: {
    url: "https://www.perplexity.ai/",
    fallback: "https://docs.perplexity.ai/",
    actions: async (page) => {
      await hideOverlays(page);
      // type a query into the public ask box if present
      const box = page.locator('textarea, [contenteditable="true"]').first();
      try {
        await box.click({ timeout: 4000 });
        await box.pressSequentially("best AI tools for founders in 2026", { delay: 70 });
        await page.waitForTimeout(2200);
      } catch {
        await smoothScroll(page, 700, 3000);
        await page.waitForTimeout(1500);
        await smoothScroll(page, 0, 2500);
      }
    },
  },
  n8n: {
    url: "https://n8n.io/",
    fallback: "https://n8n.io/workflows/",
    actions: async (page) => {
      await hideOverlays(page);
      await page.waitForTimeout(1800);
      await smoothScroll(page, 900, 3200);
      await page.waitForTimeout(1400);
      await smoothScroll(page, 1600, 2600);
    },
  },
  elevenlabs: {
    url: "https://elevenlabs.io/",
    fallback: "https://elevenlabs.io/text-to-speech",
    actions: async (page) => {
      await hideOverlays(page);
      await page.waitForTimeout(1800);
      await smoothScroll(page, 850, 3200);
      await page.waitForTimeout(1400);
      await smoothScroll(page, 1700, 2600);
    },
  },
  claude: {
    // NOT claude.ai — login + Cloudflare wall. Docs scroll instead (memory rule).
    url: "https://docs.claude.com/en/docs/intro",
    fallback: "https://www.anthropic.com/claude",
    actions: async (page) => {
      await hideOverlays(page);
      await page.waitForTimeout(1800);
      await smoothScroll(page, 800, 3200);
      await page.waitForTimeout(1200);
      await smoothScroll(page, 1500, 2800);
    },
  },
  heygen: {
    url: "https://www.heygen.com/",
    fallback: "https://www.heygen.com/avatars",
    actions: async (page) => {
      await hideOverlays(page);
      await page.waitForTimeout(2000);
      await smoothScroll(page, 900, 3200);
      await page.waitForTimeout(1200);
      await smoothScroll(page, 1800, 2600);
    },
  },
};

async function record(key, spec, useFallback = false, headed = false) {
  const url = useFallback ? spec.fallback : spec.url;
  const tmp = join(OUT_DIR, `_tmp_${key}`);
  rmSync(tmp, { recursive: true, force: true });

  // headed + stealth flags beat most Cloudflare bot checks (e.g. elevenlabs.io)
  const browser = await chromium.launch({
    headless: !headed,
    args: ["--disable-blink-features=AutomationControlled"],
  });
  const ctx = await browser.newContext({
    viewport: VIEW,
    recordVideo: { dir: tmp, size: VIEW },
    userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    locale: "en-US",
  });
  const page = await ctx.newPage();
  let blocked = false;
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 25000 });
    await page.waitForTimeout(2500);
    const body = (await page.textContent("body").catch(() => "")) || "";
    if (/verify you are human|cloudflare|just a moment|checking your browser/i.test(body.slice(0, 2500))) {
      blocked = true;
      console.log(`  [${key}] BLOCKED (challenge page) at ${url}`);
    } else {
      await spec.actions(page);
      // pad to full duration
      await page.waitForTimeout(Math.max(0, RECORD_SECS * 1000 - 8000));
    }
  } catch (e) {
    console.log(`  [${key}] nav error: ${String(e).slice(0, 120)}`);
    blocked = true;
  }
  await ctx.close();
  await browser.close();

  if (blocked) {
    rmSync(tmp, { recursive: true, force: true });
    if (!headed) {
      console.log(`  [${key}] retrying HEADED with stealth flags`);
      return record(key, spec, useFallback, true);
    }
    if (!useFallback && spec.fallback) {
      console.log(`  [${key}] retrying with fallback ${spec.fallback}`);
      return record(key, spec, true, false);
    }
    return false;
  }

  const webm = readdirSync(tmp).find(f => f.endsWith(".webm"));
  if (!webm) { console.log(`  [${key}] no video produced`); return false; }
  const dst = join(OUT_DIR, `${key}.mp4`);
  execSync(`ffmpeg -y -v error -i "${join(tmp, webm)}" -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -an "${dst}"`);
  rmSync(tmp, { recursive: true, force: true });
  console.log(`  [${key}] OK → ${dst} (from ${url})`);
  return true;
}

const wanted = process.argv.slice(2);
const keys = wanted.length ? wanted : Object.keys(DEMOS);
for (const key of keys) {
  if (!DEMOS[key]) { console.log(`unknown key ${key}`); continue; }
  console.log(`Recording ${key}…`);
  await record(key, DEMOS[key]);
}
console.log("done");
