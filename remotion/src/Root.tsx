import React from "react";
import { Composition } from "remotion";
import { ReelComposition } from "./ReelComposition";
import { ReelCompositionProps, ScriptData } from "./types";

const exampleScriptData: ScriptData = {
  title: "Your AI Is An Employee. You Just Don't Know It Yet.",
  hook_used: "#21",
  format_used: "Format 4 — Common vs Elite",
  total_duration_sec: 90,
  dsscl_scores: {
    D: 9.5,
    Share: 9.5,
    Save: 9.5,
    C: 8.0,
    L: 8.5,
    final: 9.43,
  },
  dsscl_iteration: 1,
  bgm_transition_sec: 35,
  bgm_dip_timestamps: [10, 20, 30],
  full_spoken_script:
    "Your ChatGPT is a calculator. Your AI workflow is a tool. Your AI agent is an employee. I'll explain.",
  grand_takeaway_line:
    "Most people will spend their career asking AI for help. The ones who win build AI that works while they sleep.",
  tool_mentioned: "n8n",
  sections: [
    {
      id: "hook",
      label: "HOOK",
      start_sec: 0,
      end_sec: 5,
      spoken:
        "Your ChatGPT is a calculator. Your AI workflow is a tool. Your AI agent is an employee. I'll explain.",
      on_screen_text: ["CALCULATOR.", "TOOL.", "EMPLOYEE."],
      broll_prompt:
        "dark digital calculator morphing into a humanoid robot, slow dramatic zoom, black and red, cinematic, no text, no faces, 9:16 vertical, tension",
      expression_cue: "dead serious, eyes locked into camera, slight lean forward",
      vocal_direction: "slow and deliberate, pause between each word",
      bgm_dip: false,
      bgm_track: 1,
      bgm_transition_here: false,
      broll_type: "clip",
    },
    {
      id: "context",
      label: "CONTEXT",
      start_sec: 5,
      end_sec: 10,
      spoken: "Most people use AI like a search engine. Ask. Get answer. Done.",
      on_screen_text: ["ASK.", "GET ANSWER.", "DONE."],
      broll_prompt:
        "person typing on laptop in dark room, blue screen glow, cinematic, no text, no faces, 9:16 vertical, informational",
      expression_cue: "raised eyebrow, slight smirk",
      vocal_direction: "building energy, faster pace",
      bgm_dip: false,
      bgm_track: 1,
      bgm_transition_here: false,
      broll_type: "clip",
    },
    {
      id: "trigger_1",
      label: "TRIGGER 1",
      start_sec: 10,
      end_sec: 12,
      spoken: "But what if your AI worked 24/7 without you asking?",
      on_screen_text: ["24/7", "NO ASKING."],
      broll_prompt:
        "clock spinning fast, dark background, red accent light, dramatic zoom, cinematic, no text, no faces, 9:16 vertical, tension",
      expression_cue: "leans in hard, drops voice",
      vocal_direction: "near whisper, maximum intensity",
      bgm_dip: true,
      bgm_track: 1,
      bgm_transition_here: false,
      broll_type: "card",
      card_variant: "stat",
      flash_before: true,
      card_lines: [
        { text: "24/7", size: "lg" },
        { text: "no prompting needed", size: "sm" },
        { text: "IT WORKS", size: "lg" },
      ],
      card_source_name: "AI Agent",
      card_source_subtitle: "Level 3",
    },
    {
      id: "body_1",
      label: "BODY 1",
      start_sec: 12,
      end_sec: 20,
      spoken:
        "An AI agent is different. You give it a goal, not a prompt. It decides the steps. It executes. It reports back.",
      on_screen_text: ["GOAL, NOT A PROMPT.", "IT DECIDES.", "IT EXECUTES."],
      broll_prompt:
        "robot arm assembling circuit board, blue light, neutral cinematic, no text, no faces, 9:16 vertical, informational",
      expression_cue: "confident nod, steady eye contact",
      vocal_direction: "clear, authoritative, medium pace",
      bgm_dip: false,
      bgm_track: 1,
      bgm_transition_here: false,
      broll_type: "clip",
    },
    {
      id: "trigger_2",
      label: "TRIGGER 2",
      start_sec: 20,
      end_sec: 25,
      spoken: "Companies replacing entire teams with 3 AI agents. Right now.",
      on_screen_text: ["ENTIRE TEAMS.", "3 AGENTS.", "RIGHT NOW."],
      broll_prompt:
        "empty office chairs in modern office, dramatic lighting, dark blue contrast, cinematic, no text, no faces, 9:16 vertical, tension",
      expression_cue: "serious, locked in, slight lean forward",
      vocal_direction: "drops voice, slow and deliberate",
      bgm_dip: true,
      bgm_track: 1,
      bgm_transition_here: false,
      broll_type: "card",
      card_variant: "podium",
      flash_before: true,
      card_lines: [
        { text: "Q&A  —  You ask, it answers", size: "sm" },
        { text: "Workflow  —  It acts on command", size: "sm" },
        { text: "Agent  —  It works without you", size: "lg" },
      ],
      card_source_name: "3 Levels of AI",
      card_source_subtitle: "Where are you?",
    },
    {
      id: "body_2",
      label: "BODY 2",
      start_sec: 25,
      end_sec: 30,
      spoken:
        "I know a founder in Bangalore. Two employees. Twelve AI agents. ₹40 lakh revenue last month.",
      on_screen_text: ["2 EMPLOYEES.", "12 AI AGENTS.", "₹40L LAST MONTH."],
      broll_prompt:
        "busy Indian city skyline at night, blue and orange lights, cinematic wide shot, no text, no faces, 9:16 vertical, informational",
      expression_cue: "raised eyebrow, nodding slowly",
      vocal_direction: "conversational, warm, friend sharing a secret",
      bgm_dip: false,
      bgm_track: 1,
      bgm_transition_here: false,
      broll_type: "clip",
    },
    {
      id: "trigger_3",
      label: "TRIGGER 3",
      start_sec: 30,
      end_sec: 32,
      spoken: "He set it up in n8n. Took him 20 minutes.",
      on_screen_text: ["n8n.", "20 MINUTES."],
      broll_prompt:
        "n8n workflow nodes connecting on dark screen, green and blue glow, cinematic close-up, no text, no faces, 9:16 vertical, tension",
      expression_cue: "leans in hard, drops voice to near whisper",
      vocal_direction: "slow, each word landing hard, near whisper",
      bgm_dip: true,
      bgm_track: 1,
      bgm_transition_here: false,
      broll_type: "card",
      card_variant: "stat",
      flash_before: true,
      card_lines: [
        { text: "n8n", size: "lg" },
        { text: "set up in", size: "sm" },
        { text: "20 MINUTES", size: "lg" },
        { text: "zero code", size: "sm" },
      ],
      card_source_name: "Bengaluru Founder",
      card_source_subtitle: "SaaS, 2 employees",
    },
    {
      id: "bridge",
      label: "BRIDGE",
      start_sec: 32,
      end_sec: 35,
      spoken: "The game has changed. The question is — are you playing it?",
      on_screen_text: ["THE GAME CHANGED.", "ARE YOU PLAYING?"],
      broll_prompt:
        "chess board with one piece standing, warm light starting to emerge from dark background, transitional cinematic, no text, no faces, 9:16 vertical",
      expression_cue: "calm, piercing eye contact, slight pause",
      vocal_direction: "slows down, emotional weight on each word",
      bgm_dip: false,
      bgm_track: 1,
      bgm_transition_here: false,
      broll_type: "clip",
    },
    {
      id: "grand_takeaway",
      label: "GRAND TAKEAWAY",
      start_sec: 35,
      end_sec: 40,
      spoken:
        "Most people will spend their career asking AI for help. The ones who win build AI that works while they sleep.",
      on_screen_text: ["ASKING FOR HELP", "vs", "BUILDS WHILE YOU SLEEP"],
      broll_prompt:
        "clean minimal warm desk setup, soft golden light, person relaxed not working, hopeful, 9:16 vertical",
      expression_cue: "calm, deliberate, full frame, direct eye contact",
      vocal_direction: "slow, clear, each word landing with weight",
      bgm_dip: false,
      bgm_track: 2,
      bgm_transition_here: true,
      broll_type: "clip",
    },
    {
      id: "emotion_save",
      label: "EMOTION + SAVE",
      start_sec: 40,
      end_sec: 60,
      spoken:
        "If you want to build your first AI agent — start with n8n. Free to self-host. Pick one repetitive task. Give it a goal, not a prompt. Save this — you'll want it. Follow for more builds every week.",
      on_screen_text: ["START WITH: n8n", "GOAL, NOT A PROMPT", "SAVE THIS"],
      broll_prompt:
        "n8n workflow interface on screen, automation nodes connecting, warm blue glow, person looking satisfied, 9:16 vertical",
      expression_cue: "warm smile, leaning toward camera, friend-to-friend energy",
      vocal_direction: "conversational, warm, relaxed pace",
      bgm_dip: false,
      bgm_track: 2,
      bgm_transition_here: false,
      tool_mentioned: "n8n",
      broll_type: "clip",
    },
  ],
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="ReelComposition"
      component={ReelComposition as unknown as React.FC<Record<string, unknown>>}
      // Default 90s ceiling — calculateMetadata shrinks this to actual duration
      durationInFrames={2700}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        scriptData: exampleScriptData,
        assetsDir: "assets",
        captionsData: {
          text: "Your ChatGPT is a calculator. Your AI workflow is a tool. Your AI agent is an employee.",
          segments: [
            {
              text: "Your ChatGPT is a calculator.",
              start: 0, end: 3,
              words: [
                { word: "Your",     start: 0.0,  end: 0.4 },
                { word: "ChatGPT",  start: 0.4,  end: 0.9 },
                { word: "is",       start: 0.9,  end: 1.1 },
                { word: "a",        start: 1.1,  end: 1.3 },
                { word: "calculator", start: 1.3, end: 2.1 },
              ],
            },
            {
              text: "Your AI workflow is a tool.",
              start: 3, end: 6,
              words: [
                { word: "Your",     start: 3.0,  end: 3.3 },
                { word: "AI",       start: 3.3,  end: 3.6 },
                { word: "workflow", start: 3.6,  end: 4.1 },
                { word: "is",       start: 4.1,  end: 4.3 },
                { word: "a",        start: 4.3,  end: 4.5 },
                { word: "tool",     start: 4.5,  end: 5.0 },
              ],
            },
            {
              text: "Your AI agent is an employee.",
              start: 6, end: 10,
              words: [
                { word: "Your",     start: 6.0,  end: 6.3 },
                { word: "AI",       start: 6.3,  end: 6.6 },
                { word: "agent",    start: 6.6,  end: 7.0 },
                { word: "is",       start: 7.0,  end: 7.2 },
                { word: "an",       start: 7.2,  end: 7.4 },
                { word: "employee", start: 7.4,  end: 8.2 },
              ],
            },
            {
              text: "I'll explain.",
              start: 10, end: 12,
              words: [
                { word: "I'll",    start: 10.0, end: 10.5 },
                { word: "explain", start: 10.5, end: 11.5 },
              ],
            },
          ],
        },
      } as ReelCompositionProps}
      calculateMetadata={({ props }) => {
        const p = props as unknown as ReelCompositionProps;
        // total_duration_sec is set by sync_broll_to_speech.py to the
        // actual avatar video length derived from Whisper timestamps.
        // Divide by 1.25 — video plays at 1.25× speed so composition is shorter
        return {
          durationInFrames: Math.ceil(
            (p.scriptData.total_duration_sec ?? 90) * 30 / 1.25
          ),
        };
      }}
    />
  );
};
