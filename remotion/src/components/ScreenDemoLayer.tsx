/**
 * ScreenDemoLayer.tsx — Remotion-native screen recording renderer.
 *
 * For sections with broll_type="screen", renders:
 *   1. Screenshot sequence (clean PNGs from screen_broll.mjs)
 *   2. SyntheticCursor overlay (bezier-smooth, click ripple)
 *   3. HighlightOverlay (pulsing border or spotlight)
 *   4. TypingSimulator (character-by-character natural typing)
 *   5. ZoomPan (smooth zoom into region of interest)
 *
 * Timeline is driven by assets/screen_timelines/{section_id}.json which is
 * built by screen_timeline.mjs syncing cursor_steps to Whisper word timestamps.
 *
 * Falls back to static video playback if timeline JSON not found.
 */
import React from "react";
import { Img, staticFile } from "remotion";
import { Section, ScreenTimeline } from "../types";
import { SyntheticCursor } from "./screen/SyntheticCursor";
import { HighlightOverlay } from "./screen/HighlightOverlay";
import { TypingSimulator } from "./screen/TypingSimulator";
import { ZoomPan } from "./screen/ZoomPan";
import { Pos } from "../lib/cursor-engine";

// Full-frame layout — matches BrollClipCard clip sections.
// Gradient background covers avatar, rounded box shows screen content.
const BOX_WIDTH  = 880;
const BOX_HEIGHT = 1100;
const BOX_LEFT   = (1080 - BOX_WIDTH) / 2;   // 100
const BOX_TOP    = (1920 - BOX_HEIGHT) / 2;   // 410
const BOX_RADIUS = 28;
const SCREEN_PANEL_W = BOX_WIDTH;
const SCREEN_PANEL_H = BOX_HEIGHT;

// Must match BrollClipCard — used to convert frame → script time for screenshot cycling
const PLAYBACK_RATE = 1.25;

// ── Local typed action interface ──────────────────────────────────────────────

interface TimelineAction {
  frame: number;
  type: string;
  to?: [number, number] | null;
  selector?: string | null;
  screenshot_index?: number;
  mode?: "border" | "spotlight";
  box?: [number, number, number, number];
  at?: [number, number] | null;
  text?: string;
  region?: [number, number, number, number];
  [key: string]: unknown;
}

interface ScreenDemoLayerProps {
  section: Section;
  assetsDir: string;
  fps: number;
  globalFrame: number;
  timeline: ScreenTimeline | null; // null = no timeline JSON found, use fallback
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Get the active timeline action of a given type at or before the current frame. */
function getActiveAction(actions: TimelineAction[], currentFrame: number, type: string): TimelineAction | null {
  let last: TimelineAction | null = null;
  for (const a of actions) {
    if (a.type === type && a.frame <= currentFrame) last = a;
    else if (a.frame > currentFrame) break;
  }
  return last;
}

/** Get the previous and next CURSOR_MOVE actions around the current frame. */
function getCursorMoveContext(actions: TimelineAction[], currentFrame: number) {
  const moves = actions.filter(a => a.type === "CURSOR_MOVE");
  let prev: TimelineAction | null = null;
  let next: TimelineAction | null = null;
  for (let i = 0; i < moves.length; i++) {
    if (moves[i].frame <= currentFrame) { prev = moves[i]; }
    else { next = moves[i]; break; }
  }
  return { prev, next };
}

/** Which screenshot index is active at this frame. */
function getActiveScreenshot(actions: TimelineAction[], currentFrame: number, screenshotCount: number): number {
  let idx = 0;
  for (const a of actions) {
    if (a.type === "CURSOR_MOVE" && a.frame <= currentFrame && a.screenshot_index !== undefined) {
      idx = Math.min(a.screenshot_index ?? 0, screenshotCount - 1);
    }
  }
  return idx;
}

// ── Component ─────────────────────────────────────────────────────────────────

export const ScreenDemoLayer: React.FC<ScreenDemoLayerProps> = ({
  section,
  assetsDir,
  fps,
  globalFrame,
  timeline,
}) => {
  const actions: TimelineAction[] = timeline?.actions ?? [];
  const screenshotCount = timeline?.screenshot_count ?? 1;

  // Current screenshot index
  let shotIdx = getActiveScreenshot(actions, globalFrame, screenshotCount);

  // When no timeline (terminal / screen without choreography):
  // auto-cycle through all available screenshots evenly across the section duration.
  // terminal has 5 screenshots (f0–f4), screen typically has 4 (f0–f3).
  if (!timeline) {
    const isTerminal = section.broll_type === "terminal";
    const autoCount = isTerminal ? 5 : 4;
    const sectionStartFrame = section.start_sec * fps / PLAYBACK_RATE;
    const sectionDurationFrames = Math.max(
      1,
      (section.end_sec - section.start_sec) * fps / PLAYBACK_RATE
    );
    const framesIntoSection = Math.max(0, globalFrame - sectionStartFrame);
    shotIdx = Math.min(
      Math.floor(framesIntoSection / (sectionDurationFrames / autoCount)),
      autoCount - 1
    );
  }

  const shotPath = staticFile(`${assetsDir}/screen_screenshots/${section.id}_f${shotIdx}.png`);

  // Cursor state
  const { prev: prevMove, next: _nextMove } = getCursorMoveContext(actions, globalFrame);
  const cursorPos: Pos = prevMove?.to
    ? { x: prevMove.to[0], y: prevMove.to[1] }
    : { x: 0.5, y: 0.45 };

  // Find previous cursor position for interpolation
  const allMoves = actions.filter(a => a.type === "CURSOR_MOVE");
  const prevMoveIdx = prevMove ? allMoves.indexOf(prevMove) : -1;
  const prevPrevMove = prevMoveIdx > 0 ? allMoves[prevMoveIdx - 1] : null;
  const prevPos: Pos = prevPrevMove?.to
    ? { x: prevPrevMove.to[0], y: prevPrevMove.to[1] }
    : cursorPos;

  const moveDuration = prevMove && prevPrevMove
    ? Math.max(1, prevMove.frame - prevPrevMove.frame)
    : 20;
  const frameIntoMove = prevMove ? globalFrame - prevMove.frame : 0;

  // Click state — find most recent CLICK action
  const lastClick = getActiveAction(actions, globalFrame, "CLICK");
  const clickFrame = lastClick ? lastClick.frame + 12 : null; // +12 offset from CURSOR_MOVE

  // Highlight
  const highlightAction = getActiveAction(actions, globalFrame, "HIGHLIGHT");

  // Typing
  const typeAction = getActiveAction(actions, globalFrame, "TYPE");

  // Zoom
  const zoomAction = getActiveAction(actions, globalFrame, "ZOOM");

  // Fade-in for screenshot crossfade on shot change
  const screenshotKey = `${section.id}_f${shotIdx}`;

  // Split-screen panel dimensions — screen fills top half, avatar visible in bottom half
  const panelW = SCREEN_PANEL_W;  // 1080
  const panelH = SCREEN_PANEL_H;  // 960

  const innerContent = (
    <div style={{ position: "relative", width: "100%", height: "100%", overflow: "hidden" }}>
      {/* Screenshot — cover fills the box; top-center shows page header/hero for screen sections */}
      <Img
        key={screenshotKey}
        src={shotPath}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          objectFit: section.broll_type === "terminal" ? "contain" : "cover",
          objectPosition: "top center",
          backgroundColor: "#0a0a14",
        }}
      />

