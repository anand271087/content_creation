import React from "react";
import { Audio, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Section } from "../types";

const PLAYBACK_RATE = 1.25;
const AROLL_SECS = 8;
const CYCLE_SECS = 12; // 8s aroll + 4s broll — cuts every ~12s

// Composition frames per window (at 30fps / 1.25x)
// CYCLE_FRAMES = 12 * 30 / 1.25 = 288
// AROLL_FRAMES = 8 * 30 / 1.25 = 192
const CYCLE_FRAMES = Math.round(CYCLE_SECS * 30 / PLAYBACK_RATE);   // 288
const AROLL_FRAMES = Math.round(AROLL_SECS * 30 / PLAYBACK_RATE);   // 192

interface RhythmCutsProps {
  sections: Section[];
  totalDurationSec: number; // original video duration (pre-speed-up)
  assetsDir: string;
}

export const RhythmCuts: React.FC<RhythmCutsProps> = ({
  sections,
  totalDurationSec,
  assetsDir,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const currentSec = (frame / fps) * PLAYBACK_RATE;

  // Find current section to know if rhythm applies (only clip sections)
  const currentIndex = sections.findIndex(
    (s) => currentSec >= s.start_sec && currentSec < s.end_sec
  );
  const activeIndex = currentIndex === -1 ? sections.length - 1 : currentIndex;
  const activeSection = sections[activeIndex];
  const isClipSection = (activeSection.broll_type ?? "clip") === "clip";

  // White flash: 2 composition frames at each A→B and B→A cut
  const cycleFrame = frame % CYCLE_FRAMES;
  const isAtABCut = isClipSection && cycleFrame === AROLL_FRAMES;
  const isAtBACut = isClipSection && cycleFrame === 0 && frame > 0;
  const showFlash = isAtABCut || isAtBACut;

  // Generate all transition frame positions for click sounds
  // A→B cuts: k * CYCLE_FRAMES + AROLL_FRAMES  (frames: 72, 192, 312, ...)
  // B→A cuts: k * CYCLE_FRAMES                 (frames: 120, 240, 360, ...)
  const totalCompFrames = Math.ceil((totalDurationSec / PLAYBACK_RATE) * 30);
  const clickPath = staticFile(`${assetsDir}/music/sting1.mp3`);

  const transitionFrames: number[] = [];
  for (let k = 0; k * CYCLE_FRAMES < totalCompFrames; k++) {
    const abCut = k * CYCLE_FRAMES + AROLL_FRAMES;
    const baCut = (k + 1) * CYCLE_FRAMES;
    if (abCut < totalCompFrames) transitionFrames.push(abCut);
    if (baCut < totalCompFrames) transitionFrames.push(baCut);
  }

  return (
    <>
      {/* White flash overlay at every cut */}
      {showFlash && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundColor: "#ffffff",
            opacity: 0.9,
            zIndex: 98,
            pointerEvents: "none",
          }}
        />
      )}

      {/* Click sound at every cut — sting1 at low volume for short snap effect */}
      {transitionFrames.map((f, i) => (
        <Sequence key={i} from={f} durationInFrames={6}>
          <Audio src={clickPath} volume={0.20} />
        </Sequence>
      ))}
    </>
  );
};
