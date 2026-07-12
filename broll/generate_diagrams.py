"""
generate_diagrams.py — Generate Excalidraw JSON for diagram sections.

Reads assets/script_data.json, finds sections with broll_type="diagram",
calls Claude API with the Excalidraw skill to generate JSON,
saves to assets/diagrams/{section_id}.excalidraw
"""

import json
import logging
import re
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent
SCRIPT_DATA = ROOT / "assets" / "script_data.json"
DIAGRAMS_DIR = ROOT / "assets" / "diagrams"
LOG_FILE = ROOT / "logs" / "pipeline.log"

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
DIAGRAMS_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("generate_diagrams")
logger.setLevel(logging.DEBUG)
_fmt = logging.Formatter("%(asctime)s [generate_diagrams] %(levelname)s %(message)s")
_fh = logging.FileHandler(LOG_FILE); _fh.setFormatter(_fmt); logger.addHandler(_fh)
_sh = logging.StreamHandler(sys.stdout); _sh.setFormatter(_fmt); logger.addHandler(_sh)

# ---------------------------------------------------------------------------
# Excalidraw skill prompt (embedded from SKILL_excalidraw.md)
# ---------------------------------------------------------------------------

EXCALIDRAW_SYSTEM = """You are an expert Excalidraw diagram generator. You create clean, handwritten-style diagrams using the Excalidraw JSON format.

## Design Principles

**Color tells the story:** One color per logical zone. Everything in the "input" zone is blue. Everything in the "output" zone is green. The viewer should understand structure before reading a word.

**Nesting shows containment:** If X lives inside Y, X's box is drawn inside Y's box with consistent padding. Coordinates are absolute, not relative: `child_x = parent_x + padding`.

**Labels are short:** 2-5 words per label. Longer explanations become annotations with smaller fontSize and muted color (#868e96).

**White space is structure:** 15px minimum gap between siblings. 40px minimum between major sections.

**Arrows carry intent:** Color arrows to match purpose. Label every non-obvious arrow.

---

## Layout System

Always plan coordinates before writing JSON.

1. Identify major sections (left-to-right or top-to-bottom)
2. Assign fixed width and starting x to each section
3. Calculate gaps: 40-60px between major sections, 15-25px between siblings
4. Work top-to-bottom within sections: `next_y = current_y + current_height + gap`

**Padding rules:**
- Outer box to inner label: 8-10px top offset
- Outer box to nested box: 10-15px offset on all sides
- Sibling elements: 10-15px gap

**Text centering rule (CRITICAL):** To center text inside a box, set `text.x = box.x` AND `text.width = box.width`. NEVER set text.x to the box center point — that shifts text to the right half only. The text element must start at the same x as its container and span the full width. textAlign: "center" then centers the visible characters within that span.

**Coordinate math example:**
```
Section A: x=30,  w=170  -> right edge = 200
Gap:                        40px
Section B: x=240, w=170  -> right edge = 410
```

---

## Color System

| Zone | Use for | strokeColor | backgroundColor |
|------|---------|-------------|-----------------|
| Blue | Input, source, external | #1971c2 | #e7f5ff |
| Yellow | Processing, transformation | #f59f00 | #fff9db |
| Green | Output, success | #2f9e44 | #d3f9d8 |
| Purple | Shared layers, infrastructure | #862e9c | #f3d9fa |
| Red | Host OS, warnings, errors | #c92a2a | #ffe3e3 |
| Gray | Hardware, neutral containers | #495057 | #f8f9fa |

**Critical:** Text inside colored shapes must use #1e1e1e (near-black). Never use the zone's stroke color for text on that zone's background.

---

## Typography Scale

| Role | fontSize | fontFamily |
|------|----------|------------|
| Diagram title | 32-36 | 1 (Virgil) |
| Section header | 20-24 | 1 |
| Element label | 16-18 | 1 |
| Annotation | 14-15 | 1 |
| Small note | 12-13 | 1 |

fontFamily 1 = Virgil (handwritten), 2 = Helvetica, 3 = Cascadia (monospace)

---

## Element Schema

Every element needs ALL base fields — do not omit any:

```json
{
  "id": "unique-string",
  "type": "rectangle|ellipse|diamond|arrow|line|text",
  "x": 0, "y": 0,
  "width": 100, "height": 50,
  "angle": 0,
  "strokeColor": "#1e1e1e",
  "backgroundColor": "transparent",
  "fillStyle": "hachure",
  "strokeWidth": 2,
  "strokeStyle": "solid",
  "roughness": 2,
  "opacity": 100,
  "groupIds": [],
  "frameId": null,
  "roundness": {"type": 3},
  "boundElements": [],
  "updated": 1,
  "link": null,
  "locked": false
}
```

Text elements add:
```json
{
  "text": "Label text",
  "fontSize": 16,
  "fontFamily": 1,
  "textAlign": "center",
  "verticalAlign": "top",
  "containerId": null,
  "originalText": "Label text",
  "lineHeight": 1.25
}
```

Arrow elements add:
```json
{
  "points": [[0, 0], [100, 0]],
  "lastCommittedPoint": null,
  "startBinding": null,
  "endBinding": null,
  "startArrowhead": null,
  "endArrowhead": "arrow"
}
```

---

## JSON Wrapper

Every diagram uses this shell:
```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://excalidraw.com",
  "elements": [ ... ],
  "appState": {
    "gridSize": null,
    "viewBackgroundColor": "#ffffff"
  },
  "files": {}
}
```

Canvas fits 880x1100px (portrait, 9:16 video broll box). Start coordinates at x=40, y=40.

Output ONLY the valid JSON object — no markdown fences, no explanation. Start with { and end with }."""


