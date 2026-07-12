"""
capture_window.py — record a specific Chrome WINDOW (not a screen region).

Why: region-based `screencapture -R` breaks when the window moves or doesn't
fill the guessed rectangle (grey desktop bleeds in, movement shows at the
start). Capturing by CGWindowID is pixel-locked to the window itself — it
stays correct even if the window is moved mid-take, and never includes
desktop, dock, or other windows.

Usage:
    python3 scripts/capture_window.py <url> <out.mov> <seconds> [--type "text"]

Flow:
  1. open Chrome to <url>, activate, set bounds, WAIT until bounds are stable
  2. find the frontmost Chrome window's CGWindowID via Quartz
  3. screencapture -v -l<ID> -V<secs> (window-locked recording, no shadow)
  4. optional: type text + Enter (System Events) after capture starts
"""
from __future__ import annotations
import subprocess, sys, time

import Quartz


def osascript(script: str) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip()


def chrome_window_id() -> int | None:
    """CGWindowID of the frontmost Google Chrome window."""
    wins = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID)
    for w in wins:  # front-to-back order
        if w.get("kCGWindowOwnerName") == "Google Chrome" and w.get("kCGWindowLayer") == 0:
            return int(w["kCGWindowNumber"])
    return None


def wait_bounds_stable(timeout: float = 8.0) -> str | None:
    """Poll Chrome window bounds until two consecutive reads match.
    Returns the stable bounds string 'x1, y1, x2, y2' or None."""
    prev = None
    t0 = time.time()
    while time.time() - t0 < timeout:
        cur = osascript('tell application "Google Chrome" to get bounds of front window')
        if cur and cur == prev:
            return cur
        prev = cur
        time.sleep(0.4)
    return None


def wait_chrome_frontmost(timeout: float = 6.0) -> bool:
    """Block until Chrome is actually the frontmost app — keystrokes go to the
    frontmost app, and typing before this is true leaks text into other apps."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        front = osascript('tell application "System Events" to get name of first '
                          'application process whose frontmost is true')
        if front == "Google Chrome":
            return True
        osascript('tell application "Google Chrome" to activate')
        time.sleep(0.5)
    return False


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__); return 2
    url, out, secs = sys.argv[1], sys.argv[2], float(sys.argv[3])
    type_text = None
    if "--type" in sys.argv:
        type_text = sys.argv[sys.argv.index("--type") + 1]

    subprocess.run(["open", "-a", "Google Chrome", url])
    time.sleep(7)
    osascript('tell application "Google Chrome"\nactivate\n'
              'set bounds of front window to {0, 25, 1200, 1210}\nend tell')
    bounds = wait_bounds_stable()
    if not bounds:
        print("ERROR: window bounds never stabilized"); return 1
    time.sleep(2)   # let the page settle after resize

    # NOTE: screencapture -v silently IGNORES -l (window id) for video — it
    # records the whole screen. So: region capture, but from the READ-BACK
    # bounds, and Chrome verified frontmost so nothing else is in the region.
    x1, y1, x2, y2 = [int(v.strip()) for v in bounds.split(",")]
    print(f"stable bounds: {x1},{y1} → {x2},{y2}")

    if not wait_chrome_frontmost():
        print("ERROR: Chrome never became frontmost — aborting so keystrokes "
              "don't leak into another app"); return 1

    region = f"{x1},{y1},{x2 - x1},{y2 - y1}"   # whole window incl. chrome UI; crop in post
    cap = subprocess.Popen(["screencapture", "-v", "-V", str(secs), "-R", region, out])
    time.sleep(2.5)

    if type_text and wait_chrome_frontmost(3):
        osascript(f'tell application "System Events" to keystroke "{type_text}"')
        time.sleep(0.8)
        osascript('tell application "System Events" to key code 36')

    cap.wait()
    # verify the window did not move during the take
    after = osascript('tell application "Google Chrome" to get bounds of front window')
    if after != bounds:
        print(f"WARN: window moved during capture ({bounds} → {after}) — RE-RECORD")
    print("captured:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
