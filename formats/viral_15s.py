"""
viral_15s.py — standalone 15-second viral reel builder.

Bypasses the 10-section pipeline entirely. Applies Harsha's viral-density rules
(≤15s / 35-45 words / 4 beats / no teaching / CTA carries a promise). Produces:
    assets/final/viral_15s.mp4  — 1080x1920, ~15s, avatar full-screen + captions

Usage:
    python3 scripts/viral_15s.py --topic "GPT-5.6 Terra just made agents affordable"
    python3 scripts/viral_15s.py --brief brief.md
    python3 scripts/viral_15s.py --script assets/viral_15s_script.json     # skip Claude
    python3 scripts/viral_15s.py --topic "..." --dry-run                    # script only

Env: ANTHROPIC_API_KEY, HEYGEN_API_KEY, HEYGEN_VOICE_ID, HEYGEN_AVATAR_ID_BLUE,
     ELEVENLABS_API_KEY.
"""
from __future__ import annotations
import argparse, json, logging, os, subprocess, sys, time, re
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
REF_DIR = ROOT / "reference" / "harsha_skill"
OUT_DIR = ROOT / "assets" / "final"
TMP_DIR = ROOT / "assets" / "viral_15s_tmp"
SCRIPT_OUT = ROOT / "assets" / "viral_15s_script.json"
AVATAR_OUT = ROOT / "assets" / "avatar" / "viral_15s.mp4"
CAPS_OUT = ROOT / "assets" / "captions" / "viral_15s.json"
FINAL_OUT = OUT_DIR / "viral_15s.mp4"

W, H, FPS = 1080, 1920, 30
CAPTION_FONT = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
CAPTION_SIZE = 96
CAPTION_Y_FRAC = 0.72        # captions at ~72% down the frame
BRAND_BLUE = "#2979ff"

# Chest-up crop of the raw HeyGen frame (1080x1920).
# Includes head, neck, shoulders, upper chest — CUTS OFF above the hands entirely.
# Result is scaled back to 1080x1920 (~2× zoom on face).
CROP_W = 540
CROP_H = 960
CROP_X = 270
CROP_Y = 400

for d in (OUT_DIR, TMP_DIR, AVATAR_OUT.parent, CAPS_OUT.parent):
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [viral_15s] %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("viral_15s")


def env(name: str, required: bool = True) -> str:
    load_dotenv(ROOT / ".env")
    v = (os.getenv(name) or "").strip()
    if required and not v:
        log.error("Missing env: %s", name)
        sys.exit(2)
    return v


# ── STAGE 1: Claude → 4-beat viral script ────────────────────────────────────

VIRAL_PROMPT_TEMPLATE = """You are writing a VIRAL 15-second reel for @automatewithanand (AI automation content for
Indian working professionals 22-45 building with AI).

Read the two references below and OBEY them literally:

REFERENCE 1: viral-density.md — the gold standard for viral cuts.
{viral_density}

REFERENCE 2: hook-formulas.md — pick the strongest formula for this topic.
{hook_formulas}

TOPIC / BRIEF:
{brief}

HARD RULES:
1. Total spoken script: MAX 45 WORDS. Aim for 35-40.
2. Total runtime: MAX 15 seconds. Aim for 12-14.
3. EXACTLY 4 BEATS: hook (bold claim / reveal) → reveal or payoff → proof + dream FUSED into one line → CTA with a promise.
4. Each beat is ONE spoken sentence. No compound sentences. No lists.
5. NO TEACHING breakdown ("here are 3 reasons…"). Teaching goes in Authority cuts, not this.
6. CTA must carry a promise: "Follow and I'll show you how", "Comment X and I'll DM the exact steps".
7. Hook: prefer NEGATIVE / CONTRARIAN / CURIOSITY-GAP formulas. Pass the 5 hook tests.
8. Cut every sentence the script survives without.
9. Spoken language only. 8th-grade readability. No em-dashes, no jargon.
10. Spell out numbers for TTS ("two times cheaper" not "2x cheaper").

Return ONLY a JSON object matching this exact schema (no markdown, no explanation):
{{
  "title": "<short title of this reel>",
  "content_type": "Virality",
  "hook_formula": "<Negative | Curiosity Gap | Direct Challenge | Contrarian | But Wait Flip>",
  "template_used": "<one of Harsha's 7 templates>",
  "runtime_estimate_sec": <integer, target 12-15>,
  "word_count": <integer, target 35-45>,
  "full_spoken_script": "<the full 4-beat script as one continuous string with periods between beats>",
  "beats": [
    {{"id": "hook",        "label": "Hook (Bold Claim)",     "spoken": "<one sentence, ~10 words>"}},
    {{"id": "reveal",      "label": "Reveal or Payoff",      "spoken": "<one sentence, ~10 words>"}},
    {{"id": "proof_dream", "label": "Proof + Dream (fused)", "spoken": "<one sentence, ~12 words>"}},
    {{"id": "cta",         "label": "CTA with a Promise",    "spoken": "<one sentence, ~8 words>"}}
  ]
}}"""


