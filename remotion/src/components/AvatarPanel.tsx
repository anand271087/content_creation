import React from "react";
import { OffthreadVideo, interpolate, useCurrentFrame } from "remotion";
import { Section } from "../types";

interface AvatarPanelProps {
  avatarPath: string;
  sections: Section[];
  fps: number;
}

// New full-frame layout zones:
//   y=0   → y=160   TitleHeader
//   y=160 → y=1560  AvatarPanel (this component)
//   y=1560 → y=1920 White safe zone
const AVATAR_TOP = 0;
const AVATAR_HEIGHT = 1920;
const PANEL_WIDTH = 1080;

// 1.25× playback: composition time × PLAYBACK_RATE = original video time
const PLAYBACK_RATE = 1.25;

// Base zoom to pull the face up and fill the avatar zone
// HeyGen videos often have dead space at top — 1.4× zoomed at 20% anchor
// brings the face front-and-center between the title bar and safe zone
const BASE_ZOOM = 1.4;

// Punch-in zoom levels per section type (multiplied on top of BASE_ZOOM)
const SCALE_TRIGGER = 1.12;    // trigger_1/2/3: zoom in hard
const SCALE_EMPHASIS = 1.07;   // grand_takeaway / bridge: slight zoom
const SCALE_NORMAL = 1.0;      // all other sections

const ZOOM_FRAMES = 12; // frames to animate the zoom transition

function getSectionScale(section: Section): number {
  if (section.id.startsWith("trigger")) return SCALE_TRIGGER;
  if (section.id === "grand_takeaway" || section.id === "bridge") return SCALE_EMPHASIS;
  return SCALE_NORMAL;
}

export const AvatarPanel: React.FC<AvatarPanelProps> = ({ avatarPath, sections, fps }) => {
  const frame = useCurrentFrame();
  const currentSec = (frame / fps) * PLAYBACK_RATE;

  const currentIndex = sections.findIndex(
    (s) => currentSec >= s.start_sec && currentSec < s.end_sec
  );
  const activeIndex = currentIndex === -1 ? sections.length - 1 : currentIndex;
  const activeSection = sections[activeIndex];
  const prevSection = activeIndex > 0 ? sections[activeIndex - 1] : null;

  const sectionStartFrame = activeSection.start_sec * fps / PLAYBACK_RATE;
  const framesIntoSection = frame - sectionStartFrame;

  // Punch-in zoom: animate between previous and current section's target scale
  const targetScale = getSectionScale(activeSection);
  const fromScale = prevSection ? getSectionScale(prevSection) : SCALE_NORMAL;

  const avatarScale =
    fromScale === targetScale
      ? targetScale
      : interpolate(framesIntoSection, [0, ZOOM_FRAMES], [fromScale, targetScale], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

  const isDiagram = activeSection.broll_type === "diagram";

  // ── DIAGRAM sections: split-screen layout ──────────────────────────────
  // Top half (0–960): dark background — BrollClipCard renders diagram PNG on top
  // Bottom half (960–1920): full A-roll render clipped to 960px
  //   Renders the same 1920px inner div (scale×1.4, transformOrigin "50% 35%") as normal A-roll
  //   inside a 960px clip container. Math: clip_y=0 → inner_y≈192, clip_y=960 → inner_y≈878
  //   → shows face + upper body + hands in the 960px window.
  if (isDiagram) {
    return (
      <div style={{
        position: "absolute",
        top: 0, left: 0,
        width: PANEL_WIDTH, height: AVATAR_HEIGHT,
        background: "linear-gradient(180deg, #0a0a12 0%, #111827 50%, #080810 100%)",
        overflow: "hidden",
      }}>
        {/* Bottom half clip region */}
        <div style={{
          position: "absolute",
          top: 960, left: 0,
          width: PANEL_WIDTH, height: 960,
          overflow: "hidden",
        }}>
          {/* objectFit cover + objectPosition "center top" anchors the video's
              top edge to the container top. height:120% (1152px in 960px slot)
              gives enough vertical room for cover to work while keeping full width.
              No scale transform → no black bars. */}
          <OffthreadVideo
            src={avatarPath}
            playbackRate={PLAYBACK_RATE}
            style={{
              width: "100%",
              height: "135%",
              objectFit: "cover",
              objectPosition: "center top",
              transform: "translateY(-440px)",
              filter: "contrast(1.08) saturate(1.08) brightness(1.02)",
            }}
          />
          {/* Vignette on bottom half */}
          <div style={{
            position: "absolute", inset: 0,
            background: "radial-gradient(ellipse 90% 80% at 50% 30%, transparent 40%, rgba(0,0,0,0.45) 100%)",
            pointerEvents: "none",
          }} />
        </div>
      </div>
    );
  }

  // ── Normal sections: full-frame avatar with punch-in zoom ───────────────
  return (
    <div
      style={{
        position: "absolute",
        top: AVATAR_TOP,
        left: 0,
        width: PANEL_WIDTH,
        height: AVATAR_HEIGHT,
        background: "linear-gradient(180deg, #0a0a12 0%, #111827 50%, #080810 100%)",
        overflow: "hidden",
      }}
    >
      {/* Avatar video with punch-in zoom */}
      <div
        style={{
          width: "100%",
          height: "100%",
          transform: `scale(${avatarScale * BASE_ZOOM})`,
          transformOrigin: "50% 35%",
        }}
      >
        <OffthreadVideo
          src={avatarPath}
          playbackRate={PLAYBACK_RATE}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            objectPosition: "50% 65%",
            filter: "contrast(1.08) saturate(1.08) brightness(1.02)",
          }}
        />
      </div>

      {/* Vignette overlay — focuses attention on the speaker */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(ellipse 90% 80% at 50% 35%, transparent 40%, rgba(0,0,0,0.52) 100%)",
          pointerEvents: "none",
        }}
      />
    </div>
  );
};
