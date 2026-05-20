/**
 * TypingSimulator.tsx — Character-by-character typing overlay for ScreenDemoLayer.
 *
 * Renders text being typed at a position on the screenshot, with blinking cursor.
 * Natural rhythm via typing-engine.ts (deterministic jitter, no CSS animations).
 */
import React from "react";
import { charsVisible, cursorBlink } from "../../lib/typing-engine";

interface TypingSimulatorProps {
  text: string;
  at: [number, number];   // [x_frac, y_frac] position in container
  startFrame: number;      // frame when typing begins
  currentFrame: number;
  containerW: number;
  containerH: number;
}

export const TypingSimulator: React.FC<TypingSimulatorProps> = ({
  text,
  at,
  startFrame,
  currentFrame,
  containerW,
  containerH,
}) => {
  const visible = charsVisible(text, startFrame, currentFrame);
  const showCursor = currentFrame >= startFrame && cursorBlink(currentFrame - startFrame);
  const isDone = visible.length === text.length && currentFrame > startFrame + 10;

  // After typing done, blink cursor more slowly then hide
  const finalBlink = isDone ? cursorBlink(currentFrame, 22) : showCursor;

  const x = at[0] * containerW;
  const y = at[1] * containerH;

  if (currentFrame < startFrame) return null;

  return (
    <div style={{
      position: "absolute",
      left: x,
      top: y - 24, // offset up so text baseline is at the click point
      pointerEvents: "none",
      zIndex: 52,
      display: "flex",
      alignItems: "center",
      fontFamily: "'SF Mono', 'Consolas', 'Fira Mono', monospace",
      fontSize: 15,
      fontWeight: 500,
      color: "#1e1e1e",
      background: "rgba(255,255,255,0.92)",
      borderRadius: 4,
      padding: "2px 6px",
      maxWidth: containerW * 0.55,
      boxShadow: "0 1px 6px rgba(0,0,0,0.18)",
      border: "1px solid rgba(0,0,0,0.08)",
    }}>
      <span style={{ whiteSpace: "pre" }}>{visible}</span>
      {finalBlink && (
        <span style={{
          display: "inline-block",
          width: 2,
          height: 16,
          background: "#333",
          marginLeft: 1,
          verticalAlign: "middle",
        }} />
      )}
    </div>
  );
};
