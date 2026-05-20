/**
 * SyntheticCursor.tsx — Smooth bezier-animated cursor overlay for ScreenDemoLayer.
 *
 * Renders a white circular cursor with click ripple animation.
 * Position is driven by the timeline engine (no CSS transitions).
 */
import React from "react";
import { interpolate } from "remotion";
import { interpolateCursor, microJitter, clickRippleProgress, Pos } from "../../lib/cursor-engine";

interface SyntheticCursorProps {
  pos: Pos;           // current cursor position (0–1 fractions)
  prevPos: Pos;       // previous position for bezier interpolation
  moveDuration: number; // frames for this movement
  frameIntoMove: number; // frames elapsed since this movement started
  clickFrame: number | null; // frame when click happened (null = no click)
  currentFrame: number;
  containerW: number;
  containerH: number;
}

export const SyntheticCursor: React.FC<SyntheticCursorProps> = ({
  pos,
  prevPos,
  moveDuration,
  frameIntoMove,
  clickFrame,
  currentFrame,
  containerW,
  containerH,
}) => {
  // Interpolate position with bezier easing
  const interp = interpolateCursor(prevPos, pos, frameIntoMove, moveDuration);
  const jitter  = microJitter(currentFrame, 0.001);

  const cx = (interp.x + jitter.x) * containerW;
  const cy = (interp.y + jitter.y) * containerH;

  // Click scale animation
  const ripple = clickFrame !== null ? clickRippleProgress(currentFrame, clickFrame) : 0;
  const cursorScale = ripple > 0
    ? interpolate(ripple, [0, 0.3, 0.6, 1.0], [1, 0.7, 1.15, 1.0])
    : 1;

  // Ring expansion on click
  const ringOpacity = ripple > 0
    ? interpolate(ripple, [0, 0.3, 0.7, 1.0], [0, 0.6, 0.3, 0])
    : 0;
  const ringScale = ripple > 0
    ? interpolate(ripple, [0, 1.0], [1, 2.8])
    : 1;

  const CURSOR_SIZE = 26;

  return (
    <div style={{ position: "absolute", inset: 0, pointerEvents: "none", zIndex: 50 }}>
      {/* Click ripple ring */}
      {ringOpacity > 0 && (
        <div style={{
          position: "absolute",
          left: cx - CURSOR_SIZE / 2,
          top:  cy - CURSOR_SIZE / 2,
          width: CURSOR_SIZE,
          height: CURSOR_SIZE,
          borderRadius: "50%",
          border: "2px solid rgba(255,255,255,0.8)",
          transform: `scale(${ringScale})`,
          transformOrigin: "center",
          opacity: ringOpacity,
        }} />
      )}

      {/* Cursor dot */}
      <div style={{
        position: "absolute",
        left: cx - CURSOR_SIZE / 2,
        top:  cy - CURSOR_SIZE / 2,
        width: CURSOR_SIZE,
        height: CURSOR_SIZE,
        borderRadius: "50%",
        background: "rgba(255,255,255,0.96)",
        border: "2px solid rgba(20,20,20,0.55)",
        boxShadow: "0 2px 10px rgba(0,0,0,0.4), 0 1px 3px rgba(0,0,0,0.25)",
        transform: `scale(${cursorScale})`,
        transformOrigin: "center",
      }} />
    </div>
  );
};
