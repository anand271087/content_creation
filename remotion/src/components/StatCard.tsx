import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Section } from "../types";

interface StatCardProps {
  sections: Section[];
  fps: number;
}

// Avatar zone where the card floats
const AVATAR_TOP = 160;
const AVATAR_HEIGHT = 1400;

// Purely decorative leaf SVG
const LeafPath =
  "M10 1 C10 1 18 6 18 12 C18 17 14 20 10 20 C6 20 2 17 2 12 C2 6 10 1 10 1Z";

interface FloatingLeafProps {
  index: number;
}

const FloatingLeaf: React.FC<FloatingLeafProps> = ({ index }) => {
  const frame = useCurrentFrame();
  const CYCLE = 180;
  const phaseOffset = index * 27;
  const cycleFrame = (frame + phaseOffset) % CYCLE;

  // Float from bottom to top of avatar zone
  const y = interpolate(cycleFrame, [0, CYCLE], [AVATAR_TOP + AVATAR_HEIGHT + 20, AVATAR_TOP - 80], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const x = 80 + index * 128 + Math.sin(index * 1.7) * 50;
  const swayX = interpolate((frame + phaseOffset * 2) % 100, [0, 50, 100], [-12, 12, -12], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = interpolate(cycleFrame, [0, 15, CYCLE - 15, CYCLE], [0, 0.5, 0.5, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <svg
      style={{
        position: "absolute",
        left: x + swayX,
        top: y,
        opacity,
        transform: `rotate(${index * 45 + frame * 0.4}deg)`,
        pointerEvents: "none",
        zIndex: 48,
      }}
      width={22}
      height={22}
      viewBox="0 0 20 20"
    >
      <path d={LeafPath} fill="#4caf73" />
    </svg>
  );
};

const Waveform: React.FC<{ barCount?: number }> = ({ barCount = 20 }) => {
  const frame = useCurrentFrame();
  const maxH = 40;
  const barW = 7;
  const gap = 4;

  return (
    <div style={{ display: "flex", alignItems: "center", gap, height: maxH }}>
      {Array.from({ length: barCount }).map((_, i) => {
        const h = (Math.sin(frame / 7 + i * 0.6) * 0.5 + 0.5) * maxH;
        return (
          <div
            key={i}
            style={{
              width: barW,
              height: Math.max(3, h),
              backgroundColor: "rgba(255,255,255,0.6)",
              borderRadius: 3,
              alignSelf: "center",
            }}
          />
        );
      })}
    </div>
  );
};

// ── Stat card variant ──────────────────────────────────────────────────────────

interface StatVariantProps {
  cardLines: Array<{ text: string; size: "lg" | "sm" }>;
  sourceName?: string;
  sourceSubtitle?: string;
  entryProgress: number; // 0→1
}

const StatVariant: React.FC<StatVariantProps> = ({
  cardLines,
  sourceName,
  sourceSubtitle,
  entryProgress,
}) => {
  const translateY = interpolate(entryProgress, [0, 1], [40, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        transform: `translateY(${translateY}px)`,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 20,
        width: "100%",
      }}
    >
      {/* Source header */}
      {sourceName && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
          <div
            style={{
              width: 80,
              height: 80,
              borderRadius: "50%",
              backgroundColor: "rgba(255,255,255,0.15)",
              border: "2px solid rgba(255,255,255,0.3)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: "Montserrat, sans-serif",
              fontSize: 32,
              color: "rgba(255,255,255,0.6)",
              fontWeight: 900,
            }}
          >
            {sourceName[0].toUpperCase()}
          </div>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontFamily: "Montserrat, sans-serif", fontWeight: 900, fontSize: 32, color: "#fff", lineHeight: 1.2 }}>
              {sourceName}
            </div>
            {sourceSubtitle && (
              <div style={{ fontFamily: "Montserrat, sans-serif", fontWeight: 500, fontSize: 24, color: "rgba(255,255,255,0.6)", marginTop: 2 }}>
                {sourceSubtitle}
              </div>
            )}
          </div>
          <Waveform barCount={20} />
        </div>
      )}

      {/* Content lines */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, width: "100%" }}>
        {cardLines.map((line, i) => (
          <div
            key={i}
            style={{
              fontFamily: "Montserrat, sans-serif",
              fontWeight: line.size === "lg" ? 900 : 600,
              fontSize: line.size === "lg" ? 80 : 36,
              color: line.size === "lg" ? "#ffffff" : "rgba(255,255,255,0.72)",
              textAlign: "center",
              lineHeight: line.size === "lg" ? 1.0 : 1.3,
              textTransform: line.size === "lg" ? "uppercase" : "none",
              letterSpacing: line.size === "lg" ? "0.02em" : "normal",
            }}
          >
            {line.text}
          </div>
        ))}
      </div>
    </div>
  );
};

// ── Podium / numbered listicle variant ────────────────────────────────────────

