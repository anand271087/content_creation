#!/usr/bin/env python3
"""
Build Excalidraw JSON for architecture diagrams used in the productized doc.
Outputs to docs/diagrams/*.excalidraw — render to PNG via Playwright separately.
"""
import json
import random
import string
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "diagrams"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── Excalidraw helpers ───────────────────────────────────────────────────
def _id():
    return "".join(random.choices(string.ascii_letters + string.digits, k=20))


COMMON = {
    "fillStyle": "solid",
    "strokeWidth": 2,
    "strokeStyle": "solid",
    "roughness": 0,
    "opacity": 100,
    "groupIds": [],
    "frameId": None,
    "roundness": {"type": 3},
    "seed": 1,
    "version": 1,
    "versionNonce": 1,
    "isDeleted": False,
    "boundElements": [],
    "updated": 1,
    "link": None,
    "locked": False,
}

# Brand colors
INDIGO = "#1e3a8a"
INDIGO_BG = "#dbeafe"
PURPLE = "#5b21b6"
PURPLE_BG = "#ede9fe"
TEAL = "#0f766e"
TEAL_BG = "#ccfbf1"
EMERALD = "#065f46"
EMERALD_BG = "#d1fae5"
AMBER = "#92400e"
AMBER_BG = "#fef3c7"
GRAY = "#374151"
GRAY_BG = "#f3f4f6"
ROSE = "#9f1239"
ROSE_BG = "#ffe4e6"


def rect(x, y, w, h, stroke=INDIGO, bg=INDIGO_BG):
    return {
        **COMMON,
        "id": _id(),
        "type": "rectangle",
        "x": x, "y": y, "width": w, "height": h,
        "angle": 0,
        "strokeColor": stroke,
        "backgroundColor": bg,
    }


def diamond(x, y, w, h, stroke=PURPLE, bg=PURPLE_BG):
    return {
        **COMMON,
        "id": _id(),
        "type": "diamond",
        "x": x, "y": y, "width": w, "height": h,
        "angle": 0,
        "strokeColor": stroke,
        "backgroundColor": bg,
    }


def text(x, y, w, h, content, size=18, color="#0f172a", bold=False, align="center"):
    # Use top-align so y is the top of the text — no surprise vertical-center.
    return {
        **COMMON,
        "id": _id(),
        "type": "text",
        "x": x, "y": y, "width": w, "height": max(h, int(size * 1.4)),
        "angle": 0,
        "strokeColor": color,
        "backgroundColor": "transparent",
        "text": content,
        "fontSize": size,
        "fontFamily": 5,
        "textAlign": align,
        "verticalAlign": "top",
        "containerId": None,
        "originalText": content,
        "lineHeight": 1.25,
    }


def arrow(x1, y1, x2, y2, stroke="#64748b"):
    return {
        **COMMON,
        "id": _id(),
        "type": "arrow",
        "x": x1, "y": y1,
        "width": x2 - x1, "height": y2 - y1,
        "angle": 0,
        "strokeColor": stroke,
        "backgroundColor": "transparent",
        "strokeWidth": 2,
        "points": [[0, 0], [x2 - x1, y2 - y1]],
        "lastCommittedPoint": None,
        "startBinding": None,
        "endBinding": None,
        "startArrowhead": None,
        "endArrowhead": "arrow",
        "roundness": {"type": 2},
    }


