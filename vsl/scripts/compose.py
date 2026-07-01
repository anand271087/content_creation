"""
vsl/scripts/compose.py
Compose the final ZeroHands VSL 1920x1080 mp4 from:
  - vsl/assets/avatar/<segment>.mp4   (HeyGen avatar renders with branded gradient bg)
  - vsl/assets/slides/<slide_id>.mp4   (Hyperframes slide motion graphics)
  - vsl/assets/screenrec/*             (Instagram + HeyGen + ElevenLabs walkthroughs)
  - vsl/segments.json                  (order, look, visual mode, slide_ids, recordings)
  - vsl/slide_specs.json               (slide timings)
  - vsl/creative_direction.md          (visual rulebook — baked into this script)

Visual modes:
  - full_screen_text       : full-screen slide; NO avatar visible. (hook, objection)
  - pip_over_slide         : avatar PIP bottom-left over the slide(s). (body teaching)
  - screen_share_with_pip  : screen recording full-screen with avatar PIP top-right.
  - full_face              : avatar full-screen, no slides, no PIP. (gap, offer, CTA, outro)

Title cards (TC_*): 1.2s hard-cut chapter markers inserted before segments that declare title_card_before.

Reveal moment: at the hook reveal sentence, hard audio cut 0.4s + zoom-in punch on avatar.
Pitch pivot: at the gap segment start, hard audio cut 0.6s.
Captions: Whisper word-aligned, 2-line layout, brand-blue keyword highlight.

Output: vsl/output/zerohands_vsl_16x9.mp4   (1920x1080, H.264, AAC, 30fps)
"""
from __future__ import annotations
import argparse, json, logging, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT          = Path(__file__).resolve().parent.parent
SEGMENTS_FILE = ROOT / "segments.json"
SLIDE_SPECS   = ROOT / "slide_specs.json"
AVATAR_DIR    = ROOT / "assets" / "avatar"
SLIDES_DIR    = ROOT / "assets" / "slides"
SCREENREC_DIR = ROOT / "assets" / "screenrec"
CAPTIONS_DIR  = ROOT / "assets" / "captions"
TMP_DIR       = ROOT / "assets" / "compose_tmp"
OUT_FILE      = ROOT / "output" / "zerohands_vsl_16x9.mp4"
LOG_FILE      = ROOT.parent / "logs" / "vsl_compose.log"

W, H = 1920, 1080
FPS  = 30

# PIP geometry — bottom-RIGHT, head-and-shoulders crop only.
# Slide templates have padding-right to keep their content out of this zone.
PIP_W,  PIP_H  = 320, 252            # 1.27 aspect — matches head-crop
PIP_X,  PIP_Y  = W - PIP_W - 32, H - PIP_H - 32

# Smaller PIP (top-right) when over a screen recording
PIPS_W, PIPS_H = 320, 252
PIPS_X, PIPS_Y = W - PIPS_W - 32, 32

# Head-crop region in the 1920x1080 HeyGen output — v5c: crop starts AT the hairline
# (was starting 50px above, leaving empty space at top of PIP). Hairline now touches
# the very top of the PIP box per user feedback.
HEAD_CROP_W, HEAD_CROP_H = 420, 330  # 1.272 aspect, matches PIP 320:252
HEAD_CROP_X, HEAD_CROP_Y = 755, 245  # crop starts exactly at hairline (Y shifted down +50)

# Reveal moment — within the hook segment's spoken text
REVEAL_TRIGGER_TEXT = "wasn't me"   # the sentence where the reveal lands

# Pitch pivot — at the gap segment start, hard audio cut for N seconds
PITCH_PIVOT_SILENCE_SEC = 0.6

# Caption style — long-form YouTube (NOT Hormozi reel style)
CAPTION_FONT_NAME = "Inter"           # falls back to Helvetica if Inter not installed
CAPTION_FONT_SIZE = 48                # smaller so it doesn't dominate the slide
CAPTION_OUTLINE_PX = 3
CAPTION_MARGIN_V = 56                 # px from bottom — sits below the slide content area
CAPTION_BOX_PADDING_X = 28            # box padding around the text horizontally
CAPTION_BOX_PADDING_Y = 18            # box padding around the text vertically
CAPTION_WORDS_PER_LINE_MAX = 7
CAPTION_CHARS_PER_LINE_MAX = 34
CAPTION_LINES_PER_BLOCK = 2
CAPTION_BLOCK_MIN_SEC = 0.9
CAPTION_BLOCK_MAX_SEC = 4.5

# Brand-blue keyword highlight — ASS uses BGR, so #2979ff → BGR ff7929
BRAND_BLUE_ASS = "&H00FF7929&"
WHITE_ASS      = "&H00FFFFFF&"
BLACK_ASS      = "&H00000000&"
SHADOW_ASS     = "&H80000000&"

# A noun-ish heuristic: prefer highlighting these kinds of words
HIGHLIGHT_HINTS = {
    # brand / tool names
    "claude","heygen","elevenlabs","manychat","n8n","zerohands","gpt","ai","instagram","youtube","calendly",
    # value words
    "free","every","never","stop","build","scale","clone","unlimited","funnel","booked","calls","leads","camera",
    "30+","daily","weekly","monthly",
}
WORD_CLEAN_RE = re.compile(r"[^A-Za-z0-9+#]")

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("vsl_compose")
logger.setLevel(logging.DEBUG)
_fmt = logging.Formatter("%(asctime)s [vsl_compose] %(levelname)s %(message)s")
_fh = logging.FileHandler(LOG_FILE); _fh.setFormatter(_fmt); logger.addHandler(_fh)
_sh = logging.StreamHandler(sys.stdout); _sh.setFormatter(_fmt); logger.addHandler(_sh)