interface PodiumVariantProps {
  cardLines: Array<{ text: string; size: "lg" | "sm" }>;
  sectionStartFrame: number;
  fps: number;
}

const PodiumVariant: React.FC<PodiumVariantProps> = ({ cardLines, sectionStartFrame, fps }) => {
  const frame = useCurrentFrame();
  const { fps: videoFps } = useVideoConfig();
  const STAGGER = 8;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, width: "100%" }}>
      {cardLines.map((line, i) => {
        const itemFrame = frame - (sectionStartFrame + i * STAGGER);
        const scale = spring({
          frame: itemFrame,
          fps: videoFps,
          config: { damping: 10, stiffness: 200, mass: 0.7 },
          from: 0,
          to: 1,
        });
        const opacity = interpolate(itemFrame, [0, 6], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

        return (
          <div
            key={i}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 20,
              transform: `scale(${scale})`,
              opacity,
              transformOrigin: "left center",
            }}
          >
            {/* Number badge */}
            <div
              style={{
                width: 72,
                height: 72,
                borderRadius: "50%",
                backgroundColor: "#E31A1A",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontFamily: "Montserrat, sans-serif",
                fontWeight: 900,
                fontSize: 40,
                color: "#fff",
                flexShrink: 0,
              }}
            >
              {i + 1}
            </div>
            {/* Text */}
            <div
              style={{
                fontFamily: "Montserrat, sans-serif",
                fontWeight: line.size === "lg" ? 900 : 700,
                fontSize: line.size === "lg" ? 52 : 36,
                color: line.size === "lg" ? "#ffffff" : "rgba(255,255,255,0.8)",
                lineHeight: 1.2,
                textTransform: line.size === "lg" ? "uppercase" : "none",
              }}
            >
              {line.text}
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ── Main StatCard component ────────────────────────────────────────────────────

const PLAYBACK_RATE = 1.25;

export const StatCard: React.FC<StatCardProps> = ({ sections, fps }) => {
  const frame = useCurrentFrame();
  const { fps: videoFps } = useVideoConfig();
  const currentSec = (frame / fps) * PLAYBACK_RATE;

  const currentIndex = sections.findIndex(
    (s) => currentSec >= s.start_sec && currentSec < s.end_sec
  );
  const activeIndex = currentIndex === -1 ? sections.length - 1 : currentIndex;
  const activeSection = sections[activeIndex];

  if (activeSection.broll_type !== "card") return null;

  const cardLines = activeSection.card_lines ?? [];
  const variant = activeSection.card_variant ?? "stat";
  const sectionStartFrame = activeSection.start_sec * fps / PLAYBACK_RATE;
  const framesIntoSection = frame - sectionStartFrame;

  // Card entrance: spring scale + opacity
  const entryScale = spring({
    frame: framesIntoSection,
    fps: videoFps,
    config: { damping: 14, stiffness: 180, mass: 0.9 },
    from: 0.88,
    to: 1.0,
  });
  const entryOpacity = interpolate(framesIntoSection, [0, 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const entryProgress = interpolate(framesIntoSection, [0, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <>
      {/* Floating leaves — behind the card */}
      {Array.from({ length: 7 }).map((_, i) => (
        <FloatingLeaf key={i} index={i} />
      ))}

      {/* Dim overlay on avatar — draws attention to the card */}
      <div
        style={{
          position: "absolute",
          top: AVATAR_TOP,
          left: 0,
          width: 1080,
          height: AVATAR_HEIGHT,
          backgroundColor: "rgba(0,0,0,0.55)",
          zIndex: 49,
          pointerEvents: "none",
          opacity: entryOpacity,
        }}
      />

      {/* Floating card — centered in the avatar zone */}
      <div
        style={{
          position: "absolute",
          top: AVATAR_TOP,
          left: 0,
          width: 1080,
          height: AVATAR_HEIGHT,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 50,
          pointerEvents: "none",
        }}
      >
        <div
          style={{
            width: 900,
            backgroundColor: "rgba(10, 20, 35, 0.92)",
            backdropFilter: "blur(16px)",
            WebkitBackdropFilter: "blur(16px)",
            borderRadius: 32,
            border: "1.5px solid rgba(255,255,255,0.15)",
            boxShadow: "0 24px 80px rgba(0,0,0,0.75), 0 0 0 1px rgba(255,255,255,0.05)",
            padding: variant === "podium" ? "44px 48px" : "48px 52px",
            transform: `scale(${entryScale})`,
            opacity: entryOpacity,
          }}
        >
          {variant === "podium" ? (
            <PodiumVariant
              cardLines={cardLines}
              sectionStartFrame={sectionStartFrame}
              fps={fps}
            />
          ) : (
            <StatVariant
              cardLines={cardLines}
              sourceName={activeSection.card_source_name}
              sourceSubtitle={activeSection.card_source_subtitle}
              entryProgress={entryProgress}
            />
          )}
        </div>
      </div>
    </>
  );
};
