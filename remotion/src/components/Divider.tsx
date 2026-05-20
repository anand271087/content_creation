import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { Section } from "../types";

interface DividerProps {
  sections: Section[];
  fps: number;
}

const LAYOUT_FRAMES = 8;

export const Divider: React.FC<DividerProps> = ({ sections, fps }) => {
  const frame = useCurrentFrame();
  const currentSec = frame / fps;

  const currentIndex = sections.findIndex(
    (s) => currentSec >= s.start_sec && currentSec < s.end_sec
  );
  const activeIndex = currentIndex === -1 ? sections.length - 1 : currentIndex;
  const activeSection = sections[activeIndex];
  const prevSection = activeIndex > 0 ? sections[activeIndex - 1] : null;

  const activeLayout = activeSection.layout ?? "split";
  const prevLayout = prevSection ? (prevSection.layout ?? "split") : activeLayout;
  const sectionStartFrame = activeSection.start_sec * fps;
  const framesIntoSection = frame - sectionStartFrame;

  const targetOpacity = activeLayout === "broll_full" ? 0 : 1;
  const fromOpacity = prevLayout === "broll_full" ? 0 : 1;
  const opacity =
    fromOpacity === targetOpacity
      ? targetOpacity
      : interpolate(framesIntoSection, [0, LAYOUT_FRAMES], [fromOpacity, targetOpacity], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

  return (
    <div
      style={{
        position: "absolute",
        top: 960,
        left: 0,
        width: 1080,
        height: 4,
        backgroundColor: "white",
        zIndex: 5,
        opacity,
      }}
    />
  );
};