# ── Caption helpers ─────────────────────────────────────────────────────────
def _seconds_to_ass(t: float) -> str:
    """ASS time format: H:MM:SS.cs"""
    if t < 0: t = 0
    h = int(t // 3600); t -= h * 3600
    m = int(t // 60);   t -= m * 60
    s = int(t)
    cs = int(round((t - s) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _flatten_words(captions_json: dict) -> list[dict]:
    """Pull every word with start/end from Whisper-shaped JSON."""
    out = []
    for seg in captions_json.get("segments", []):
        for w in seg.get("words", []) or []:
            txt = (w.get("word") or w.get("text") or "").strip()
            if not txt:
                continue
            try:
                start = float(w["start"]); end = float(w["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if end <= start:
                continue
            out.append({"word": txt, "start": start, "end": end})
    return out


def _pick_highlight_index(words_in_line: list[dict]) -> int:
    """Pick a single word in the line to highlight in brand blue."""
    best_i, best_score = 0, -1
    for i, w in enumerate(words_in_line):
        clean = WORD_CLEAN_RE.sub("", w["word"]).lower()
        if not clean:
            continue
        score = 0
        if clean in HIGHLIGHT_HINTS: score += 100
        if clean.isupper() or clean.istitle(): score += 5
        if any(ch.isdigit() for ch in clean): score += 8
        score += len(clean) // 2
        if score > best_score:
            best_score, best_i = score, i
    return best_i


def _group_into_blocks(words: list[dict]) -> list[dict]:
    """Group flat words into caption blocks (1-2 lines, each up to 6 words)."""
    blocks = []
    if not words:
        return blocks
    i = 0
    while i < len(words):
        block_lines: list[list[dict]] = []
        block_start = words[i]["start"]
        # Build up to CAPTION_LINES_PER_BLOCK lines
        while len(block_lines) < CAPTION_LINES_PER_BLOCK and i < len(words):
            line: list[dict] = []
            char_count = 0
            while (i < len(words)
                   and len(line) < CAPTION_WORDS_PER_LINE_MAX
                   and char_count + len(words[i]["word"]) + 1 <= CAPTION_CHARS_PER_LINE_MAX):
                line.append(words[i])
                char_count += len(words[i]["word"]) + 1
                # Break on sentence-ending punctuation to align with natural pauses
                if line[-1]["word"].endswith((".", "?", "!")):
                    i += 1
                    break
                i += 1
            if not line:
                break
            block_lines.append(line)
            # Stop adding lines if last word ended a sentence
            if block_lines[-1][-1]["word"].endswith((".", "?", "!")):
                break
        if not block_lines:
            break
        block_end = block_lines[-1][-1]["end"]
        # Clamp block duration to [min, max]
        dur = block_end - block_start
        if dur < CAPTION_BLOCK_MIN_SEC:
            block_end = block_start + CAPTION_BLOCK_MIN_SEC
        if dur > CAPTION_BLOCK_MAX_SEC:
            block_end = block_start + CAPTION_BLOCK_MAX_SEC
        blocks.append({"start": block_start, "end": block_end, "lines": block_lines})
    return blocks


def _ass_line(line: list[dict]) -> str:
    """Render a single line as ASS text with one brand-blue highlight."""
    hi = _pick_highlight_index(line)
    parts = []
    for i, w in enumerate(line):
        word = w["word"]
        if i == hi:
            parts.append("{\\c" + BRAND_BLUE_ASS[2:-1] + "&}" + word + "{\\c" + WHITE_ASS[2:-1] + "&}")
        else:
            parts.append(word)
    return " ".join(parts)


def build_ass_for_segment(captions_json_path: Path, ass_out_path: Path) -> bool:
    """Build an .ass subtitle file from the segment's caption JSON. Return False if empty."""
    if not captions_json_path.exists():
        return False
    cap = json.loads(captions_json_path.read_text())
    words = _flatten_words(cap)
    if not words:
        return False
    blocks = _group_into_blocks(words)
    if not blocks:
        return False

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {W}\n"
        f"PlayResY: {H}\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
        "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{CAPTION_FONT_NAME},{CAPTION_FONT_SIZE},"
        f"{WHITE_ASS},{WHITE_ASS},{BLACK_ASS},{SHADOW_ASS},"
        f"-1,0,0,0,100,100,0,0,1,{CAPTION_OUTLINE_PX},2,2,80,80,{CAPTION_MARGIN_V},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    lines_out = [header]
    for blk in blocks:
        ass_text = "\\N".join(_ass_line(line) for line in blk["lines"])
        lines_out.append(
            f"Dialogue: 0,{_seconds_to_ass(blk['start'])},{_seconds_to_ass(blk['end'])},"
            f"Default,,0,0,0,,{ass_text}\n"
        )
    ass_out_path.write_text("".join(lines_out))
    return True


CAPTION_FONT_FILE = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def _drawtext_escape(s: str) -> str:
    """Escape a string for ffmpeg drawtext text= param."""
    # Escape backslash → \\, then: colon, single quote, comma, brackets
    return (s.replace("\\", "\\\\")
             .replace(":", "\\:")
             .replace("'", "\\'")
             .replace(",", "\\,")
             .replace("[", "\\[")
             .replace("]", "\\]")
             .replace("%", "\\%"))


def _escape_filter_path(p: Path) -> str:
    """Escape a filesystem path for ffmpeg filtergraph (textfile=, fontfile= etc.)."""
    return (str(p)
            .replace("\\", "\\\\")
            .replace(":", "\\:")
            .replace(",", "\\,")
            .replace("'", "\\'")
            .replace(" ", "\\ "))


def burn_captions(in_video: Path, blocks: list[dict], out_video: Path, tmp_dir: Path) -> Path:
    """
    Burn caption blocks via chained ffmpeg drawtext filters.

    Each block is rendered as a single drawtext with timing gated by enable=between.
    Text is written to a per-block .txt file so we don't have to escape apostrophes,
    quotes, or special characters in the filtergraph.
    """
    if not blocks:
        run_ff(["ffmpeg", "-y", "-i", str(in_video),
                "-c", "copy", str(out_video)],
               f"copy:{in_video.stem}")
        return out_video

    # Use a font path without spaces if possible; otherwise escape the space.
    candidate_fonts = [
        Path(CAPTION_FONT_FILE),
        Path("/System/Library/Fonts/Helvetica.ttc"),
        Path("/System/Library/Fonts/HelveticaNeue.ttc"),
    ]
    chosen_font = next((p for p in candidate_fonts if p.exists()), None)
    if chosen_font is None:
        logger.warning("no suitable font found — captions disabled")
        run_ff(["ffmpeg", "-y", "-i", str(in_video),
                "-c", "copy", str(out_video)], f"copy:{in_video.stem}")
        return out_video
    font_arg = f"fontfile={_escape_filter_path(chosen_font)}"

    drawtext_chain = []
    cap_subdir = tmp_dir / f"{in_video.stem}_caps"
    cap_subdir.mkdir(parents=True, exist_ok=True)

    for bi, blk in enumerate(blocks):
        # Plain-text caption: 1-2 lines, words joined by spaces, lines by \n
        lines = []
        for line in blk["lines"]:
            words = [w["word"] for w in line]
            lines.append(" ".join(words))
        text = "\n".join(lines)
        txt_path = cap_subdir / f"blk_{bi:03d}.txt"
        txt_path.write_text(text, encoding="utf-8")
        txtfile_arg = _escape_filter_path(txt_path)

        start = max(0.0, float(blk["start"]))
        end   = max(start + 0.1, float(blk["end"]))

        drawtext_chain.append(
            f"drawtext={font_arg}:textfile={txtfile_arg}"
            f":fontsize={CAPTION_FONT_SIZE}"
            f":fontcolor=white"
            f":bordercolor=black@0.92"
            f":borderw={CAPTION_OUTLINE_PX}"
            f":box=1"
            f":boxcolor=black@0.68"
            f":boxborderw={CAPTION_BOX_PADDING_Y}|{CAPTION_BOX_PADDING_X}"
            f":line_spacing=12"
            f":x=(w-text_w)/2"
            f":y=h-text_h-{CAPTION_MARGIN_V}"
            f":enable=between(t\\,{start:.2f}\\,{end:.2f})"   # no single quotes — escape commas only
        )

    vf = ",".join(drawtext_chain)
    run_ff(["ffmpeg", "-y", "-i", str(in_video),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "copy",
            str(out_video)],
           f"burn_captions:{in_video.stem}")
    return out_video


def run_ff(cmd: list[str], label: str = "") -> None:
    """Run ffmpeg cmd, raise on failure. Logs the command at debug."""
    pretty = " ".join(cmd[:8]) + (" ..." if len(cmd) > 8 else "")
    logger.debug("ffmpeg [%s]: %s", label, pretty)
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        logger.error("ffmpeg failed [%s] exit=%d", label, res.returncode)
        logger.error("stderr tail:\n%s", res.stderr[-2000:])
        raise RuntimeError(f"ffmpeg failed: {label}")


def probe_duration(p: Path) -> float:
    if not p.exists():
        return 0.0
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
        capture_output=True, text=True,
    )
    try:
        return float(res.stdout.strip() or 0)
    except ValueError:
        return 0.0


def build_full_screen_text_segment(seg: dict, slides_for_seg: list[Path], avatar_path: Path,
                                   out_path: Path, tmp: Path) -> Path:
    """
    HYBRID HOOK MODE — alternate full-screen avatar chunks with full-screen text slides.

    Strategy:
      - Total segment duration = avatar audio length (we never cut the audio).
      - Split that duration into N+1 chunks where N = number of slides for this seg.
      - Odd chunks show the AVATAR (full-screen with blurred-extended backdrop).
      - Even chunks show the next SLIDE in sequence.
      - Hard cuts only — no transitions. Reads as fast-cut hook editing.

    Result for the hook (audio ≈ 21s, 3 slides H1/H2/H3):
      0.0–3.0s  : avatar
      3.0–6.0s  : H1 slide
      6.0–9.0s  : avatar
      9.0–12.0s : H2 slide
      12.0–15.0s: avatar
      15.0–18.0s: H3 slide
      18.0–21.0s: avatar (the reveal)
    """
    # 1. Extract avatar audio (full segment audio is the timing master)
    avatar_audio = tmp / f"{seg['id']}_audio.wav"
    run_ff(["ffmpeg", "-y", "-i", str(avatar_path), "-vn", "-acodec", "pcm_s16le",
            "-ar", "48000", "-ac", "2", str(avatar_audio)], f"{seg['id']}.extract_audio")
    audio_dur = probe_duration(avatar_audio)

    # 2. Build the full-face-styled avatar source — aggressive zoom-fill (no side bars).
    avatar_ff = tmp / f"{seg['id']}_avatar_ff.mp4"
    STRIP_W = 1200
    STRIP_X = (W - STRIP_W) // 2
    SCALED_H = int(round(H * W / STRIP_W))
    FACE_CENTRE_Y = int(round(400 * W / STRIP_W))
    CROP_TOP = max(0, min(SCALED_H - H, FACE_CENTRE_Y - H // 2))
    fc_avatar = (
        f"[0:v]crop={STRIP_W}:{H}:{STRIP_X}:0,"
        f"scale={W}:{SCALED_H}:flags=lanczos,"
        f"crop={W}:{H}:0:{CROP_TOP}[outv]"
    )
    run_ff(["ffmpeg", "-y", "-i", str(avatar_path),
            "-filter_complex", fc_avatar, "-map", "[outv]",
            "-an",      # we'll add audio after stitching
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            str(avatar_ff)], f"{seg['id']}.avatar_full_face")

    # 3. Plan chunks: avatar, slide1, avatar, slide2, ..., avatar
    n_slides = max(1, len(slides_for_seg))
    n_avatars = n_slides + 1
    total_chunks = n_avatars + n_slides
    # Avatar chunks get slightly more time than slide chunks; weights 1.0 avatar, 0.9 slide
    weight_avatar, weight_slide = 1.0, 0.9
    total_weight = weight_avatar * n_avatars + weight_slide * n_slides
    avatar_chunk = audio_dur * (weight_avatar / total_weight)
    slide_chunk  = audio_dur * (weight_slide  / total_weight)
    logger.info("[%s] hybrid hook — audio=%.2fs, %d avatar chunks of %.2fs + %d slide chunks of %.2fs",
                seg["id"], audio_dur, n_avatars, avatar_chunk, n_slides, slide_chunk)

    pieces = []
    cursor = 0.0
    avatar_dur_src = probe_duration(avatar_ff)
    for i in range(total_chunks):
        is_avatar = (i % 2 == 0)
        dur = avatar_chunk if is_avatar else slide_chunk
        # clamp last chunk so total matches audio_dur
        if i == total_chunks - 1:
            dur = max(0.5, audio_dur - cursor)

        out = tmp / f"{seg['id']}_chunk{i:02d}.mp4"
        if is_avatar:
            # Pull a slice of the full-face avatar starting at `cursor` — stays in sync with audio.
            start = min(cursor, max(0.0, avatar_dur_src - dur))
            run_ff(["ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(avatar_ff),
                    "-t", f"{dur:.3f}",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-an", "-r", str(FPS),
                    str(out)], f"{seg['id']}.chunk{i}_avatar")
        else:
            slide_idx = (i - 1) // 2
            sp = slides_for_seg[min(slide_idx, n_slides - 1)]
            run_ff(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(sp),
                    "-t", f"{dur:.3f}",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-an", "-r", str(FPS),
                    str(out)], f"{seg['id']}.chunk{i}_slide{slide_idx}")
        pieces.append(out)
        cursor += dur

    # 4. Concat all chunks (video only)
    concat_txt = tmp / f"{seg['id']}_chunks_concat.txt"
    concat_txt.write_text("\n".join(f"file '{p}'" for p in pieces))
    concat_v = tmp / f"{seg['id']}_video.mp4"
    run_ff(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
            "-c", "copy", str(concat_v)], f"{seg['id']}.chunks_concat")

    # 5. Mux avatar audio
    run_ff(["ffmpeg", "-y", "-i", str(concat_v), "-i", str(avatar_audio),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
            str(out_path)], f"{seg['id']}.mux")
    return out_path


def build_pip_over_slide_segment(seg: dict, slides_for_seg: list[Path], avatar_path: Path,
                                 out_path: Path, tmp: Path) -> Path:
    """Avatar PIP bottom-left over slide(s). Slides cycle through segment duration."""
    avatar_dur = probe_duration(avatar_path)
    if not slides_for_seg:
        logger.warning("[%s] pip_over_slide but no slides — falling back to full_face", seg["id"])
        return build_full_face_segment(seg, avatar_path, out_path, tmp)

    # Build the slide background track (concat, looped to match avatar duration)
    per_slide = avatar_dur / max(1, len(slides_for_seg))
    looped = []
    for i, sp in enumerate(slides_for_seg):
        out = tmp / f"{seg['id']}_slide{i}.mp4"
        run_ff(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(sp),
                "-t", f"{per_slide:.3f}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", str(FPS), str(out)],
               f"{seg['id']}.slide{i}")
        looped.append(out)
    concat_file = tmp / f"{seg['id']}_slides_concat.txt"
    concat_file.write_text("\n".join(f"file '{p}'" for p in looped))
    slides_bg = tmp / f"{seg['id']}_bg.mp4"
    run_ff(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c", "copy", str(slides_bg)], f"{seg['id']}.bg_concat")

    # Head-crop the avatar to just face/upper-shoulders, then scale to PIP size,
    # round corners (mask with rounded-rect alpha), and overlay bottom-right.
    filter_complex = (
        f"[1:v]crop={HEAD_CROP_W}:{HEAD_CROP_H}:{HEAD_CROP_X}:{HEAD_CROP_Y},"
        f"scale={PIP_W}:{PIP_H}:flags=lanczos,format=yuva420p[pip_raw];"
        # Subtle brand-blue stroke around the PIP for separation from the slide
        f"[pip_raw]pad={PIP_W+6}:{PIP_H+6}:3:3:color=0x2979ff[pip];"
        f"[0:v][pip]overlay={PIP_X-3}:{PIP_Y-3}:shortest=1[outv]"
    )
    run_ff(["ffmpeg", "-y", "-i", str(slides_bg), "-i", str(avatar_path),
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", "1:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-shortest", str(out_path)],
           f"{seg['id']}.pip")
    return out_path


def _flatten_caption_words(seg_id: str) -> list[tuple[str, float, float]] | None:
    """Load Scribe JSON for a segment, return [(clean_word, start, end), ...]. None if missing."""
    cap_json = CAPTIONS_DIR / f"{seg_id}.json"
    if not cap_json.exists():
        return None
    try:
        cap = json.loads(cap_json.read_text())
    except Exception:
        return None
    out = []
    for s in cap.get("segments", []):
        for w in s.get("words", []) or []:
            t = (w.get("word") or w.get("text") or "").strip().lower()
            try:
                ts = float(w["start"]); te = float(w["end"])
            except (KeyError, TypeError, ValueError):
                continue
            cw = re.sub(r"[^a-z0-9]", "", t)
            if cw:
                out.append((cw, ts, te))
    return out


def _find_first_phrase(words: list[tuple[str, float, float]], target_tokens: list[str],
                      start_after: float = 0.0) -> float | None:
    """Find timestamp where the FIRST word of the matching phrase starts.

    target_tokens is a list of consecutive clean-word forms — e.g. ["let","me","show"].
    Returns the start of the first token of the first match (with start >= start_after),
    or None if not found.
    """
    for i in range(len(words) - len(target_tokens) + 1):
        if all(words[i + j][0] == target_tokens[j] for j in range(len(target_tokens))):
            if words[i][1] >= start_after:
                return words[i][1]
    return None


def _build_value_step2_clone_segment(seg: dict, slides_for_seg: list[Path],
                                     avatar_path: Path, out_path: Path, tmp: Path) -> Path:
    """
    Special-case 3-phase builder for value_step2_clone:
      Phase A (0 → T_show):    avatar PIP over slide B9 (tool explanations)
      Phase B (T_show → T_mid): HeyGen recording, with LAST 3s = Heygen_part2.mov
      Phase C (T_mid → T_end):  ElevenLabs recording
    """
    avatar_dur = probe_duration(avatar_path)
    words = _flatten_caption_words(seg["id"])
    if not words:
        logger.warning("[%s] no Scribe captions — falling back to generic screen_share", seg["id"])
        # Fall through to generic builder by calling the standard implementation
        return _build_screen_share_with_pip_generic(seg, slides_for_seg, avatar_path, out_path, tmp)

    # Locate the transition cue ("let me quickly show" or "let me show")
    t_show = (_find_first_phrase(words, ["let", "me", "quickly", "show"]) or
              _find_first_phrase(words, ["let", "me", "show"]) or
              _find_first_phrase(words, ["quickly", "show"]))
    if t_show is None:
        # Try "show you"
        t_show = _find_first_phrase(words, ["show", "you"])
    # If still missing, fall back to 70% of segment (rough cue)
    if t_show is None:
        t_show = avatar_dur * 0.62

    last_word_end = max((te for _, _, te in words), default=avatar_dur)
    t_end = min(avatar_dur, last_word_end + 0.4)

    # Split recordings 50/50 between t_show and t_end
    t_mid = t_show + (t_end - t_show) * 0.55   # slight bias toward HeyGen (richer visual)
    phase_a_dur = max(2.0, t_show)
    phase_b_dur = max(2.0, t_mid - t_show)
    phase_c_dur = max(2.0, t_end - t_mid)

    logger.info("[%s] 3-phase plan: A=0-%.2f (slide+PIP), B=%.2f-%.2f (HeyGen), C=%.2f-%.2f (ElevenLabs)",
                seg["id"], t_show, t_show, t_mid, t_mid, t_end)

    # ── Build avatar audio (full, with silence beyond t_end trimmed off) ──
    avatar_trimmed = tmp / f"{seg['id']}_avatar_trim.mp4"
    run_ff(["ffmpeg", "-y", "-i", str(avatar_path),
            "-t", f"{t_end:.3f}",
            "-c", "copy", str(avatar_trimmed)], f"{seg['id']}.avatar_trim")

    # ── Slice the avatar mp4 into 3 chunks (each carries its own audio) ──
    chunks = []
    cur = 0.0
    for label, dur in [("A", phase_a_dur), ("B", phase_b_dur), ("C", phase_c_dur)]:
        chunk = tmp / f"{seg['id']}_chunk{label}.mp4"
        run_ff(["ffmpeg", "-y", "-ss", f"{cur:.3f}", "-i", str(avatar_trimmed),
                "-t", f"{dur:.3f}",
                "-c", "copy", str(chunk)], f"{seg['id']}.chunk_{label}_slice")
        chunks.append(chunk)
        cur += dur

    a_avatar, b_avatar, c_avatar = chunks

    # ── Phase A: avatar PIP over slide (the B9 slide), durations matched ──
    slide_path = slides_for_seg[0] if slides_for_seg else None
    phase_a_out = tmp / f"{seg['id']}_phaseA.mp4"
    if slide_path and slide_path.exists():
        # Build a slide-bg of phase_a_dur
        slide_bg = tmp / f"{seg['id']}_phaseA_bg.mp4"
        run_ff(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(slide_path),
                "-t", f"{phase_a_dur:.3f}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", str(FPS), str(slide_bg)],
               f"{seg['id']}.phaseA_bg")
        # Overlay head-crop PIP bottom-right
        filter_complex = (
            f"[1:v]crop={HEAD_CROP_W}:{HEAD_CROP_H}:{HEAD_CROP_X}:{HEAD_CROP_Y},"
            f"scale={PIP_W}:{PIP_H}:flags=lanczos,format=yuva420p[pip_raw];"
            f"[pip_raw]pad={PIP_W+6}:{PIP_H+6}:3:3:color=0x2979ff[pip];"
            f"[0:v][pip]overlay={PIP_X-3}:{PIP_Y-3}:shortest=1[outv]"
        )
        run_ff(["ffmpeg", "-y", "-i", str(slide_bg), "-i", str(a_avatar),
                "-filter_complex", filter_complex,
                "-map", "[outv]", "-map", "1:a?",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                "-shortest", str(phase_a_out)], f"{seg['id']}.phaseA_pip")
    else:
        # No slide available — fall back to full-face avatar for phase A
        logger.warning("[%s] phase A — no slide, using full_face avatar", seg["id"])
        STRIP_W = 1200
        STRIP_X = (W - STRIP_W) // 2
        SCALED_H = int(round(H * W / STRIP_W))
        FACE_CENTRE_Y = int(round(400 * W / STRIP_W))
        CROP_TOP = max(0, min(SCALED_H - H, FACE_CENTRE_Y - H // 2))
        fc = (f"[0:v]crop={STRIP_W}:{H}:{STRIP_X}:0,"
              f"scale={W}:{SCALED_H}:flags=lanczos,"
              f"crop={W}:{H}:0:{CROP_TOP}[outv]")
        run_ff(["ffmpeg", "-y", "-i", str(a_avatar),
                "-filter_complex", fc, "-map", "[outv]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                str(phase_a_out)], f"{seg['id']}.phaseA_fullface")

    # ── Phase B: HeyGen recordings (Heygen_part1 + last 3s = Heygen_part2), avatar PIP ──
    phase_b_out = tmp / f"{seg['id']}_phaseB.mp4"
    part1_path = SCREENREC_DIR / "Heygen_part1.mov"
    part2_path = SCREENREC_DIR / "Heygen_part2.mov"
    PART2_TAIL_SEC = 3.0  # last 3s of phase B = part2 footage (your avatars only)

    if part1_path.exists() and part2_path.exists() and phase_b_dur > PART2_TAIL_SEC + 1:
        # Part 1 segment: phase_b_dur - 3 seconds. Speed-up trimmed source to fit.
        p1_window = phase_b_dur - PART2_TAIL_SEC
        # Trim part1 to (window * 2x cap) seconds, then play at adjusted speed
        p1_raw_dur = probe_duration(part1_path)
        p1_speed = min(2.0, max(1.0, p1_raw_dur / p1_window))
        p1_src_trim = p1_window * p1_speed if p1_speed > 1.0 else min(p1_raw_dur, p1_window)
        p1_chunk = tmp / f"{seg['id']}_phaseB_p1.mp4"
        run_ff(["ffmpeg", "-y", "-i", str(part1_path),
                "-t", f"{p1_src_trim:.3f}",
                "-an", "-vf", f"setpts=PTS/{p1_speed},scale={W}:{H}:force_original_aspect_ratio=decrease,"
                              f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,fps={FPS}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-t", f"{p1_window:.3f}", str(p1_chunk)],
               f"{seg['id']}.phaseB_p1")

        # Part 2 chunk: show the user's avatar library at the START of part2.
        # (The "My Avatars" grid with Anand-Grey / Anand-Blue-White / Anand-K / etc.
        # lives in the first ~10s of part2 — pulling from p2_start=0 is correct.)
        p2_raw_dur = probe_duration(part2_path)
        p2_speed = min(2.0, max(1.0, p2_raw_dur / PART2_TAIL_SEC))
        p2_start = 0.0     # ← start of part2 = the avatar library page
        p2_chunk = tmp / f"{seg['id']}_phaseB_p2.mp4"
        run_ff(["ffmpeg", "-y", "-ss", f"{p2_start:.3f}", "-i", str(part2_path),
                "-t", f"{PART2_TAIL_SEC * p2_speed:.3f}",
                "-an", "-vf", f"setpts=PTS/{p2_speed},scale={W}:{H}:force_original_aspect_ratio=decrease,"
                              f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,fps={FPS}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-t", f"{PART2_TAIL_SEC:.3f}", str(p2_chunk)],
               f"{seg['id']}.phaseB_p2")

        # Concat p1 + p2
        b_bg_concat = tmp / f"{seg['id']}_phaseB_concat.txt"
        b_bg_concat.write_text(f"file '{p1_chunk}'\nfile '{p2_chunk}'\n")
        b_bg = tmp / f"{seg['id']}_phaseB_bg.mp4"
        run_ff(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(b_bg_concat),
                "-c", "copy", str(b_bg)], f"{seg['id']}.phaseB_bg_concat")

        # Overlay avatar PIP top-right
        filter_complex = (
            f"[1:v]crop={HEAD_CROP_W}:{HEAD_CROP_H}:{HEAD_CROP_X}:{HEAD_CROP_Y},"
            f"scale={PIPS_W}:{PIPS_H}:flags=lanczos,format=yuva420p[pip_raw];"
            f"[pip_raw]pad={PIPS_W+6}:{PIPS_H+6}:3:3:color=0x2979ff[pip];"
            f"[0:v][pip]overlay={PIPS_X-3}:{PIPS_Y-3}:shortest=1[outv]"
        )
        run_ff(["ffmpeg", "-y", "-i", str(b_bg), "-i", str(b_avatar),
                "-filter_complex", filter_complex,
                "-map", "[outv]", "-map", "1:a?",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                "-shortest", str(phase_b_out)], f"{seg['id']}.phaseB_pip")
    else:
        logger.warning("[%s] phase B — missing part1/part2 — falling back to full_face", seg["id"])
        # full_face fallback
        STRIP_W = 1200
        STRIP_X = (W - STRIP_W) // 2
        SCALED_H = int(round(H * W / STRIP_W))
        FACE_CENTRE_Y = int(round(400 * W / STRIP_W))
        CROP_TOP = max(0, min(SCALED_H - H, FACE_CENTRE_Y - H // 2))
        fc = (f"[0:v]crop={STRIP_W}:{H}:{STRIP_X}:0,scale={W}:{SCALED_H}:flags=lanczos,"
              f"crop={W}:{H}:0:{CROP_TOP}[outv]")
        run_ff(["ffmpeg", "-y", "-i", str(b_avatar), "-filter_complex", fc,
                "-map", "[outv]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                str(phase_b_out)], f"{seg['id']}.phaseB_fullface")

    # ── Phase C: ElevenLabs recording, avatar PIP ──
    phase_c_out = tmp / f"{seg['id']}_phaseC.mp4"
    eleven_path = SCREENREC_DIR / "eleven_labs.mov"
    if eleven_path.exists():
        e_raw_dur = probe_duration(eleven_path)
        e_speed = min(2.0, max(1.0, e_raw_dur / phase_c_dur))
        e_src_trim = phase_c_dur * e_speed if e_speed > 1.0 else min(e_raw_dur, phase_c_dur)
        c_bg = tmp / f"{seg['id']}_phaseC_bg.mp4"
        run_ff(["ffmpeg", "-y", "-i", str(eleven_path),
                "-t", f"{e_src_trim:.3f}",
                "-an", "-vf", f"setpts=PTS/{e_speed},scale={W}:{H}:force_original_aspect_ratio=decrease,"
                              f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,fps={FPS}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-t", f"{phase_c_dur:.3f}", str(c_bg)],
               f"{seg['id']}.phaseC_bg")
        filter_complex = (
            f"[1:v]crop={HEAD_CROP_W}:{HEAD_CROP_H}:{HEAD_CROP_X}:{HEAD_CROP_Y},"
            f"scale={PIPS_W}:{PIPS_H}:flags=lanczos,format=yuva420p[pip_raw];"
            f"[pip_raw]pad={PIPS_W+6}:{PIPS_H+6}:3:3:color=0x2979ff[pip];"
            f"[0:v][pip]overlay={PIPS_X-3}:{PIPS_Y-3}:shortest=1[outv]"
        )
        run_ff(["ffmpeg", "-y", "-i", str(c_bg), "-i", str(c_avatar),
                "-filter_complex", filter_complex,
                "-map", "[outv]", "-map", "1:a?",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                "-shortest", str(phase_c_out)], f"{seg['id']}.phaseC_pip")
    else:
        logger.warning("[%s] phase C — missing eleven_labs.mov — fallback full_face", seg["id"])
        STRIP_W = 1200
        STRIP_X = (W - STRIP_W) // 2
        SCALED_H = int(round(H * W / STRIP_W))
        FACE_CENTRE_Y = int(round(400 * W / STRIP_W))
        CROP_TOP = max(0, min(SCALED_H - H, FACE_CENTRE_Y - H // 2))
        fc = (f"[0:v]crop={STRIP_W}:{H}:{STRIP_X}:0,scale={W}:{SCALED_H}:flags=lanczos,"
              f"crop={W}:{H}:0:{CROP_TOP}[outv]")
        run_ff(["ffmpeg", "-y", "-i", str(c_avatar), "-filter_complex", fc,
                "-map", "[outv]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                str(phase_c_out)], f"{seg['id']}.phaseC_fullface")

    # ── Concat phases A + B + C ──
    final_concat_txt = tmp / f"{seg['id']}_final_concat.txt"
    final_concat_txt.write_text(f"file '{phase_a_out}'\nfile '{phase_b_out}'\nfile '{phase_c_out}'\n")
    run_ff(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(final_concat_txt),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            str(out_path)], f"{seg['id']}.concat_phases")
    return out_path


def _build_screen_share_with_pip_generic(seg: dict, slides_for_seg: list[Path],
                                         avatar_path: Path, out_path: Path, tmp: Path) -> Path:
    """Original (pre-3-phase) screen_share_with_pip logic — used by `proof` and as fallback."""
    return build_screen_share_with_pip_segment(seg, slides_for_seg, avatar_path, out_path, tmp)


def _compute_screen_share_split_points(seg_id: str, rec_groups: list[dict],
                                       avatar_dur: float) -> list[float] | None:
    """
    For screen_share_with_pip segments with multiple recording groups, use the Scribe
    caption JSON to find when the avatar transitions between topics (e.g. HeyGen →
    ElevenLabs). Returns a list of per-group durations that align the recording switch
    with the spoken transition.

    Returns None if captions are unavailable or transition words can't be found —
    caller falls back to even split.
    """
    cap_json = CAPTIONS_DIR / f"{seg_id}.json"
    if not cap_json.exists():
        return None
    try:
        cap = json.loads(cap_json.read_text())
    except Exception:
        return None

    # Build a flat word list with timestamps
    words = []
    for s in cap.get("segments", []):
        for w in s.get("words", []) or []:
            t = (w.get("word") or w.get("text") or "").strip().lower()
            try:
                start = float(w["start"])
            except (KeyError, TypeError, ValueError):
                continue
            if t:
                words.append((re.sub(r"[^a-z0-9]", "", t), start))
    if not words:
        return None

    # For value_step2_clone: switch HeyGen → ElevenLabs at the first mention of
    # "voice" or "elevenlabs" — the avatar says "For your voice, you use ElevenLabs".
    group_labels = [g.get("label", "") for g in rec_groups]
    if len(rec_groups) == 2 and "heygen" in group_labels[0].lower() and ("eleven" in group_labels[1].lower() or "voice" in group_labels[1].lower()):
        # Find the FIRST occurrence of "voice" or "elevenlabs" — that's the switch point
        switch_t = None
        for w, t in words:
            if w in ("voice", "elevenlabs", "eleven"):
                switch_t = t
                break
        if switch_t is None:
            return None
        # Trim so the second group's window ends BEFORE the avatar finishes the segment.
        # avatar_dur includes a small tail of silence after the last word; trim a bit.
        last_word_end = max((t for _, t in words), default=avatar_dur)
        # Stop the ElevenLabs visual ~0.6s after the last spoken word (matches natural cadence)
        end_t = min(avatar_dur, last_word_end + 0.6)
        heygen_dur = max(2.0, switch_t)
        eleven_dur = max(2.0, end_t - switch_t)
        logger.info("[%s] Scribe split: HeyGen 0.0–%.2fs, ElevenLabs %.2f–%.2fs",
                    seg_id, heygen_dur, switch_t, switch_t + eleven_dur)
        return [heygen_dur, eleven_dur]
    return None


def build_screen_share_with_pip_segment(seg: dict, slides_for_seg: list[Path],
                                        avatar_path: Path, out_path: Path, tmp: Path) -> Path:
    """
    Screen recording full-screen + avatar PIP top-right.
    For value_step2_clone there's a group spec — stitch in order, speed-up to fit avatar duration.
    For proof — one phone recording, vertically centered with brand padding.
    """
    avatar_dur = probe_duration(avatar_path)
    rec_groups = seg.get("screen_recording_groups") or [{
        "label": "main",
        "files": (seg["screen_recording"] if isinstance(seg["screen_recording"], list)
                  else [seg["screen_recording"]]),
    }]

    # Build a single "screen content" mp4 to underlay.
    if seg["id"] == "proof":
        # Portrait phone — frame inside a centered phone-shaped panel.
        rec_path = SCREENREC_DIR / rec_groups[0]["files"][0]
        if not rec_path.exists():
            logger.warning("[%s] missing %s — falling back to full_face", seg["id"], rec_path.name)
            return build_full_face_segment(seg, avatar_path, out_path, tmp)
        # Scale to fit 600 wide × 1080 tall, centered on a brand-color canvas.
        # The phone scroll is 384×848 portrait. We scale to 600×1080 letterboxed/cropped to phone-ish.
        bg = tmp / f"{seg['id']}_phone_panel.mp4"
        rec_dur = probe_duration(rec_path)
        needs_loop = rec_dur < avatar_dur
        # filter_complex:
        #   [0:v] = lavfi black canvas (1920x1080)
        #   [1:v] = portrait Instagram recording (384x848 native)
        # Scale recording to fit 1000px tall while keeping its native aspect (≈ 453x1000),
        # overlay centered on the black canvas, with a subtle brand-blue 4px stroke.
        filter_complex = (
            "[1:v]scale=-2:1000:flags=lanczos,"
            "pad=iw+8:ih+8:4:4:color=0x2979ff[phone];"
            "[0:v][phone]overlay=(W-w)/2:(H-h)/2[outv]"
        )
        cmd = ["ffmpeg", "-y",
               "-f", "lavfi", "-t", f"{avatar_dur:.3f}",
               "-i", f"color=c=black:s={W}x{H}:r={FPS}"]
        if needs_loop:
            cmd += ["-stream_loop", "-1"]
        cmd += ["-t", f"{avatar_dur:.3f}", "-i", str(rec_path),
                "-filter_complex", filter_complex, "-map", "[outv]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", str(FPS),
                "-t", f"{avatar_dur:.3f}", str(bg)]
        run_ff(cmd, f"{seg['id']}.phone_panel")
        screen_bg = bg
    else:
        # value_step2_clone: 2+ groups (HeyGen + ElevenLabs). Use the Scribe caption JSON
        # to find when the avatar transitions from "HeyGen" to "ElevenLabs / voice" — the
        # recording switch lands at that exact word, so the visual on screen matches what
        # the avatar is saying. Falls back to even split if captions unavailable.
        n_groups = len(rec_groups)
        split_points = _compute_screen_share_split_points(seg["id"], rec_groups, avatar_dur)
        even_group_dur = avatar_dur / n_groups   # only used as fallback below
        group_videos = []
        for gi, grp in enumerate(rec_groups):
            files = [SCREENREC_DIR / f for f in grp["files"] if (SCREENREC_DIR / f).exists()]
            if not files:
                logger.warning("[%s] group %d files missing — skipping", seg["id"], gi)
                continue
            # Per-group duration: from Scribe split if available, else fall back to even split.
            this_group_dur = (split_points[gi] if split_points and gi < len(split_points)
                              else even_group_dur)
            logger.info("[%s] group %d (%s) window=%.2fs", seg["id"], gi, grp.get("label", ""), this_group_dur)
            # Concat the group's files
            concat_txt = tmp / f"{seg['id']}_g{gi}_concat.txt"
            concat_txt.write_text("\n".join(f"file '{p}'" for p in files))
            stitched = tmp / f"{seg['id']}_g{gi}_stitched.mp4"
            run_ff(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
                    "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                           f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setpts=PTS-STARTPTS,fps={FPS}",
                    "-pix_fmt", "yuv420p", str(stitched)],
                   f"{seg['id']}.g{gi}_stitched")
            # Compute speed factor to fit this_group_dur — but CAP at 2x.
            # Beyond 2x, screen-recordings look like blurred fast-forward and the viewer
            # can't read what's happening. Instead, trim the source down to (target × 2)s
            # first, then play that at exactly 2x.
            raw_dur = probe_duration(stitched)
            MAX_SPEED = 2.0
            ideal_speed = raw_dur / this_group_dur if this_group_dur > 0 else 1.0
            if ideal_speed > MAX_SPEED:
                # trim then 2x
                trim_dur = this_group_dur * MAX_SPEED
                trimmed = tmp / f"{seg['id']}_g{gi}_trimmed.mp4"
                run_ff(["ffmpeg", "-y", "-i", str(stitched),
                        "-t", f"{trim_dur:.3f}",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-an", "-pix_fmt", "yuv420p", "-r", str(FPS),
                        str(trimmed)], f"{seg['id']}.g{gi}_trim")
                stitched = trimmed
                speed = MAX_SPEED
                logger.info("[%s] group %d source %.1fs > %.1fs target — trimmed to %.1fs then 2x",
                            seg["id"], gi, raw_dur, this_group_dur, trim_dur)
            else:
                speed = max(1.0, ideal_speed)
                logger.info("[%s] group %d source %.1fs → %.1fs window at %.2fx speed",
                            seg["id"], gi, raw_dur, this_group_dur, speed)
            sped = tmp / f"{seg['id']}_g{gi}_sped.mp4"
            run_ff(["ffmpeg", "-y", "-i", str(stitched),
                    "-an", "-vf", f"setpts=PTS/{speed}",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-r", str(FPS),
                    "-t", f"{this_group_dur:.3f}", str(sped)],
                   f"{seg['id']}.g{gi}_sped")
            group_videos.append(sped)
        if not group_videos:
            logger.warning("[%s] no recordings found — fallback to full_face", seg["id"])
            return build_full_face_segment(seg, avatar_path, out_path, tmp)
        concat_txt = tmp / f"{seg['id']}_all_concat.txt"
        concat_txt.write_text("\n".join(f"file '{p}'" for p in group_videos))
        screen_bg = tmp / f"{seg['id']}_screen_bg.mp4"
        run_ff(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
                "-c", "copy", str(screen_bg)], f"{seg['id']}.screen_concat")

    # Overlay avatar head-crop PIP top-right with brand-blue stroke.
    filter_complex = (
        f"[1:v]crop={HEAD_CROP_W}:{HEAD_CROP_H}:{HEAD_CROP_X}:{HEAD_CROP_Y},"
        f"scale={PIPS_W}:{PIPS_H}:flags=lanczos,format=yuva420p[pip_raw];"
        f"[pip_raw]pad={PIPS_W+6}:{PIPS_H+6}:3:3:color=0x2979ff[pip];"
        f"[0:v][pip]overlay={PIPS_X-3}:{PIPS_Y-3}:shortest=1[outv]"
    )
    run_ff(["ffmpeg", "-y", "-i", str(screen_bg), "-i", str(avatar_path),
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", "1:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-shortest", str(out_path)],
           f"{seg['id']}.pip_screen")
    return out_path


def build_split_screen_left_avatar_segment(seg: dict, slides_for_seg: list[Path],
                                           avatar_path: Path, out_path: Path, tmp: Path) -> Path:
    """
    Split-screen layout:
      LEFT HALF  (0–960):   the avatar (cropped tight to face + body, fills the half)
      RIGHT HALF (960–1920): the slide template's content panel

    The slide template renders 1920×1080 with content positioned in the right half;
    the left half is a neutral dark gradient that gets fully covered by the avatar
    overlay. A 4px brand-blue vertical seam at x=958 (drawn in the template) keeps
    the boundary clean.

    Avatar crop math (1920×1080 source):
      - HeyGen renders the avatar as a vertical strip ~750px wide centred at x=960.
      - We crop a 900×1080 region centred on the avatar (x=510→1410), then scale that
        to 960×1152 (preserves aspect), then center-crop to 960×1080.
      - Result fills the left half edge-to-edge with no black bars.
    """
    avatar_dur = probe_duration(avatar_path)
    if not slides_for_seg:
        logger.warning("[%s] split_screen but no slide — falling back to full_face", seg["id"])
        return build_full_face_segment(seg, avatar_path, out_path, tmp)

    slide_path = slides_for_seg[0]

    # Build slide background sized to avatar duration (loops if needed)
    slide_bg = tmp / f"{seg['id']}_split_bg.mp4"
    run_ff(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(slide_path),
            "-t", f"{avatar_dur:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(FPS), str(slide_bg)],
           f"{seg['id']}.split_bg")

    # Chest-up framing (per user feedback) — avatar visible from hairline down to
    # upper chest only; no waist/jeans/chair. Hands still in frame when speaker
    # gestures at chest level.
    #
    # Source range:   y=220 (hairline) → y=828 (upper-chest)   = 608px tall
    # Width:          608 * 0.889 (target aspect 960/1080) ≈ 540px wide
    # Crop:           540×608 centred on the avatar (x=690 → 1230)
    # Scale to fill:  960×1080 (1.78× zoom — face is intimate, not cinematic)
    filter_complex = (
        "[1:v]crop=540:608:690:220,"
        "scale=960:1080:flags=lanczos,"
        "format=yuv420p[avatar_half];"
        "[0:v][avatar_half]overlay=0:0:shortest=1[outv]"
    )
    run_ff(["ffmpeg", "-y", "-i", str(slide_bg), "-i", str(avatar_path),
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", "1:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-shortest", str(out_path)],
           f"{seg['id']}.split_screen")
    return out_path


def build_full_face_segment(seg: dict, avatar_path: Path,
                            out_path: Path, tmp: Path) -> Path:
    """
    Avatar full-screen, no slides, no PIP — aggressive zoom-fill.

    HeyGen avatars are recorded in 9:16 portrait, so the avatar appears as a vertical
    strip (~750px wide) in the centre of 1920x1080. The previous "blurred-extended"
    backdrop still showed visible dark sides. This pass crops to the avatar strip
    alone and scales it up to fill the whole 1920x1080 frame — no black/blur sides.
    Face fills the screen; head + chest visible, slight top/bottom crop accepted.

    Math (assuming face centre at ~y=400 in the 1080-tall source):
      - crop 750x1080 centred on the avatar strip → 750x1080
      - scale to 1920x2767 (keeping aspect, 2.56x zoom)
      - centre-crop 1920x1080 around the face → final
    """
    # v8 — reduced zoom from 2.56× to ~1.6× for sharper face per user feedback.
    # Larger crop region (1200px wide instead of 750) means less per-pixel stretching.
    # Slight dark side bars are acceptable — sharpness > fill.
    STRIP_W = 1200           # wider crop = less zoom on the avatar's actual strip
    STRIP_X = (W - STRIP_W) // 2   # 360 — centred
    SCALED_H = int(round(H * W / STRIP_W))     # 1080 * 1920/1200 = 1728
    FACE_CENTRE_Y = int(round(400 * W / STRIP_W))   # 640
    CROP_TOP = max(0, min(SCALED_H - H, FACE_CENTRE_Y - H // 2))  # ~100
    filter_complex = (
        f"[0:v]crop={STRIP_W}:{H}:{STRIP_X}:0,"
        f"scale={W}:{SCALED_H}:flags=lanczos,"
        f"crop={W}:{H}:0:{CROP_TOP}[outv]"
    )
    run_ff(["ffmpeg", "-y", "-i", str(avatar_path),
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-r", str(FPS),
            str(out_path)], f"{seg['id']}.full_face")
    return out_path


def build_title_card(slide_path: Path, out_path: Path, tmp: Path) -> Path:
    """Re-encode title card slide to a no-audio mp4 with silent audio track (so concat works)."""
    silent_audio = tmp / f"{out_path.stem}_silent.wav"
    dur = probe_duration(slide_path)
    run_ff(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo",
            "-t", f"{dur:.3f}", "-c:a", "pcm_s16le", str(silent_audio)],
           f"{out_path.stem}.silent_audio")
    run_ff(["ffmpeg", "-y", "-i", str(slide_path), "-i", str(silent_audio),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-vf", f"scale={W}:{H},fps={FPS}",
            "-c:a", "aac", "-b:a", "192k",
            str(out_path)], f"{out_path.stem}.title_card")
    return out_path


def _apply_pitch_pivot_silence(in_video: Path, out_video: Path, dur_sec: float = PITCH_PIVOT_SILENCE_SEC) -> Path:
    """Dip avatar audio to zero for the first `dur_sec` seconds — makes the viewer lean in."""
    run_ff(["ffmpeg", "-y", "-i", str(in_video),
            "-af", f"volume=enable='lt(t,{dur_sec:.2f})':volume=0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            str(out_video)], f"pitch_pivot:{in_video.stem}")
    return out_video


def build_segment(seg: dict, tmp: Path, burn_captions_flag: bool = True) -> Path:
    sid = seg["id"]
    mode = seg["visual_mode"]
    avatar_path = AVATAR_DIR / f"{sid}.mp4"
    if not avatar_path.exists():
        logger.error("[%s] missing avatar mp4 — run heygen_render.py first", sid)
        raise RuntimeError(f"avatar missing for {sid}")
    slides_for_seg = [SLIDES_DIR / f"{slide_id}.mp4" for slide_id in (seg.get("slide_ids") or [])
                      if (SLIDES_DIR / f"{slide_id}.mp4").exists()]
    raw_out = tmp / f"seg_{sid}_raw.mp4"
    if mode == "full_screen_text":
        build_full_screen_text_segment(seg, slides_for_seg, avatar_path, raw_out, tmp)
    elif mode == "pip_over_slide":
        build_pip_over_slide_segment(seg, slides_for_seg, avatar_path, raw_out, tmp)
    elif mode == "screen_share_with_pip":
        # value_step2_clone uses the dedicated 3-phase builder (slide → HeyGen → ElevenLabs).
        if sid == "value_step2_clone":
            _build_value_step2_clone_segment(seg, slides_for_seg, avatar_path, raw_out, tmp)
        else:
            build_screen_share_with_pip_segment(seg, slides_for_seg, avatar_path, raw_out, tmp)
    elif mode == "full_face":
        build_full_face_segment(seg, avatar_path, raw_out, tmp)
    elif mode == "split_screen_left_avatar":
        build_split_screen_left_avatar_segment(seg, slides_for_seg, avatar_path, raw_out, tmp)
    else:
        raise RuntimeError(f"unknown visual_mode {mode}")

    current = raw_out

    # Pitch-pivot silence — only on the `gap` segment, dips first 0.6s of avatar audio.
    if sid == "gap":
        pp_out = tmp / f"seg_{sid}_pp.mp4"
        _apply_pitch_pivot_silence(current, pp_out)
        current = pp_out

    # Caption burn-in (drawtext-based; no libass required)
    if burn_captions_flag:
        cap_json = CAPTIONS_DIR / f"{sid}.json"
        if cap_json.exists():
            words = _flatten_words(json.loads(cap_json.read_text()))
            blocks = _group_into_blocks(words)
            if blocks:
                burned = tmp / f"seg_{sid}_capped.mp4"
                burn_captions(current, blocks, burned, tmp)
                current = burned
            else:
                logger.warning("[%s] caption JSON empty — skipping burn", sid)
        else:
            logger.warning("[%s] no captions JSON at %s — skipping burn", sid, cap_json)

    # Ensure final filename matches the expected `seg_<sid>.mp4`
    final_out = tmp / f"seg_{sid}.mp4"
    if current != final_out:
        if final_out.exists():
            final_out.unlink()
        current.rename(final_out)
    return final_out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--no-captions", action="store_true",
                   help="skip Whisper caption burn-in (faster, useful for previewing)")
    p.add_argument("--keep-tmp", action="store_true", help="keep compose_tmp/ for debugging")
    args = p.parse_args()

    if not SEGMENTS_FILE.exists():
        logger.error("missing %s", SEGMENTS_FILE); return 2
    segments = json.loads(SEGMENTS_FILE.read_text())

    # Verify all segment avatar mp4s present before starting
    missing = [s["id"] for s in segments if not (AVATAR_DIR / f"{s['id']}.mp4").exists()]
    if missing:
        logger.error("missing avatar mp4s for segments: %s", ", ".join(missing))
        logger.error("run vsl/scripts/heygen_render.py first")
        return 2

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    if TMP_DIR.exists() and not args.keep_tmp:
        shutil.rmtree(TMP_DIR)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    pieces: list[Path] = []
    for seg in segments:
        # Optional title card before this segment
        tc = seg.get("title_card_before")
        if tc:
            # slide_specs uses short TC ids ("TC_PROOF", "TC_SYSTEM" ...) — strip leading "THE "
            tc_norm = tc.strip()
            if tc_norm.lower().startswith("the "):
                tc_norm = tc_norm[4:]
            tc_id = f"TC_{tc_norm.upper().replace(' ', '_').replace('-', '_')}"
            tc_slide = SLIDES_DIR / f"{tc_id}.mp4"
            if tc_slide.exists():
                tc_out = TMP_DIR / f"tc_{tc_id}.mp4"
                build_title_card(tc_slide, tc_out, TMP_DIR)
                pieces.append(tc_out)
                logger.info("title card inserted: %s", tc_id)
            else:
                logger.warning("title card %s missing — skipping", tc_id)

        # The segment itself
        out = build_segment(seg, TMP_DIR, burn_captions_flag=not args.no_captions)
        pieces.append(out)
        logger.info("[%s] piece built: %s (%.1fs)", seg["id"], out.name, probe_duration(out))

    # Build piece_labels parallel to pieces[] so the xfade plan knows what each piece is.
    # We reconstruct it from segments using the SAME guards as the loop above
    # (title card only counts if its slide actually exists on disk).
    piece_labels: list[str] = []
    for seg in segments:
        tc = seg.get("title_card_before")
        if tc:
            tc_norm = tc.strip()
            if tc_norm.lower().startswith("the "): tc_norm = tc_norm[4:]
            tc_id = f"TC_{tc_norm.upper().replace(' ', '_').replace('-', '_')}"
            if (SLIDES_DIR / f"{tc_id}.mp4").exists():
                piece_labels.append("title_card")
        piece_labels.append(seg["id"])

    # ── End card: 2.4s ZEROHANDS title + fade to black, prevents the abrupt cut ──
    endcard = TMP_DIR / "endcard.mp4"
    endcard_audio = TMP_DIR / "endcard_silent.wav"
    endcard_dur = 2.4
    # Silent audio track so the concat stays in sync
    run_ff(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo",
            "-t", f"{endcard_dur:.2f}", "-c:a", "pcm_s16le", str(endcard_audio)],
           "endcard.silent_audio")
    # Build the visual card via lavfi color + drawtext
    font_path_card = ("/System/Library/Fonts/Supplemental/Arial Bold.ttf"
                      if Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf").exists()
                      else "/System/Library/Fonts/Helvetica.ttc")
    font_esc = font_path_card.replace(":", "\\:").replace(" ", "\\ ")
    # Two-line card: big "ZEROHANDS" + small handle subtitle, with a fade-out in last 0.6s
    vf_card = (
        f"drawtext=fontfile={font_esc}:text=ZEROHANDS:fontsize=180:fontcolor=white"
        f":bordercolor=black:borderw=4:x=(w-text_w)/2:y=(h-text_h)/2-40,"
        f"drawtext=fontfile={font_esc}:text=@automatewithanand:fontsize=42"
        f":fontcolor=0x2979ff:x=(w-text_w)/2:y=(h-text_h)/2+150,"
        # 0.5s fade-in at start + 0.6s fade-out at end
        f"fade=t=in:st=0:d=0.4,fade=t=out:st={endcard_dur - 0.6:.2f}:d=0.6"
    )
    run_ff(["ffmpeg", "-y",
            "-f", "lavfi", "-t", f"{endcard_dur:.2f}",
            "-i", f"color=c=black:s={W}x{H}:r={FPS}",
            "-i", str(endcard_audio),
            "-vf", vf_card,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-t", f"{endcard_dur:.2f}",
            str(endcard)], "endcard.build")
    pieces.append(endcard)
    piece_labels.append("endcard")

    # ── Selective crossfade plan ──
    # Boundaries where we WANT a soft 0.25s crossfade. Everything else stays hard-cut.
    XFADE_DUR = 0.25
    # Crossfades disabled in v7 — concat filter parameter mismatches between pieces
    # built by different code paths make the xfade chain too brittle to ship right now.
    # BGM continuity (final_polish) handles the abrupt-cut feel for v7. We can revisit
    # by normalizing piece encoders + using xfade-only chains in a later pass.
    soft_boundary_pairs: set[tuple[str, str]] = set()

    # Build the xfade decision list (one per gap between piece i and piece i+1)
    n = len(pieces)
    xfade_at: list[bool] = [False] * (n - 1)
    for i in range(n - 1):
        a, b = piece_labels[i], piece_labels[i + 1]
        if (a, b) in soft_boundary_pairs:
            xfade_at[i] = True

    final_concat = TMP_DIR / "final_concat.mp4"
    if not any(xfade_at):
        # No xfade boundaries — fall back to fast `-c copy` concat
        concat_txt = TMP_DIR / "final_concat.txt"
        concat_txt.write_text("\n".join(f"file '{p}'" for p in pieces))
        run_ff(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
                "-c", "copy", str(final_concat)], "final_concat")
    else:
        # Build a chained xfade filter graph. Each xfade takes 2 inputs and produces 1
        # output; we chain them so [v0][v1] → v01, [v01][v2] → v012, etc.
        # Pieces that aren't xfaded use a 0-duration xfade (functionally a hard cut)
        # so the same chain handles both — keeps the graph uniform.
        # Durations are needed to compute each xfade's offset (overlap point in timeline).
        durs = [probe_duration(p) for p in pieces]
        logger.info("Crossfade plan: %s",
                    ", ".join(f"{piece_labels[i]}→{piece_labels[i+1]}{'(xfade)' if xfade_at[i] else ''}"
                              for i in range(n - 1)))
        # Build filter_complex
        v_parts: list[str] = []
        a_parts: list[str] = []
        # Initial labels for v/a are [0:v] [0:a]
        prev_v = "[0:v]"
        prev_a = "[0:a]"
        # Cumulative timeline duration of the chain so far (= dur of prev_v on the timeline)
        chain_dur = durs[0]
        for i in range(1, n):
            xf = XFADE_DUR if xfade_at[i - 1] else 0.0   # 0 = hard cut
            offset = max(0.0, chain_dur - xf)
            new_v = f"[v{i}]"
            new_a = f"[a{i}]"
            if xf > 0:
                v_parts.append(
                    f"{prev_v}[{i}:v]xfade=transition=fade:duration={xf:.2f}:"
                    f"offset={offset:.3f}{new_v}"
                )
                a_parts.append(
                    f"{prev_a}[{i}:a]acrossfade=d={xf:.2f}{new_a}"
                )
            else:
                # Hard cut via concat filter (no overlap)
                v_parts.append(f"{prev_v}[{i}:v]concat=n=2:v=1:a=0{new_v}")
                a_parts.append(f"{prev_a}[{i}:a]concat=n=2:v=0:a=1{new_a}")
            chain_dur = chain_dur + durs[i] - xf
            prev_v, prev_a = new_v, new_a

        last_v = prev_v.strip("[]")
        last_a = prev_a.strip("[]")
        filter_complex = ";".join(v_parts + a_parts)

        cmd = ["ffmpeg", "-y"]
        for p in pieces:
            cmd += ["-i", str(p)]
        cmd += ["-filter_complex", filter_complex,
                "-map", f"[{last_v}]", "-map", f"[{last_a}]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                str(final_concat)]
        run_ff(cmd, "final_concat_xfade")

    # Final polish pass on top of the concatenated piece:
    #   1. Light audio compression + EQ tilt (voice reads expert, not hype).
    #   2. Lower-third "@automatewithanand · ZEROHANDS" handle for first 30s.
    #   3. Subtle brand-blue underline at the very bottom for the first 30s.
    final_concat_dur = probe_duration(final_concat)
    font_path = ("/System/Library/Fonts/Supplemental/Arial Bold.ttf"
                 if Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf").exists()
                 else "/System/Library/Fonts/Helvetica.ttc")

    # v5 final polish pass — higher quality encoding + global unsharp for that "4K feel"
    # without needing HeyGen to actually re-render at 4K.
    # • unsharp=5:5:0.9 — subtle sharpening of all frames (face + slide text)
    # • preset=slow + crf=17 — meaningful detail uplift vs. v4 (veryfast/20)
    handle_text = "@automatewithanand   |   ZEROHANDS"
    handle_text_esc = (handle_text
                       .replace("\\", "\\\\")
                       .replace(":", "\\:")
                       .replace(",", "\\,")
                       .replace("'", "\\'"))
    escaped_font = font_path.replace(":", "\\:").replace(",", "\\,").replace(" ", "\\ ")
    # v9 — output at 4K (3840×2160) with 1.2× speed-up. Lanczos upscale + heavier
    # unsharp + setpts=PTS/1.2 (video) + atempo=1.2 (audio in af_chain below).
    # At 1.2× the avatar plays with more energy and the runtime drops ~12:19 → ~10:15.
    SPEED = 1.2
    vf_video = (
        # Upscale 1920×1080 → 3840×2160 with high-quality lanczos resampling
        f"scale=3840:2160:flags=lanczos,"
        # Heavier unsharp at 4K — moderate luma + slight chroma sharpening
        f"unsharp=7:7:1.2:5:5:0.0,"
        # Brand-blue stripe at the very bottom — 12px (doubled for 4K), first 30s only
        f"drawbox=y=ih-12:width=iw:height=12:color=0x2979ff@0.85:t=fill:"
        f"enable=between(t\\,0.5\\,30),"
        # Handle text — sizes doubled to read at the same visual scale on 4K
        f"drawtext=fontfile={escaped_font}:text={handle_text_esc}"
        f":fontsize=64:fontcolor=white:bordercolor=black:borderw=4"
        f":box=1:boxcolor=black@0.6:boxborderw=36|28"
        f":x=96:y=h-th-56"
        f":enable=between(t\\,0.5\\,30),"
        # 1.2× speed-up — setpts is the last step so all overlays are still
        # frame-aligned at source time before time gets compressed
        f"setpts=PTS/{SPEED}"
    )

    # ── BGM mix (6% volume, ducked from 600s onwards for the close) ──
    # vsl/assets/music/bgm.mp3 must exist (generated by vsl/scripts/generate_bgm.py).
    # Without it we just skip the BGM and use the voice-only pass.
    bgm_path = ROOT / "assets" / "music" / "bgm.mp3"
    BGM_DUCK_AT = 600.0   # gap segment starts ~10:00 — duck BGM here so the close is dry

    if bgm_path.exists():
        logger.info("Mixing BGM %s at 6%% volume, ducked from %.0fs", bgm_path, BGM_DUCK_AT)
        # One filter_complex handles video (unsharp + lower-third + stripe) + audio (BGM mix).
        # NB: amix normalize=0 is CRITICAL — without it, ffmpeg averages all inputs by
        # default, which halves the voice volume. With normalize=0 the voice stays at
        # 1.0 and the BGM at its explicit 6% level — they sum cleanly.
        af_chain = (
            f"[1:a]aloop=loop=-1:size=2147483647,"
            f"volume=enable='lt(t\\,{BGM_DUCK_AT:.0f})':volume=0.06,"
            f"volume=enable='gte(t\\,{BGM_DUCK_AT:.0f})':volume=0[bgm];"
            f"[0:a][bgm]amix=inputs=2:normalize=0:duration=first:dropout_transition=0,"
            f"dynaudnorm=g=5:s=20,equalizer=f=4000:t=q:w=1.5:g=2[aout]"
        )
        full_fc = f"[0:v]{vf_video}[vout];{af_chain}"
        run_ff(["ffmpeg", "-y",
                "-i", str(final_concat), "-i", str(bgm_path),
                "-filter_complex", full_fc,
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "slow", "-crf", "17",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                str(OUT_FILE)], "final_polish_with_bgm")
    else:
        logger.warning("BGM not found at %s — final pass without BGM", bgm_path)
        # 1.2× speed: setpts on video (in vf_video) + atempo on audio.
        af_voice = f"atempo={SPEED},dynaudnorm=g=5:s=20,equalizer=f=4000:t=q:w=1.5:g=2"
        run_ff(["ffmpeg", "-y", "-i", str(final_concat),
                "-af", af_voice,
                "-vf", vf_video,
                "-c:v", "libx264", "-preset", "slow", "-crf", "17",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                str(OUT_FILE)], "final_polish")

    dur = probe_duration(OUT_FILE)
    size_mb = OUT_FILE.stat().st_size / 1e6
    logger.info("VSL complete — %.1fs (%.1f min), %.1f MB → %s", dur, dur / 60, size_mb, OUT_FILE)

    if not args.keep_tmp:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    print(f"\n→ {OUT_FILE}  ({dur/60:.1f} min, {size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
