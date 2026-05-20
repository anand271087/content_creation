/**
 * typing-engine.ts — Natural character-by-character typing simulation.
 *
 * Given text, startFrame, and typing speed, returns the visible portion
 * of text at a given frame. Simulates natural typing rhythm with
 * slight speed variation between characters.
 */

const BASE_CHARS_PER_FRAME = 0.45; // ~1 char per 2.2 frames = ~67ms at 30fps
const JITTER_FACTOR = 0.3; // ±30% speed variation per character

/**
 * Pre-compute cumulative frame offsets for each character using deterministic
 * "random" jitter (seeded by character index so it's consistent across frames).
 */
function buildCharFrames(text: string, startFrame: number, charsPerFrame = BASE_CHARS_PER_FRAME): number[] {
  const frames: number[] = [];
  let current = startFrame;
  for (let i = 0; i < text.length; i++) {
    frames.push(Math.round(current));
    // Deterministic jitter based on character index
    const jitter = 1 + JITTER_FACTOR * Math.sin(i * 1.618 + 0.5);
    current += (1 / charsPerFrame) * jitter;
  }
  return frames;
}

/**
 * Returns the visible text at a given frame.
 * text: full text to type
 * startFrame: frame when typing begins
 * frame: current Remotion frame
 */
export function charsVisible(text: string, startFrame: number, frame: number): string {
  if (frame < startFrame) return '';
  if (!text) return '';

  const charFrames = buildCharFrames(text, startFrame);
  // Find how many characters should be visible at this frame
  let count = 0;
  for (let i = 0; i < charFrames.length; i++) {
    if (frame >= charFrames[i]) count = i + 1;
    else break;
  }
  return text.slice(0, count);
}

/** Total frames needed to type the full text. */
export function typingDuration(text: string, charsPerFrame = BASE_CHARS_PER_FRAME): number {
  if (!text) return 0;
  const frames = buildCharFrames(text, 0, charsPerFrame);
  return frames[frames.length - 1] + Math.round(1 / charsPerFrame);
}

/** Cursor blink — returns true if cursor should be visible at this frame. */
export function cursorBlink(frame: number, blinkRateFrames = 18): boolean {
  return Math.floor(frame / blinkRateFrames) % 2 === 0;
}
