/**
 * generate_hyperframes_broll.mjs — Render Hyperframes motion-graphic brolls for all clip sections.
 *
 * Replaces Kling AI for sections that were previously broll_type="clip".
 * Screen, terminal, diagram, and text_card sections are untouched.
 *
 * Usage:
 *   node scripts/generate_hyperframes_broll.mjs
 *   node scripts/generate_hyperframes_broll.mjs --force     # re-render even if .mp4 exists
 *   node scripts/generate_hyperframes_broll.mjs body_1      # render specific section only
 */

import { readFileSync, writeFileSync, mkdirSync, rmSync, existsSync, statSync } from "fs";
import { execSync, spawnSync } from "child_process";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { tmpdir } from "os";
import { randomBytes } from "crypto";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");
const SCRIPT_DATA = resolve(ROOT, "assets", "script_data.json");
const BROLL_DIR = resolve(ROOT, "assets", "broll");
const TPL_DIR = resolve(ROOT, "hyperframes-templates");
const HF_BASE_JSON = resolve(TPL_DIR, "hyperframes.json");
const HF_BASE_META = resolve(TPL_DIR, "meta.json");
const GSAP_LOCAL   = resolve(TPL_DIR, "gsap.min.js");  // local GSAP — no CDN fetch during render

// Regex to match any CDN GSAP URL (cdnjs, jsdelivr, unpkg)
const GSAP_CDN_RE = /https?:\/\/[^"']*(?:gsap)[^"']*\.js/g;

const args = process.argv.slice(2);
const FORCE = args.includes("--force");
const TARGET_SECTION = args.find(a => !a.startsWith("--"));

// ── Template selection ─────────────────────────────────────────────────────────

const SECTION_TEMPLATE = {
  hook:           "tpl_hook_slam.html",
  context:        "tpl_hook_slam.html",
  trigger_1:      "tpl_trigger_kinetic.html",
  trigger_2:      "tpl_trigger_kinetic.html",
  trigger_3:      "tpl_trigger_kinetic.html",
  body_1:         "tpl_body_card.html",
  body_2:         "tpl_body_card.html",
  bridge:         "tpl_bridge_concept.html",
  grand_takeaway: "tpl_quote_reveal.html",
  emotion_save:   "tpl_cta_card.html",
};

// Fixed animation durations per section type — clips loop in Remotion so duration
// only needs to cover the animation, not the full section playtime.
const SECTION_DURATION = {
  hook:           8,
  context:        8,
  trigger_1:      3,
  trigger_2:      3,
  trigger_3:      3,
  body_1:         8,
  body_2:         8,
  bridge:         5,
  grand_takeaway: 6,
  emotion_save:   12,
};

// ── Tool metadata for UI mockup template ──────────────────────────────────────

const TOOL_META = {
  n8n:      { color: "#FF6D00", url_accent: "app.n8n.io", url_rest: "/workflow/editor", icons: ["🪝","⚡","📤"] },
  obsidian: { color: "#7C3AED", url_accent: "obsidian.md",  url_rest: "/vault",           icons: ["📥","🧠","🔗"] },
  claude:   { color: "#FF6B35", url_accent: "claude.ai",    url_rest: "/new",              icons: ["💬","🤖","✅"] },
  chatgpt:  { color: "#10A37F", url_accent: "chat.openai.com", url_rest: "/",             icons: ["💬","⚡","📤"] },
  zapier:   { color: "#FF4A00", url_accent: "zapier.com",   url_rest: "/editor",           icons: ["🪝","⚡","📤"] },
  make:     { color: "#6D28D9", url_accent: "make.com",     url_rest: "/scenarios",        icons: ["⚙️","🔄","📤"] },
  notion:   { color: "#e9e9e9", url_accent: "notion.so",    url_rest: "/workspace",        icons: ["📝","⚡","✅"] },
  heygen:   { color: "#2563EB", url_accent: "app.heygen.com", url_rest: "/videos",         icons: ["🎬","🤖","📹"] },
  codex:    { color: "#8B5CF6", url_accent: "codex.openai.com", url_rest: "/",            icons: ["📖","🧠","⚡"] },
  github:   { color: "#e9e9e9", url_accent: "github.com",   url_rest: "/actions",          icons: ["🐙","⚡","✅"] },
  gmail:    { color: "#EA4335", url_accent: "mail.google.com", url_rest: "/",             icons: ["📧","⚡","✅"] },
  slack:    { color: "#4A154B", url_accent: "app.slack.com", url_rest: "/messages",        icons: ["💬","⚡","📤"] },
};

function detectTool(section) {
  const text = ((section.spoken || "") + " " + (section.tool_mentioned || "")).toLowerCase();
  for (const name of Object.keys(TOOL_META)) {
    if (text.includes(name)) return { name, ...TOOL_META[name] };
  }
  return { name: "Automation", color: "#3B82F6", url_accent: "dashboard.app.io", url_rest: "/workflow", icons: ["🪝","⚡","✅"] };
}

// Satellite positions for knowledge graph (6 slots, pre-computed for 1080x1920 canvas)
// Center: (540, 960). Radius: 340px. Slots at 60° intervals starting from 330° (top-right)
const SAT_POSITIONS = [
  { left: 686, top: 630  },  // slot 0: top-right      (330°)
  { left: 826, top: 850  },  // slot 1: right           (30°)
  { left: 756, top: 1130 },  // slot 2: bottom-right    (90° shifted)
  { left: 144, top: 1130 },  // slot 3: bottom-left
  { left:  74, top: 850  },  // slot 4: left
  { left: 204, top: 630  },  // slot 5: top-left
];
const SAT_COLORS = ["#6366F1","#10B981","#F59E0B","#EF4444","#3B82F6","#A855F7"];

function pickTemplate(section) {
  // Explicit override from Stage 1 script data
  if (section.broll_template) return section.broll_template;

  // broll_type: "screen" → animated UI mockup (replaces real screen recording)
  if (section.broll_type === "screen") return "tpl_ui_mockup.html";

  // broll_type: "diagram" → knowledge graph for interconnected concepts, else flow diagram
  if (section.broll_type === "diagram") {
    const spoken = (section.spoken || "").toLowerCase();
    const isGraph = /\b(graph|knowledge|brain|wiki|connect|network|interlink|nodes|web|second brain)\b/.test(spoken);
    return isGraph ? "tpl_knowledge_graph.html" : "tpl_diagram_flow.html";
  }

  const lines = section.on_screen_text || [];
  const first = (lines[0] || "").toUpperCase();
  const spoken = (section.spoken || "").toLowerCase();

  // Stat line: starts with digits, or contains unit suffixes like 5x, 90%, ₹50k
  const isStatLine = /^[\d,\.]+/.test(first) || /\d+[xX%kKmMbB₹$]/.test(first);

  // VS/split: 4+ on_screen_text items suggests two pairs of contrast content
  const isVsSplit = lines.length >= 4;

  // Tech/command: spoken mentions technical verbs → terminal template fits
  const isTech = /\b(install|run|command|terminal|code|api|deploy|build|execute|script|npm|pip|git|setup|config)\b/.test(spoken);

  // Chart data: cost comparisons or ROI stats with numbers + comparison language
  const isChartData = /\d+[xX%kKmMbB₹$]/.test(spoken) && /vs|compared|cheaper|cost|₹|saved|saving|revenue|price|free/.test(spoken);

  // Notification stack: automation trigger / webhook / workflow events
  const isNotificationStack = /\b(notif|trigger|webhook|alert|automat|workflow|sends|fires|runs|execut|schedule)\b/.test(spoken);

  // Horizontal flowchart: pipeline steps or sequential tool chain
  const isPipelineFlow = /\b(pipeline|step[s]?|then|next|claude|deepseek|codex|flow|process|agent|workflow)\b/.test(spoken) && lines.length >= 2;

  switch (section.id) {
    case "hook":
      return "tpl_hook_slam.html";

    case "context":
      return isStatLine ? "tpl_stat_counter.html" : "tpl_hook_slam.html";

    case "trigger_1":
      return "tpl_trigger_kinetic.html";

    case "trigger_2":
      return "tpl_trigger_kinetic.html";

    case "trigger_3":
      // Third trigger uses glitch for visual variety
      return "tpl_glitch_title.html";

    case "body_1":
      if (isChartData)        return "tpl_data_chart.html";
      if (isNotificationStack) return "tpl_notification_stack.html";
      if (isVsSplit)          return "tpl_vs_split.html";
      if (isStatLine)         return "tpl_stat_counter.html";
      if (isTech)             return "tpl_terminal_type.html";
      return "tpl_body_card.html";

    case "body_2":
      // Always visually different from body_1
      if (isChartData)        return "tpl_data_chart.html";
      if (isNotificationStack) return "tpl_notification_stack.html";
      if (isVsSplit)          return "tpl_vs_split.html";
      if (isTech)             return "tpl_terminal_type.html";
      return "tpl_flow_steps.html";

    case "bridge":
      // Horizontal flowchart for pipeline/process bridges; fallback to concept card
      if (isPipelineFlow) return "tpl_flowchart_h.html";
      return "tpl_bridge_concept.html";

    case "grand_takeaway":
      // Longer quotes → spotlight reveal; shorter → word-by-word quote
      return spoken.split(" ").length > 18 ? "tpl_spotlight_reveal.html" : "tpl_quote_reveal.html";

    case "emotion_save":
      return "tpl_cta_card.html";

    default:
      return "tpl_hook_slam.html";
  }
}

function pickDuration(section) {
  return SECTION_DURATION[section.id] ?? Math.min(10, Math.max(3, section.end_sec - section.start_sec));
}

// ── Render one section ─────────────────────────────────────────────────────────

async function renderSection(section, scriptData) {
  const sid = section.id;
  const out = resolve(BROLL_DIR, `${sid}.mp4`);

  if (!FORCE && existsSync(out) && statSync(out).size > 10000) {
    console.log(`[${sid}] Already exists (${Math.round(statSync(out).size / 1024)}KB) — skipping`);
    return { sid, skipped: true };
  }

  const tplName = pickTemplate(section);
  const tplPath = resolve(TPL_DIR, tplName);

  if (!existsSync(tplPath)) {
    console.error(`[${sid}] Template not found: ${tplPath}`);
    return { sid, error: "template not found" };
  }

  const duration = pickDuration(section).toFixed(1);

  // Build section data payload — merge everything the templates might need
  const sectionData = {
    id: sid,
    label: section.label || sid,
    spoken: section.spoken || "",
    on_screen_text: section.on_screen_text || [],
    card_lines: section.card_lines || [],
    tool_mentioned: section.tool_mentioned || scriptData.tool_mentioned || "",
    grand_takeaway_line: scriptData.grand_takeaway_line || "",
    duration_sec: parseFloat(duration),
  };

  // Inject data into template HTML
  let html = readFileSync(tplPath, "utf8");
  html = html.replace("__SECTION_DATA_PLACEHOLDER__", JSON.stringify(sectionData));
  html = html.replace(/data-duration="__DURATION__"/, `data-duration="${duration}"`);

  // tpl_body_card: inject static item HTML so items exist before JS runs
  if (tplName === "tpl_body_card.html" && html.includes("__ITEMS_HTML_PLACEHOLDER__")) {
    const COLORS = [
      { stroke: "#1971c2", bg: "#1a3a5c", text: "#74c0fc" },
      { stroke: "#2f9e44", bg: "#1a3d27", text: "#8ce99a" },
      { stroke: "#f59f00", bg: "#3d3000", text: "#ffd43b" },
      { stroke: "#862e9c", bg: "#2e1640", text: "#da77f2" },
      { stroke: "#c92a2a", bg: "#3d1010", text: "#ff6b6b" },
    ];
    const textItems = (sectionData.card_lines && sectionData.card_lines.length
      ? sectionData.card_lines
      : sectionData.on_screen_text) || [];
    const itemsHtml = textItems.slice(0, 5).map((text, i) => {
      const c = COLORS[i % COLORS.length];
      return `<div class="item" id="item-${i}">
        <div class="num-circle" style="background:${c.bg}; border:3px solid ${c.stroke};">
          <span style="color:${c.text}">${i + 1}</span>
        </div>
        <div class="item-label">${text}</div>
      </div>`;
    }).join("\n      ");
    html = html.replace("__ITEMS_HTML_PLACEHOLDER__", itemsHtml);
  }

  // tpl_flow_steps: inject static step boxes + arrows so they exist before JS runs
  if (tplName === "tpl_flow_steps.html" && html.includes("__ITEMS_HTML_PLACEHOLDER__")) {
    const textItems = (sectionData.card_lines && sectionData.card_lines.length
      ? sectionData.card_lines
      : sectionData.on_screen_text) || [];
    const stepsHtml = textItems.slice(0, 4).map((text, i) => {
      const arrowRow = i < textItems.slice(0, 4).length - 1
        ? `<div class="arrow-row" id="farrow-${i}">
          <svg viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M14 4 L14 20 M8 14 L14 20 L20 14" stroke="rgba(77,171,247,0.5)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>`
        : "";
      return `<div class="step-box" id="fstep-${i}">
        <div class="step-num">${i + 1}</div>
        <div class="step-text">${text}</div>
      </div>${arrowRow}`;
    }).join("\n      ");
    html = html.replace("__ITEMS_HTML_PLACEHOLDER__", stepsHtml);
  }

  // ── tpl_ui_mockup: inject tool metadata + workflow steps ─────────────────────
  if (tplName === "tpl_ui_mockup.html") {
    const tool = detectTool(section);
    const textItems = (sectionData.card_lines && sectionData.card_lines.length
      ? sectionData.card_lines
      : sectionData.on_screen_text) || [];
    const [n1 = "Input", n2 = "Process", n3 = "Output"] = textItems;
    const [i1 = "🪝", i2 = "⚡", i3 = "📤"] = tool.icons;
    // URL split: accent part is the domain, rest is the path
    const urlAccent = tool.url_accent;
    const urlRest   = tool.url_rest;
    const logLine   = `Workflow "${textItems.slice(0,2).join(" → ")}" running...`;
    html = html
      .replace(/__TOOL_NAME__/g,       tool.name)
      .replace(/__TOOL_URL_ACCENT__/g,  urlAccent)
      .replace(/__TOOL_URL_REST__/g,    urlRest)
      .replace(/__ACCENT_COLOR__/g,     tool.color)
      .replace(/__NODE_1__/g,           n1)
      .replace(/__NODE_2__/g,           n2)
      .replace(/__NODE_3__/g,           n3)
      .replace(/__NODE_1_ICON__/g,      i1)
      .replace(/__NODE_2_ICON__/g,      i2)
      .replace(/__NODE_3_ICON__/g,      i3)
      .replace(/__LOG_LINE__/g,         logLine);
  }

  // ── tpl_flowchart_h: inject 3 step boxes + result bar ───────────────────────
  if (tplName === "tpl_flowchart_h.html") {
    const textItems = (sectionData.card_lines && sectionData.card_lines.length
      ? sectionData.card_lines
      : sectionData.on_screen_text) || [];
    const FLOW_ICONS = ["📥", "⚡", "📤"];
    const [step1 = "Step 1", step2 = "Step 2", step3 = "Step 3"] = textItems;
    // Sub-labels: use remaining card_lines beyond index 3, or empty string
    const sub1 = textItems[3] || "";
    const sub2 = textItems[4] || "";
    const sub3 = textItems[5] || "";
    const result = textItems[6] || `${step1} → ${step2} → ${step3}`;
    const titleText = (sectionData.on_screen_text[0] || sectionData.label || "The Process").toUpperCase();
    html = html
      .replace("__FLOW_TITLE__",   titleText)
      .replace(/__ICON_1__/g,       FLOW_ICONS[0])
      .replace(/__ICON_2__/g,       FLOW_ICONS[1])
      .replace(/__ICON_3__/g,       FLOW_ICONS[2])
      .replace(/__STEP_1__/g,       step1)
      .replace(/__STEP_2__/g,       step2)
      .replace(/__STEP_3__/g,       step3)
      .replace(/__SUB_1__/g,        sub1)
      .replace(/__SUB_2__/g,        sub2)
      .replace(/__SUB_3__/g,        sub3)
      .replace(/__RESULT__/g,       result);
  }

  // ── tpl_diagram_flow: inject node boxes + connectors ─────────────────────────
  if (tplName === "tpl_diagram_flow.html" && html.includes("__DIAGRAM_NODES_HTML__")) {
    const textItems = (sectionData.card_lines && sectionData.card_lines.length
      ? sectionData.card_lines
      : sectionData.on_screen_text) || [];
    const ACCENT_COLORS = ["#6366F1","#3B82F6","#10B981","#F59E0B","#EF4444"];
    const NODE_ICONS    = ["⚡","🔄","✅","📤","🎯"];
    const nodesHtml = textItems.slice(0, 5).map((text, i) => {
      const color   = ACCENT_COLORS[i % ACCENT_COLORS.length];
      const icon    = NODE_ICONS[i % NODE_ICONS.length];
      const isLast  = i === Math.min(textItems.length, 5) - 1;
      const arrowDiv = !isLast
        ? `<div class="diag-connector" id="diagConn${i}" style="background:linear-gradient(180deg,${color}55,transparent);"></div>`
        : "";
      const pillHtml = isLast
        ? `<div class="progress-pill"><div class="progress-dot"></div>Done</div>`
        : "";
      return `<div class="diag-node" id="diagNode${i}">
  <div class="node-accent" style="background:${color};"></div>
  <div class="node-icon">${icon}</div>
  <div class="node-text">
    <div class="node-name">${text}</div>
  </div>
  ${pillHtml}
</div>${arrowDiv}`;
    }).join("\n    ");
    const titleText = (sectionData.on_screen_text[0] || sectionData.label || "How It Works").toUpperCase();
    html = html
      .replace("__DIAGRAM_NODES_HTML__", nodesHtml)
      .replace("__DIAGRAM_TITLE__", titleText);
  }

  // ── tpl_knowledge_graph: inject center + satellites + SVG lines ───────────────
  if (tplName === "tpl_knowledge_graph.html" && html.includes("__SATELLITES_HTML__")) {
    const textItems = (sectionData.card_lines && sectionData.card_lines.length
      ? sectionData.card_lines
      : sectionData.on_screen_text) || [];
    const CX = 540, CY = 960;
    // Center = first item or section label
    const centerLabel = textItems[0] || sectionData.label || "Your Brain";
    const satellites  = textItems.slice(1, 7); // up to 6 satellites
    // Build satellite HTML
    const satHtml = satellites.map((text, i) => {
      const pos   = SAT_POSITIONS[i];
      const color = SAT_COLORS[i % SAT_COLORS.length];
      return `<div class="satellite sat-${i}" id="sat${i}" style="left:${pos.left - 110}px; top:${pos.top - 60}px; border-color:${color}44;">
  <div class="sat-label">${text}</div>
</div>`;
    }).join("\n  ");
    // Build SVG lines from center to each satellite center
    const svgLines = satellites.map((_, i) => {
      const pos   = SAT_POSITIONS[i];
      const color = SAT_COLORS[i % SAT_COLORS.length];
      return `<line class="conn-line" id="conn${i}" x1="${CX}" y1="${CY}" x2="${pos.left}" y2="${pos.top}" stroke="${color}" stroke-opacity="0.4" stroke-width="1.5" stroke-dasharray="400" stroke-dashoffset="400"/>`;
    }).join("\n    ");
    html = html
      .replace("__SATELLITES_HTML__",   satHtml)
      .replace("__CONN_LINES_SVG__",     svgLines)
      .replace("__CENTER_LABEL__",       centerLabel)
      .replace("__CENTER_ICON__",        "🧠")
      .replace("__GRAPH_TITLE__",        (sectionData.on_screen_text[0] || "Knowledge Graph").toUpperCase())
      .replace("__GRAPH_FOOTER__",       "Everything connects. Nothing is siloed.");
  }

  // Create temp render project dir
  const tmpId = randomBytes(4).toString("hex");
  const tmpProject = resolve(tmpdir(), `hf-broll-${sid}-${tmpId}`);
  mkdirSync(tmpProject, { recursive: true });

  try {
    // Replace all CDN GSAP URLs with local copy — prevents network hang on jsDelivr
    if (existsSync(GSAP_LOCAL)) {
      html = html.replace(GSAP_CDN_RE, "./gsap.min.js");
      writeFileSync(resolve(tmpProject, "gsap.min.js"), readFileSync(GSAP_LOCAL));
    }

    // Write index.html with injected data
    writeFileSync(resolve(tmpProject, "index.html"), html);

    // Copy hyperframes.json and meta.json (required by CLI)
    writeFileSync(resolve(tmpProject, "hyperframes.json"), readFileSync(HF_BASE_JSON));
    const meta = JSON.parse(readFileSync(HF_BASE_META, "utf8"));
    meta.id = `hf-broll-${sid}`;
    meta.name = `hf-broll-${sid}`;
    writeFileSync(resolve(tmpProject, "meta.json"), JSON.stringify(meta));

    console.log(`[${sid}] Rendering ${tplName} (${duration}s) → ${out}`);

    const result = spawnSync("npx", [
      "hyperframes@latest", "render", tmpProject,
      "-o", out,
      "-f", "30",
      "-q", "standard",
      "--quiet",
    ], {
      stdio: "inherit",
      shell: false,     // no shell wrapper → SIGTERM reaches child directly
      timeout: 180000,  // 3 min hard limit per section
    });

    if (result.status !== 0) {
      throw new Error(`hyperframes render exited with code ${result.status}`);
    }

    if (!existsSync(out) || statSync(out).size < 5000) {
      throw new Error(`Output file missing or too small: ${out}`);
    }

    console.log(`[${sid}] ✅ ${Math.round(statSync(out).size / 1024)}KB`);
    return { sid, output: out };

  } catch (err) {
    console.error(`[${sid}] ❌ Failed: ${err.message}`);
    return { sid, error: err.message };
  } finally {
    rmSync(tmpProject, { recursive: true, force: true });
  }
}

// ── Main ───────────────────────────────────────────────────────────────────────

async function main() {
  if (!existsSync(SCRIPT_DATA)) {
    console.error("❌ assets/script_data.json not found");
    process.exit(1);
  }

  const scriptData = JSON.parse(readFileSync(SCRIPT_DATA, "utf8"));
  mkdirSync(BROLL_DIR, { recursive: true });

  // Sections eligible for Hyperframes rendering
  const sections = scriptData.sections.filter(s => {
    const t = s.broll_type;
    // terminal: skipped (handled separately if needed)
    if (t === "terminal") return false;
    // text_card uses static PNG — no video needed
    if (t === "text_card") return false;
    // Apply section filter if provided
    if (TARGET_SECTION && s.id !== TARGET_SECTION) return false;
    return true;
  });

  if (sections.length === 0) {
    console.log("No clip sections to render.");
    return;
  }

  // Parallel rendering in batches of 3 — enough to 3x throughput without OOM
  const BATCH_SIZE = 3;
  console.log(`\nRendering ${sections.length} section(s) with Hyperframes (batch=${BATCH_SIZE})...\n`);

  const results = [];
  for (let i = 0; i < sections.length; i += BATCH_SIZE) {
    const batch = sections.slice(i, i + BATCH_SIZE);
    const batchResults = await Promise.all(batch.map(s => renderSection(s, scriptData)));
    results.push(...batchResults);
  }

  const ok = results.filter(r => !r.error && !r.skipped);
  const skipped = results.filter(r => r.skipped);
  const failed = results.filter(r => r.error);

  console.log(`\n── Summary ──────────────────────────────────────────`);
  console.log(`  Rendered: ${ok.length}  Skipped: ${skipped.length}  Failed: ${failed.length}`);
  if (failed.length > 0) {
    console.log(`  Failed: ${failed.map(r => r.sid).join(", ")}`);
    process.exit(1);
  }
}

main();
