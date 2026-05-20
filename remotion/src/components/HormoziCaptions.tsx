import React from "react";
import { useCurrentFrame } from "remotion";
import { Section } from "../types";

interface WhisperWord {
  word: string;
  start: number;
  end: number;
  probability?: number;
}

export interface WhisperData {
  segments: Array<{
    words?: WhisperWord[];
    text: string;
    start: number;
    end: number;
  }>;
  text: string;
}

interface HormoziCaptionsProps {
  captionsData: WhisperData;
  fps: number;
  sections?: Section[];
}

// Flatten all Whisper segments into a clean word list with absolute timestamps.
// Post-processing:
//   - Merge tokens that start with "-" into the previous word (e.g. "follow" + "-ups" → "follow-ups")
//   - Strip leading/trailing punctuation that would look odd in display (commas, periods)
//   - Skip pure-punctuation tokens
function extractWords(data: WhisperData): WhisperWord[] {
  const raw: WhisperWord[] = [];
  for (const seg of data.segments) {
    if (seg.words && seg.words.length > 0) {
      for (const w of seg.words) {
        const clean = w.word.trim();
        if (clean) raw.push({ word: clean, start: w.start, end: w.end });
      }
    }
  }

  const words: WhisperWord[] = [];
  for (const w of raw) {
    // Merge hyphen-continuation tokens into previous word (e.g. "-ups")
    if (w.word.startsWith("-") && words.length > 0) {
      const prev = words[words.length - 1];
      prev.word = prev.word + w.word;
      prev.end = w.end;
      continue;
    }
    // Merge "Bot" / ".bot" suffix into previous "Claude"/"Clawed" token → "Clawdbot"
    if (/^\.?bot/i.test(w.word.trim()) && words.length > 0) {
      const prev = words[words.length - 1];
      if (prev.word.toLowerCase() === "claude" || prev.word.toLowerCase() === "clawed") {
        prev.word = "Clawdbot";
        prev.end = w.end;
        continue;
      }
    }
    // Strip trailing commas/periods that Whisper attaches to words
    let display = w.word.replace(/[.,;:!?]+$/, "").trim();
    // Correct common Whisper mis-transcriptions for this channel
    if (display.toLowerCase() === "cloud") display = "Claude";
    if (display.toLowerCase() === "clot") display = "Claude";
    if (display.toLowerCase() === "clode") display = "Claude";
    if (display.toLowerCase() === "claud") display = "Claude";
    if (display.toLowerCase() === "claude.bot") display = "Clawdbot";
    if (display.toLowerCase() === "claudebot") display = "Clawdbot";
    if (display.toLowerCase() === "clawdbot") display = "Clawdbot";
    if (display.toLowerCase() === "clawed-bot") display = "Clawdbot";
    if (display.toLowerCase() === "clodbot") display = "Clawdbot";
    // Skip tokens that are purely punctuation after stripping
    if (!display || /^[.,;:!?-]+$/.test(display)) continue;
    words.push({ word: display, start: w.start, end: w.end });
  }
  return words;
}

// Normal sections: bottom=440 → captions at y≈1480 (lower third of avatar zone)
// Diagram split-screen: bottom=130 → captions at y≈1790 (bottom safe zone, below avatar face)
const CAPTION_BOTTOM_PX = 440;
const CAPTION_BOTTOM_DIAGRAM_PX = 130;

// 1.25× playback: composition time × PLAYBACK_RATE = original Whisper timestamp
const PLAYBACK_RATE = 1.25;

export const HormoziCaptions: React.FC<HormoziCaptionsProps> = ({
  captionsData,
  fps,
  sections,
}) => {
  const frame = useCurrentFrame();
  const currentSec = (frame / fps) * PLAYBACK_RATE;

  const isDiagram = React.useMemo(() => {
    if (!sections) return false;
    const active = sections.find((s) => currentSec >= s.start_sec && currentSec < s.end_sec)
      ?? sections[sections.length - 1];
    return active?.broll_type === "diagram";
  }, [sections, currentSec]);

  const captionBottom = isDiagram ? CAPTION_BOTTOM_DIAGRAM_PX : CAPTION_BOTTOM_PX;

  const words = React.useMemo(() => extractWords(captionsData), [captionsData]);
  if (words.length === 0) return null;

  // Find the index of the word currently being spoken
  let activeIdx = -1;
  for (let i = 0; i < words.length; i++) {
    const nextStart = words[i + 1]?.start ?? words[i].end + 2;
    if (currentSec >= words[i].start && currentSec < nextStart) {
      activeIdx = i;
      break;
    }
  }

  // Nothing active (silence / before first word / after last word)
  if (activeIdx === -1) return null;

  // Show a window of 3 words: align window boundary to multiples of 3
  const windowStart = Math.floor(activeIdx / 3) * 3;
  const windowWords = words.slice(windowStart, windowStart + 3);

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: captionBottom,
        display: "flex",
        flexDirection: "row",
        flexWrap: "wrap",
        justifyContent: "center",
        alignItems: "flex-end",
        padding: "0 40px",
        pointerEvents: "none",
        zIndex: 30,
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "row",
          flexWrap: "wrap",
          justifyContent: "center",
          alignItems: "flex-end",
          gap: 20,
          backgroundColor: "rgba(0,0,0,0.65)",
          borderRadius: 10,
          padding: "6px 16px",
        }}
      >
        {windowWords.map((w, i) => {
          const globalIdx = windowStart + i;
          const isActive = globalIdx === activeIdx;
          return (
            <span
              key={`${windowStart}-${i}`}
              style={{
                fontFamily: "Montserrat, sans-serif",
                fontWeight: 900,
                fontSize: 72,
                WebkitTextStroke: "6px black",
                paintOrder: "stroke fill" as React.CSSProperties["paintOrder"],
                textAlign: "center",
                lineHeight: 1.2,
                display: "inline-block",
                color: isActive ? "#FF3D00" : "white",
                textTransform: "uppercase",
              }}
            >
              {w.word}
            </span>
          );
        })}
      </div>
    </div>
  );
};