      {/* Highlight overlay */}
      {highlightAction?.box && (
        <HighlightOverlay
          box={highlightAction.box as [number, number, number, number]}
          mode={highlightAction.mode ?? "border"}
          frame={globalFrame}
          startFrame={highlightAction.frame}
          containerW={panelW}
          containerH={panelH}
        />
      )}

      {/* Typing simulator */}
      {typeAction?.text && typeAction?.at && (
        <TypingSimulator
          text={typeAction.text}
          at={typeAction.at as [number, number]}
          startFrame={typeAction.frame}
          currentFrame={globalFrame}
          containerW={panelW}
          containerH={panelH}
        />
      )}

      {/* Cursor — hidden for terminal sections (no real pointer) */}
      {section.broll_type !== "terminal" && (
        <SyntheticCursor
          pos={cursorPos}
          prevPos={prevPos}
          moveDuration={moveDuration}
          frameIntoMove={frameIntoMove}
          clickFrame={clickFrame}
          currentFrame={globalFrame}
          containerW={panelW}
          containerH={panelH}
        />
      )}
    </div>
  );

  return (
    <>
      {/* Full-frame gradient background — covers avatar entirely, same as clip broll */}
      <div style={{
        position: "absolute", top: 0, left: 0,
        width: 1080, height: 1920,
        background: "linear-gradient(180deg, #060e1c 0%, #0d1b2e 55%, #050b14 100%)",
        zIndex: 19, pointerEvents: "none",
      }} />

      {/* Rounded screen box — same position/size as BrollClipCard clip box */}
      <div style={{
        position: "absolute",
        top: BOX_TOP, left: BOX_LEFT,
        width: BOX_WIDTH, height: BOX_HEIGHT,
        borderRadius: BOX_RADIUS, overflow: "hidden",
        backgroundColor: "#000",
        zIndex: 20,
        border: "2px solid rgba(255,255,255,0.75)",
        boxShadow: "0 12px 48px rgba(0,0,0,0.75), 0 0 0 1px rgba(255,255,255,0.1)",
      }}>
        {/* ZoomPan wraps everything inside the box */}
        {zoomAction?.region ? (
          <ZoomPan
            region={zoomAction.region as [number, number, number, number]}
            zoomStartFrame={zoomAction.frame}
            zoomDuration={20}
            currentFrame={globalFrame}
          >
            {innerContent}
          </ZoomPan>
        ) : (
          innerContent
        )}
      </div>
    </>
  );
};
