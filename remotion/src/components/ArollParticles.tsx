import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { Section } from "../types";

// Shows during non-clip sections (card/none) where the avatar is fully visible
// Also shows during clip sections as a subtle background effect

const PLAYBACK_RATE = 1.25;

// Avatar zone
const AVATAR_TOP = 0;
const AVATAR_HEIGHT = 1920;

// 8 particles with different sizes, start positions, fall speeds, opacities
const PARTICLES = [
  { x: 120,  size: 18, fallSecs: 5.0, delay: 0.0,  opacity: 0.25, drift: 30  },
  { x: 280,  size: 12, fallSecs: 6.5, delay: 1.2,  opacity: 0.18, drift: -20 },
  { x: 480,  size: 22, fallSecs: 4.5, delay: 0.5,  opacity: 0.22, drift: 40  },
  { x: 640,  size: 10, fallSecs: 7.0, delay: 2.1,  opacity: 0.15, drift: -35 },
  { x: 760,  size: 16, fallSecs: 5.5, delay: 0.9,  opacity: 0.20, drift: 25  },
  { x: 900,  size: 20, fallSecs: 4.8, delay: 1.7,  opacity: 0.18, drift: -15 },
  { x: 200,  size: 14, fallSecs: 6.0, delay: 3.0,  opacity: 0.16, drift: 20  },
  { x: 840,  size: 11, fallSecs: 7.5, delay: 0.3,  opacity: 0.14, drift: -28 },
];

interface ArollParticlesProps {
  fps: number;
  sections?: Section[];
}

export const ArollParticles: React.FC<ArollParticlesProps> = ({ fps, sections }) => {
  const frame = useCurrentFrame();
  const currentSec = (frame / fps) * PLAYBACK_RATE;

  // Hide during b-roll window — mirrors BrollClipCard section-relative logic exactly
  const AROLL_SECS = 8;
  const CYCLE_SECS = 12;

  if (sections) {
    const activeSection = sections.find(
      (s) => currentSec >= s.start_sec && currentSec < s.end_sec
    ) ?? sections[sections.length - 1];
    const brollType = activeSection.broll_type ?? "clip";
    if (brollType === "card") return null;
    if (brollType === "diagram") return null; // diagram overlay covers top half
    if (brollType === "clip") {
      const sectionElapsed = currentSec - activeSection.start_sec;
      const sectionDuration = activeSection.end_sec - activeSection.start_sec;
      const arollThreshold = Math.min(AROLL_SECS, Math.max(0, sectionDuration - 4));
      const timeInCycle = sectionElapsed % CYCLE_SECS;
      if (timeInCycle >= arollThreshold) return null;
    }
  }

  return (
    <div
      style={{
        position: "absolute",
        top: AVATAR_TOP,
        left: 0,
        width: 1080,
        height: AVATAR_HEIGHT,
        overflow: "hidden",
        pointerEvents: "none",
        zIndex: 18, // above avatar (zIndex default ~1), below b-roll gradient (19)
      }}
    >
      {PARTICLES.map((p, i) => {
        const fallFrames = p.fallSecs * fps / PLAYBACK_RATE;
        const delayFrames = p.delay * fps / PLAYBACK_RATE;
        // Loop each particle independently using its own cycle
        const particleFrame = (frame + delayFrames) % fallFrames;
        const progress = particleFrame / fallFrames;

        const y = interpolate(progress, [0, 1], [-40, AVATAR_HEIGHT + 40]);
        const x = p.x + interpolate(progress, [0, 0.5, 1], [0, p.drift, 0]);
        const rotation = interpolate(progress, [0, 1], [0, 360]);

        // Fade in at top, fade out at bottom
        const opacity = p.opacity * interpolate(
          progress,
          [0, 0.08, 0.88, 1],
          [0, 1, 1, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x,
              top: y,
              width: p.size,
              height: p.size * 1.6, // leaf-like oval shape
              backgroundColor: "rgba(255,255,255,1)",
              borderRadius: "50% 50% 40% 60% / 60% 40% 60% 40%", // organic leaf shape
              opacity,
              transform: `rotate(${rotation}deg)`,
            }}
          />
        );
      })}
    </div>
  );
};
