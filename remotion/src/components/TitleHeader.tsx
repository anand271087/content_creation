import React from "react";

interface TitleHeaderProps {
  title: string;
}

// Splits the title into two short lines — max 4 words each.
// 1. Try splitting on " — " or ": " (clean natural break)
// 2. Fallback: first 4 words = line1, next 4 words = line2
function splitTitle(title: string): [string, string] {
  const dashIdx = title.indexOf(" — ");
  if (dashIdx !== -1) {
    const l1 = title.slice(0, dashIdx).trim().split(" ").slice(0, 4).join(" ");
    const l2 = title.slice(dashIdx + 3).trim().split(" ").slice(0, 4).join(" ");
    return [l1, l2];
  }
  const colonIdx = title.indexOf(": ");
  if (colonIdx !== -1) {
    const l1 = title.slice(0, colonIdx).trim().split(" ").slice(0, 4).join(" ");
    const l2 = title.slice(colonIdx + 2).trim().split(" ").slice(0, 4).join(" ");
    return [l1, l2];
  }
  // Fallback: first 4 words line1, next 4 words line2
  const words = title.split(" ");
  return [words.slice(0, 4).join(" "), words.slice(4, 8).join(" ")];
}

export const TitleHeader: React.FC<TitleHeaderProps> = ({ title }) => {
  const [line1, line2] = splitTitle(title);

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: 1080,
        height: 160,
        backgroundColor: "#ffffff",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 4,
        zIndex: 40,
        pointerEvents: "none",
      }}
    >
      <span
        style={{
          fontFamily: "Montserrat, sans-serif",
          fontWeight: 900,
          fontSize: 44,
          color: "#E31A1A",
          textAlign: "center",
          lineHeight: 1.1,
          padding: "0 40px",
        }}
      >
        {line1}
      </span>
      <span
        style={{
          fontFamily: "Montserrat, sans-serif",
          fontWeight: 800,
          fontSize: 40,
          color: "#111111",
          textAlign: "center",
          lineHeight: 1.1,
          padding: "0 40px",
        }}
      >
        {line2}
      </span>
    </div>
  );
};