def _build_prompt(diagram_prompt: str, section_label: str) -> str:
    return f"""Generate an Excalidraw diagram for this viral reel section: {section_label}

Diagram concept: {diagram_prompt}

Requirements:
- Canvas: 880x1100px portrait (fits a 9:16 video broll overlay box)
- White background (#ffffff), all text in Virgil font (fontFamily: 1)
- HANDWRITTEN STYLE: fillStyle="hachure" on all filled shapes, roughness=2 on all elements, roundness={{"type": 3}} on all rectangles
- Readable at a glance — viewer has 4 seconds
- Plan your layout with coordinate math before writing JSON
- Use color zones (Blue=input/old, Yellow=processing, Green=output/new) to tell the story visually
- 4-8 elements max — simple beats complex every time
- Short labels: 2-5 words per element

CREATIVE VISUAL STYLE — go beyond plain boxes:
- For company/tool comparisons (OpenAI vs Anthropic, GPT vs Claude, etc.): use LARGE EMOJI characters as visual anchors in text elements instead of plain rectangles. Place a big emoji (🤖 🧠 ⚡ 🚀 🔥 💡 📊 🏆) at the top of each entity's column as its icon, then label below.
- For timelines or progress charts: use a horizontal bar made of filled rectangles with varying widths to show growth. Each bar labeled with the model name + value. Makes it feel like a real infographic.
- For before/after or comparisons: use a bold diagonal dividing line splitting the canvas, LEFT side red-tinted for "before/bad", RIGHT side green-tinted for "after/good". No boring two-column tables.
- For flow diagrams: replace plain rectangular boxes with a mix of shapes — diamond for decision points, ellipse for start/end, rectangle for process steps. Vary the shapes so it doesn't look like a boring list.
- For stat/number callouts: make the number itself HUGE (fontSize 64-80) centered in the canvas as the hero element, with a small label below. Think magazine infographic, not a slide deck.
- For rankings or leaderboards: use a podium-style layout — tallest bar in center (1st place), shorter on sides. Fill bars with color gradient from gold to silver to bronze.
- For people/companies being discussed: use a large circle with their initial letter inside (like an avatar) as the visual representation. e.g., a blue circle with "D" for Dario, a green circle with "O" for OpenAI.
- NEVER use a plain grid of identical boxes. Every diagram must have at least one visual element that isn't a rectangle with text inside.

Output only the Excalidraw JSON object."""

def _extract_json(text: str) -> dict:
    """Extract JSON from Claude's response, handling markdown fences."""
    text = text.strip()
    # Remove ```json ... ``` fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # Find the JSON object
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(text)

def generate_diagram(section: dict, client: anthropic.Anthropic) -> dict:
    """Generate Excalidraw JSON for one section."""
    section_id = section["id"]
    diagram_prompt = section.get("diagram_prompt", f"Explain: {section.get('spoken', '')[:100]}")
    label = section.get("label", section_id)

    logger.info("[%s] Generating diagram: %s", section_id, diagram_prompt[:80])

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=EXCALIDRAW_SYSTEM,
        messages=[{"role": "user", "content": _build_prompt(diagram_prompt, label)}],
    )

    raw = response.content[0].text
    diagram_json = _extract_json(raw)
    logger.info("[%s] Generated %d elements", section_id, len(diagram_json.get("elements", [])))
    return diagram_json

def run_generate_diagrams(script_data: dict | None = None) -> dict:
    """Main entry point. Returns {"success": bool, "generated": list[str]}"""
    if script_data is None:
        if not SCRIPT_DATA.exists():
            return {"success": False, "error": "script_data.json not found"}
        script_data = json.loads(SCRIPT_DATA.read_text())

    diagram_sections = [s for s in script_data.get("sections", []) if s.get("broll_type") == "diagram"]

    if not diagram_sections:
        logger.info("No diagram sections found — skipping diagram generation")
        return {"success": True, "generated": []}

    import os
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"success": False, "error": "ANTHROPIC_API_KEY not set"}

    client = anthropic.Anthropic(api_key=api_key)
    generated = []
    failed = []

    for section in diagram_sections:
        section_id = section["id"]
        out_path = DIAGRAMS_DIR / f"{section_id}.excalidraw"

        if out_path.exists() and out_path.stat().st_size > 0:
            logger.info("[%s] Diagram already exists — skipping", section_id)
            generated.append(section_id)
            continue

        try:
            diagram = generate_diagram(section, client)
            out_path.write_text(json.dumps(diagram, indent=2, ensure_ascii=False))
            logger.info("[%s] Saved → %s", section_id, out_path)
            generated.append(section_id)
        except Exception as e:
            logger.error("[%s] Failed: %s", section_id, e)
            failed.append(section_id)

    return {"success": len(failed) == 0, "generated": generated, "failed": failed}

if __name__ == "__main__":
    result = run_generate_diagrams()
    print(json.dumps(result, indent=2))
