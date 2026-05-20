import React from "react";
import {
  Video,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { Section, ScreenTimeline } from "../types";

interface BrollClipCardProps {
  sections: Section[];
  assetsDir: string;
  fps: number;
  screenTimelines?: Record<string, ScreenTimeline>; // section_id → timeline
}

const PLAYBACK_RATE = 1.25;

// A-roll / B-roll rhythm: 8s avatar then 4s b-roll (12s cycle)
// Cuts every ~12s instead of every 5s — much less frequent
const AROLL_SECS = 8;
const CYCLE_SECS = 12;

// Box centered in the full frame (y=0→1920)
// 9:16 broll clips displayed in a portrait-oriented box to minimize cropping
// Box: 880px wide, 1100px tall → y=410→1510 (centered in full frame)
const BOX_WIDTH = 880;
const BOX_HEIGHT = 1100;
const BOX_LEFT = (1080 - BOX_WIDTH) / 2;   // 100
const BOX_TOP = (1920 - BOX_HEIGHT) / 2;   // 410 — centered in full frame
const BOX_RADIUS = 28;

// Full-frame constants (for dim overlay)
const AVATAR_TOP = 0;
const AVATAR_HEIGHT = 1920;

export const BrollClipCard: React.FC<BrollClipCardProps> = ({
  sections,
  assetsDir,
  fps,
  screenTimelines = {},
}) => {
  const frame = useCurrentFrame();
  const currentSec = (frame / fps) * PLAYBACK_RATE;

  const currentIndex = sections.findIndex(
    (s) => currentSec >= s.start_sec && currentSec < s.end_sec
  );
  const activeIndex = currentIndex === -1 ? sections.length - 1 : currentIndex;
  const activeSection = sections[activeIndex];

  const brollType = activeSection.broll_type ?? "clip";

  // ── DIAGRAM / SCREEN / TERMINAL sections: show HyperFrames MP4 for full section ──
  // These sections are rendered as animated MP4s by generate_hyperframes_broll.mjs.
  // Display in the same rounded box as clip sections, visible for the entire section
  // (no A/B rhythm gap — diagram/screen content should be seen the whole time).
  if (brollType === "diagram" || brollType === "screen" || brollType === "terminal") {
    return (
      <>
        {/* Full-frame dark background — covers avatar */}
        <div style={{
          position: "absolute", top: AVATAR_TOP, left: 0,
          width: 1080, height: AVATAR_HEIGHT,
          background: "linear-gradient(180deg, #060e1c 0%, #0d1b2e 55%, #050b14 100%)",
          zIndex: 19, pointerEvents: "none",
        }} />

        {/* Rounded box — same geometry as clip sections */}
        <div style={{
          position: "absolute", top: BOX_TOP, left: BOX_LEFT,
          width: BOX_WIDTH, height: BOX_HEIGHT,
          borderRadius: BOX_RADIUS, overflow: "hidden",
          backgroundColor: "#000", zIndex: 20,
          border: "2px solid rgba(255,255,255,0.75)",
          boxShadow: "0 12px 48px rgba(0,0,0,0.75), 0 0 0 1px rgba(255,255,255,0.1)",
        }}>
          <Video
            src={staticFile(`${assetsDir}/broll/${activeSection.id}.mp4`)}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
            loop muted playbackRate={PLAYBACK_RATE}
          />
        </div>
      </>
    );
  }

  // ── TEXT_CARD sections: card PNG for ENTIRE section (no A/B rhythm gap) ──
  // Shows the numbered-list card from the moment the section starts.
  // Like diagram sections — always visible, no avatar-first delay.
  if (brollType === "text_card") {
    const sectionStartFrame2 = activeSection.start_sec * fps / PLAYBACK_RATE;
    const framesIntoSection2 = Math.max(0, frame - sectionStartFrame2);
    const sectionDurationFrames2 = Math.max(
      (activeSection.end_sec - activeSection.start_sec) * fps / PLAYBACK_RATE - 1, 1
    );
    const zoomScale2 = interpolate(
      framesIntoSection2,
      [0, sectionDurationFrames2],
      [1.0, 1.05],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    return (
      <>
        <div style={{
          position: "absolute", top: AVATAR_TOP, left: 0,
          width: 1080, height: AVATAR_HEIGHT,
          background: "linear-gradient(180deg, #060e1c 0%, #0d1b2e 55%, #050b14 100%)",
          zIndex: 19, pointerEvents: "none",
        }} />
        <div style={{
          position: "absolute", top: BOX_TOP, left: BOX_LEFT,
          width: BOX_WIDTH, height: BOX_HEIGHT,
          borderRadius: BOX_RADIUS, overflow: "hidden",
          backgroundColor: "#0d1117", zIndex: 20,
          border: "2px solid rgba(255,255,255,0.75)",
          boxShadow: "0 12px 48px rgba(0,0,0,0.75), 0 0 0 1px rgba(255,255,255,0.1)",
        }}>
          <div style={{
            position: "absolute", inset: 0,
            transform: `scale(${zoomScale2})`,
            transformOrigin: "center center",
          }}>
            <Img
              src={staticFile(`${assetsDir}/diagrams/${activeSection.id}_card.png`)}
              style={{ width: "100%", height: "100%", objectFit: "contain", backgroundColor: "#fff" }}
            />
          </div>
        </div>
      </>
    );
  }

  // ── CLIP sections: section-relative rhythm ────────────────────────────
  const sectionElapsed = currentSec - activeSection.start_sec;
  // broll_pool: rotate through multiple clips per broll window (avoids same clip looping)
  const brollPool: string[] = activeSection.broll_pool ?? [activeSection.id];
  const brollWindowIndex = Math.floor(sectionElapsed / CYCLE_SECS);
  const activeBrollId = brollPool[brollWindowIndex % brollPool.length];
  const sectionDuration = activeSection.end_sec - activeSection.start_sec;
  // Adaptive threshold: short sections get broll sooner so clip always fits
  const arollThreshold = Math.min(AROLL_SECS, Math.max(0, sectionDuration - 4));
  const timeInCycle = sectionElapsed % CYCLE_SECS;
  const isInBrollWindow = timeInCycle >= arollThreshold;

  if (!isInBrollWindow) return null;

  // Ken Burns zoom relative to section start
  const sectionStartFrame = activeSection.start_sec * fps / PLAYBACK_RATE;
  const framesIntoSection = frame - sectionStartFrame;
  const sectionDurationFrames = Math.max(
    (activeSection.end_sec - activeSection.start_sec) * fps / PLAYBACK_RATE - 1,
    1
  );
  const isTrigger = activeSection.id.startsWith("trigger");
  const zoomEnd = isTrigger ? 1.14 : 1.08;
  const zoomScale = interpolate(
    framesIntoSection,
    [0, sectionDurationFrames],
    [1.0, zoomEnd],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Gradient tone shifts based on section mood
  const isWarm = activeSection.id === "emotion_save" || activeSection.id === "grand_takeaway";
  const isBridge = activeSection.id === "bridge";
  const bgGradient = isWarm
    ? "linear-gradient(180deg, #120b04 0%, #1e1108 50%, #0c0804 100%)"
    : isBridge
    ? "linear-gradient(180deg, #0c0818 0%, #150f22 50%, #080510 100%)"
    : "linear-gradient(180deg, #060e1c 0%, #0d1b2e 55%, #050b14 100%)";

  return (
    <>
      {/* Full gradient background — completely replaces avatar during clip broll window */}
      <div style={{
        position: "absolute", top: AVATAR_TOP, left: 0,
        width: 1080, height: AVATAR_HEIGHT,
        background: bgGradient, zIndex: 19, pointerEvents: "none",
      }} />

      {/* B-roll rounded box — foreground element */}
      <div style={{
        position: "absolute", top: BOX_TOP, left: BOX_LEFT,
        width: BOX_WIDTH, height: BOX_HEIGHT,
        borderRadius: BOX_RADIUS, overflow: "hidden",
        backgroundColor: "#000", zIndex: 20,
        border: "2px solid rgba(255,255,255,0.75)",
        boxShadow: "0 12px 48px rgba(0,0,0,0.75), 0 0 0 1px rgba(255,255,255,0.1)",
      }}>
        <div style={{
          position: "absolute", inset: 0,
          transform: `scale(${zoomScale})`,
          transformOrigin: "center center",
        }}>
          <Video
            src={staticFile(`${assetsDir}/broll/${activeBrollId}.mp4`)}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
            loop muted playbackRate={PLAYBACK_RATE}
          />
        </div>
      </div>
    </>
  );
};
