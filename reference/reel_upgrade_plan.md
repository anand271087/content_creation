# Reel Upgrade Plan — batch 2 analysis (2026-07-21)

5 reels analyzed. Key realization: **4 of the 5 are Instagram's own @creators/education
reels** (Mosseri, Carly, Reif) — deliberately low-edit *authority* pieces that reach
because of who posts them, not how they're cut. Only **2 are creator-grade formats worth
building** (Chris Chung's matrix, Joe Anderson's effect tutorial). Treat the IG ones as a
source of *primitives and hooks*, not formats to clone.

## The 5 reels

| Code | Creator | What | Verdict for us |
|------|---------|------|----------------|
| DA0ua3-yuDg | Adam Mosseri (IG head) | "Tips for good hooks" | Authority variant — low-edit slot only |
| C8U55spveJo | Carly (IG) | Hashtag myth-bust, 90s | **Anti-pattern** — harvest hook only |
| DXuBKZojyOj | Chris Chung | "5 rules to 2x views" sticky matrix | **NEW format: matrix_board** ✅ build |
| DAovc5zPIBj | Reif Harrison (IG @creators) | "How I use audio" | **Anti-pattern** — harvest 2 primitives |
| Da0Rpo-R2oj | Joe Anderson | "Instant vacation effect" tutorial | **NEW format: effect_recipe** ✅ build |

## DO's (validated across the batch)
1. **Set expectations in frame 1** — a pinned "what this reel is" title pill beats cliffhanger bait for informational content (Mosseri).
2. **Result-first live hook** — perform the finished payoff before explaining; make the transition device a physical action so hook = lesson (Joe Anderson clothing-toss).
3. **Shrink the promise** — "you only need 3 clips / 3 nodes" → high completion (Joe).
4. **Pin the outcome as a persistent title on board formats** — replaces the hook, sets the reward (Chris Chung).
5. **Dedicated accent "payoff column"** — the rightmost result cell in its own color = the dopamine (Chris).
6. **Myth-bust open loop** — "everyone believes X… here's the real deal", land on a contrarian data line and stop (Carly).
7. **Invisible same-frame jump cuts** — delete breaths on any talking-head; tightens energy for free (Reif).
8. **Expression per beat** carries retention when there's no b-roll (Carly) — a videographer note.
9. **Parallel sentence syntax** ("If your X does A not B, you get C" ×5) = binge (Chris).
10. **End on the payoff / callback replay** ("and it should look like this") — 5/5 reels do this.

## DON'Ts (mostly the anti-patterns)
1. **DON'T ship a bare grey-wall monologue** — no framework, no CTA. It only works with platform-level authority; our data says boards beat it 5–10×. (Carly, Reif)
2. **DON'T open with "hey what's up, I'm X"** — no TAM pull, no loop (Reif).
3. **DON'T rely on cliffhanger bait** for informational content — clear expectation-setting can win (Mosseri).
4. **DON'T add music stings / light-leaks** — 5/5 reels avoid them; word-synced cuts carry rhythm (confirms our no-flash decision).
5. **DON'T use IG-default sentence-case captions un-styled** — top creators have punchier styling; keep our accent + dark-pill law.
6. **DON'T over-caption** — one action noun/verb per beat on tutorials (Joe).
7. **DON'T grade/stylize screen-record UI** — native = trust (Joe).
8. **DON'T omit the keyword CTA** — every IG reel here skips it (fine for a platform, wrong for a growth channel).

## What's NEW vs our library

### Build as new formats (on request)
- **matrix_board** (Chris Chung) 🏗 medium — 2-D grid: labeled row rail × formula columns × accent payoff column, one cell per spoken word; finished grid = cheat-sheet save asset. No grid compositor exists yet. Niche fit: "2x your output with AI" automation cheat-sheets.
- **effect_recipe** (Joe Anderson) 🏗 medium — result-first live hook → scope promise → ingredients board → screen-record step chain (one keyword caption/action) → callback replay. Maps directly to "build this automation in N nodes." ~90% screen recording; avatar only for hook+CTA.

### New edit primitives to add to the machinery
- **Pinned frame-1 title pill** (`pinned_title_pill`, persists through hook) 🔨 ~1h
- **Phrase-chunked sentence-case captions** (calm authority mode, soft shadow) 🔨 ~2h
- **Two-tone emphasis caption pill** (bold lead word + grey trailing, one line) 🔨 small
- **Invisible same-frame jump-cut** (cut where Scribe word-gap > ~0.35s) 🔨 ≤half day, high reuse
- **Colored-text-on-white bookmark pills** (section labels per tip) 🔨 ~30min
- **Ingredients preview board** (floating numbered device mockups) 🏗 medium — needed for effect_recipe
- **Accent payoff-column** layout convention 🔨 — needed for matrix_board
- **Persistent outcome-title on board formats** (optional header) 🔨
- **Animated gradient result-frame** for callback closes 🔨 low

### Confirms decisions we already made
- No light-leaks (5/5) · lowercase micro-captions trend · word-sync everywhere · end on payoff · dark-pill legibility.

## Recommended change list (priority order)
1. **Add the 5 cheap primitives** to `core/` + caption machinery (jump-cut, two-tone pill, pinned title pill, phrase captions, bookmark pills) — they upgrade EVERY existing format, ~1.5 days total.
2. **Build `matrix_board`** — highest-value new format (visible-framework class, cheat-sheet save-value), strong niche fit.
3. **Build `effect_recipe`** — best tutorial grammar for "build X in N nodes"; reuses capture stack.
4. **Add invisible jump-cut to the finish chain** as an optional pass — free energy boost on talking-head sources.
5. **Do NOT** add a bare-monologue format — logged as anti-pattern.

## Caveats
- These reference reels expose no view/like counts (IG hides them via the API), so "what works" here is judged on craft + our prior performance data, not their metrics.
- The 4 IG-education reels reach on platform authority; don't over-index on their low-edit restraint as a growth strategy — it's a house style for a platform, not a playbook for a 43-follower channel.
