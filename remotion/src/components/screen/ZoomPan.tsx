/**
 * ZoomPan.tsx — Smooth zoom into a screen region, wraps children.
 *
 * Interpolates from identity transform to a computed zoom/pan transform
 * over zoomDuration frames, then holds at the zoomed state.
 */
import React from "react";
import { interpolate } from "remotion";
import { computeZoom, interpolateZoom, zoomToCss } from "../../lib/zoom-engine";

interface ZoomPanProps {
  region: [number, number, number, number]; // [x_frac, y_frac, w_frac, h_frac]
  zoomStartFrame: number;
  zoomDuration: number; // frames to animate zoom in
  currentFrame: number;
  children: React.ReactNode;
}

export const ZoomPan: React.FC<ZoomPanProps> = ({
  region,
  zoomStartFrame,
  zoomDuration,
  currentFrame,
  children,
}) => {
  const target   = computeZoom(region, 0.04);
  const elapsed  = currentFrame - zoomStartFrame;
  const progress = elapsed < 0 ? 0 : Math.min(1, elapsed / Math.max(1, zoomDuration));

  // Ease-out — fast at start, slows to final position
  const easedP = 1 - Math.pow(1 - progress, 3);
  const zoom   = interpolateZoom(target, easedP);

  return (
    <div style={{
      position: "absolute",
      inset: 0,
      overflow: "hidden",
      transformOrigin: "center center",
      transform: zoomToCss(zoom),
    }}>
      {children}
    </div>
  );
};
