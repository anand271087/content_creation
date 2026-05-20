"""One-shot script to poll all known task IDs and download broll clips."""
import requests, time, json, os, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

api_key = os.getenv("KIE_API_KEY")
headers = {"Authorization": f"Bearer {api_key}"}
broll_dir = Path(__file__).parent.parent / "assets" / "broll"
broll_dir.mkdir(exist_ok=True)

tasks = {
    "trigger_2": "febec146903dcbbae80e8520f5f4a2fd",
    "hook": "9add35f16c514acef0636ffd75786b9c",
    "body_1": "779b849d8cb844cc7309d8ad3f80fcbf",
    "trigger_1": "7b7578ff02c92c23c9ce92874047b3be",
    "context": "22ca77179e0a93f67f3d6e581d94c172",
    "bridge": "4d63a78ee9b3e6459ccf7682631e8ef4",
    "body_2": "048c535337d225c7fec5e8e255cbf5e5",
    "trigger_3": "12e0754db3e8867e28d0572dfb9c4914",
    "grand_takeaway": "16003bf21c6911a67a1cc80eef305645",
    "emotion_save": "c2ccbf9c3d2a73182f1fd3ae6bc9da8c",
}

pending = dict(tasks)
downloaded = {}

print(f"Polling {len(pending)} tasks...", flush=True)
for attempt in range(40):
    if not pending:
        break
    time.sleep(15)
    done = []
    for section_id, task_id in list(pending.items()):
        r = requests.get(
            f"https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}",
            headers=headers, timeout=30
        ).json()
        payload = r.get("data") or {}
        state = payload.get("state", "")
        print(f"  [{section_id}] state={state}", flush=True)
        if state == "success":
            result = json.loads(payload.get("resultJson") or "{}")
            urls = result.get("resultUrls") or []
            url = urls[0] if urls else result.get("video_url")
            if url:
                dest = broll_dir / f"{section_id}.mp4"
                resp = requests.get(url, stream=True, timeout=120)
                with open(dest, "wb") as f:
                    for chunk in resp.iter_content(8192):
                        f.write(chunk)
                size = dest.stat().st_size
                print(f"  [{section_id}] ✓ {size} bytes -> {dest.name}", flush=True)
                downloaded[section_id] = str(dest)
            else:
                print(f"  [{section_id}] No URL in resultJson!", flush=True)
            done.append(section_id)
        elif state in ("fail", "failed"):
            print(f"  [{section_id}] FAILED", flush=True)
            done.append(section_id)
    for s in done:
        del pending[s]
    if pending:
        print(f"  Still waiting: {list(pending.keys())}", flush=True)

print(f"\nDone. Downloaded {len(downloaded)}/10: {list(downloaded.keys())}", flush=True)
sys.exit(0 if len(downloaded) == 10 else 1)
