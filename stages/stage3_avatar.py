"""
Stage 3 — Avatar Video Generation (HeyGen)
Reads full_spoken_script from assets/script_data.json, submits to HeyGen,
polls until complete, downloads to assets/avatar/avatar_video.mp4.
"""

import json
import logging
import os
import random
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
SCRIPT_DATA_PATH = ROOT / "assets" / "script_data.json"
AVATAR_DIR = ROOT / "assets" / "avatar"
AVATAR_OUTPUT = AVATAR_DIR / "avatar_video.mp4"
LOG_FILE = ROOT / "logs" / "pipeline.log"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("stage3_avatar")
logger.setLevel(logging.DEBUG)

_fmt = logging.Formatter("%(asctime)s [stage3_avatar] %(levelname)s %(message)s")

_fh = logging.FileHandler(LOG_FILE)
_fh.setFormatter(_fmt)
logger.addHandler(_fh)

_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(_fmt)
logger.addHandler(_sh)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
HEYGEN_GENERATE_URL = "https://api.heygen.com/v2/video/generate"
HEYGEN_STATUS_URL = "https://api.heygen.com/v1/video_status.get"

POLL_INTERVAL_SEC = 20
TASK_TIMEOUT_SEC = 1800      # 30 minutes
MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]   # seconds
SCRIPT_MAX_CHARS = 5000


# ---------------------------------------------------------------------------
# TTS issue detector — catches patterns HeyGen will mispronounce
# ---------------------------------------------------------------------------

# Known patterns that TTS handles correctly — skip warning for these
_TTS_OK_PATTERNS = re.compile(
    r"\b(AI|API|GWS|CLI|URL|HTML|CSV|PDF|DM|CTA|UX|UI|PR|CEO|COO|CFO|CTO|HR|SaaS|GitHub|ChatGPT|GPT|Claude|n8n|N-eight-N)\b",
    re.IGNORECASE,
)

def _check_tts_issues(text: str) -> list[str]:
    """
    Scan normalized text for patterns that HeyGen TTS will mispronounce.
    Returns list of warning strings (empty = all good).
    """
    issues = []

    # Non-ASCII symbols left after normalization (currency, special chars)
    # Strip SSML break tags first — they are intentional and contain < >
    text_no_tags = re.sub(r"<break[^>]*/?>", "", text)
    non_ascii = re.findall(r"[₹$€£¥%&@#*^~`|\\<>{}[\]]", text_no_tags)
    if non_ascii:
        issues.append(f"Non-ASCII / special symbols still present: {list(set(non_ascii))} — TTS may read these literally")

    # Raw numbers with commas or 4+ digits (should be spelled out)
    raw_nums = re.findall(r"\b\d{4,}\b|\b\d{1,3}(?:,\d{3})+\b", text)
    if raw_nums:
        issues.append(f"Large numbers not spelled out: {raw_nums} — TTS may say digits individually")

    # Em-dashes — replace with comma+space for natural pause
    if "—" in text or "–" in text:
        issues.append("Em-dash (—/–) found — replace with ', ' or '. ' for a cleaner TTS pause")

    # ALL-CAPS words not in the known-safe list
    all_caps = re.findall(r"\b[A-Z]{3,}\b", text)
    unknown_caps = [w for w in all_caps if not _TTS_OK_PATTERNS.match(w)]
    if unknown_caps:
        issues.append(f"Unknown ALL-CAPS abbreviations: {list(set(unknown_caps))} — check pronunciation")

    # Slash-separated items (e.g. n8n/ChatGPT) — TTS often reads "/" as "slash"
    # Exclude break tags (they contain slashes in </break>)
    slashes = re.findall(r"\w+/\w+", re.sub(r"<[^>]+>", "", text))
    if slashes:
        issues.append(f"Slash-separated tokens: {slashes} — replace '/' with ' or ' for natural speech")

    return issues


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _heygen_headers(api_key: str) -> dict:
    return {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
    }