def labeled_box(x, y, w, h, title, subtitle="", stroke=INDIGO, bg=INDIGO_BG, title_size=20):
    """Render a rectangle with title (top-aligned) and optional subtitle below."""
    elems = [rect(x, y, w, h, stroke, bg)]
    if subtitle:
        title_h = int(title_size * 1.4)
        # Center title+subtitle vertically as a group
        gap = 8
        sub_size = 13
        sub_h = int(sub_size * 1.4)
        total = title_h + gap + sub_h
        top = y + (h - total) // 2
        elems.append(text(x + 10, top, w - 20, title_h, title, size=title_size, bold=True))
        elems.append(text(x + 10, top + title_h + gap, w - 20, sub_h, subtitle, size=sub_size, color="#475569"))
    else:
        title_h = int(title_size * 1.4)
        elems.append(text(x + 10, y + (h - title_h) // 2, w - 20, title_h, title, size=title_size, bold=True))
    return elems


def save(name, elements, app_state=None):
    """Save an Excalidraw JSON file."""
    if app_state is None:
        app_state = {"viewBackgroundColor": "#ffffff", "gridSize": None}
    data = {
        "type": "excalidraw",
        "version": 2,
        "source": "https://excalidraw.com",
        "elements": elements,
        "appState": app_state,
        "files": {},
    }
    out = OUT_DIR / f"{name}.excalidraw"
    out.write_text(json.dumps(data, indent=2))
    print(f"  wrote {out.name} ({len(elements)} elements)")


# ─────────────────────────────────────────────────────────────────
# DIAGRAM 1 — FUNCTIONAL FLOW
# ─────────────────────────────────────────────────────────────────
def diagram_functional():
    elems = []
    cx = 800  # canvas center

    # Title
    elems.append(text(cx - 350, 30, 700, 40,
                      "Functional Architecture — Content Brief to Reel",
                      size=26, bold=True, color="#0f172a"))

    # Top: Content Brief
    elems += labeled_box(cx - 200, 100, 400, 80,
                         "Content Brief / Topic",
                         "driven by client prompt template",
                         stroke=AMBER, bg=AMBER_BG)
    elems.append(arrow(cx, 184, cx, 220))

    # Stage 1: Script Generation
    elems += labeled_box(cx - 220, 230, 440, 100,
                         "STAGE 1 — Script Generation",
                         "Topic → 10-section narrative · self-scored to quality bar",
                         stroke=INDIGO, bg=INDIGO_BG)
    elems.append(arrow(cx, 334, cx, 380))

    # Parallel block header
    elems.append(text(cx - 200, 380, 400, 28,
                      "Parallel Media Generation",
                      size=16, bold=True, color=PURPLE))

    # Three parallel boxes
    y = 420
    for i, (label, sub, stroke, bg) in enumerate([
        ("STAGE 2 · B-Roll", "motion-graphic, diagram, screen", PURPLE, PURPLE_BG),
        ("STAGE 3 · Avatar", "synthetic talking-head video", PURPLE, PURPLE_BG),
        ("STAGE 4 · Audio",  "ambient bed + impact stings", PURPLE, PURPLE_BG),
    ]):
        bx = cx - 480 + i * 320
        elems += labeled_box(bx, y, 280, 110, label, sub, stroke=stroke, bg=bg, title_size=16)
        # Arrow up from parent
        elems.append(arrow(cx, 334 + 76, bx + 140, y))
        # Arrow down to compose
        elems.append(arrow(bx + 140, y + 110, cx, y + 170))

    # Stage 5: Compose
    cy = y + 170
    elems += labeled_box(cx - 240, cy, 480, 100,
                         "STAGE 5 — Compose & Render",
                         "word-level alignment · 1080×1920 reel · 1.25× fast cut",
                         stroke=INDIGO, bg=INDIGO_BG)
    elems.append(arrow(cx, cy + 104, cx, cy + 140))

    # Stage 6: Quality Review (with loop-back)
    cy2 = cy + 150
    elems += labeled_box(cx - 220, cy2, 440, 90,
                         "STAGE 6 — Quality Review",
                         "multi-image visual scoring · loops back if below bar",
                         stroke=ROSE, bg=ROSE_BG)
    elems.append(arrow(cx, cy2 + 94, cx, cy2 + 130))

    # Loop-back arrow
    elems.append(arrow(cx - 220, cy2 + 45, cx - 320, cy2 + 45, stroke=ROSE))
    elems.append(arrow(cx - 320, cy2 + 45, cx - 320, 280, stroke=ROSE))
    elems.append(arrow(cx - 320, 280, cx - 220, 280, stroke=ROSE))
    elems.append(text(cx - 410, cy2 - 60, 160, 24, "below bar →", size=13, color=ROSE))

    # Stage 8: Social Copy
    cy3 = cy2 + 140
    elems += labeled_box(cx - 220, cy3, 440, 90,
                         "STAGE 8 — Social Copy",
                         "YouTube · Instagram · LinkedIn captions + hashtags",
                         stroke=TEAL, bg=TEAL_BG)
    elems.append(arrow(cx, cy3 + 94, cx, cy3 + 130))

    # Final
    cy4 = cy3 + 140
    elems += labeled_box(cx - 240, cy4, 480, 100,
                         "Final Reel + Asset Bundle",
                         "final_reel.mp4 · final_reel_fast.mp4 · captions · social copy",
                         stroke=EMERALD, bg=EMERALD_BG)

    save("functional_architecture", elems)


# ─────────────────────────────────────────────────────────────────
# DIAGRAM 2 — TECHNICAL ARCHITECTURE
# ─────────────────────────────────────────────────────────────────
def diagram_technical():
    elems = []
    cx = 800

    # Title
    elems.append(text(cx - 280, 30, 560, 40,
                      "Technical Architecture",
                      size=26, bold=True))

    # Layer 1: Orchestration
    elems += labeled_box(cx - 450, 100, 900, 90,
                         "ORCHESTRATION LAYER",
                         "stage runner · retry · parallel execution · crash recovery · state persistence · logging",
                         stroke=INDIGO, bg=INDIGO_BG, title_size=18)

    # Two columns: AI/Language, Media Generation
    elems.append(arrow(cx - 200, 200, cx - 200, 240))
    elems.append(arrow(cx + 200, 200, cx + 200, 240))

    # AI/Language layer — title at top, bullets below
    elems.append(rect(cx - 440, 250, 380, 200, stroke=PURPLE, bg=PURPLE_BG))
    elems.append(text(cx - 430, 265, 360, 24, "AI / LANGUAGE LAYER", size=17, bold=True, align="center"))
    elems.append(text(cx - 425, 315, 350, 22, "• Script generator (LLM API)", size=13, align="left"))
    elems.append(text(cx - 425, 345, 350, 22, "• Quality scorer (LLM API)", size=13, align="left"))
    elems.append(text(cx - 425, 375, 350, 22, "• Visual reviewer (LLM vision)", size=13, align="left"))
    elems.append(text(cx - 425, 405, 350, 22, "• Social copy writer (LLM API)", size=13, align="left"))

    # Media generation layer — title at top, bullets below
    elems.append(rect(cx + 60, 250, 380, 200, stroke=PURPLE, bg=PURPLE_BG))
    elems.append(text(cx + 70, 265, 360, 24, "MEDIA GENERATION LAYER", size=17, bold=True, align="center"))
    elems.append(text(cx + 75, 315, 350, 22, "• Synthetic avatar API", size=13, align="left"))
    elems.append(text(cx + 75, 345, 350, 22, "• Music + impact stings", size=13, align="left"))
    elems.append(text(cx + 75, 375, 350, 22, "• Reference imagery (optional)", size=13, align="left"))
    elems.append(text(cx + 75, 405, 350, 22, "• Word-level transcription (local)", size=13, align="left"))

    # Converge to render layer
    elems.append(arrow(cx - 250, 450, cx, 510))
    elems.append(arrow(cx + 250, 450, cx, 510))

    # Render layer
    elems += labeled_box(cx - 400, 520, 800, 110,
                         "ANIMATION & RENDER LAYER",
                         "motion-graphic engine · video composition · media transcode",
                         stroke=INDIGO, bg=INDIGO_BG, title_size=17)
    elems.append(arrow(cx, 630, cx, 670))

    # Asset store
    elems += labeled_box(cx - 350, 680, 700, 90,
                         "ASSET STORE",
                         "versioned JSON contracts · stage-isolated working directories",
                         stroke=EMERALD, bg=EMERALD_BG, title_size=17)

    save("technical_architecture", elems)


# ─────────────────────────────────────────────────────────────────
# DIAGRAM 3 — TIMING / WALL-CLOCK
# ─────────────────────────────────────────────────────────────────
def diagram_timing():
    elems = []
    elems.append(text(450, 30, 700, 40,
                      "End-to-End Wall-Clock per Reel",
                      size=26, bold=True))

    # Time axis (0 to 25 min)
    axis_y = 110
    axis_left = 200
    axis_right = 1500
    elems.append(arrow(axis_left, axis_y, axis_right, axis_y, stroke="#94a3b8"))
    for m in range(0, 26, 5):
        x = axis_left + (axis_right - axis_left) * m / 25
        elems.append(text(x - 20, axis_y + 10, 40, 20, f"{m}m", size=12, color="#64748b"))

    # Bars
    def bar(label, t0, t1, y, stroke, bg):
        x0 = axis_left + (axis_right - axis_left) * t0 / 25
        x1 = axis_left + (axis_right - axis_left) * t1 / 25
        elems.append(rect(x0, y, x1 - x0, 40, stroke=stroke, bg=bg))
        elems.append(text(40, y + 6, 150, 28, label, size=14, align="left"))

    y = 170
    bar("Script",         0,    1.5,  y, INDIGO, INDIGO_BG); y += 50
    elems.append(text(20, y, 180, 28, "▶ PARALLEL",
                      size=12, bold=True, color=PURPLE, align="left")); y += 30
    bar("B-Roll",         2,    5,    y, PURPLE, PURPLE_BG); y += 50
    bar("Avatar",         2,    12,   y, PURPLE, PURPLE_BG); y += 50
    bar("Audio",          2,    4,    y, PURPLE, PURPLE_BG); y += 50
    bar("Whisper align",  12,   15,   y, GRAY, GRAY_BG); y += 50
    bar("Remotion render", 15,  20,   y, GRAY, GRAY_BG); y += 50
    bar("Speed-up + thumb", 20, 22,   y, GRAY, GRAY_BG); y += 50
    bar("Quality review", 22,   23,   y, ROSE, ROSE_BG); y += 50
    bar("Social copy",    23,   23.4, y, TEAL, TEAL_BG); y += 50

    # Summary
    elems.append(text(450, y + 30, 700, 40,
                      "Total: 15 to 25 minutes per reel",
                      size=20, bold=True, color=EMERALD))

    save("timing_gantt", elems)


# ─────────────────────────────────────────────────────────────────
# DIAGRAM 4 — EXTENSIBILITY SURFACES
# ─────────────────────────────────────────────────────────────────
def diagram_extensibility():
    elems = []
    cx = 800
    elems.append(text(cx - 280, 30, 560, 40,
                      "Four Extension Points",
                      size=26, bold=True))

    # 1. Prompt
    elems += labeled_box(cx - 320, 110, 640, 90,
                         "1 · Client Prompt Template",
                         "swap scripting style without touching code",
                         stroke=AMBER, bg=AMBER_BG, title_size=17)
    elems.append(arrow(cx, 200, cx, 240))

    elems += labeled_box(cx - 200, 250, 400, 60, "Stage 1",
                         stroke=GRAY, bg=GRAY_BG, title_size=15)
    elems.append(arrow(cx, 310, cx, 350))

    # 2. Visual templates
    elems += labeled_box(cx - 320, 360, 640, 90,
                         "2 · Visual Template Library",
                         "add new motion-graphic patterns by dropping HTML files",
                         stroke=AMBER, bg=AMBER_BG, title_size=17)
    elems.append(arrow(cx, 450, cx, 490))

    elems += labeled_box(cx - 200, 500, 400, 60, "Stages 2 · 3 · 4",
                         stroke=GRAY, bg=GRAY_BG, title_size=15)
    elems.append(arrow(cx, 560, cx, 600))

    # 3. External providers
    elems += labeled_box(cx - 320, 610, 640, 90,
                         "3 · External Provider Swaps",
                         "avatar · music · imagery — configurable via .env",
                         stroke=AMBER, bg=AMBER_BG, title_size=17)
    elems.append(arrow(cx, 700, cx, 740))

    # 4. Composition
    elems += labeled_box(cx - 320, 750, 640, 90,
                         "4 · Composition Layer",
                         "change layout, captions, rhythm via React components",
                         stroke=AMBER, bg=AMBER_BG, title_size=17)

    save("extensibility", elems)


if __name__ == "__main__":
    print(f"Building diagrams in: {OUT_DIR}")
    diagram_functional()
    diagram_technical()
    diagram_timing()
    diagram_extensibility()
    print("Done.")
