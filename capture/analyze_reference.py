"""analyze_reference.py — download + dissect a reference Instagram reel.

The method that unlocked every format analysis this project has done:
GraphQL doc_id endpoint (no auth) → video_url → download IMMEDIATELY (signed
tokens expire) → evenly-spaced frames → Scribe transcript.

Usage:
    python3 capture/analyze_reference.py <instagram-url-or-shortcode>

Output (under assets/reference_analysis/<shortcode>/):
    reel.mp4, frames/f_00..09.png, grid_row1.png, grid_row2.png, words.json,
    transcript.txt, meta.txt
"""
from __future__ import annotations
import gzip
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
DOC_ID = "10015901848480474"


def shortcode_of(url_or_code: str) -> str:
    m = re.search(r"/(?:p|reel|reels)/([A-Za-z0-9_-]+)", url_or_code)
    return m.group(1) if m else url_or_code.strip("/")


def fetch(url: str, headers: dict) -> bytes:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=45) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return data


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    code = shortcode_of(sys.argv[1])
    out_dir = ROOT / "assets" / "reference_analysis" / code
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    variables = json.dumps({"shortcode": code, "fetch_tagged_user_count": None,
                            "hoisted_comment_id": None, "hoisted_reply_id": None})
    gql = (f"https://www.instagram.com/graphql/query/?doc_id={DOC_ID}"
           f"&variables={urllib.request.quote(variables)}")
    body = fetch(gql, {"User-Agent": UA, "x-ig-app-id": "936619743392459",
                       "Accept-Encoding": "gzip"}).decode("utf-8", "replace")

    m = re.search(r'"video_url":"([^"]+)"', body)
    if not m:
        print(f"ERROR: no video_url for {code} (login-walled or doc_id rotated)")
        return 1
    video_url = json.loads(f'"{m.group(1)}"')
    owner = re.search(r'"username":"([^"]+)"', body)
    cap = re.search(r'"text":"((?:[^"\\]|\\.){10,300})"', body)

    # download immediately — signed URL expires fast
    reel = out_dir / "reel.mp4"
    reel.write_bytes(fetch(video_url, {"User-Agent": UA,
                                       "Referer": "https://www.instagram.com/"}))
    dur = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(reel)]).decode().strip())

    meta = [f"shortcode: {code}",
            f"owner: {owner.group(1) if owner else '?'}",
            f"duration: {dur:.1f}s",
            f"caption: {json.loads(chr(34) + cap.group(1)[:250] + chr(34)) if cap else '?'}"]
    (out_dir / "meta.txt").write_text("\n".join(meta) + "\n")
    print("\n".join(meta))

    # 10 evenly spaced frames + 2 montage rows
    for i in range(10):
        t = 0.3 + i * (dur - 1) / 9
        subprocess.run(["ffmpeg", "-y", "-ss", f"{t:.1f}", "-i", str(reel),
                        "-frames:v", "1", "-vf", "scale=216:384",
                        str(frames_dir / f"f_{i:02d}.png")], capture_output=True)
    for row, idxs in (("grid_row1.png", range(0, 5)), ("grid_row2.png", range(5, 10))):
        ins = []
        for i in idxs:
            ins += ["-i", str(frames_dir / f"f_{i:02d}.png")]
        subprocess.run(["ffmpeg", "-y", *ins, "-filter_complex",
                        "[0][1][2][3][4]hstack=5", str(out_dir / row)],
                       capture_output=True)

    # Scribe transcript
    subprocess.run([sys.executable, str(ROOT / "speech" / "transcribe_elevenlabs.py"),
                    str(reel), "--output", str(out_dir / "words.json")], check=True)
    words = json.loads((out_dir / "words.json").read_text())
    (out_dir / "transcript.txt").write_text(words.get("text", ""))
    print(f"\ntranscript: {words.get('text', '')[:300]}…")
    print(f"\nall outputs → {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
