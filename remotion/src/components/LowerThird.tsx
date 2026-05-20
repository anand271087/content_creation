import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

interface LowerThirdProps {
  handle: string;          // e.g. "@automatewithanand"
  showUntilSec?: number;   // hide after this many seconds (default 8)
}

// Sits inside the avatar panel (y=160–1560 in new full-frame layout).
// Slides in from left at frame 0, fades out before showUntilSec.
const AVATAR_PANEL_TOP = 0;

export const LowerThird: React.FC<LowerThirdProps> = ({
  handle,
  showUntilSec = 8,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const showUntilFrame = showUntilSec * fps;
  const fadeOutStart = showUntilFrame - fps * 1.0; // fade out 1s before hiding

  if (frame > showUntilFrame) return null;

  // Slide in from left
  const slideX = spring({
    frame,
    fps,
    config: { damping: 18, stiffness: 200, mass: 0.8 },
    from: -300,
    to: 0,
  });

  // Fade out near the end
  const opacity = interpolate(
    frame,
    [fadeOutStart, showUntilFrame],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <div
      style={{
        position: "absolute",
        top: AVATAR_PANEL_TOP + 24,
        left: 24,
        transform: `translateX(${slideX}px)`,
        opacity,
        display: "flex",
        alignItems: "center",
        gap: 0,
        zIndex: 20,
        pointerEvents: "none",
      }}
    >
      {/* Yellow accent bar */}
      <div
        style={{
          width: 6,
          height: 48,
          backgroundColor: "#FFD700",
          borderRadius: "3px 0 0 3px",
        }}
      />
      {/* Handle pill */}
      <div
        style={{
          backgroundColor: "rgba(0,0,0,0.75)",
          padding: "8px 18px",
          borderRadius: "0 6px 6px 0",
          display: "flex",
          flexDirection: "column",
          gap: 2,
        }}
      >
        <span
          style={{
            fontFamily: "Montserrat, sans-serif",
            fontWeight: 900,
            fontSize: 26,
            color: "#FFD700",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            lineHeight: 1,
          }}
        >
          {handle}
        </span>
        <span
          style={{
            fontFamily: "Montserrat, sans-serif",
            fontWeight: 600,
            fontSize: 18,
            color: "rgba(255,255,255,0.8)",
            letterSpacing: "0.02em",
            lineHeight: 1,
          }}
        >
          AI Automation
        </span>
      </div>
    </div>
  );
};
