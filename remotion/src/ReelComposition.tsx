import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile, useVideoConfig } from "remotion";
import { ReelCompositionProps } from "./types";
import { AvatarPanel } from "./components/AvatarPanel";
import { BrollClipCard } from "./components/BrollClipCard";
import { HormoziCaptions } from "./components/HormoziCaptions";
import { SectionFlash } from "./components/SectionFlash";
import { RhythmCuts } from "./components/RhythmCuts";
import { ArollParticles } from "./components/ArollParticles";

// 1.25× playback: all timestamp→frame conversions divide by PLAYBACK_RATE
const PLAYBACK_RATE = 1.25;

export const ReelComposition: React.FC<ReelCompositionProps> = ({
  scriptData,
  assetsDir,
  captionsData,
  screenTimelines = {},
}) => {
  const { fps } = useVideoConfig();

  const avatarPath = staticFile(`${assetsDir}/avatar/avatar_video.mp4`);
  const sting1Path = staticFile(`${assetsDir}/music/sting1.mp3`);
  const sting2Path = staticFile(`${assetsDir}/music/sting2.mp3`);
  const sting3Path = staticFile(`${assetsDir}/music/sting3.mp3`);

  // Scale timestamps from original-video time → composition frames
  const bgmDipFrames = scriptData.bgm_dip_timestamps.map((s) => Math.round(s * fps / PLAYBACK_RATE));

  const totalDurationSec = scriptData.total_duration_sec ?? 60;

  return (
    <AbsoluteFill style={{ backgroundColor: "#000000" }}>

      {/* Avatar: full-bleed, y=0 → y=1920, with punch-in zoom + vignette */}
      <AvatarPanel avatarPath={avatarPath} sections={scriptData.sections} fps={fps} />

      {/* Falling leaf particles during non-clip sections — sits above avatar, below b-roll */}
      <ArollParticles fps={fps} sections={scriptData.sections} />

      {/* B-roll full-frame: hard cut — covers avatar entirely during broll_type="clip" sections */}
      <BrollClipCard
        sections={scriptData.sections}
        assetsDir={assetsDir}
        fps={fps}
        screenTimelines={screenTimelines}
      />

      {/* Hormozi captions — positioned in white safe zone at bottom */}
      <HormoziCaptions captionsData={captionsData} fps={fps} sections={scriptData.sections} />

      {/* White flash + click at A/B cuts — 12s cycle (8s avatar, 4s broll) */}
      <RhythmCuts
        sections={scriptData.sections}
        totalDurationSec={totalDurationSec}
        assetsDir={assetsDir}
      />

      {/* Black flash at major chapter breaks (flash_before: true sections) — zIndex=100 */}
      <SectionFlash sections={scriptData.sections} fps={fps} />

      {/* ── AUDIO ── */}

      {/* Avatar voice at 1.25x to stay in sync with sped-up video */}
      <Audio src={avatarPath} volume={4.0} playbackRate={PLAYBACK_RATE} />

      {/* BGM removed — only section stings at trigger timestamps */}
      <Sequence
        from={bgmDipFrames[0] ?? Math.round(10 * fps / PLAYBACK_RATE)}
        durationInFrames={Math.round(2 * fps)}
      >
        <Audio src={sting1Path} volume={0.70} />
      </Sequence>

      <Sequence
        from={bgmDipFrames[1] ?? Math.round(20 * fps / PLAYBACK_RATE)}
        durationInFrames={Math.round(2 * fps)}
      >
        <Audio src={sting2Path} volume={0.70} />
      </Sequence>

      <Sequence
        from={bgmDipFrames[2] ?? Math.round(30 * fps / PLAYBACK_RATE)}
        durationInFrames={Math.round(2 * fps)}
      >
        <Audio src={sting3Path} volume={0.70} />
      </Sequence>
    </AbsoluteFill>
  );
};
