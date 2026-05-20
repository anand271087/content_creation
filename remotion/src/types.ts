export interface Section {
  id: string;
  label: string;
  start_sec: number;
  end_sec: number;
  spoken: string;
  on_screen_text: string[];
  broll_prompt: string;
  expression_cue: string;
  vocal_direction: string;
  bgm_dip: boolean;
  bgm_track: number;
  bgm_transition_here: boolean;
  tool_mentioned?: string;
  layout?: "split" | "broll_full";  // kept for backwards compat, unused by new layout
  broll_type?: "clip" | "card" | "none" | "diagram" | "screen";  // clip=rounded card overlay, card=overlay stat card, none=pure avatar, diagram=excalidraw PNG, screen=Remotion screen demo
  screen_capture?: {
    url: string;
    description: string;
    cursor_steps?: Array<{
      label?: string;
      spoken_cue?: string;
      xy?: [number, number];
      selector?: string;
      highlight_box?: [number, number, number, number];
      highlight?: boolean;
      click?: boolean;
      type?: string;
      zoom_to?: [number, number, number, number];
      wait_ms?: number;
    }>;
  };
  card_lines?: Array<{ text: string; size: "lg" | "sm" }>;  // required when broll_type="card"
  card_variant?: "stat" | "podium";  // stat=number/claim card (default), podium=numbered listicle (1,2,3)
  card_source_name?: string;      // optional header name on stat card
  card_source_subtitle?: string;  // optional subtitle on stat card
  flash_before?: boolean;         // 2-frame black flash before this section (chapter break)
  broll_pool?: string[];          // rotate through these clip IDs in broll windows (prevents same clip looping)
}

export interface DSSCLScores {
  D: number;
  Share: number;
  Save: number;
  C: number;
  L: number;
  final: number;
}

export interface ScriptData {
  title: string;
  hook_used: string;
  format_used: string;
  total_duration_sec: number;
  dsscl_scores: DSSCLScores;
  dsscl_iteration: number;
  bgm_transition_sec: number;
  bgm_dip_timestamps: number[];
  full_spoken_script: string;
  grand_takeaway_line: string;
  tool_mentioned: string;
  sections: Section[];
}

export interface WhisperWord {
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

export interface ScreenTimelineAction {
  frame: number;
  type: string;
  [key: string]: unknown;
}

export interface ScreenTimeline {
  section_id: string;
  section_start_sec: number;
  section_end_sec: number;
  screenshot_count: number;
  actions: ScreenTimelineAction[];
}

export interface ReelCompositionProps {
  scriptData: ScriptData;
  assetsDir: string;
  captionsData: WhisperData;
  screenTimelines?: Record<string, ScreenTimeline>; // section_id → timeline JSON
}