def _request_with_retry(method: str, url: str, *, headers: dict,
                         json_body: dict | None = None,
                         params: dict | None = None,
                         stream: bool = False,
                         label: str = "") -> requests.Response:
    """HTTP request with 3 retries and exponential backoff."""
    last_exc: Exception | None = None
    for attempt, wait in enumerate(RETRY_BACKOFF, start=1):
        try:
            resp = requests.request(
                method, url,
                headers=headers,
                json=json_body,
                params=params,
                stream=stream,
                timeout=60,
            )
            if resp.status_code < 500:
                return resp
            logger.warning("%s HTTP %s (attempt %d/%d) — retrying in %ds",
                           label, resp.status_code, attempt, MAX_RETRIES, wait)
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("%s request error (attempt %d/%d): %s — retrying in %ds",
                           label, attempt, MAX_RETRIES, exc, wait)
        time.sleep(wait)

    # Final attempt
    try:
        return requests.request(
            method, url,
            headers=headers,
            json=json_body,
            params=params,
            stream=stream,
            timeout=60,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"{label} — all {MAX_RETRIES + 1} attempts failed: {exc}"
        ) from exc


def _submit_heygen_video(script: str, avatar_id: str, voice_id: str,
                          api_key: str) -> str:
    """Submit avatar video generation to HeyGen. Returns video_id."""
    voice_speed = float(os.getenv("HEYGEN_VOICE_SPEED", "1.0"))
    voice_config: dict = {
        "type": "text",
        "input_text": script,
        "voice_id": voice_id,
    }
    if voice_speed != 1.0:
        voice_config["speed"] = voice_speed
        logger.info("Voice speed set to %.2f (HEYGEN_VOICE_SPEED)", voice_speed)

    body = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal",
                },
                "voice": voice_config,
                "background": {
                    "type": "color",
                    "value": "#000000",
                },
            }
        ],
        "dimension": {"width": 1080, "height": 1920},
    }

    logger.info("Submitting avatar video to HeyGen (script length=%d chars)", len(script))
    resp = _request_with_retry(
        "POST", HEYGEN_GENERATE_URL,
        headers=_heygen_headers(api_key),
        json_body=body,
        label="heygen_submit",
    )

    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"HeyGen submit failed — HTTP {resp.status_code}: {resp.text}"
        )

    data = resp.json()
    # HeyGen v2 response: {"data": {"video_id": "..."}, "error": null}
    video_id = (
        data.get("data", {}).get("video_id")
        or data.get("video_id")
    )
    if not video_id:
        raise RuntimeError(f"HeyGen response missing video_id: {data}")

    logger.info("HeyGen video submitted — video_id=%s", video_id)
    return video_id


def _poll_heygen_video(video_id: str, api_key: str) -> str:
    """Poll HeyGen status until completed. Returns video download URL."""
    deadline = time.time() + TASK_TIMEOUT_SEC

    with tqdm(desc="HeyGen polling", unit="poll", leave=True) as bar:
        while time.time() < deadline:
            time.sleep(POLL_INTERVAL_SEC)
            bar.update(1)

            resp = _request_with_retry(
                "GET", HEYGEN_STATUS_URL,
                headers=_heygen_headers(api_key),
                params={"video_id": video_id},
                label="heygen_poll",
            )

            if resp.status_code != 200:
                logger.warning("Poll HTTP %s — will retry", resp.status_code)
                continue

            data = resp.json()
            payload = data.get("data", data)
            status = (payload.get("status") or "").lower()
            bar.set_postfix(status=status)

            logger.debug("HeyGen poll — status=%s", status)

            if status == "completed":
                video_url = payload.get("video_url")
                if not video_url:
                    raise RuntimeError(
                        f"HeyGen completed but no video_url in payload: {payload}"
                    )
                logger.info("HeyGen video ready — url=%s", video_url)
                return video_url

            if status == "failed":
                reason = payload.get("error") or payload.get("message") or str(payload)
                raise RuntimeError(f"HeyGen video generation failed: {reason}")

            # pending / processing — keep polling
            logger.debug("HeyGen status='%s' — continuing to poll", status)

    raise TimeoutError(
        f"HeyGen video_id={video_id} did not complete within {TASK_TIMEOUT_SEC}s"
    )


