import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { Section } from "../types";

interface SectionFlashProps {
  sections: Section[];
  fps: number;
}

// 2-frame black flash at the start of sections with flash_before: true
const FLASH_DURATION_FRAMES = 2;
const PLAYBACK_RATE = 1.25;

export const SectionFlash: React.FC<SectionFlashProps> = ({ sections, fps }) => {
  const frame = useCurrentFrame();

  // Find sections that should have a flash before them
  const flashSections = sections.filter((s) => s.flash_before === true);

  // Find if we're currently in a flash window
  let flashOpacity = 0;

  for (const section of flashSections) {
    const sectionStartFrame = section.start_sec * fps / PLAYBACK_RATE;
    const framesFromStart = frame - sectionStartFrame;

    if (framesFromStart >= 0 && framesFromStart < FLASH_DURATION_FRAMES) {
      // Hard black for the flash frames
      flashOpacity = 1;
      break;
    }

    // Quick 2-frame pre-flash just before the section starts
    const framesUntilStart = sectionStartFrame - frame;
    if (framesUntilStart >= 0 && framesUntilStart < FLASH_DURATION_FRAMES) {
      flashOpacity = 1;
      break;
    }
  }

  if (flashOpacity === 0) return null;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        backgroundColor: "#000000",
        opacity: flashOpacity,
        zIndex: 100,
        pointerEvents: "none",
      }}
    />
  );
};
