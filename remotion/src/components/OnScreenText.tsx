import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Section } from "../types";

interface OnScreenTextProps {
  sections: Section[];
  fps: number;
}

const STAGGER_FRAMES = 3;
const FADE_OUT_FRAMES = 5;
// Clip card occupies y=750→1520 (lower zone). On-screen text appears
// overlaid inside the clip card, near its bottom: bottom=450 → text at y≈1470.
const CLIP_CARD_TEXT_BOTTOM = 450;
const CYCLE_THRESHOLD_SEC = 8; // sections longer than this cycle items one at a time

// Section type → first-word accent color
// hook/triggers: red (#FF3333) — danger / urgency
// grand_takeaway: gold (#FFD700) — highlight
// all others: white (no accent)
const ACCENT_COLOR: Record<string, string> = {
  hook: "#FF3333",
  trigger_1: "#FF3333",
  trigger_2: "#FF3333",
  trigger_3: "#FF3333",
  grand_takeaway: "#FFD700",
};

const textStyle: React.CSSProperties = {
  fontFamily: "Montserrat, sans-serif",
  fontWeight: 900,
  // fontSize is set per-word dynamically by computeFontSize() based on text length
  // so long lines never overflow the 1080-wide canvas. Default kept as a safe fallback.
  fontSize: 52,
  color: "white",
  textShadow:
    "3px 3px 0 #000, -3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000",
  textAlign: "center",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  lineHeight: 1.2,
  margin: 0,
  padding: "0 24px",
  whiteSpace: "nowrap",
};

// Auto-fit font size so the text always fits within ~990px of canvas width.
// Extrabold uppercase Montserrat ≈ 0.62 * fontSize per char; pick the largest
// fontSize that keeps width <= TARGET_W. Clamped to a viewer-readable range.
const TARGET_W = 990; // 1080 - 2*24px padding - 42px slack
const CHAR_RATIO = 0.62;
const computeFontSize = (text: string): number => {
  const len = Math.max(1, text.length);
  const maxBySize = Math.floor(TARGET_W / (len * CHAR_RATIO));
  return Math.max(34, Math.min(72, maxBySize));
};

interface WordItemProps {
  text: string;
  wordIndex: number;
  sectionStartFrame: number;
  sectionEndFrame: number;
  fps: number;
  accentColor?: string; // applied to first item (wordIndex === 0) only
}

const WordItem: React.FC<WordItemProps> = ({
  text,
  wordIndex,
  sectionStartFrame,
  sectionEndFrame,
  fps,
  accentColor,
}) => {
  const frame = useCurrentFrame();
  const { fps: videoFps } = useVideoConfig();

  const entryFrame = sectionStartFrame + wordIndex * STAGGER_FRAMES;
  const framesFromEntry = frame - entryFrame;
  const framesFromEnd = sectionEndFrame - frame;

  // Spring scale animation: 0.85 → 1.0 on enter
  const scale = spring({
    frame: framesFromEntry,
    fps: videoFps,
    config: {
      damping: 12,
      stiffness: 180,
      mass: 0.8,
    },
    from: 0.85,
    to: 1.0,
  });

  // Opacity: fade in quickly on entry, fade out over last FADE_OUT_FRAMES
  const entryOpacity = interpolate(framesFromEntry, [0, 4], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const exitOpacity = interpolate(
    framesFromEnd,
    [0, FADE_OUT_FRAMES],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }
  );

  const opacity = Math.min(entryOpacity, exitOpacity);

  // Don't render before this word's entry frame
  if (frame < entryFrame) return null;

  const color = wordIndex === 0 && accentColor ? accentColor : textStyle.color;

  return (
    <div
      style={{
        ...textStyle,
        fontSize: computeFontSize(text),
        color,
        opacity,
        transform: `scale(${scale})`,
        transformOrigin: "center center",
      }}
    >
      {text}
    </div>
  );
};

export const OnScreenText: React.FC<OnScreenTextProps> = ({
  sections,
  fps,
}) => {
  const frame = useCurrentFrame();
  const currentSec = frame / fps;

  // Find the currently active section
  const currentIndex = sections.findIndex(
    (s) => currentSec >= s.start_sec && currentSec < s.end_sec
  );

  const activeIndex =
    currentIndex === -1 ? sections.length - 1 : currentIndex;
  const activeSection = sections[activeIndex];

  if (!activeSection || !activeSection.on_screen_text?.length) return null;

  // StatCard sections render their own text — skip OnScreenText for those
  if (activeSection.broll_type === "card") return null;

  const sectionStartFrame = activeSection.start_sec * fps;
  const sectionEndFrame = activeSection.end_sec * fps;
  const sectionDurationSec = activeSection.end_sec - activeSection.start_sec;
  const items = activeSection.on_screen_text;
  const accentColor = ACCENT_COLOR[activeSection.id];

  const containerStyle: React.CSSProperties = {
    position: "absolute",
    left: 0,
    width: 1080,
    bottom: CLIP_CARD_TEXT_BOTTOM,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "flex-end",
    gap: 8,
    pointerEvents: "none",
    zIndex: 10,
  };

  // Long sections: cycle items one at a time so the screen doesn't stay static
  if (sectionDurationSec >= CYCLE_THRESHOLD_SEC && items.length > 0) {
    const framesPerItem = Math.floor((sectionEndFrame - sectionStartFrame) / items.length);
    const framesIntoSection = frame - sectionStartFrame;
    const currentItemIdx = Math.min(
      Math.floor(framesIntoSection / framesPerItem),
      items.length - 1
    );
    const itemStartFrame = sectionStartFrame + currentItemIdx * framesPerItem;
    const itemEndFrame = itemStartFrame + framesPerItem;

    return (
      <div style={containerStyle}>
        <WordItem
          key={`${activeSection.id}-cycle-${currentItemIdx}`}
          text={items[currentItemIdx]}
          wordIndex={0}
          sectionStartFrame={itemStartFrame}
          sectionEndFrame={itemEndFrame}
          fps={fps}
          accentColor={accentColor}
        />
      </div>
    );
  }

  // Short sections: stagger all items in together (original behaviour)
  return (
    <div style={containerStyle}>
      {items.map((text, i) => (
        <WordItem
          key={`${activeSection.id}-${i}`}
          text={text}
          wordIndex={i}
          sectionStartFrame={sectionStartFrame}
          sectionEndFrame={sectionEndFrame}
          fps={fps}
          accentColor={accentColor}
        />
      ))}
    </div>
  );
};
