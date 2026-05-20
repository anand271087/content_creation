/**
 * HighlightOverlay.tsx — Animated highlight box for ScreenDemoLayer.
 *
 * Two modes:
 * - "border": pulsing blue border around the highlighted region
 * - "spotlight": dim entire frame except the highlighted region (cutout)
 */
import React from "react";
import { interpolate } from "remotion";

interface HighlightOverlayProps {
  box: [number, number, number, number]; // [x_frac, y_frac, w_frac, h_frac]
  mode: "border" | "spotlight";
  frame: number;       // current global frame
  startFrame: number;  // frame when highlight appeared
  containerW: number;
  containerH: number;
}

export const HighlightOverlay: React.FC<HighlightOverlayProps> = ({
  box,
  mode,
  frame,
  startFrame,
  containerW,
  containerH,
}) => {
  const [xf, yf, wf, hf] = box;
  const x = xf * containerW;
  const y = yf * containerH;
  const w = wf * containerW;
  const h = hf * containerH;

  const elapsed = frame - startFrame;
  const fadeIn = Math.min(1, elapsed / 8); // 8-frame fade in

  // Pulse: 0→1→0 cycle at ~1.2s = 36 frames
  const pulsePhase = (elapsed % 36) / 36;
  const pulseOp = 0.4 + 0.6 * Math.sin(pulsePhase * Math.PI);

  if (mode === "border") {
    return (
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none", zIndex: 48 }}>
        <div style={{
          position: "absolute",
          left: x - 5,
          top:  y - 5,
          width: w + 10,
          height: h + 10,
          borderRadius: 10,
          border: `3px solid rgba(59,130,246,${pulseOp * fadeIn})`,
          boxShadow: `0 0 0 2px rgba(59,130,246,${0.2 * fadeIn}), 0 0 20px rgba(59,130,246,${0.35 * fadeIn})`,
        }} />
      </div>
    );
  }

  // Spotlight mode — four dim rectangles forming a cutout
  const dim = `rgba(0,0,0,${0.55 * fadeIn})`;
  return (
    <div style={{ position: "absolute", inset: 0, pointerEvents: "none", zIndex: 48 }}>
      {/* Top */}
      <div style={{ position: "absolute", left: 0, top: 0, width: containerW, height: y, background: dim }} />
      {/* Bottom */}
      <div style={{ position: "absolute", left: 0, top: y + h, width: containerW, height: containerH - y - h, background: dim }} />
      {/* Left */}
      <div style={{ position: "absolute", left: 0, top: y, width: x, height: h, background: dim }} />
      {/* Right */}
      <div style={{ position: "absolute", left: x + w, top: y, width: containerW - x - w, height: h, background: dim }} />
      {/* Border around cutout */}
      <div style={{
        position: "absolute",
        left: x - 2, top: y - 2, width: w + 4, height: h + 4,
        borderRadius: 8,
        border: `2px solid rgba(255,255,255,${0.5 * fadeIn})`,
      }} />
    </div>
  );
};
