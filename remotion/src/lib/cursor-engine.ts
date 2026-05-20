/**
 * cursor-engine.ts — Smooth bezier cursor path math for SyntheticCursor.
 *
 * Given two positions (prevPos, nextPos) and a duration in frames,
 * returns the cursor (x, y) at a given frame offset using cubic bezier easing
 * with optional overshoot for natural feel.
 */

export interface Pos {
  x: number; // 0–1 fraction of container width
  y: number; // 0–1 fraction of container height
}

/**
 * Cubic bezier easing — matches CSS cubic-bezier(0.25, 0.46, 0.45, 0.94).
 * t: 0–1
 */
function cubicBezier(t: number, p1x: number, p1y: number, p2x: number, p2y: number): number {
  // Simplified numerical evaluation of cubic bezier
  const cx = 3 * p1x;
  const bx = 3 * (p2x - p1x) - cx;
  const ax = 1 - cx - bx;
  const cy = 3 * p1y;
  const by = 3 * (p2y - p1y) - cy;
  const ay = 1 - cy - by;

  // Find t for x using Newton-Raphson
  let tx = t;
  for (let i = 0; i < 4; i++) {
    const xErr = ((ax * tx + bx) * tx + cx) * tx - t;
    const dx   = (3 * ax * tx + 2 * bx) * tx + cx;
    if (Math.abs(dx) < 1e-6) break;
    tx -= xErr / dx;
  }
  // Evaluate y at tx
  return ((ay * tx + by) * tx + cy) * tx;
}

/**
 * Interpolate cursor position from prev → next over durationFrames.
 * frame: current frame offset from movement start (0 = at prev, durationFrames = at next)
 * Returns position clamped to [0, 1].
 */
export function interpolateCursor(
  prev: Pos,
  next: Pos,
  frame: number,
  durationFrames: number
): Pos {
  if (durationFrames <= 0) return next;
  const t = Math.min(1, Math.max(0, frame / durationFrames));
  // Ease-out-cubic (ease into final position, slight overshoot)
  const easedT = cubicBezier(t, 0.25, 0.46, 0.45, 0.94);
  return {
    x: prev.x + (next.x - prev.x) * easedT,
    y: prev.y + (next.y - prev.y) * easedT,
  };
}

/**
 * Micro-jitter — adds a tiny random-looking offset to make cursor feel alive.
 * Uses frame as seed for deterministic "random" values.
 */
export function microJitter(frame: number, amplitude = 0.0015): Pos {
  // Deterministic pseudo-random based on frame
  const sx = Math.sin(frame * 0.37 + 1.1) * Math.cos(frame * 0.19);
  const sy = Math.cos(frame * 0.41 + 2.3) * Math.sin(frame * 0.23);
  return { x: sx * amplitude, y: sy * amplitude };
}

/**
 * Click ripple progress — returns 0–1 progress of click animation.
 * clickFrame: frame when click happened. Returns 0 if not in ripple window.
 */
export function clickRippleProgress(frame: number, clickFrame: number, rippleDuration = 18): number {
  const elapsed = frame - clickFrame;
  if (elapsed < 0 || elapsed > rippleDuration) return 0;
  return elapsed / rippleDuration;
}