def _download_video(url: str, dest: Path) -> None:
    """Stream-download the avatar video and verify non-zero filesize."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    for attempt, wait in enumerate(RETRY_BACKOFF + [0], start=1):
        try:
            logger.info("Downloading avatar video → %s", dest)
            resp = requests.get(url, stream=True, timeout=300)
            resp.raise_for_status()

            total = int(resp.headers.get("content-length", 0))
            with open(dest, "wb") as fh, tqdm(
                total=total or None,
                unit="B",
                unit_scale=True,
                desc="avatar_video.mp4",
                leave=True,
            ) as bar:
                for chunk in resp.iter_content(chunk_size=8192):
                    fh.write(chunk)
                    bar.update(len(chunk))

            size = dest.stat().st_size
            if size == 0:
                raise RuntimeError(f"Downloaded avatar file is empty: {dest}")

            logger.info("Avatar download complete — %d bytes", size)
            return

        except Exception as exc:
            logger.warning("Download attempt %d failed: %s", attempt, exc)
            if dest.exists():
                dest.unlink()
            if wait:
                time.sleep(wait)

    raise RuntimeError(f"All download attempts failed for {url}")


# ---------------------------------------------------------------------------
# TTS normalization — HeyGen reads symbols and digits literally
# ---------------------------------------------------------------------------

def _normalize_for_tts(text: str) -> str:
    """
    Convert currency symbols, large numbers, and abbreviations into
    words that HeyGen TTS can pronounce naturally.

    Examples:
      ₹40,000  →  forty thousand rupees
      ₹2,000   →  two thousand rupees
      ₹90K     →  ninety thousand rupees
      $500     →  five hundred dollars
      n8n      →  N-eight-N
    """
    def inr_with_commas(m: re.Match) -> str:
        """₹1,23,456 → spelled out + rupees"""
        raw = m.group(1).replace(",", "")
        n = int(raw)
        return _num_to_words(n) + " rupees"

    def inr_k(m: re.Match) -> str:
        """₹90K → ninety thousand rupees"""
        n = int(m.group(1)) * 1000
        return _num_to_words(n) + " rupees"

    def usd_with_commas(m: re.Match) -> str:
        raw = m.group(1).replace(",", "")
        n = int(raw)
        return _num_to_words(n) + " dollars"

    def usd_k(m: re.Match) -> str:
        n = int(m.group(1)) * 1000
        return _num_to_words(n) + " dollars"

    # K-suffixed patterns first (more specific — prevents partial match by number pattern)
    # ₹90K
    text = re.sub(r"₹(\d+)[Kk]", inr_k, text)
    # ₹1,23,456 or ₹40,000
    text = re.sub(r"₹([\d,]+)", inr_with_commas, text)
    # $5K
    text = re.sub(r"\$(\d+)[Kk]", usd_k, text)
    # $500 / $1,000
    text = re.sub(r"\$([\d,]+)", usd_with_commas, text)
    # n8n → N eight N (so TTS doesn't say "en-eight-en" awkwardly)
    text = re.sub(r"\bn8n\b", "N-eight-N", text)
    # "10x" / "3x" → "ten times" / "three times"
    text = re.sub(r"\b(\d+)[xX]\b", lambda m: _num_to_words(int(m.group(1))) + " times", text)
    # Percentages — "95%" → "ninety-five percent"
    text = re.sub(r"\b(\d+)%", lambda m: _num_to_words(int(m.group(1))) + " percent", text)
    # Ordinals — "1st" → "first", "2nd" → "second", etc.
    _ORDINALS = {
        "1st": "first", "2nd": "second", "3rd": "third", "4th": "fourth",
        "5th": "fifth", "6th": "sixth", "7th": "seventh", "8th": "eighth",
        "9th": "ninth", "10th": "tenth",
    }
    text = re.sub(r"\b(\d+(?:st|nd|rd|th))\b",
                  lambda m: _ORDINALS.get(m.group(1), m.group(1)), text)
    # Model names like "GPT-4" / "Claude-3" → "GPT four" / "Claude three"
    text = re.sub(r"\b(GPT|Claude|Llama|Gemini)-(\d)\b",
                  lambda m: f"{m.group(1)} {_ONES[int(m.group(2))]}", text)
    # Em-dash / en-dash → SSML break tag for a proper 0.5s spoken pause
    # HeyGen supports <break time="Xs"/> — much cleaner than comma
    text = re.sub(r"\s*[—–]\s*", " <break time=\"0.5s\"/> ", text)
    # ALL-CAPS keywords that are just words, not abbreviations → sentence case
    # e.g. "Comment AGENT below" → "Comment Agent below" so TTS reads naturally
    text = re.sub(r"\b([A-Z]{4,})\b", lambda m: m.group(1).capitalize(), text)

    # Long sentences with no pause — insert <break time="0.3s"/> before conjunctions
    def _insert_pause_breaks(t: str) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", t)
        result = []
        for sent in sentences:
            words = sent.split()
            # Only add break if sentence is long and has no pause tag already
            if len(words) > 14 and '<break' not in sent:
                for conj in [" and ", " but ", " so ", " because ", " while ", " when ", " which "]:
                    idx = sent.lower().find(conj)
                    if idx != -1:
                        sent = sent[:idx] + " <break time=\"0.3s\"/> " + sent[idx:].lstrip()
                        break
            result.append(sent)
        return " ".join(result)

    text = _insert_pause_breaks(text)
    return text


_ONES = [
    "", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def _num_to_words(n: int) -> str:
    """Convert integer ≤ 9,99,99,999 to English words."""
    if n == 0:
        return "zero"
    if n < 0:
        return "minus " + _num_to_words(-n)

    parts = []
    if n >= 10_000_000:
        parts.append(_num_to_words(n // 10_000_000) + " crore")
        n %= 10_000_000
    if n >= 100_000:
        parts.append(_num_to_words(n // 100_000) + " lakh")
        n %= 100_000
    if n >= 1_000:
        parts.append(_num_to_words(n // 1_000) + " thousand")
        n %= 1_000
    if n >= 100:
        parts.append(_num_to_words(n // 100) + " hundred")
        n %= 100
    if n >= 20:
        tens = _TENS[n // 10]
        ones = _ONES[n % 10]
        parts.append(tens + ("-" + ones if ones else ""))
    elif n > 0:
        parts.append(_ONES[n])
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Public stage entrypoint
# ---------------------------------------------------------------------------

def run_stage3(force: bool = False, dry_run: bool = False) -> dict:
    """
    Run Stage 3 — Avatar Video Generation.

    Args:
        force:   Re-generate even if avatar_video.mp4 already exists.
        dry_run: Normalize TTS and write tts_preview.txt but skip HeyGen submission.

    Returns:
        {
            "success": bool,
            "output_path": str,          # absolute path to avatar_video.mp4
            "duration_sec": float,
            "error": str | None,
        }
    """
    start = time.time()
    load_dotenv(ROOT / ".env")

    api_key = os.getenv("HEYGEN_API_KEY", "")
    voice_id = os.getenv("HEYGEN_VOICE_ID", "")

    _avatar_candidates = [
        v for k, v in os.environ.items()
        if k.startswith("HEYGEN_AVATAR_ID") and v.strip()
    ]
    if not _avatar_candidates:
        _avatar_candidates = [os.getenv("HEYGEN_AVATAR_ID", "")]
    avatar_id = random.choice(_avatar_candidates)
    logger.info(f"Selected avatar_id={avatar_id} (pool size={len(_avatar_candidates)})")

    missing = [k for k, v in {
        "HEYGEN_API_KEY": api_key,
        "HEYGEN_AVATAR_ID (any variant)": avatar_id,
        "HEYGEN_VOICE_ID": voice_id,
    }.items() if not v]

    if missing:
        return {
            "success": False,
            "output_path": "",
            "duration_sec": 0.0,
            "error": f"Missing env vars: {', '.join(missing)}",
        }

    # Load script data
    if not SCRIPT_DATA_PATH.exists():
        return {
            "success": False,
            "output_path": "",
            "duration_sec": 0.0,
            "error": f"script_data.json not found at {SCRIPT_DATA_PATH}",
        }

    with open(SCRIPT_DATA_PATH) as fh:
        script_data = json.load(fh)

    full_script = script_data.get("full_spoken_script", "")
    if not full_script:
        return {
            "success": False,
            "output_path": "",
            "duration_sec": 0.0,
            "error": "full_spoken_script is empty in script_data.json",
        }

    # Normalize numbers for TTS — HeyGen reads symbols/digits literally
    full_script = _normalize_for_tts(full_script)

    # Save normalized script to a preview file so it can be reviewed before generation
    preview_path = ROOT / "assets" / "tts_preview.txt"
    preview_path.write_text(full_script, encoding="utf-8")
    logger.info("TTS preview saved → %s", preview_path)
    logger.info("──────────────── TTS SCRIPT (what HeyGen will say) ────────────────")
    for line in full_script.split(". "):
        if line.strip():
            logger.info("  %s.", line.strip())
    logger.info("────────────────────────────────────────────────────────────────────")

    # Check for TTS issues — warns but does not block
    tts_issues = _check_tts_issues(full_script)
    if tts_issues:
        logger.warning("TTS quality issues detected (%d) — review tts_preview.txt before spending credits:", len(tts_issues))
        for issue in tts_issues:
            logger.warning("  ⚠ %s", issue)
    else:
        logger.info("TTS check passed — no pronunciation issues detected.")

    # Dry run — skip HeyGen submission, just output the normalized TTS preview
    if dry_run:
        logger.info("DRY RUN — HeyGen submission skipped. Review: %s", preview_path)
        return {
            "success": True,
            "output_path": str(preview_path),
            "duration_sec": round(time.time() - start, 2),
            "error": None,
            "dry_run": True,
        }

    # Truncate if needed
    if len(full_script) > SCRIPT_MAX_CHARS:
        logger.warning(
            "full_spoken_script is %d chars — truncating to %d (HeyGen limit)",
            len(full_script), SCRIPT_MAX_CHARS,
        )
        full_script = full_script[:SCRIPT_MAX_CHARS]

    # Skip if already downloaded (crash recovery) — unless force=True
    if AVATAR_OUTPUT.exists() and AVATAR_OUTPUT.stat().st_size > 0 and not force:
        logger.info("Avatar video already exists — skipping generation")
        duration = time.time() - start
        return {
            "success": True,
            "output_path": str(AVATAR_OUTPUT),
            "duration_sec": round(duration, 2),
            "error": None,
        }

    try:
        video_id = _submit_heygen_video(full_script, avatar_id, voice_id, api_key)
        video_url = _poll_heygen_video(video_id, api_key)
        _download_video(video_url, AVATAR_OUTPUT)
    except Exception as exc:
        duration = time.time() - start
        logger.error("Stage 3 failed after %.1fs: %s", duration, exc)
        return {
            "success": False,
            "output_path": "",
            "duration_sec": round(duration, 2),
            "error": str(exc),
        }

    duration = time.time() - start
    logger.info("Stage 3 complete in %.1fs — %s", duration, AVATAR_OUTPUT)
    return {
        "success": True,
        "output_path": str(AVATAR_OUTPUT),
        "duration_sec": round(duration, 2),
        "error": None,
    }


# ---------------------------------------------------------------------------
# Standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse as _ap
    _parser = _ap.ArgumentParser()
    _parser.add_argument("--dry-run", action="store_true", help="Normalize TTS only, skip HeyGen submission")
    _parser.add_argument("--force", action="store_true", help="Re-generate even if avatar_video.mp4 exists")
    _args = _parser.parse_args()
    result = run_stage3(force=_args.force, dry_run=_args.dry_run)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["success"] else 1)
