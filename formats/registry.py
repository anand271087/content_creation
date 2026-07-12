"""Format registry + the edit decision engine (mirrors CLAUDE.md).

Each entry: build(avatar, captions, out) callable + metadata used to pick a
format from a script's SHAPE (see `decide`).
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Format:
    key: str
    module: str                      # import path of the builder
    description: str
    script_pattern: str
    content_type: str                # Virality | Authority | Conversion
    calendar_slot: str
    status: str                      # production | demo
    shape_regexes: list[str] = field(default_factory=list)


REGISTRY: dict[str, Format] = {f.key: f for f in [
    Format("tier_stack", "formats.tier_stack",
           "Bad/Good/Great blurred logo cards, un-blur on spoken word",
           "For X: A is bad. B is good. C is great.",
           "Virality", "Mon short-viral", "production",
           [r"\bis bad\b.*\bis good\b.*\bis great\b"]),
    Format("tier_board", "formats.tier_board",
           "S-F tier board, items float then land + accumulate",
           "[ITEM]. [GRADE]. [one punchy reason].",
           "Virality", "Wed short-viral", "production",
           [r"\b(s tier|[abcdf])\b[.!]", r"\bgrade|rank(ing)?\b"]),
    Format("tier_timeline", "formats.tier_timeline",
           "Stage/timeline board — WHEN to do what",
           "[ITEM]. [STAGE]. [reason].",
           "Virality", "Wed alternate", "production",
           [r"\b(day one|first client|lakh|stage|when you)\b"]),
    Format("countdown", "formats.countdown",
           "Countdown 5→1 with LIVE screen-demo cards",
           "Number N, [Tool]. [what it does]. [proof number].",
           "Conversion", "any", "production",
           [r"\bnumber (five|four|three|two|one)\b"]),
    Format("checklist", "formats.checklist",
           "5-step rainbow checklist, ghosted then lit per beat",
           "First/step one … [action]",
           "Authority", "Tue authority", "demo",
           [r"\b(step (one|two|1|2)|first,.*second,)\b"]),
    Format("sort_board", "formats.sort_board",
           "3-column sort: Matters / Doesn't Matter / Hurtful",
           "[HABIT]. [Verdict]. [reason].",
           "Virality", "Wed short-viral", "demo",
           [r"\b(matters|doesn'?t matter|hurtful)\b"]),
    Format("timer", "formats.timer",
           "Live countdown timer card + reframe monologue",
           "time-boxed promise → chained quotables",
           "Virality", "reach play", "demo",
           [r"\b(in under \d+ seconds|60 seconds, so pay attention)\b"]),
]}


def decide(script_text: str) -> list[tuple[str, int]]:
    """Rank formats by how strongly the script's shape matches. Returns
    [(format_key, hits)] sorted best-first. Empty = talking-head/pipeline."""
    text = script_text.lower()
    scores = []
    for f in REGISTRY.values():
        hits = sum(1 for rx in f.shape_regexes if re.search(rx, text))
        if hits:
            scores.append((f.key, hits))
    return sorted(scores, key=lambda x: -x[1])


def get_builder(key: str) -> Callable:
    import importlib
    return importlib.import_module(REGISTRY[key].module).build