def call_claude(topic: str, brief: str) -> dict:
    """Ask Claude for a 15s viral script. Returns parsed JSON."""
    import anthropic

    key = env("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=key)

    viral_density = (REF_DIR / "viral-density.md").read_text(encoding="utf-8")
    hook_formulas = (REF_DIR / "hook-formulas.md").read_text(encoding="utf-8")

    prompt = VIRAL_PROMPT_TEMPLATE.format(
        viral_density=viral_density,
        hook_formulas=hook_formulas,
        brief=f"{topic}\n\n{brief}" if brief else topic,
    )
    log.info("Calling Claude (prompt=%d chars)…", len(prompt))

    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    # Strip any accidental markdown fences
    text = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", text, flags=re.DOTALL).strip()
    data = json.loads(text)

    # Guardrails
    wc = len(data.get("full_spoken_script", "").split())
    log.info("Script: %d words / target ≤45", wc)
    if wc > 55:
        log.warning("Script exceeds 55 words — HeyGen output will exceed 15s.")
    if len(data.get("beats", [])) != 4:
        log.warning("Expected 4 beats, got %d", len(data.get("beats", [])))
    return data


# ── STAGE 2: HeyGen → avatar mp4 ────────────────────────────────────────────

HEYGEN_GEN = "https://api.heygen.com/v2/video/generate"
HEYGEN_STATUS = "https://api.heygen.com/v1/video_status.get"


def submit_heygen(script: str, api_key: str, avatar_id: str, voice_id: str) -> str:
    body = {
        "video_inputs": [{
            "character": {"type": "avatar", "avatar_id": avatar_id, "avatar_style": "normal"},
            "voice":     {"type": "text", "input_text": script, "voice_id": voice_id},
            "background":{"type": "color", "value": "#000000"},
        }],
        "dimension": {"width": W, "height": H},
    }
    r = requests.post(HEYGEN_GEN, headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
                      json=body, timeout=60)
    if r.status_code not in (200, 201):
        log.error("HeyGen submit %d: %s", r.status_code, r.text[:400]); sys.exit(1)
    vid = (r.json().get("data") or {}).get("video_id")
    if not vid:
        log.error("HeyGen: no video_id in response"); sys.exit(1)
    return vid


def poll_heygen(vid: str, api_key: str, timeout: int = 900) -> str:
    log.info("HeyGen polling video_id=%s", vid)
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(15)
        r = requests.get(HEYGEN_STATUS, headers={"X-Api-Key": api_key},
                         params={"video_id": vid}, timeout=30)
        if r.status_code != 200:
            log.warning("poll HTTP %d", r.status_code); continue
        payload = r.json().get("data", r.json())
        status = (payload.get("status") or "").lower()
        log.info("HeyGen status=%s", status)
        if status == "completed":
            return payload["video_url"]
        if status == "failed":
            log.error("HeyGen failed: %s", payload); sys.exit(1)
    log.error("HeyGen poll timeout"); sys.exit(1)


def download(url: str, dest: Path) -> None:
    log.info("Downloading → %s", dest.name)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for c in r.iter_content(8192):
                if c: f.write(c)


# ── STAGE 3: ElevenLabs Scribe transcription ─────────────────────────────────

def transcribe_scribe(mp4: Path, json_out: Path) -> None:
    """Delegate to the existing transcribe_elevenlabs.py adapter."""
    script = ROOT / "scripts" / "transcribe_elevenlabs.py"
    if not script.exists():
        log.error("missing %s", script); sys.exit(2)
    log.info("Transcribing via ElevenLabs Scribe…")
    r = subprocess.run(
        [sys.executable, str(script), str(mp4), "--output", str(json_out)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        log.error("Scribe failed:\n%s", r.stderr[-1500:]); sys.exit(1)


# ── STAGE 4: ffmpeg → burn Hormozi captions + finalise ──────────────────────

def _drawtext_escape(s: str) -> str:
    return (s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
             .replace(",", "\\,").replace("[", "\\[").replace("]", "\\]").replace("%", "\\%"))


def build_word_stream(caps_json: Path) -> list[dict]:
    """Flatten Scribe/Whisper JSON into a list of (word, start, end)."""
    data = json.loads(caps_json.read_text())
    out = []
    for seg in data.get("segments", []):
        for w in seg.get("words", []) or []:
            t = (w.get("word") or w.get("text") or "").strip()
            if not t: continue
            try:
                out.append({"word": t, "start": float(w["start"]), "end": float(w["end"])})
            except (KeyError, TypeError, ValueError):
                continue
    return out


def burn_captions(in_mp4: Path, out_mp4: Path, words: list[dict]) -> None:
    """Burn Hormozi-style single-word captions using chained drawtext filters."""
    if not words:
        log.warning("No word timings — copying without captions")
        subprocess.run(["ffmpeg", "-y", "-i", str(in_mp4), "-c", "copy", str(out_mp4)],
                       check=True, capture_output=True)
        return

    # Write each word to its own textfile so drawtext doesn't fight quoting/apostrophes.
    caps_tmp = TMP_DIR / "word_files"
    caps_tmp.mkdir(exist_ok=True)
    filters = []
    for i, w in enumerate(words):
        # Strip trailing punctuation (looks cleaner on the burnt caption)
        clean = re.sub(r"[.,!?;:]$", "", w["word"]).upper()
        fpath = caps_tmp / f"w_{i:04d}.txt"
        fpath.write_text(clean, encoding="utf-8")
        f_arg = str(fpath).replace(":", "\\:").replace(",", "\\,").replace(" ", "\\ ")
        font = CAPTION_FONT.replace(":", "\\:").replace(" ", "\\ ")
        start = max(0.0, w["start"])
        end   = max(start + 0.08, w["end"])
        # Highlight every 4th word in brand-blue for visual rhythm
        color = BRAND_BLUE if (i % 4 == 3) else "white"
        filters.append(
            f"drawtext=fontfile={font}:textfile={f_arg}"
            f":fontsize={CAPTION_SIZE}:fontcolor={color}"
            f":bordercolor=black:borderw=6"
            f":x=(w-text_w)/2:y=h*{CAPTION_Y_FRAC}"
            f":enable=between(t\\,{start:.2f}\\,{end:.2f})"
        )
    # Chest-up crop → scale back to 1080×1920, then drawtext chain on top.
    crop_prefix = f"crop={CROP_W}:{CROP_H}:{CROP_X}:{CROP_Y},scale={W}:{H}"
    vf = crop_prefix + "," + ",".join(filters)

    log.info("Burning %d word captions with ffmpeg drawtext (chest-up crop %dx%d @ %d,%d)…",
             len(words), CROP_W, CROP_H, CROP_X, CROP_Y)
    subprocess.run([
        "ffmpeg", "-y", "-i", str(in_mp4),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "slow", "-crf", "17",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        str(out_mp4),
    ], check=True)


# ── main ────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--topic", help="Topic/hook for the reel (short one-liner)")
    p.add_argument("--brief", help="Path to a longer brief markdown/txt file (optional)")
    p.add_argument("--script", help="Skip Claude — use an existing viral_15s_script.json")
    p.add_argument("--skip-avatar", action="store_true", help="Skip HeyGen render (reuse existing avatar)")
    p.add_argument("--skip-transcribe", action="store_true",
                   help="Skip Scribe (reuse existing assets/captions/viral_15s.json)")
    p.add_argument("--dry-run", action="store_true", help="Generate script only; skip HeyGen + ffmpeg")
    args = p.parse_args()

    # Step 1 — get the script
    if args.script:
        script_data = json.loads(Path(args.script).read_text())
        log.info("Using existing script from %s", args.script)
    else:
        if not args.topic and not args.brief:
            log.error("Need --topic or --brief (or --script to reuse existing).")
            return 2
        brief = ""
        if args.brief:
            brief = Path(args.brief).read_text()
        script_data = call_claude(args.topic or "", brief)
        SCRIPT_OUT.write_text(json.dumps(script_data, indent=2, ensure_ascii=False))
        log.info("Wrote script → %s", SCRIPT_OUT)

    print("\n─── SCRIPT ───────────────────────────────")
    print(f"  Title:         {script_data.get('title')}")
    print(f"  Hook formula:  {script_data.get('hook_formula')}")
    print(f"  Template:      {script_data.get('template_used')}")
    print(f"  Word count:    {script_data.get('word_count')}  (target 35-45)")
    print(f"  Runtime est.:  {script_data.get('runtime_estimate_sec')}s  (target ≤15)")
    print()
    for i, b in enumerate(script_data.get("beats", []), 1):
        print(f"  Beat {i} — {b['label']}: {b['spoken']}")
    print("──────────────────────────────────────────\n")

    if args.dry_run:
        log.info("Dry run — script printed, no HeyGen or ffmpeg.")
        return 0

    # Step 2 — HeyGen render
    if not args.skip_avatar or not AVATAR_OUT.exists():
        api_key = env("HEYGEN_API_KEY")
        voice = env("HEYGEN_VOICE_ID")
        avatar = env("HEYGEN_AVATAR_ID_BLUE")
        vid = submit_heygen(script_data["full_spoken_script"], api_key, avatar, voice)
        url = poll_heygen(vid, api_key)
        download(url, AVATAR_OUT)
        log.info("Avatar mp4 written (%d KB)", AVATAR_OUT.stat().st_size // 1024)
    else:
        log.info("--skip-avatar: reusing existing %s", AVATAR_OUT)

    # Step 3 — transcribe
    if args.skip_transcribe and CAPS_OUT.exists():
        log.info("--skip-transcribe: reusing existing %s", CAPS_OUT)
    else:
        transcribe_scribe(AVATAR_OUT, CAPS_OUT)
    words = build_word_stream(CAPS_OUT)
    log.info("Got %d word timestamps", len(words))

    # Step 4 — burn captions + finalise
    burn_captions(AVATAR_OUT, FINAL_OUT, words)

    dur = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(FINAL_OUT)],
    ).decode().strip())
    size_mb = FINAL_OUT.stat().st_size / 1e6
    print(f"\n✅ viral_15s built — {dur:.1f}s / {size_mb:.1f} MB → {FINAL_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
