---
name: video
description: Analyze a video or screen recording by extracting frames and spawning an analysis agent
---

## STOP - READ THESE RULES FIRST

**FORBIDDEN ACTIONS (will break the plugin):**
1. **NEVER use the Bash tool** - no commands at all, the hooks handle everything
2. **NEVER run docker commands** - no `docker pull`, `docker images`, `docker run`, NOTHING
3. **NEVER make up registry names** - no ghcr.io/anything, no anthropic, no ellyseum
4. **NEVER run cv-run, yt-dlp, ffmpeg, ffprobe** - the hooks handle this
5. **NEVER improvise** - only do exactly what this skill says

**YOUR ONLY ACTIONS ARE:**
- Check the STATUS from hook output
- If CACHED: spawn the video-analyzer agent (Task tool)
- Otherwise: say the MESSAGE from hook output and STOP

**If you don't know what to do: say "Something went wrong with video processing" and STOP.**

---

## Instructions

When this command is invoked, a hook has already started processing. Look for the hook output in context (starts with "=== VIDEO HOOK RESULT ===").

### Command Variants

| Command | Description |
|---------|-------------|
| `/video <url/path> <question>` | Analyze video |
| `/video follow-up <question>` | Ask about most recently analyzed video |
| `/video --list` | Show all cached videos |
| `/video --clear` | Remove all cached videos |

---

## Step 1: Check Hook Status

**IMPORTANT:** Look for "=== VIDEO HOOK RESULT ===" in the system context. The hook output contains key:value pairs. Parse them carefully:

Example hook output:
```
=== VIDEO HOOK RESULT ===
STATUS: PROCESSING
LOG_FILE: /tmp/video-process-12345.log
CACHE_DIR: /home/user/.claude/claude-vision/video-cache/abc123
MESSAGE: Started video processing...
=== USE THESE EXACT PATHS ===
```

Extract the EXACT values - do not use placeholder numbers. If the hook says `LOG:/tmp/video-process-89328.log`, use exactly that path, not a different number.

Fields:
- `STATUS:` - Current state
- `CACHE:` - Path to cached data
- `LOG:` - Path to processing log (use this EXACT path)
- `MESSAGE:` - User-friendly status message

**Handle based on STATUS:**

| Status | Action |
|--------|--------|
| `CACHED` | Proceed to Step 2 (spawn agent) |
| `PROCESSING` | Say the MESSAGE and tell user to try again in a moment |
| `READY` | No URL was provided - ask user for a video URL |
| `DOCKER_PULLING` | Say the MESSAGE (it includes progress %) |
| `DOCKER_FAILED` | Say the MESSAGE |
| `NOT_CONFIGURED` | Say: "Video not configured. Run /claude-vision-setup first." |
| `NO_TOOLS` | Say the MESSAGE |

**For any status except CACHED: just say the message and STOP. Do not use Bash. Do not try to wait or poll.**

---

## Step 2: Spawn Video Analyzer Agent

Once you have the CACHE_DIR path from hook context, spawn the video-analyzer agent.

**Read the metadata first using Read tool (NOT Bash):**
- Read file: `<CACHE_DIR>/metadata.json`

**Then spawn the agent with Task tool:**

```
Task tool:
  subagent_type: "claude-vision:video-analyzer"
  description: "Analyze video"
  prompt: |
    Analyze this video and answer the user's question.

    ## Video Information
    - Cache directory: <CACHE path>
    - Title: <from metadata>
    - Duration: <from metadata> seconds
    - Frames: <frame_count from metadata>

    ## User's Question
    <the user's original question about the video>

    ## Instructions
    1. Read the transcript from <CACHE>/subtitles.srt if it exists
    2. Read all frames from <CACHE>/frames/
    3. Analyze the content and answer the question
```

The agent will read the frames and transcript with its fresh 200k context.

---

## Step 3: Return Results

Present the agent's analysis to the user. The main conversation stays lean.

---

## Special Commands

### `/video --list`

```bash
CACHE_DIR="$HOME/.claude/claude-vision/video-cache"
for dir in "$CACHE_DIR"/*/; do
  [[ -f "${dir}metadata.json" ]] && cat "${dir}metadata.json" && echo ""
done
```

Present as a table: hash, title, duration, cached date.

### `/video --clear`

```bash
rm -rf "$HOME/.claude/claude-vision/video-cache"
echo "Cache cleared."
```

### `/video follow-up <question>`

Find most recent cache by timestamp in metadata.json, then spawn agent with that cache.

---

## Notes

- All video processing happens in the hook (background)
- Do NOT use Bash for the main video flow - just check status and spawn agent
- The agent sees all frames; you only see the analysis
- Cache persists across sessions
