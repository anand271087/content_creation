import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

interface EndCardProps {
  handle: string;           // e.g. "@automatewithanand"
  totalDurationSec: number; // from scriptData.total_duration_sec
  showLastSec?: number;     // how many seconds before end to show (default 4)
}

// Overlays the full frame for the last N seconds.
// Fades in over 0.5s, stays at full opacity until the end.
export const EndCard: React.FC<EndCardProps> = ({
  handle,
  totalDurationSec,
  showLastSec = 4,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const showAtFrame = (totalDurationSec - showLastSec) * fps;
  const fadeInEnd = showAtFrame + fps * 0.5; // 0.5s fade-in

  if (frame < showAtFrame) return null;

  const opacity = interpolate(frame, [showAtFrame, fadeInEnd], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Scale-in for the icon
  const iconScale = spring({
    frame: frame - showAtFrame,
    fps,
    config: { damping: 14, stiffness: 160, mass: 0.9 },
    from: 0.6,
    to: 1.0,
  });

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: 1080,
        height: 1920,
        backgroundColor: "rgba(0,0,0,0.82)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        opacity,
        zIndex: 50,
        pointerEvents: "none",
        gap: 32,
      }}
    >
      {/* Arrow icon */}
      <div
        style={{
          transform: `scale(${iconScale})`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 16,
        }}
      >
        {/* Up-arrow pointing to the follow button */}
        <div
          style={{
            width: 0,
            height: 0,
            borderLeft: "30px solid transparent",
            borderRight: "30px solid transparent",
            borderBottom: "50px solid #FFD700",
          }}
        />

        {/* FOLLOW label */}
        <div
          style={{
            fontFamily: "Montserrat, sans-serif",
            fontWeight: 900,
            fontSize: 80,
            color: "#FFD700",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            lineHeight: 1,
            textShadow: "3px 3px 0 rgba(0,0,0,0.6)",
          }}
        >
          FOLLOW
        </div>

        {/* Handle */}
        <div
          style={{
            fontFamily: "Montserrat, sans-serif",
            fontWeight: 700,
            fontSize: 44,
            color: "rgba(255,255,255,0.92)",
            letterSpacing: "0.03em",
            lineHeight: 1,
          }}
        >
          {handle}
        </div>

        {/* Subtitle */}
        <div
          style={{
            fontFamily: "Montserrat, sans-serif",
            fontWeight: 500,
            fontSize: 28,
            color: "rgba(255,255,255,0.6)",
            letterSpacing: "0.05em",
            lineHeight: 1,
            textTransform: "uppercase",
            marginTop: 8,
          }}
        >
          AI Automation · New builds every week
        </div>
      </div>
    </div>
  );
};
