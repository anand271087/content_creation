/**
 * vsl/scripts/render_slides.mjs
 *
 * Render every slide referenced in vsl/slide_specs.json into vsl/assets/slides/<slide_id>.mp4
 * at 1920×1080 using the 16:9 Hyperframes templates in vsl/hyperframes-templates/.
 *
 * Usage:
 *   node vsl/scripts/render_slides.mjs                 # render only slides whose output is missing or stale
 *   node vsl/scripts/render_slides.mjs --force         # re-render everything
 *   node vsl/scripts/render_slides.mjs H1 H2           # render only specific slide ids
 *
 * Modularity: each slide's content hash is recorded in vsl/state.json. If the hash matches
 * the existing rendered MP4, the render is skipped.
 */

import { readFileSync, writeFileSync, mkdirSync, rmSync, existsSync, statSync } from "fs";
import { spawnSync } from "child_process";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { tmpdir } from "os";
import { randomBytes, createHash } from "crypto";

const __dirname = dirname(fileURLToPath(import.meta.url));
const VSL_ROOT      = resolve(__dirname, "..");
const TPL_DIR       = resolve(VSL_ROOT, "hyperframes-templates");
const SLIDES_OUTDIR = resolve(VSL_ROOT, "assets", "slides");
const STATE_FILE    = resolve(VSL_ROOT, "state.json");
const HF_JSON       = resolve(TPL_DIR, "hyperframes.json");
const GSAP_LOCAL    = resolve(TPL_DIR, "gsap.min.js");
const GSAP_CDN_RE   = /https?:\/\/[^"']*(?:gsap)[^"']*\.js/g;

const args = process.argv.slice(2);
const FORCE = args.includes("--force");
const TARGETS = args.filter(a => !a.startsWith("--"));

// ── Load inputs ──────────────────────────────────────────────────────────────
const brand = JSON.parse(readFileSync(resolve(VSL_ROOT, "brand.json"), "utf8"));
const specs = JSON.parse(readFileSync(resolve(VSL_ROOT, "slide_specs.json"), "utf8"));

const state = existsSync(STATE_FILE) ? JSON.parse(readFileSync(STATE_FILE, "utf8")) : { slides: {} };
state.slides = state.slides || {};

mkdirSync(SLIDES_OUTDIR, { recursive: true });

// Template-name → file mapping (slide_specs uses generic names, we map to actual files)
const TPL_MAP = {
  tpl_glitch_title:      "tpl_title_slam.html",
  tpl_hook_slam:         "tpl_title_slam.html",
  tpl_notification_stack:"tpl_chat_bubble.html",
  tpl_quote_reveal:      "tpl_quote_reveal.html",
  tpl_body_card:         "tpl_body_card.html",
  tpl_data_chart:        "tpl_bar_chart.html",
  tpl_flow_steps:        "tpl_flow_steps.html",
  tpl_knowledge_graph:   "tpl_knowledge_graph.html",
  tpl_diagram_flow:      "tpl_funnel_flow.html",
  tpl_split_offer:       "tpl_split_offer.html",
  tpl_split_cta:         "tpl_split_cta.html",
};

// ── Helpers ─────────────────────────────────────────────────────────────────
const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const upper = (s) => esc(String(s ?? "").toUpperCase());

function accentKey(spec) {
  // slide_spec.accent can be "primary" | "accent" | "danger" — used by tpl_body_card.
  const a = (spec.accent || "primary").toLowerCase();
  if (a === "danger") return "danger";    // template knows --danger CSS var
  if (a === "accent") return "accent";
  return "primary";
}

// ── Per-template prop builders ──────────────────────────────────────────────
const BUILDERS = {
  tpl_title_slam(compId, spec) {
    const p = spec.props || {};
    const lines = (p.lines && p.lines.length) ? p.lines : [p.title || compId, p.subtitle || "", ""];
    return {
      __EYEBROW__: upper(p.eyebrow || "ZEROHANDS"),
      __LINE1__:   upper(lines[0] || ""),
      __LINE2__:   upper(lines[1] || ""),
      __LINE3__:   upper(lines[2] || ""),
    };
  },
  tpl_chat_bubble(compId, spec) {
    const p = spec.props || {};
    // No label spans — left/right alignment + gray/blue color already communicate "viewer vs you".
    // Stacked "VIEWER VIEWER YOU" labels were visually noisy and overlapping bubble edges.
    const msgs = (p.messages || []).map(m => {
      const cls = (m.voice === "you") ? "you" : "viewer";
      return `<div class="row ${cls}"><div class="bubble ${cls}">${esc(m.text)}</div></div>`;
    }).join("\n      ");
    return {
      __TITLE__: upper(p.title || ""),
      __MESSAGES_HTML__: msgs,
    };
  },
  tpl_quote_reveal(compId, spec) {
    const p = spec.props || {};
    const quote = p.quote || "";
    const words = quote.split(/\s+/).filter(Boolean);
    const accentEvery = 4;       // make every 4th word accent for visual rhythm
    const wordHtml = words.map((w, i) => {
      const cls = (i % accentEvery === 2) ? "word accent" : "word";
      return `<span class="${cls}">${esc(w)}</span>`;
    }).join(" ");
    return {
      __QUOTE_HTML__: wordHtml,
      __ATTRIBUTION__: upper(p.attribution || ""),
    };
  },
  tpl_body_card(compId, spec) {
    const p = spec.props || {};
    const items = p.items || [];
    const cols  = items.length >= 5 ? "1fr 1fr" : "1fr";
    // Number column always shows ordinal (01, 02, ...) — keeps it clean and on-brand.
    // (Icon names like "clock"/"burn" are kept in slide_specs.json as semantic
    // labels in case we wire real SVG icons later, but we don't render them as text.)
    const itemsHtml = items.map((it, i) => {
      const num = it.n || String(i + 1).padStart(2, "0");
      return `<div class="item"><div class="num">${esc(num)}</div><div class="text">${esc(it.text || it.label || "")}</div></div>`;
    }).join("\n    ");
    return {
      __PILL__:       "ZEROHANDS",
      __TITLE__:      upper(p.title || ""),
      __GRID_COLS__:  cols,
      __ITEMS_HTML__: itemsHtml,
      __ACCENT_KEY__: accentKey(spec),
    };
  },
  tpl_bar_chart(compId, spec) {
    const p = spec.props || {};
    const rows = (p.bars || []).map(b => {
      const colorClass = (b.color === "danger") ? "danger" : "primary";
      const pct = Math.max(0, Math.min(100, Math.round(b.value || 0)));
      return `<div class="row" data-value="${pct}">
        <div class="meta"><span class="label">${esc(b.label || "")}</span>
          <span class="value">${pct}%</span></div>
        <div class="track"><div class="fill ${colorClass}"></div></div>
      </div>`;
    }).join("\n    ");
    return {
      __PILL__:     "ZEROHANDS",
      __TITLE__:    upper(p.title || ""),
      __SUBTITLE__: upper(p.subtitle || ""),
      __ROWS_HTML__: rows,
    };
  },
  tpl_flow_steps(compId, spec) {
    const p = spec.props || {};
    const steps = p.steps || [];
    const arrowSvg =
      `<svg viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">` +
      `<path d="M4 14 L24 14 M18 8 L24 14 L18 20" stroke="currentColor" stroke-width="2.5" ` +
      `stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    const parts = [];
    steps.forEach((s, i) => {
      parts.push(`<div class="step"><div class="num">STEP ${esc(s.n || (i+1))}</div>
        <div class="name">${esc(s.label || "")}</div>
        <div class="sub">${esc(s.sub || "")}</div></div>`);
      if (i < steps.length - 1) parts.push(`<div class="arrow">${arrowSvg}</div>`);
    });
    return {
      __PILL__:        "ZEROHANDS",
      __TITLE__:       upper(p.title || ""),
      __STEPS_HTML__:  parts.join("\n      "),
    };
  },
  tpl_knowledge_graph(compId, spec) {
    const p = spec.props || {};
    const branches = (p.branches || []).slice(0, 3);
    const html = branches.map((b, i) => {
      const leaves = (b.leaves || []).map(l => `<div class="leaf">→ ${esc(l)}</div>`).join("");
      return `<div class="branch b${i}"><div class="branch-title">${esc(b.label || "")}</div>${leaves}</div>`;
    }).join("\n    ");
    return {
      __PILL__:         "STRATEGY",
      __TITLE__:        upper(p.title || ""),
      __CENTER_LABEL__: upper(p.center || ""),
      __BRANCHES_HTML__: html,
    };
  },
  tpl_split_offer(compId, spec) {
    const p = spec.props || {};
    const items = p.items || [];
    const itemsHtml = items.map((it, i) => {
      const n = it.n || String(i + 1).padStart(2, "0");
      const lbl = it.label || it.text || "";
      return `<div class="item"><div class="n">${esc(n)}</div><div class="lbl">${esc(lbl)}</div></div>`;
    }).join("\n      ");
    return {
      __TITLE__: upper(p.title || ""),
      __ITEMS_HTML__: itemsHtml,
    };
  },
  tpl_split_cta(compId, spec) {
    const p = spec.props || {};
    // The template renders its own headline/meta — we only need the title placeholder
    // if we ever want to override. For now everything is baked into the HTML.
    return {
      __TITLE__: upper(p.headline_line1 || "BOOK"),
    };
  },
  tpl_funnel_flow(compId, spec) {
    const p = spec.props || {};
    const nodes = p.nodes || [];
    const arrowSvg =
      `<svg viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">` +
      `<path d="M4 14 L24 14 M18 8 L24 14 L18 20" stroke="currentColor" stroke-width="2.5" ` +
      `stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    const parts = [];
    nodes.forEach((n, i) => {
      const isLast = (i === nodes.length - 1);
      parts.push(`<div class="node ${isLast ? "last" : ""}">
        <div class="step-id">STEP ${i + 1}</div>
        <div class="lbl">${esc(n.label || "")}</div>
        <div class="sub">${esc(n.sub || "")}</div>
      </div>`);
      if (!isLast) parts.push(`<div class="arrow">${arrowSvg}</div>`);
    });
    return {
      __PILL__:       "ZEROHANDS",
      __TITLE__:      upper(p.title || ""),
      __NODES_HTML__: parts.join("\n      "),
      __RIBBON__:     "VIEWS → CALLS",
    };
  },
};

// Map slide_spec "template" string → builder fn (via TPL_MAP file alias)
function builderFor(tplName) {
  // tplName comes from slide_specs (e.g. "tpl_data_chart"); resolve to the actual file alias's builder
  const file = TPL_MAP[tplName];
  if (!file) return null;
  // builder key is the file name without .html
  const builderKey = file.replace(".html", "");
  return BUILDERS[builderKey] || null;
}

function templateFileFor(tplName) {
  return TPL_MAP[tplName];
}

// ── Flatten slide_specs into a list of slide records to render ─────────────
function gatherSlides() {
  const out = [];
  for (const [sid, spec] of Object.entries(specs.title_cards || {})) out.push({ sid, spec });
  for (const [sid, spec] of Object.entries(specs.hook || {}))        out.push({ sid, spec });
  for (const [sid, spec] of Object.entries(specs.body || {}))        out.push({ sid, spec });
  return out;
}

function specHash(spec, brand) {
  const h = createHash("sha256");
  h.update(JSON.stringify(spec));
  h.update("|");
  h.update(JSON.stringify({ primary: brand.primary, accent: brand.accent, bg: brand.bg, bg2: brand.bg_secondary, text: brand.text }));
  return h.digest("hex").slice(0, 12);
}

async function renderOne(slide) {
  const { sid, spec } = slide;
  const out = resolve(SLIDES_OUTDIR, `${sid}.mp4`);
  const hash = specHash(spec, brand);
  const prev = state.slides[sid];

  if (!FORCE && existsSync(out) && statSync(out).size > 8000 && prev && prev.hash === hash) {
    console.log(`[${sid}] unchanged — skipping (${Math.round(statSync(out).size / 1024)}KB)`);
    return { sid, skipped: true };
  }

  const build = builderFor(spec.template);
  const tplFile = templateFileFor(spec.template);
  if (!build || !tplFile) {
    console.error(`[${sid}] ! no builder/template for "${spec.template}"`);
    return { sid, error: "no builder" };
  }

  const tplPath = resolve(TPL_DIR, tplFile);
  if (!existsSync(tplPath)) {
    console.error(`[${sid}] ! template file missing: ${tplPath}`);
    return { sid, error: "template file missing" };
  }

  const duration = (spec.duration_sec || 4).toFixed(2);
  const props = build(sid, spec);

  const palette = {
    __BG__:            brand.bg,
    __BG_SECONDARY__:  brand.bg_secondary,
    __TEXT__:          brand.text,
    __PRIMARY__:       brand.primary,
    __ACCENT__:        brand.accent,
  };
  const allReplacements = {
    __COMP_ID__:  sid,
    __DURATION__: duration,
    ...palette,
    ...props,
  };

  let html = readFileSync(tplPath, "utf8");
  for (const [k, v] of Object.entries(allReplacements)) {
    html = html.split(k).join(String(v));
  }
  html = html.replace(GSAP_CDN_RE, "./gsap.min.js");

  // Write to tmp project
  const tmpId = randomBytes(4).toString("hex");
  const tmpProject = resolve(tmpdir(), `vsl-slide-${sid}-${tmpId}`);
  mkdirSync(tmpProject, { recursive: true });

  try {
    writeFileSync(resolve(tmpProject, "index.html"), html);
    writeFileSync(resolve(tmpProject, "gsap.min.js"), readFileSync(GSAP_LOCAL));
    writeFileSync(resolve(tmpProject, "hyperframes.json"), readFileSync(HF_JSON));
    const meta = { id: `vsl-slide-${sid}`, name: `vsl-slide-${sid}`, version: "1.0.0" };
    writeFileSync(resolve(tmpProject, "meta.json"), JSON.stringify(meta));

    console.log(`[${sid}] → ${tplFile}  (${duration}s)  ${out}`);
    const result = spawnSync("npx", [
      "hyperframes@latest", "render", tmpProject,
      "-o", out,
      "-f", "30",
      "-q", "standard",
      "--quiet",
    ], { stdio: "inherit", shell: false, timeout: 240000 });

    if (result.status !== 0) throw new Error(`hyperframes render exited code ${result.status}`);
    if (!existsSync(out) || statSync(out).size < 4000) throw new Error("output too small / missing");

    state.slides[sid] = { hash, mp4: out, rendered_at: new Date().toISOString() };
    console.log(`[${sid}] ✅ ${Math.round(statSync(out).size / 1024)}KB`);
    return { sid, output: out };
  } catch (err) {
    console.error(`[${sid}] ❌ ${err.message}`);
    return { sid, error: err.message };
  } finally {
    rmSync(tmpProject, { recursive: true, force: true });
  }
}

async function main() {
  let slides = gatherSlides();
  if (TARGETS.length) {
    slides = slides.filter(s => TARGETS.includes(s.sid));
    if (!slides.length) { console.error("No matching slide ids:", TARGETS.join(", ")); process.exit(2); }
  }
  console.log(`Rendering ${slides.length} slide(s)…  force=${FORCE}\n`);

  const results = [];
  // Render in serial — hyperframes render is GPU-heavy enough that 3 at once OOMs sometimes
  for (const s of slides) {
    results.push(await renderOne(s));
  }
  writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));

  const ok = results.filter(r => !r.error && !r.skipped);
  const skipped = results.filter(r => r.skipped);
  const failed = results.filter(r => r.error);
  console.log("\n──── Summary ────");
  console.log(`  Rendered: ${ok.length}`);
  console.log(`  Skipped:  ${skipped.length}`);
  console.log(`  Failed:   ${failed.length}`);
  if (failed.length) {
    console.log(`  Failed ids: ${failed.map(r => r.sid).join(", ")}`);
    process.exit(1);
  }
}

main();
