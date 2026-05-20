import React from "react";
import {
  AbsoluteFill,
  Video,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { Section } from "../types";

interface BrollPanelProps {
  sections: Section[];
  assetsDir: string;
  fps: number;
}

const PANEL_HEIGHT_SPLIT = 960;   // 50% of 1920 (split layout)
const PANEL_HEIGHT_FULL = 1920;   // full screen (broll_full layout)
const CROSSFADE_FRAMES = 8;
const LAYOUT_FRAMES = 8;          // frames to animate layout transition

export const BrollPanel: React.FC<BrollPanelProps> = ({
  sections,
  assetsDir,
  fps,
}) => {
  const frame = useCurrentFrame();
  const currentSec = frame / fps;

  // Find the currently active section
  const currentIndex = sections.findIndex(
    (s) => currentSec >= s.start_sec && currentSec < s.end_sec
  );

  // Clamp to last section if we're at or past the end
  const activeIndex =
    currentIndex === -1 ? sections.length - 1 : currentIndex;
  const activeSection = sections[activeIndex];

  // Determine if we're in a crossfade transition window (entering the section)
  const sectionStartFrame = activeSection.start_sec * fps;
  const framesIntoSection = frame - sectionStartFrame;

  // Opacity for the incoming clip: fade in over CROSSFADE_FRAMES
  const incomingOpacity =
    activeIndex === 0
      ? 1 // No fade-in on the very first clip
      : interpolate(framesIntoSection, [0, CROSSFADE_FRAMES], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

  // Previous section for outgoing crossfade
  const prevSection = activeIndex > 0 ? sections[activeIndex - 1] : null;
  const outgoingOpacity =
    prevSection !== null
      ? interpolate(framesIntoSection, [0, CROSSFADE_FRAMES], [1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      : 0;

  // Ken Burns zoom: slow scale-up over the section duration
  const sectionDurationFrames = Math.max(
    (activeSection.end_sec - activeSection.start_sec) * fps - 1,
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

  // Outgoing clip: show its max-zoom state at the crossfade boundary
  const prevZoomEnd =
    prevSection && prevSection.id.startsWith("trigger") ? 1.14 : 1.08;

  // Layout: animate height between split (960) and broll_full (1920)
  const activeLayout = activeSection.layout ?? "split";
  const prevLayout = prevSection ? (prevSection.layout ?? "split") : activeLayout;
  const targetHeight = activeLayout === "broll_full" ? PANEL_HEIGHT_FULL : PANEL_HEIGHT_SPLIT;
  const fromHeight = prevLayout === "broll_full" ? PANEL_HEIGHT_FULL : PANEL_HEIGHT_SPLIT;
  const panelHeight =
    fromHeight === targetHeight
      ? targetHeight
      : interpolate(framesIntoSection, [0, LAYOUT_FRAMES], [fromHeight, targetHeight], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

  const containerStyle: React.CSSProperties = {
    position: "absolute",
    top: 0,
    left: 0,
    width: 1080,
    height: panelHeight,
    overflow: "hidden",
    backgroundColor: "#000",
  };

  const videoStyle: React.CSSProperties = {
    width: "100%",
    height: "100%",
    objectFit: "cover",
  };

  return (
    <div style={containerStyle}>
      {/* Outgoing clip (previous section) during crossfade */}
      {prevSection && framesIntoSection < CROSSFADE_FRAMES && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            opacity: outgoingOpacity,
            transform: `scale(${prevZoomEnd})`,
            transformOrigin: "center center",
          }}
        >
          <Video
            src={staticFile(`${assetsDir}/broll/${prevSection.id}.mp4`)}
            style={videoStyle}
            loop
            muted
          />
        </div>
      )}

      {/* Incoming clip (active section) with Ken Burns zoom */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          opacity: incomingOpacity,
          transform: `scale(${zoomScale})`,
          transformOrigin: "center center",
        }}
      >
        <Video
          src={staticFile(`${assetsDir}/broll/${activeSection.id}.mp4`)}
          style={videoStyle}
          loop
          muted
        />
      </div>
    </div>
  );
};
